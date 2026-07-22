"""Normalize transpiled method trees into verification events."""

from __future__ import annotations

import logging
from typing import Any

from pyhamilton.verification.models import (
    EventCategory,
    NormalizedEvent,
    dedupe_preserving_order,
    normalize_resource_name,
)


LOGGER = logging.getLogger(__name__)

LOOP_BODY_MULTIPLIER = "body_multiplier"
LOOP_FULLY_UNROLLED = "fully_unrolled"
LOOP_NONE = "no_loops"


def detect_loop_convention(steps: list[dict[str, Any]], loop_groups: list[dict[str, Any]]) -> str:
    for loop_group in loop_groups or []:
        try:
            span = int(loop_group["end_step"]) - int(loop_group["start_step"]) + 1
            iteration_size = int(loop_group["iteration_size"])
            iterations = int(loop_group["iterations"])
        except (KeyError, TypeError, ValueError):
            continue

        if span == iteration_size:
            return LOOP_BODY_MULTIPLIER
        if span == iterations * iteration_size:
            return LOOP_FULLY_UNROLLED
    return LOOP_NONE


def expand_method_tree(
    steps: list[dict[str, Any]],
    loop_groups: list[dict[str, Any]] | None = None,
) -> list[NormalizedEvent]:
    """Expand method-tree loop groups and normalize StepCards."""

    flat_steps = _expand_steps(steps, loop_groups or [])
    events: list[NormalizedEvent] = []
    for step in flat_steps:
        event = stepcard_to_normalized_event(step, sequence=len(events))
        if event is not None:
            events.append(event)
    return events


def stepcard_to_normalized_event(
    card: dict[str, Any],
    sequence: int = 0,
) -> NormalizedEvent | None:
    action = card.get("action")
    if not action:
        LOGGER.warning("Skipping StepCard without action")
        return None

    params = card.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    category = _category_for_stepcard(str(action), params)
    return NormalizedEvent(
        sequence=sequence,
        category=category,
        action=_normalized_action(str(action), params),
        resources=_resources_for_stepcard(str(action), params),
        volume_ul=_volume_for_stepcard(params),
        head=_head_for_stepcard(str(action), params),
        channel_count=_channel_count_for_stepcard(str(action), params),
        metadata={"card": card},
    )


def _expand_steps(steps: list[dict[str, Any]], loop_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    convention = detect_loop_convention(steps, loop_groups)
    if convention in (LOOP_NONE, LOOP_FULLY_UNROLLED):
        return list(steps)

    groups_by_start = {
        int(loop_group["start_step"]): loop_group
        for loop_group in loop_groups
        if _valid_loop_group(loop_group)
    }
    expanded: list[dict[str, Any]] = []
    index = 1
    while index <= len(steps):
        loop_group = groups_by_start.get(index)
        if loop_group is None:
            expanded.append(steps[index - 1])
            index += 1
            continue

        start = int(loop_group["start_step"])
        end = int(loop_group["end_step"])
        iterations = int(loop_group["iterations"])
        body = steps[start - 1 : end]
        for _ in range(iterations):
            expanded.extend(body)
        index = end + 1
    return expanded


def _valid_loop_group(loop_group: dict[str, Any]) -> bool:
    try:
        int(loop_group["start_step"])
        int(loop_group["end_step"])
        int(loop_group["iterations"])
        int(loop_group["iteration_size"])
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _category_for_stepcard(action: str, params: dict[str, Any]) -> EventCategory:
    if action == "initialize":
        return EventCategory.INITIALIZE
    if action == "transport":
        return EventCategory.TRANSPORT
    if action == "lid_transport":
        return EventCategory.LID_TRANSPORT
    if action == "module_action":
        return EventCategory.MODULE_ACTION
    if action in {"tip_pickup", "tip_pickup_8ch", "tip_pickup_96mph"}:
        return EventCategory.TIP_PICKUP
    if action in {"tip_eject", "tip_eject_8ch", "tip_eject_96mph"}:
        return EventCategory.TIP_EJECT
    if action == "tip_transfer_to_adapter" or action == "tip_return_to_rack":
        return EventCategory.TIP_STAGING
    if action == "aspirate":
        return EventCategory.ASPIRATE
    if action == "dispense":
        return EventCategory.DISPENSE
    if action == "pipette_dwell":
        operation = str(params.get("operation", "")).lower()
        return {
            "aspirate": EventCategory.ASPIRATE,
            "dispense": EventCategory.DISPENSE,
            "mix": EventCategory.MIX,
        }.get(operation, EventCategory.OTHER)
    if action in {"incubate", "wait"}:
        return EventCategory.WAIT
    return EventCategory.OTHER


def _normalized_action(action: str, params: dict[str, Any]) -> str:
    if action == "module_action":
        return str(params.get("action") or params.get("operation") or action)
    if action == "pipette_dwell":
        return str(params.get("operation") or action)
    if action in {"incubate", "wait"}:
        return "wait"
    return action


def _resources_for_stepcard(action: str, params: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    if action == "initialize":
        values.extend(_as_list(params.get("targets")))
    elif action in {"transport", "lid_transport"}:
        values.extend([params.get("from"), params.get("to")])
    elif action == "module_action":
        values.append(params.get("target"))
    elif action == "tip_pickup":
        values.append(params.get("tip_source"))
    elif action == "tip_eject":
        values.append(params.get("destination"))
    elif action == "tip_pickup_8ch" or action == "tip_pickup_96mph":
        values.append(params.get("from"))
    elif action == "tip_eject_8ch" or action == "tip_eject_96mph":
        values.append(params.get("to"))
    elif action == "tip_transfer_to_adapter":
        values.extend([params.get("from"), params.get("to")])
    elif action == "tip_return_to_rack":
        values.append(params.get("to"))
    elif action == "aspirate":
        values.append(params.get("source"))
    elif action == "dispense":
        values.append(params.get("destination"))
    elif action == "pipette_dwell":
        values.append(params.get("at"))

    return dedupe_preserving_order(
        [normalize_resource_name(str(value)) for value in values if value]
    )


def _volume_for_stepcard(params: dict[str, Any]) -> float | None:
    if "volume_ul" not in params:
        return None
    try:
        return float(params["volume_ul"])
    except (TypeError, ValueError):
        return None


def _head_for_stepcard(action: str, params: dict[str, Any]) -> str | None:
    if action in {"tip_pickup_8ch", "tip_eject_8ch"}:
        return "head_8ch"
    if action in {"tip_pickup_96mph", "tip_eject_96mph", "tip_transfer_to_adapter"}:
        return "head_96mph"
    if action == "tip_return_to_rack":
        return _string_or_none(params.get("actor"))
    if action in {"tip_pickup", "tip_eject", "aspirate", "dispense"}:
        return _string_or_none(params.get("head"))
    if action == "pipette_dwell":
        return _string_or_none(params.get("actor"))
    return None


def _channel_count_for_stepcard(action: str, params: dict[str, Any]) -> int | None:
    if action.endswith("_96mph"):
        return 96
    if action.endswith("_8ch"):
        return 8
    if action == "pipette_dwell" and params.get("at_column") is not None:
        return 8
    if params.get("channel_count") is not None:
        try:
            return int(params["channel_count"])
        except (TypeError, ValueError):
            return None
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)

