"""Parser for PyHamilton ``robot_json.log`` command logs."""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

from pyhamilton.verification.models import (
    EventCategory,
    NormalizedEvent,
    dedupe_preserving_order,
    normalize_resource_name,
    parse_labware_positions,
)


LOGGER = logging.getLogger(__name__)

TRANSPORT_START_COMMANDS = {"gripGet", "iSwapGet"}
TRANSPORT_END_BY_START = {
    "gripGet": "gripPlace",
    "iSwapGet": "iSwapPlace",
}
TRANSPORT_HALF_COMMANDS = set(TRANSPORT_END_BY_START) | set(TRANSPORT_END_BY_START.values())

COMMAND_CATEGORY: dict[str, EventCategory] = {
    "initialize": EventCategory.INITIALIZE,
    "channelTipPickUp": EventCategory.TIP_PICKUP,
    "channelAspirate": EventCategory.ASPIRATE,
    "channelDispense": EventCategory.DISPENSE,
    "channelTipEject": EventCategory.TIP_EJECT,
    "mph96TipPickUp": EventCategory.TIP_PICKUP,
    "mph96Aspirate": EventCategory.ASPIRATE,
    "mph96Dispense": EventCategory.DISPENSE,
    "mph96TipEject": EventCategory.TIP_EJECT,
    "ODTC_Connect": EventCategory.MODULE_ACTION,
    "ODTC_ExecuteMethod": EventCategory.MODULE_ACTION,
    "ODTC_GetStatus": EventCategory.OTHER,
    "ODTC_Initialize": EventCategory.INITIALIZE,
    "ODTC_OpenDoor": EventCategory.MODULE_ACTION,
    "ODTC_CloseDoor": EventCategory.MODULE_ACTION,
    "ODTC_Reset": EventCategory.MODULE_ACTION,
    "ODTC_Terminate": EventCategory.OTHER,
    "end": EventCategory.OTHER,
}

ODTC_ACTIONS = {
    "ODTC_Connect": "connect",
    "ODTC_ExecuteMethod": "run_program",
    "ODTC_GetStatus": "get_status",
    "ODTC_Initialize": "initialize",
    "ODTC_OpenDoor": "open_door",
    "ODTC_CloseDoor": "close_door",
    "ODTC_Reset": "reset",
    "ODTC_Terminate": "terminate",
}


def parse_robot_json_log(path: str | Path) -> list[NormalizedEvent]:
    """Parse a ``robot_json.log`` file into ordered normalized events."""

    path = Path(path)
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = _parse_record_line(stripped, line_number)
            if record is None:
                continue
            if "command" not in record:
                LOGGER.warning("Skipping robot_json.log line %s without command key", line_number)
                continue
            record["_line_number"] = line_number
            records.append(record)

    records.sort(key=_record_sort_key)
    events: list[NormalizedEvent] = []
    pending_transport: dict[str, Any] | None = None

    for record in records:
        command = record.get("command")
        if command in TRANSPORT_HALF_COMMANDS:
            event, pending_transport = _consume_transport_half(record, pending_transport)
            if event is not None:
                events.append(event)
            continue

        if pending_transport is not None:
            LOGGER.warning(
                "Skipping unmatched transport command %s on line %s",
                pending_transport.get("command"),
                pending_transport.get("_line_number"),
            )
            pending_transport = None

        events.append(_record_to_event(record))

    if pending_transport is not None:
        LOGGER.warning(
            "Skipping unmatched transport command %s on line %s",
            pending_transport.get("command"),
            pending_transport.get("_line_number"),
        )

    return _assign_sequences(events)


def _parse_record_line(line: str, line_number: int) -> dict[str, Any] | None:
    try:
        parsed = ast.literal_eval(line)
    except (ValueError, SyntaxError):
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            LOGGER.warning("Skipping malformed robot_json.log line %s", line_number)
            return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Skipping non-dict robot_json.log line %s", line_number)
        return None
    return parsed


