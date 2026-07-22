"""Health-only parser for Hamilton VENUS trace files."""

from __future__ import annotations

import re
from pathlib import Path

from pyhamilton.verification.models import RunHealthReport


GUID_RE = re.compile(r"STAR_OEM_noFan_(.+?)_Trace\.trc$", re.IGNORECASE)
ANALYZE_RE = re.compile(r"Analyze method", re.IGNORECASE)
ANALYZE_COMPLETE_RE = re.compile(r"Analyze method\s*-\s*complete", re.IGNORECASE)
CONNECTED_RE = re.compile(r"(connection established|connected)", re.IGNORECASE)
END_RE = re.compile(
    r"((command|cmd).*['\"]?end['\"]?|['\"]command['\"]\s*:\s*['\"]end['\"]|end command)",
    re.IGNORECASE,
)
ERROR_RE = re.compile(r"(Main\s*-\s*error|\berror\b)", re.IGNORECASE)


def parse_trc_health(path: str | Path) -> RunHealthReport:
    """Extract run-health signals from a VENUS ``.trc`` file."""

    path = Path(path)
    guid = extract_trc_guid(path)
    analyzed_ok = False
    connected = False
    reached_end = False
    errors: list[str] = []
    raw_signal_lines: list[str] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue

            is_analyze = bool(ANALYZE_RE.search(stripped))
            is_connected = bool(CONNECTED_RE.search(stripped))
            is_end = bool(END_RE.search(stripped))
            is_error = _is_error_line(stripped)

            if not (is_analyze or is_connected or is_end or is_error):
                continue

            raw_signal_lines.append(stripped)
            if is_analyze and ANALYZE_COMPLETE_RE.search(stripped) and not is_error:
                analyzed_ok = True
            if is_connected:
                connected = True
            if is_end:
                reached_end = True
            if is_error:
                errors.append(stripped)

    if not raw_signal_lines:
        return RunHealthReport(
            guid=guid,
            analyzed_ok=False,
            connected=False,
            reached_end=False,
            errors=["no signal lines in trace"],
            raw_signal_lines=[],
        )

    return RunHealthReport(
        guid=guid,
        analyzed_ok=analyzed_ok,
        connected=connected,
        reached_end=reached_end,
        errors=errors,
        raw_signal_lines=raw_signal_lines,
    )


def extract_trc_guid(path: str | Path) -> str:
    match = GUID_RE.search(Path(path).name)
    return match.group(1) if match else ""


def _is_error_line(line: str) -> bool:
    if not ERROR_RE.search(line):
        return False
    lowered = line.lower()
    return "without error" not in lowered and "no error" not in lowered

