# Fully self‑contained implementation of TrackedTips + StackedResources
# with on‑disk persistence (SQLite in ~/.pyhamilton/tip_tracker.db).


from __future__ import annotations
import string, shutil, os, string, re
from datetime import datetime

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from collections import defaultdict
from typing import List, Tuple, Optional, Dict

# ────────────────────────── HAMILTON imports ──────────────────────────
from pyhamilton import OEM_LAY_PATH, LAY_BACKUP_DIR        # noqa: F401 (kept for context)
from .oemerr import ResourceUnavailableError               # noqa: F401
from .deckresource import (LayoutManager, ResourceType,    # noqa: F401
                            Plate24, Plate96, Tip96,
                            resource_list_with_prefix, layout_item, DeckResource)

# ────────────────────────── Persistence helpers ───────────────────────
_DOTDIR   = Path.home() / ".pyhamilton"
_DOTDIR.mkdir(parents=True, exist_ok=True)
_DB_PATH  = _DOTDIR / "tip_tracker.db"

@contextmanager
def _get_conn():
    """Yield a SQLite connection with WAL enabled and autocommit on exit."""
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def _ensure_table() -> None:
    with _get_conn() as conn:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS tips(
              tracker_id     TEXT,
              position_idx   INTEGER,
              rack_name      TEXT,
              occupied       INTEGER,
              PRIMARY KEY (tracker_id, position_idx)
          )
        """)

_ensure_table()  # one‑time at import


# ────────────────────────── TrackedTips ────────────────────────────────
class TrackedTips:
    """
    Persistently tracks individual tips across one or more DeckResources.

    State lives both in-memory (`self.occupancy`) and on disk
    (`~/.pyhamilton/tip_tracker.db`).  All mutating operations sync to disk.
    """

    # ------------------------------------------------------------------
    def __init__(self,
                 tip_racks: List[DeckResource],
                 tracker_id: str | None = None):
        """
        Parameters
        ----------
        tip_racks : list[DeckResource]
            The racks this tracker manages.
        tracker_id : str, optional
            Identifier used as the namespace inside the shared DB.
            Defaults to a deterministic hash of rack layout names.
        """
        self.tip_racks   : List[DeckResource] = tip_racks
        self.tracker_id  : str = tracker_id or "|".join(r.layout_name() for r in tip_racks)

        # Build default in‑RAM state (all tips occupied).
        self.occupancy: List[Tuple[DeckResource, bool]] = []
        for rack in tip_racks:
            self.occupancy.extend([(rack, True) for _ in range(rack._num_items)])

        # Reconcile with on‑disk data (or seed the DB if brand‑new).
        self._hydrate_from_db()

    # ----------------------------- Factories --------------------------
    @classmethod
    def from_prefix(cls,
                    tracker_id: str,
                    prefix   : str,
                    count    : int,
                    lmgr     : LayoutManager,
                    tip_type : ResourceType = Tip96) -> "TrackedTips":
        """
        Allocate `count` racks named f"{prefix}_{i:04d}" via `lmgr`,
        then return a new TrackedTips instance managing them.
        """
        resources = [
            lmgr.assign_unused_resource(ResourceType(tip_type, f"{prefix}_{i:04d}"))
            for i in range(1, count + 1)
        ]
        return cls(resources, tracker_id=tracker_id)

    # ------------------------ Public API ------------------------------
    def mark_occupied(self, index: int) -> None:
        rack, _ = self.occupancy[index]
        self.occupancy[index] = (rack, True)
        self._update_row(index, True)

    def mark_unoccupied(self, index: int) -> None:
        rack, _ = self.occupancy[index]
        self.occupancy[index] = (rack, False)
        self._update_row(index, False)

    def is_occupied(self, index: int) -> bool:
        return self.occupancy[index][1]

    def count_remaining(self) -> int:
        return sum(1 for _, occ in self.occupancy if occ)

    def total_tips(self) -> int:
        return len(self.occupancy)

    def fetch_next(self, n: int) -> List[Tuple[DeckResource, int]]:
        """
        Return and mark unoccupied the next `n` available tips.
        Output format: (DeckResource, position_within_rack).
        """
        fetched: List[Tuple[int, DeckResource, int]] = []
        seen: Dict[int, int] = {}

        for idx, (rack, occ) in enumerate(self.occupancy):
            if not occ:
                continue
            rid = id(rack)
            pos = seen.setdefault(rid, 0)
            seen[rid] += 1
            fetched.append((idx, rack, pos))
            if len(fetched) == n:
                break

        if len(fetched) < n:
            raise ValueError(f"Only {len(fetched)} tips available; {n} requested.")

        for idx, _, _ in fetched:
            self.mark_unoccupied(idx)          # syncs to DB

        return [(rack, pos) for _, rack, pos in fetched]

    def fetch_rack(self) -> Optional[DeckResource]:
        """
        If an entire rack of 96 still‑occupied tips exists, return that rack
        and mark its tips unoccupied. Otherwise return None.
        """
        by_rack: Dict[DeckResource, List[int]] = defaultdict(list)
        for idx, (rack, occ) in enumerate(self.occupancy):
            by_rack[rack].append(idx if occ else -1)  # -1 for used

        for rack, indices in by_rack.items():
            if len(indices) == 96 and all(i >= 0 for i in indices):
                for idx in indices:
                    self.mark_unoccupied(idx)        # syncs each tip
                return rack
        return None

    # ------------------- Persistence internals ------------------------
    def _hydrate_from_db(self) -> None:
        with _get_conn() as conn:
            cur = conn.execute(
                "SELECT position_idx, rack_name, occupied "
                "FROM tips WHERE tracker_id = ?;",
                (self.tracker_id,)
            )
            rows = cur.fetchall()

            if not rows:                     # first‑time tracker → seed DB
                self._flush_entire_state()
                return

            # overwrite default RAM state with DB contents
            rack_map = {r.layout_name(): r for r in self.tip_racks}
            for pos, rack_name, occ_int in rows:
                rack = rack_map.get(rack_name)
                if rack is None:
                    continue  # stale DB row; ignore
                self.occupancy[pos] = (rack, bool(occ_int))

    def _update_row(self, position_idx: int, occupied: bool) -> None:
        rack = self.occupancy[position_idx][0]
        with _get_conn() as conn:
            conn.execute("""INSERT OR REPLACE INTO tips
                               (tracker_id, position_idx, rack_name, occupied)
                            VALUES (?,?,?,?);""",
                         (self.tracker_id,
                          position_idx,
                          rack.layout_name(),
                          int(occupied)))

    def _flush_entire_state(self) -> None:
        with _get_conn() as conn:
            conn.executemany("""INSERT OR REPLACE INTO tips
                                   (tracker_id, position_idx, rack_name, occupied)
                                VALUES (?,?,?,?);""",
                             [(self.tracker_id,
                               idx,
                               rack.layout_name(),
                               int(occ))
                              for idx, (rack, occ) in enumerate(self.occupancy)])


# ────────────────────────── StackedResources ──────────────────────────
_STACKED_DB = _DOTDIR / "stacked_resources.db"   # separate file so schemas stay tidy


def _get_stacked_conn():
    """SQLite connection for stacked‑resource tracking (WAL enabled)."""
    conn = sqlite3.connect(_STACKED_DB)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _ensure_stacked_table() -> None:
    with _get_stacked_conn() as conn:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS stacked(
              tracker_id   TEXT,
              rack_name    TEXT,
              slot_idx     INTEGER,
              available    INTEGER,
              PRIMARY KEY (tracker_id, rack_name, slot_idx)
          )
        """)
        conn.commit()


