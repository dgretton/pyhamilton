from enum import IntEnum
from dataclasses import dataclass


class TipType(IntEnum):
    """Hamilton tip types mapped to their database codes (values)."""
    uL_10   = 3
    uL_300  = 1
    uL_50   = 23
    uL_1000 = 5
    
    # Additional tip types from the table
    uL_300_base = 0
    uL_10_with_filter = 2
    uL_1000_with_filter = 4
    needle_50_old = 6
    needle_300_old = 7
    needle_1000_old = 8
    needle_10 = 11
    needle_300 = 12
    needle_1000 = 13
    uL_30_for_384 = 15
    uL_50_for_384 = 20
    uL_50_with_filter = 22
    uL_5000 = 25
    rocket_300_for_384 = 28
    uL_4000_with_filter = 29
    uL_300_clear = 30
    uL_50_clear = 31
    uL_10_clear = 32
    uL_50_conductive_for_384 = 33
    piercing_250 = 35
    slim_core_300 = 36
    uL_50_clear_for_384 = 37
    piercing_150_with_filter = 44
    slim_core_300_with_filter = 45

    @property
    def volume(self) -> int:
        """Return the volume in µL for this tip type."""
        mapping = {
            TipType.uL_10: 10,
            TipType.uL_300: 300,
            TipType.uL_50: 50,
            TipType.uL_1000: 1000,
            TipType.uL_300_base: 300,
            TipType.uL_10_with_filter: 10,
            TipType.uL_1000_with_filter: 1000,
            TipType.needle_50_old: 50,
            TipType.needle_300_old: 300,
            TipType.needle_1000_old: 1000,
            TipType.needle_10: 10,
            TipType.needle_300: 300,
            TipType.needle_1000: 1000,
            TipType.uL_30_for_384: 30,
            TipType.uL_50_for_384: 50,
            TipType.uL_50_with_filter: 50,
            TipType.uL_5000: 5000,
            TipType.rocket_300_for_384: 300,
            TipType.uL_4000_with_filter: 4000,
            TipType.uL_300_clear: 300,
            TipType.uL_50_clear: 50,
            TipType.uL_10_clear: 10,
            TipType.uL_50_conductive_for_384: 50,
            TipType.piercing_250: 250,
            TipType.slim_core_300: 300,
            TipType.uL_50_clear_for_384: 50,
            TipType.piercing_150_with_filter: 150,
            TipType.slim_core_300_with_filter: 300,
        }
        return mapping[self]

    @classmethod
    def from_volume(cls, volume: int) -> "TipType":
        """Look up a TipType enum from a µL volume."""
        reverse_map = {
            10: cls.uL_10,
            300: cls.uL_300,
            50: cls.uL_50,
            1000: cls.uL_1000,
        }
        try:
            return reverse_map[volume]
        except KeyError:
            raise ValueError(f"No TipType defined for volume {volume} µL")

    @property
    def has_filter(self) -> bool:
        """Return True if this tip type has a filter."""
        filter_tips = {
            self.uL_10_with_filter,
            self.uL_1000_with_filter,
            self.uL_50_with_filter,
            self.uL_4000_with_filter,
            self.piercing_150_with_filter,
            self.slim_core_300_with_filter,
        }
        return self in filter_tips

    @property
    def is_needle(self) -> bool:
        """Return True if this is a needle tip type."""
        needle_tips = {
            self.needle_50_old,
            self.needle_300_old,
            self.needle_1000_old,
            self.needle_10,
            self.needle_300,
            self.needle_1000,
        }
        return self in needle_tips

    @property
    def is_384_compatible(self) -> bool:
        """Return True if this tip is designed for 384-well plates."""
        plate_384_tips = {
            self.uL_30_for_384,
            self.uL_50_for_384,
            self.rocket_300_for_384,
            self.uL_50_conductive_for_384,
            self.uL_50_clear_for_384,
        }
        return self in plate_384_tips