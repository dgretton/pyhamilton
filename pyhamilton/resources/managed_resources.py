# Fully self‑contained implementation of TrackedTips + StackedResources
# with on‑disk persistence (SQLite in ~/.pyhamilton/tip_tracker.db).


from __future__ import annotations
import string, shutil, os, string, re
from datetime import datetime

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from collections import defaultdict
from typing import List, Tuple, Optional, Dict, TypeVar, Type

# ────────────────────────── HAMILTON imports ──────────────────────────
from pyhamilton import OEM_LAY_PATH, LAY_BACKUP_DIR        # noqa: F401 (kept for context)
from ..oemerr import ResourceUnavailableError               # noqa: F401
from .deckresource import (LayoutManager, ResourceType,    # noqa: F401
                            Plate24, Plate96, Tip96,
                            resource_list_with_prefix, layout_item, DeckResource)
from ..interface import HamiltonInterface
from .enums import TipType
from .deckresource import LayoutManager

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

# ────────────────────────── TrackedTips ──────────────────────────
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
                    reset    : bool = True) -> TrackedTips:
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

    def fetch_rack_with_min_columns(self, min_columns: int) -> Optional[Tuple[DeckResource, List[int]]]:
        """
        Return the first rack that has at least `min_columns` complete columns of occupied tips
        (anywhere in the rack). If found, returns a tuple of:
            (rack, occupancy_map)
        where `occupancy_map` is a list of 96 integers (1 = occupied, 0 = used)
        representing the rack's tips **before** they are marked unoccupied.

        Side-effect: If a qualifying rack is found, ALL tips in that rack are marked unoccupied.

        Parameters
        ----------
        min_columns : int
            Minimum number of complete columns (of 8 tips) that must be occupied.

        Returns
        -------
        Optional[Tuple[DeckResource, List[int]]]
            (rack, occupancy_map) if found; otherwise None.
        """
        # Build rack → starting absolute index map once
        rack_start_indices = {rack: sum(r._num_items for r in self.tip_racks[:i])
                            for i, rack in enumerate(self.tip_racks)}

        for rack in self.tip_racks:
            rack_start = rack_start_indices[rack]
            # Snapshot occupancy for this rack (booleans, length 96 expected)
            occupancy_bools = [self.occupancy[rack_start + i][1] for i in range(96)]
            # Count full columns (12 columns × 8 rows layout assumed)
            full_columns = sum(
                1 for col in range(12)
                if all(occupancy_bools[col * 8 + row] for row in range(8))
            )

            if full_columns >= min_columns:
                # Convert to 1/0 map BEFORE mutating state
                occupancy_map = [1 if b else 0 for b in occupancy_bools]

                # Mark all tips as unoccupied (persisted via mark_unoccupied)
                for i in range(96):
                    self.mark_unoccupied(rack_start + i)

                return rack, occupancy_map

        raise Exception(f"No rack found with at least {min_columns} full columns.")

    def reset_all(self) -> None:
        """
        Mark **every** tip in every managed rack as present/available again
        and persist that state to the on-disk SQLite table.

        This is functionally the same as constructing the tracker with
        ``reset=True``—but it can be invoked at any time after the object
        exists.

        Example
        -------
        >>> tracker.reset_all()      # all tips are now 'full' again
        """
        # 1) Update the in-memory occupancy list
        for i, (rack, _) in enumerate(self.occupancy):
            self.occupancy[i] = (rack, True)

        # 2) Push the fresh state to disk in one shot
        self._flush_entire_state()

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

    def fill_rack_from_occupancy_map(self, rack: DeckResource, occupancy_map: List[int]) -> None:
        """
        Set the occupancy state of a specific rack based on the provided occupancy map.
        
        This method complements fetch_rack_with_min_columns() by allowing you to restore
        a rack's state from a previously captured occupancy map.
        
        Parameters
        ----------
        rack : DeckResource
            The specific rack to update. Must be managed by this tracker.
        occupancy_map : List[int]
            A list of 96 integers where 1 = occupied/available and 0 = unoccupied/used.
            The list should match the rack's layout (12 columns × 8 rows).
            
        Raises
        ------
        ValueError
            • If the rack is not managed by this tracker
            • If occupancy_map length doesn't match the rack size (expected 96)
            • If occupancy_map contains values other than 0 or 1
            
        Example
        -------
        >>> # Capture state before fetching
        >>> rack, old_occupancy = tracker.fetch_rack_with_min_columns(4)
        >>> # ... use the rack for some operations ...
        >>> # Later, restore the original state
        >>> tracker.fill_rack_from_occupancy_map(rack, old_occupancy)
        """
        # Validate that we manage this rack
        if rack not in self.tip_racks:
            raise ValueError(f"Rack {rack.layout_name()} is not managed by this tracker.")
        
        # Validate occupancy map size
        if len(occupancy_map) != 96:
            raise ValueError(f"Occupancy map must have 96 entries, got {len(occupancy_map)}.")
        
        # Validate occupancy map values
        if not all(val in (0, 1) for val in occupancy_map):
            raise ValueError("Occupancy map must contain only 0 (unoccupied) or 1 (occupied) values.")
        
        # Find the starting absolute index for this rack
        rack_start_idx = 0
        for r in self.tip_racks:
            if r == rack:
                break
            rack_start_idx += r._num_items
        else:
            # This shouldn't happen given our first check, but just in case
            raise ValueError(f"Rack {rack.layout_name()} not found in tip_racks.")
        
        # Update each position in the rack according to the occupancy map
        for pos_in_rack, should_be_occupied in enumerate(occupancy_map):
            abs_idx = rack_start_idx + pos_in_rack
            
            if should_be_occupied == 1:
                # Should be occupied/available
                if not self.is_occupied(abs_idx):
                    self.mark_occupied(abs_idx)
            else:
                # Should be unoccupied/used
                if self.is_occupied(abs_idx):
                    self.mark_unoccupied(abs_idx)

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

