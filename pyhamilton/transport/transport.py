from ..interface import HamiltonInterface
from ..liquid_handling_wrappers import move_plate_using_gripper
from ..resources import DeckResource, Lid

from dataclasses import dataclass
from enum import Enum, IntEnum
from typing import Any, Dict, Literal, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

class GrippedResource(str, Enum):
    """Logical type of labware being transported."""

    MIDI = "midi"
    LID = "lid"
    PCR = "pcr"

    # -------- convenience --------
    def __str__(self) -> str:  # pragma: no‑cover – makes reprs nicer when debugging
        return self.value

    @classmethod
    def parse(cls, s: Union[str, "GrippedResource"]) -> "GrippedResource":
        """Case‑insensitive co‑ercion helper."""
        if isinstance(s, cls):
            return s
        s_normalised = str(s).strip().lower()
        for member in cls:
            if member.value == s_normalised or member.name.lower() == s_normalised:
                return member
        raise ValueError(f"Unknown GrippedResource: {s!r}")


class GripDirection(IntEnum):
    FRONT = 1
    RIGHT = 2
    BACK = 3
    LEFT = 4

# ---------------------------------------------------------------------------
# Parameter container
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class GripperParams:
    """All the user‑tunable parameters needed for either transport mode."""

    # ── parameters common to both iSWAP & CO‑RE gripper ────────────────────
    grip_width: float
    width_before: float
    grip_height: float
    #transport_mode: int  # 0 = plate only, 1 = lid only, 2 = plate + lid

    # ── iSWAP‑specific ─────────────────────────────────────────────────────
    grip_mode: int  # 0 = small side; 1 = large side (aka long side)
    inverse_grip: bool
    labware_orientation_get: int
    labware_orientation_place: int

    # ------------------------------------------------------------------
    # Formatting helpers – keep the ugly mapping code in *one* place.
    # ------------------------------------------------------------------

    def _complex_dict(self, orientation: int) -> Dict[str, float]:
        """Return the minimal *Complex* movement dict for ``move_plate``."""
        return {
            "retractDist": 0.0,
            "liftUpHeight": 20.0,
            "labwareOrientation": orientation,
        }

    # .................................................................

    def as_iswap_call(self) -> Tuple[int, Dict[str, float], Dict[str, float], Dict[str, Any]]:
        """Translate to the four blocks expected by ``HamiltonInterface.move_plate``.

        Returns
        -------
        inversion : int
            0 | 1 – passed via the *dedicated* ``inversion`` arg.
        cmplx_get : dict
            Provided via ``CmplxGetDict``.
        cmplx_place : dict
            Provided via ``CmplxPlaceDict``.
        more_opts : dict
            Passed as ``**more_options`` – *must* only contain keys that map
            one‑to‑one with the iSWAP command template.
        """
        inversion = 1 if self.inverse_grip else 0

        # Complex movement dictionaries – required if we want *any* custom
        # labware orientation (otherwise we clash with the library defaults).
        cmplx_get = self._complex_dict(self.labware_orientation_get)
        cmplx_place = self._complex_dict(self.labware_orientation_place)

        # Additional options that map directly to the ISWAP_GET/PLACE keyword
        # template.  (Names must *exactly* match those templates.)
        more_opts: Dict[str, Any] = {
            "gripMode": self.grip_mode,
            "gripWidth": self.grip_width,
            "widthBefore": self.width_before,
            "gripHeight": self.grip_height,
            #"transportMode": self.transport_mode, Don't use this parameter for now
        }
        return inversion, cmplx_get, cmplx_place, more_opts


# ---------------------------------------------------------------------------
# Master configuration tables (iSWAP)
# ---------------------------------------------------------------------------

