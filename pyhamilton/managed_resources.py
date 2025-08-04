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
                 volume_capacity: int,
                 tracker_id: str | None = None,
                 reset: bool = True,
                 ):
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
        self.volume_capacity: int = volume_capacity

        # Build default in‑RAM state (all tips occupied).
        self.occupancy: List[Tuple[DeckResource, bool]] = []
        for rack in tip_racks:
            self.occupancy.extend([(rack, True) for _ in range(rack._num_items)])

        # Reconcile with on‑disk data (or seed the DB if brand‑new).
        if reset:           # optional hard‑reset switch
            self._flush_entire_state()
            self.restored_from_db = False
        else:
            self.restored_from_db = self._hydrate_from_db()

    # ----------------------------- Factories --------------------------
    @classmethod
    def from_prefix(cls,
                    tracker_id: str,
                    volume_capacity: int,
                    prefix   : str,
                    count    : int,
                    lmgr     : LayoutManager,
                    tip_type : ResourceType = Tip96,
                    reset    : bool = True) -> "TrackedTips":
        """
        Allocate `count` racks named f"{prefix}_{i:04d}" via `lmgr`,
        then return a new TrackedTips instance managing them.
        """
        resources = [
            lmgr.assign_unused_resource(ResourceType(tip_type, f"{prefix}_{i:04d}"))
            for i in range(1, count + 1)
        ]
        return cls(resources, volume_capacity=volume_capacity, tracker_id=tracker_id, reset=reset)

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

        for idx, (rack, occ) in enumerate(self.occupancy):
            if not occ:
                continue

            # Correct position inside this rack (0‑based)
            pos_in_rack = idx % rack._num_items      # works for any rack size

            fetched.append((idx, rack, pos_in_rack))
            if len(fetched) == n:
                break

        if len(fetched) < n:
            raise ValueError(
                f"Only {len(fetched)} tips available; {n} requested."
            )

        # Mark the returned tips as used and sync to DB
        for idx, _, _ in fetched:
            self.mark_unoccupied(idx)

        # Strip the internal absolute index before returning
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


    def replace_tips(self, positions: List[Tuple[DeckResource, int]]) -> None:
        """
        Mark the given tips as present/available again.

        Parameters
        ----------
        positions : list[tuple[DeckResource, int]]
            A collection of (rack, pos_in_rack) pairs where `pos_in_rack`
            is 0-based within that rack.

        Raises
        ------
        ValueError
            • If the rack is not managed by this tracker  
            • If the position is out of range for that rack  
            • If the tip at that location is already occupied
        """
        # Build a mapping of rack → starting absolute index once
        rack_starts: Dict[DeckResource, int] = {}
        offset = 0
        for rack in self.tip_racks:
            rack_starts[rack] = offset
            offset += rack._num_items

        for rack, pos_in_rack in positions:
            if rack not in rack_starts:
                raise ValueError(f"Rack {rack.layout_name()} not managed by this tracker.")
            if not (0 <= pos_in_rack < rack._num_items):
                raise ValueError(f"Position {pos_in_rack} out of range for rack {rack.layout_name()}.")

            abs_idx = rack_starts[rack] + pos_in_rack

            if self.is_occupied(abs_idx):
                raise ValueError(f"Tip at {rack.layout_name()}[{pos_in_rack}] is already occupied.")

            # Persistently mark the tip as available again
            self.mark_occupied(abs_idx)

    # ------------------- Persistence internals ------------------------
    def _hydrate_from_db(self) -> bool:
        with _get_conn() as conn:
            cur = conn.execute(
                "SELECT position_idx, rack_name, occupied "
                "FROM tips WHERE tracker_id = ?;",
                (self.tracker_id,)
            )
            rows = cur.fetchall()

            if not rows:  # first‑time tracker → seed DB
                self._flush_entire_state()
                return False

            # overwrite default RAM state with DB contents
            rack_map = {r.layout_name(): r for r in self.tip_racks}
            for pos, rack_name, occ_int in rows:
                rack = rack_map.get(rack_name)
                if rack is None:
                    continue  # stale DB row; ignore
                self.occupancy[pos] = (rack, bool(occ_int))

            return True

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
    A persistent stack of named resources (as strings), supporting
    FIFO access and database-backed availability tracking.
    """

    def __init__(self,
                 resource_names: List[str],
                 tracker_id: Optional[str] = None):
        """
        Parameters
        ----------
        resource_names : list[str]
            The initial resource names to be managed.
        tracker_id : str, optional
            Namespace for persistence. Defaults to joined resource names.
        """
        self.resource_names = resource_names
        self.tracker_id     = tracker_id or "|".join(resource_names)
        self._stacked: List[str] = list(resource_names)

        self._hydrate_from_db()

    @classmethod
    def from_prefix(cls,
                    tracker_id: str,
                    prefix    : str,
                    count     : int) -> "StackedResources":
        """
        Create a StackedResources instance with names like 'prefix_0001', etc.

        Parameters
        ----------
        tracker_id : str
            Unique ID to scope persistence.
        prefix : str
            Base name for the resources.
        count : int
            How many named resources to generate.
        """
        resource_names = [f"{prefix}_{i:04d}" for i in range(1, count + 1)]
        return cls(resource_names, tracker_id=tracker_id)

    def get_stacked(self) -> List[str]:
        """Return the current list of available resources."""
        return self._stacked

    def count(self) -> int:
        """Return the number of available resources."""
        return len(self._stacked)

    def fetch_next(self) -> List[str]:
        """
        Pop and return the next resource from the stack.
        Persistently marks them as unavailable.
        """
        if len(self._stacked) < 1:
            raise ValueError(f"Only {len(self._stacked)} resources available; 1 requested.")

        fetched = self._stacked[:1]
        self._stacked = self._stacked[1:]

        for rname in fetched:
            self._update_row(rname, available=False)

        return fetched[0]

    # ---------------------- Persistence Helpers ----------------------

    def _hydrate_from_db(self) -> None:
        """Restore from DB or seed from initial list if new."""
        with _get_stacked_conn() as conn:
            cur = conn.execute(
                "SELECT rack_name, available FROM stacked WHERE tracker_id = ?;",
                (self.tracker_id,))
            rows = cur.fetchall()

            if not rows:
                self._flush_entire_state(conn)
                conn.commit()
                return

            valid_names = set(self.resource_names)
            self._stacked = [
                rname for rname, available in rows
                if available and rname in valid_names
            ]

    def _update_row(self, rname: str, *, available: bool) -> None:
        """Insert or update a single row in the DB."""
        with _get_stacked_conn() as conn:
            conn.execute("""INSERT OR REPLACE INTO stacked
                               (tracker_id, rack_name, slot_idx, available)
                            VALUES (?,?,NULL,?);""",
                         (self.tracker_id, rname, int(available)))
            conn.commit()

    def _flush_entire_state(self, conn) -> None:
        """Write the full available list to the DB."""
        conn.executemany("""INSERT OR REPLACE INTO stacked
                               (tracker_id, rack_name, slot_idx, available)
                            VALUES (?,?,NULL,?);""",
                         [(self.tracker_id, rname, 1) for rname in self._stacked])