T = TypeVar('T', bound='DeckResource')

class StackedResources:
    """
    A persistent stack of named resources (as strings), supporting
    top-of-stack-first access and database-backed availability tracking.
    """

    def __init__(self,
                 resource_names: List[str],
                 tracker_id: Optional[str],
                 lmgr: Optional[LayoutManager],
                 resource_type: Type[T],
                 reset: bool = True):
        
        self.resource_names = list(resource_names)  # fixed order definition
        self.tracker_id     = tracker_id or "|".join(resource_names)
        self._stacked: List[str] = list(resource_names)
        self.resource_type = resource_type

        self.lmgr = lmgr
        if lmgr is not None:
            for rname in resource_names:
                resource_present_in_layfile = any([rname in line for line in lmgr.lines])
                if not resource_present_in_layfile:
                    raise ValueError(f"Resource '{rname}' not found in LayoutManager.")

        if reset:
            # Hard reset: clear any prior rows for this tracker_id and seed to "full"
            with _get_stacked_conn() as conn:
                conn.execute("DELETE FROM stacked WHERE tracker_id = ?;", (self.tracker_id,))
                self._flush_entire_state(conn)
                conn.commit()
        else:
            # Rehydrate from DB if present; otherwise seed to full
            self._hydrate_from_db()

    @classmethod
    def from_prefix(cls,
                    tracker_id: str,
                    prefix    : str,
                    count     : int,
                    lmgr      : LayoutManager,
                    resource_type: Type[T],
                    reset     : bool = True) -> StackedResources:
        """
        Create a stack with HIGHEST index at the TOP (fetched first).
        Example: count=4 → top: prefix_0004, prefix_0003, prefix_0002, prefix_0001
        """
        ascending = [f"{prefix}_{i:04d}" for i in range(1, count + 1)]
        top_first = list(reversed(ascending))
        return cls(top_first, tracker_id=tracker_id, lmgr=lmgr, resource_type=resource_type, reset=reset)

    def get_stacked(self) -> List[str]:
        """Return the current list of available resources (top-first)."""
        return self._stacked

    def count(self) -> int:
        """Return the number of available resources."""
        return len(self._stacked)

    def fetch_next(self) -> str:
        """
        Pop and return the next resource from the top of the stack.
        Persistently marks it as unavailable and remembers it for put_back_top().
        """
        if len(self._stacked) < 1:
            raise ValueError(f"Only {len(self._stacked)} resources available; 1 requested.")

        rname = self._stacked.pop(0)
        self._last_fetched = rname
        self._update_row(rname, available=False)
        resource = self.resource_type(rname)
        return resource

    def put_back(self) -> str:
        """
        Restore the next positional resource to the TOP of the stack, mark it available,
        and return its name.

        Logic:
        - self.resource_names is the canonical, top-first order (e.g. 0004,0003,0002,0001).
        - self._stacked is a subsequence (available ones).
        - Putting back picks the highest-priority *missing* name and inserts it at index 0.
        """
        # Compute which names are currently missing (unavailable), in top-first order.
        missing = [r for r in self.resource_names if r not in self._stacked]

        if not missing:
            raise RuntimeError("Stack is already full; nothing to put back.")

        rname = missing[0]          # highest-priority missing item
        self._stacked.insert(0, rname)
        self._update_row(rname, available=True)
        resource = self.resource_type(rname)
        return resource

    def reset_all(self) -> None:
        """
        Reset all resources to available state and restore the full stack.
        This marks every resource as available again and rebuilds the stack
        to its original top-first order.
        
        This is functionally the same as constructing the tracker with
        ``reset=True``—but it can be invoked at any time after the object
        exists.
        
        Example
        -------
        >>> stack.reset_all()      # all resources are now available again
        """
        # 1) Update the in-memory stack to full state
        self._stacked = list(self.resource_names)
        
        # 2) Push the fresh state to disk in one shot
        with _get_stacked_conn() as conn:
            # Clear existing entries for this tracker
            conn.execute("DELETE FROM stacked WHERE tracker_id = ?;", (self.tracker_id,))
            # Write all resources as available
            self._flush_entire_state(conn)
            conn.commit()

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
            availability = {r: bool(a) for r, a in rows if r in valid_names}
            self._stacked = [r for r in self.resource_names if availability.get(r, False)]

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