_ensure_stacked_table()          # run at import time
# ────────────────────────── StackedResources (persistent) ─────────────
class StackedResources:
    """
    Treat several DeckResources as one vertical stack and persist
    which items remain between runs.
    """

    # ------------------------------------------------------------------
    def __init__(self,
                 resources : List[DeckResource],
                 tracker_id: str | None = None):
        """
        Parameters
        ----------
        resources : list[DeckResource]
            Racks/plates/etc. that form the stack.
        tracker_id : str, optional
            Namespace inside the DB.  Defaults to a join of rack names.
        """
        self.resources  = resources
        self.tracker_id = tracker_id or "|".join(r.layout_name() for r in resources)

        # Build default “everything available” list --------------------
        self._stacked: List[Tuple[DeckResource, int]] = []
        for r in resources:
            self._stacked.extend([(r, i) for i in range(r._num_items())])

        # Reconcile with on‑disk copy
        self._hydrate_from_db()

    # ----------------------- Public API ------------------------------
    def get_stacked(self) -> List[Tuple[DeckResource, int]]:
        """Return the live list (read‑only)."""
        return self._stacked

    def count(self) -> int:
        """Number of remaining items."""
        return len(self._stacked)

    def fetch_next(self, n: int) -> List[Tuple[DeckResource, int]]:
        """
        Pop `n` items from the stack (FIFO) and persist the change.
        Returns tuples of (DeckResource, slot_idx).
        """
        if n > len(self._stacked):
            raise ValueError(f"Only {len(self._stacked)} resources available; {n} requested.")

        fetched = self._stacked[:n]
        self._stacked = self._stacked[n:]

        # Mark each fetched item unavailable in DB
        for rack, slot in fetched:
            self._update_row(rack, slot, available=False)

        return fetched

    # ---------------------- Persistence helpers ----------------------
    def _hydrate_from_db(self) -> None:
        """Overwrite default stack with DB copy, or seed DB if new."""
        with _get_stacked_conn() as conn:
            cur = conn.execute(
                "SELECT rack_name, slot_idx, available "
                "FROM stacked WHERE tracker_id = ?;",
                (self.tracker_id,))
            rows = cur.fetchall()

            if not rows:
                self._flush_entire_state(conn)   # first‑time run
                conn.commit()
                return

            # Map rack names back to live objects
            rack_map = {r.layout_name(): r for r in self.resources}
            self._stacked = [
                (rack_map[r_name], slot)
                for r_name, slot, avail in rows if avail and r_name in rack_map
            ]

    def _update_row(self, rack: DeckResource, slot_idx: int, *, available: bool) -> None:
        """Insert or replace a single row."""
        with _get_stacked_conn() as conn:
            conn.execute("""INSERT OR REPLACE INTO stacked
                               (tracker_id, rack_name, slot_idx, available)
                            VALUES (?,?,?,?);""",
                         (self.tracker_id,
                          rack.layout_name(),
                          slot_idx,
                          int(available)))
            conn.commit()

    def _flush_entire_state(self, conn) -> None:
        """Write the current in‑memory stack to disk (bulk)."""
        conn.executemany("""INSERT OR REPLACE INTO stacked
                               (tracker_id, rack_name, slot_idx, available)
                            VALUES (?,?,?,?);""",
                         [(self.tracker_id,
                           rack.layout_name(),
                           slot,
                           1)               # 1 = available
                          for rack, slot in self._stacked])









