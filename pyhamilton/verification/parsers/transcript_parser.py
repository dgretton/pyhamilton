"""Parser for simulator stdout transcript logs."""

from __future__ import annotations

import re
from pathlib import Path

from pyhamilton.verification.models import EventCategory, NormalizedEvent


ODTC_RE = re.compile(r"Simulating ODTC (?:protocol|status).*?['\"]([^'\"]+)['\"]")
WAIT_RE = re.compile(r"skipping (\d+)\s*s wait", re.IGNORECASE)
STEP_RE = re.compile(r"Executing step: (\S+)")


def parse_run_transcript(path_or_text: str | Path) -> list[NormalizedEvent]:
    """Extract low-confidence normalized events from a run transcript."""

    text = _read_path_or_text(path_or_text)
    events: list[NormalizedEvent] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        odtc_match = ODTC_RE.search(line)
        if odtc_match:
            method_name = odtc_match.group(1)
            events.append(
                NormalizedEvent(
                    sequence=0,
                    category=EventCategory.MODULE_ACTION,
                    action="run_program",
                    resources=["ODTC"],
                    metadata={
                        "line_number": line_number,
                        "method_name": method_name,
                        "raw_line": line,
                    },
                )
            )
            continue

        wait_match = WAIT_RE.search(line)
        if wait_match:
            duration_s = int(wait_match.group(1))
            events.append(
                NormalizedEvent(
                    sequence=0,
                    category=EventCategory.WAIT,
                    action="wait",
                    metadata={
                        "line_number": line_number,
                        "duration_s": duration_s,
                        "raw_line": line,
                    },
                )
            )
            continue

        step_match = STEP_RE.search(line)
        if step_match:
            events.append(
                NormalizedEvent(
                    sequence=0,
                    category=EventCategory.OTHER,
                    action="executing_step",
                    metadata={
                        "line_number": line_number,
                        "step": step_match.group(1),
                        "raw_line": line,
                    },
                )
            )

    for sequence, event in enumerate(events):
        event.sequence = sequence
    return events


def _read_path_or_text(path_or_text: str | Path) -> str:
    if isinstance(path_or_text, Path):
        return path_or_text.read_text(encoding="utf-8")

    value = str(path_or_text)
    candidate = Path(value)
    if candidate.exists():
        return candidate.read_text(encoding="utf-8")

    if "\n" in value or "\r" in value:
        return value
    if candidate.suffix or "\\" in value or "/" in value:
        raise FileNotFoundError(value)
    return value

