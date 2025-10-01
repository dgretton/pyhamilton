from pyhamilton import (HamiltonInterface, LayoutManager, Reservoir60mL, TrackedTips, StackedResources, Tip96, Plate96, layout_item,
                        normal_logging)

import os

from pyhamilton_advanced import transfer_96

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

# Perhaps import stack management

MIDI_OffMagnet = layout_item(lmgr, Plate96, 'MIDI_Pipette')  # Assuming this is defined elsewhere in the layout
MIDI_OnMagnet = layout_item(lmgr, Plate96, 'MIDI_OnMagnet')  # Assuming this is defined elsewhere in the layout

MagBeads_Container = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0001')
ER_Mix = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0002')
EDTA = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0003')

tips = tip_tracker_50uL = TrackedTips.from_prefix(
    tracker_id="TIP_50uLF_L",
    prefix="TIP_50uLF_L",
    count=8,
    tip_type=Tip96,
    lmgr=lmgr,
    reset=True  # Reset the tracker state
)


# This works
with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()
    normal_logging(ham_int, os.getcwd())


    transfer_96(ham_int, tips, MIDI_OffMagnet, MIDI_OnMagnet, 20, liquid_class='Tip_50ulFilter_Water_DispenseSurface_Empty')