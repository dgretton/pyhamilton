from __future__ import annotations
import json
from dataclasses import dataclass, asdict, replace
from pathlib import Path
from typing import Any, Final

# ───────────────────────────── File location ─────────────────────────────
_DOTDIR: Final[Path] = Path.home() / ".pyhamilton"
_DOTDIR.mkdir(exist_ok=True)
_DEFAULTS_PATH: Final[Path] = _DOTDIR / "defaults.json"


# ───────────────────────────── Settings dataclass ─────────────────────────
@dataclass(slots=True, frozen=True)
class Defaults:
    """
    Persistent user-wide defaults for PyHamilton configuration.
    Automatically loaded from ~/.pyhamilton/defaults.json if available.
    """
    robot_type: str = "STAR"
    core_gripper_sequence: list[str] = ()

    # (internal) pointer to source file for debugging
    _source_file: Path | None = None


# ───────────────────────────── Internal load logic ────────────────────────
def _read_file() -> dict[str, Any]:
    if not _DEFAULTS_PATH.exists():
        return {}
    try:
        with _DEFAULTS_PATH.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError):
        return {}


# cache the singleton
_defaults_singleton: Defaults | None = None


def defaults(**overrides) -> Defaults:
    """
    Get the current default settings.
    You can optionally pass overrides to get a copy with modified fields.
    """
    global _defaults_singleton
    if _defaults_singleton is None:
        raw = _read_file()
        _defaults_singleton = Defaults(**raw, _source_file=_DEFAULTS_PATH)

    if overrides:
        return replace(_defaults_singleton, **overrides)
    return _defaults_singleton


# ───────────────────────────── Save and reload utilities ──────────────────
def save(new_defaults: Defaults | None = None) -> None:
    """
    Save the provided Defaults object (or current one) to disk.
    """
    obj = new_defaults or defaults()
    data = asdict(obj)
    data.pop("_source_file", None)
    with _DEFAULTS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def reload() -> Defaults:
    """
    Force a reload of the defaults from disk, replacing the cached singleton.
    """
    global _defaults_singleton
    _defaults_singleton = None
    return defaults()
