"""Shared data model for simulation verification."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventCategory(str, Enum):
    INITIALIZE = "initialize"
    TIP_PICKUP = "tip_pickup"
    TIP_EJECT = "tip_eject"
    ASPIRATE = "aspirate"
    DISPENSE = "dispense"
    MIX = "mix"
    TRANSPORT = "transport"
    LID_TRANSPORT = "lid_transport"
    MODULE_ACTION = "module_action"
    WAIT = "wait"
    TIP_STAGING = "tip_staging"
    OTHER = "other"


@dataclass
class NormalizedEvent:
    sequence: int
    category: EventCategory
    action: str
    resources: list[str] = field(default_factory=list)
    volume_ul: float | None = None
    head: str | None = None
    channel_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunHealthReport:
    guid: str
    analyzed_ok: bool
    connected: bool
    reached_end: bool
    errors: list[str] = field(default_factory=list)
    raw_signal_lines: list[str] = field(default_factory=list)


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_resource_name(raw: str) -> str:
    """Canonicalize Hamilton resource names without changing case."""

    return _WHITESPACE_RE.sub(" ", str(raw).strip())


def dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


def parse_labware_positions(field: str) -> list[str]:
    """Parse semicolon-delimited ``"Resource, N"`` labware position fields."""

    if field is None:
        return []

    resources: list[str] = []
    for item in str(field).split(";"):
        item = item.strip()
        if not item:
            continue
        resource = item.split(",", 1)[0]
        normalized = normalize_resource_name(resource)
        if normalized:
            resources.append(normalized)
    return dedupe_preserving_order(resources)