def _record_sort_key(record: dict[str, Any]) -> tuple[int, int]:
    raw_id = record.get("id")
    try:
        return (int(str(raw_id), 16), int(record.get("_line_number", 0)))
    except (TypeError, ValueError):
        return (2**63 - 1, int(record.get("_line_number", 0)))


def _record_to_event(record: dict[str, Any]) -> NormalizedEvent:
    command = str(record.get("command"))
    category = COMMAND_CATEGORY.get(command, _category_for_unknown_command(command))
    action = ODTC_ACTIONS.get(command, command)
    head = _head_for_command(command)
    return NormalizedEvent(
        sequence=0,
        category=category,
        action=action,
        resources=_resources_for_record(record),
        volume_ul=_volume_for_record(record),
        head=head,
        channel_count=_channel_count_for_record(record),
        metadata=_metadata(record),
    )


def _category_for_unknown_command(command: str) -> EventCategory:
    if command.startswith("ODTC_") or command.startswith("HHS_"):
        return EventCategory.MODULE_ACTION
    return EventCategory.OTHER


def _head_for_command(command: str) -> str | None:
    if command.startswith("channel"):
        return "head_8ch"
    if command.startswith("mph96"):
        return "head_96mph"
    return None


def _resources_for_record(record: dict[str, Any]) -> list[str]:
    resources: list[str] = []
    labware_positions = record.get("labwarePositions")
    if labware_positions is not None:
        resources.extend(parse_labware_positions(str(labware_positions)))

    for key in ("resource", "target", "deckResource", "device", "module"):
        if record.get(key):
            resources.append(normalize_resource_name(str(record[key])))

    command = str(record.get("command", ""))
    if command.startswith("ODTC_"):
        resources.append("ODTC")
    elif command.startswith("HHS_"):
        resources.append("HHS")

    return dedupe_preserving_order(resources)


def _volume_for_record(record: dict[str, Any]) -> float | None:
    for key in ("aspirateVolume", "dispenseVolume"):
        if key in record:
            return _as_float(record[key])

    volumes = record.get("volumes")
    if isinstance(volumes, list) and volumes:
        for volume in volumes:
            parsed = _as_float(volume)
            if parsed is not None:
                return parsed
    return None


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _channel_count_for_record(record: dict[str, Any]) -> int | None:
    channel_variable = record.get("channelVariable")
    if channel_variable is not None:
        return str(channel_variable).count("1")

    command = str(record.get("command", ""))
    if command.startswith("mph96"):
        return 96
    return None


def _consume_transport_half(
    record: dict[str, Any],
    pending_transport: dict[str, Any] | None,
) -> tuple[NormalizedEvent | None, dict[str, Any] | None]:
    command = str(record.get("command"))
    if command in TRANSPORT_START_COMMANDS:
        if pending_transport is not None:
            LOGGER.warning(
                "Skipping unmatched transport command %s on line %s",
                pending_transport.get("command"),
                pending_transport.get("_line_number"),
            )
        return None, record

    if pending_transport is None:
        LOGGER.warning(
            "Skipping transport place command %s on line %s without matching get",
            command,
            record.get("_line_number"),
        )
        return None, None

    expected = TRANSPORT_END_BY_START.get(str(pending_transport.get("command")))
    if command != expected:
        LOGGER.warning(
            "Skipping mismatched transport commands %s/%s on lines %s/%s",
            pending_transport.get("command"),
            command,
            pending_transport.get("_line_number"),
            record.get("_line_number"),
        )
        return None, None

    resources = dedupe_preserving_order(
        _resources_for_record(pending_transport) + _resources_for_record(record)
    )
    event = NormalizedEvent(
        sequence=0,
        category=EventCategory.TRANSPORT,
        action="transport",
        resources=resources,
        metadata={
            "get": _metadata(pending_transport),
            "place": _metadata(record),
        },
    )
    return event, None


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "_line_number"}


def _assign_sequences(events: list[NormalizedEvent]) -> list[NormalizedEvent]:
    for sequence, event in enumerate(events):
        event.sequence = sequence
    return events

