from pyhamilton import (HamiltonInterface, LayoutManager, Reservoir60mL, TrackedTips, StackedResources, Tip96, Plate96, layout_item,
                        normal_logging)

import os

from pyhamilton_advanced import shear_plate_96, double_aspirate_supernatant_96, ethanol_wash, pip_transfer

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

# Perhaps import stack management

MIDI_OffMagnet = layout_item(lmgr, Plate96, 'MIDI_Pipette')  # Assuming this is defined elsewhere in the layout
MagBeads_Container = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0001')
ER_Mix = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0002')
EDTA = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0003')

tips = tip_tracker_50uL = TrackedTips.from_prefix(
    tracker_id="TIP_50uLF_L",
    prefix="TIP_50uLF_L",
    volume_capacity=50,
    count=8,
    tip_type=Tip96,
    lmgr=lmgr,
    reset=True  # Reset the tracker state
)


# This seems to mostly work. We don't yet query the user for refilling troughs or try to accumulate residual volumes.
# 50 seconds between dispense cycles
with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()
    normal_logging(ham_int, os.getcwd())

    aspiration_positions = [(MagBeads_Container, idx) for idx in range(8)]
    dispense_positions = [(MIDI_OffMagnet, idx) for idx in range(96)]
    volumes = [50]*96

    pip_transfer(ham_int, tips, aspiration_positions, dispense_positions, volumes, 
                 liquid_class = 'Tip_50ulFilter_Water_DispenseSurface_Empty', aspirate_height_from_bottom=1,
                 dispense_height_from_bottom=1)