class TipSupportTracker:
    WELLS_PER_COL = 8
    NUM_COLS = 12
    TOTAL_WELLS = WELLS_PER_COL * NUM_COLS  # 96

    def __init__(self, resource):
        self.resource = resource
        self.occupancy = [0] * self.TOTAL_WELLS  # 1 = available, 0 = empty
        self.tip_vol = None
        self.source_rack = None  # set on add_rack
        self.source_tip_tracker = None  # set on add_rack

    def _update_rack_in_tracker(self, rack, tip_occupancies, tip_tracker, tip_vol):
        """Load a full fresh rack into the support (assumes all wells have tips)."""
        self.occupancy = tip_occupancies
        self.tip_vol = tip_vol
        self.source_rack = rack
        self.source_tip_tracker = tip_tracker

    def remove_rack(self, rack=None):
        """Clear current rack state."""
        self.occupancy = [0] * self.TOTAL_WELLS
        self.tip_vol = None
        self.source_rack = None

    def has_available_tips(self, num_tips: int) -> bool:
        return sum(self.occupancy) >= num_tips

    def _rightmost_indices_for_n_columns(self, n: int):
        if not (1 <= n <= self.NUM_COLS):
            raise ValueError(f"n must be between 1 and {self.NUM_COLS}, got {n}")
        full = [all(self.occupancy[c*self.WELLS_PER_COL + r] for r in range(self.WELLS_PER_COL))
                for c in range(self.NUM_COLS)]
        cols = [c for c in range(self.NUM_COLS-1, -1, -1) if full[c]][:n]
        if len(cols) < n:
            raise ValueError(f"Only found {len(cols)} full columns; {n} requested.")
        return sorted(i for c in cols for i in range(c*self.WELLS_PER_COL, (c+1)*self.WELLS_PER_COL))

    def fetch_n_columns(self, ham_int: HamiltonInterface, n: int, tip_tracker: TrackedTips):
        """
        Returns (tips, leftmost_col_idx) where tips are the wells in the right-most
        n columns, and leftmost_col_idx is 1-based column index of the left-most column fetched.
        """
        if self.source_rack is None:
            self.tip_support_add_rack(ham_int, tip_tracker, n)
        
        if self.tip_vol != tip_tracker.volume_capacity:
            print(f"Tip volume mismatch: support has {self.tip_vol}, tracker has {tip_tracker.volume_capacity}. Replacing rack.")
            self.tip_support_add_rack(ham_int, tip_tracker, n)
        
        try:
            indices = self._rightmost_indices_for_n_columns(n)
        except ValueError:
            self.tip_support_add_rack(ham_int, tip_tracker, n)
            indices = self._rightmost_indices_for_n_columns(n)

        # If available, mark and return
        if all(self.occupancy[i] == 1 for i in indices):
            for i in indices:
                self.occupancy[i] = 0

            leftmost_col_idx = indices[0] // self.WELLS_PER_COL + 1
            return leftmost_col_idx

        if not all(self.occupancy[i] == 1 for i in indices):
            raise RuntimeError(f"After replacing rack, still no right-most {n} columns available.")


    def tip_support_add_rack(self, ham_int: HamiltonInterface, tracked_tips: TrackedTips, num_columns: int):
        """
        Eject current rack (if any), fetch another with >= num_columns available columns,
        and load it here. Assumes `tracked_tips.fetch_rack_with_min_columns` returns a rack
        object with tips in the left-most columns populated (or all).
        """
        
        tip_rack, tip_occupancies = tracked_tips.fetch_rack_with_min_columns(num_columns)

        if self.source_rack is not None:
            # Place any currently-held tips back and eject the existing rack
            ham_int.tip_pick_up_96(self.resource)
            ham_int.tip_eject_96(self.source_rack)
            self.source_tip_tracker.fill_rack_from_occupancy_map(self.source_rack, self.occupancy)

        # Load the new rack into the support
        # We have to modify the labware property of the tip support at runtime
        ham_int.set_labware_property(self.resource.layout_name(), 'MlStarCore96TipRack', TipType.from_volume(tracked_tips.volume_capacity))
        

        ham_int.tip_pick_up_96(tip_rack)
        ham_int.tip_eject_96(self.resource)
        self._update_rack_in_tracker(tip_rack, tip_occupancies, tracked_tips, tracked_tips.volume_capacity)