_GRIPPER_CONFIGS: Dict[tuple[str, GripDirection], GripperParams] = {
    # MIDI plates
    ("midi", GripDirection.FRONT): GripperParams(124.5, 130.0, 8.0,  1, False, 3, 3),
    ("midi", GripDirection.RIGHT): GripperParams(80.0, 87.0, 8.0,  0, False, 4, 4),
    ("midi", GripDirection.BACK): GripperParams(124.5, 130.0, 8.0,  1, True, 1, 1),
    ("midi", GripDirection.LEFT): GripperParams(80.0, 87.0, 8.0,  0, True, 2, 2),

    # Lids
    ("lid", GripDirection.FRONT): GripperParams(126.0, 130.0, 5.0,  1, False, 3, 3),
    ("lid", GripDirection.RIGHT): GripperParams(85.3, 88.0, 5.0,  0, False, 4, 4),
    ("lid", GripDirection.BACK): GripperParams(126.0, 130.0, 5.0, 1,  True, 1, 1),
    ("lid", GripDirection.LEFT): GripperParams(85.3, 88.0, 5.0, 0, True, 2, 2),

    # PCR plates
    ("pcr", GripDirection.FRONT): GripperParams(126.0, 130.0, 7.0,  1, False, 3, 3),
    ("pcr", GripDirection.RIGHT): GripperParams(82.5, 85.5, 7.0,  0, False, 4, 4),
    ("pcr", GripDirection.BACK): GripperParams(126.0, 130.0, 7.0,  1, True, 1, 1),
    ("pcr", GripDirection.LEFT): GripperParams(82.5, 85.5, 7.0, 0, True, 2, 2),
}

# ---------------------------------------
# CO‑RE gripper fall‑back dimensions only
# ---------------------------------------

_CORE_GRIPPER_DIMENSIONS = {
    GrippedResource.MIDI: (79.0, 87.0),
    GrippedResource.LID: (85.3, 91.0),
    GrippedResource.PCR: (80.0, 86.0),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_core_gripper_params(
    *,
    resource_type: Union[Literal["midi", "lid", "pcr"], GrippedResource] = "midi",
    stack: bool,
) -> GripperParams:
    """Return minimal parameter‑set for a CO‑RE gripper operation."""
    rt = GrippedResource.parse(resource_type)
    grip_width, width_before = _CORE_GRIPPER_DIMENSIONS[rt]

    return GripperParams(
        grip_width=grip_width,
        width_before=width_before,
        grip_height=8.0 if stack else 15.0,
        #transport_mode=1 if rt is GrippedResource.LID else 0, Avoid using this parameter for now
        grip_mode=0,  # not used by CO‑RE gripper but required by dataclass
        inverse_grip=False,
        labware_orientation_get=1,
        labware_orientation_place=1,
    )


# ...........................................................................

def get_gripper_params(
    *,
    resource_type: Union[Literal["midi", "lid", "pcr"], GrippedResource],
    grip_direction: Optional[Union[int, GripDirection]] = None,
    iswap: bool = True,
    core_gripper: bool = False,
    stack: bool = False,
) -> GripperParams:
    """Resolve the correct parameter block for a given transport request."""
    rt = GrippedResource.parse(resource_type)

    if core_gripper:
        return get_core_gripper_params(resource_type=rt, stack=stack)

    # --- iSWAP path -------------------------------------------------------
    if not iswap:
        raise ValueError("Only iSWAP or core gripper modes are supported.")
    if grip_direction is None:
        raise ValueError("grip_direction must be supplied for iSWAP moves.")

    gd = GripDirection(int(grip_direction))
    try:
        return _GRIPPER_CONFIGS[(rt.value, gd)]
    except KeyError as exc:  # pragma: no‑cover
        raise ValueError(
            f"No configuration for resource_type={rt.value!r}, grip_direction={gd.name} ({int(gd)})."
        ) from exc


# ---------------------------------------------------------------------------
# High‑level wrapper – the *one* public function you call.
# ---------------------------------------------------------------------------

def transport_resource(
    ham_int: HamiltonInterface,
    source: Any,
    destination: Any,
    *,
    grip_direction: Optional[Union[int, GripDirection]] = None,
    resource_type: Union[Literal["midi", "lid", "pcr"], GrippedResource] = "midi",
    iswap: bool = False,
    core_gripper: bool = False,
    stack: bool = False,
) -> Any:
    """Move a plate / lid from *source* ➜ *destination* using preconfigured parameters for different
    labware types and grip directions. Exactly one of *iswap* or *core_gripper* **must** be ``True``.

    Parameters
    ----------
    ham_int
        Active ``HamiltonInterface`` instance.
    source, destination
        • *iSWAP*: ``DeckResource`` objects  
        • CO‑RE gripper: **str** sequence names.
    grip_direction
        Required for iSWAP, ignored for CO‑RE gripper.
    resource_type
        ``"midi" | "lid" | "pcr"`` (case‑insensitive) or a :class:`GrippedResource`.
    iswap, core_gripper
        Exactly one of these flags **must** be ``True``.
    stack
        When ``core_gripper`` is ``True`` set a lower *gripHeight* if stacking
        (i.e. loading onto an existing plate lid).
    """
    params = get_gripper_params(
        resource_type=resource_type,
        grip_direction=grip_direction,
        iswap=iswap,
        core_gripper=core_gripper,
        stack=stack,
    )

    # .....................................................................
    if iswap:
        if isinstance(source, Lid) and isinstance(destination, Lid):
            source = source.layout_name()
            destination = destination.layout_name()
            inversion, cmplx_get, cmplx_place, more_opts = params.as_iswap_call()
            return ham_int.move_by_seq(
                source,
                destination,
                CmplxGetDict=cmplx_get,
                CmplxPlaceDict=cmplx_place,
                inversion=inversion,
                **more_opts,
            )

        if isinstance(source, DeckResource) and isinstance(destination, DeckResource):
            inversion, cmplx_get, cmplx_place, more_opts = params.as_iswap_call()
            return ham_int.move_plate(
                source,
                destination,
                CmplxGetDict=cmplx_get,
                CmplxPlaceDict=cmplx_place,
                inversion=inversion,
                **more_opts,
            )
        
        # Elif both are strings
        elif isinstance(source, str) and isinstance(destination, str):
            inversion, cmplx_get, cmplx_place, more_opts = params.as_iswap_call()
            return ham_int.move_by_seq(source, 
                                       destination, 
                                       CmplxGetDict=cmplx_get,
                                       CmplxPlaceDict=cmplx_place,
                                       inversion=inversion,
                                       **more_opts,
                                       )
        
        else:
            raise TypeError("source & destination must be DeckResource objects or strings for iSWAP moves.")

    # .....................................................................
    if core_gripper:
        if isinstance(source, DeckResource) and isinstance(destination, DeckResource):
            # Check whether source and destination are both of the same type
            if type(source) != type(destination):
                raise Exception("Source is of type {} and destination is of type {}. " \
                "Both must be of the same type for CORE gripper movement".format(type(source), type(destination)))

            source = source.layout_name()
            destination = destination.layout_name()
        
        if not isinstance(source, str) or not isinstance(destination, str):
            raise Exception("Source and destination must be strings for CORE gripper movement")

        # ``lid`` operations are encoded by *transport_mode* == 1 in our params.
        return move_plate_using_gripper(
            ham_int,
            source,
            destination,
            gripHeight=params.grip_height,
            gripWidth=params.grip_width,
            openWidth=params.width_before,
            #lid=params.transport_mode == 1, Avoid using this for now
        )

    # Should never get here – both modes mutually exclusive
    raise AssertionError("Either iSWAP or core_gripper must be selected.")



if __name__ == "__main__":
    with HamiltonInterface(windowed=True, simulating=False) as ham_int:
        ham_int.initialize()
        # Example: core-gripper move with a lid, front grip
        transport_resource(
            ham_int,
            "HSP_Pipette2",
            "HHS2_HSP",
            grip_direction=GripDirection.FRONT,
            resource_type=GrippedResource.LID,
            core_gripper=True
        )








