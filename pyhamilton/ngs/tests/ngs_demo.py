from pyhamilton import (HamiltonInterface, LayoutManager, Reservoir60mL, TrackedTips, StackedResources, Tip96, Plate96, layout_item,
                        normal_logging, tracked_tip_pick_up, tracked_tip_pick_up_96)

import os

from pyhamilton_advanced import (shear_plate_96, double_aspirate_supernatant_96, ethanol_wash, pip_transfer, multi_dispense, 
                                    build_dispense_batches, batch_columnwise_positions, split_aspiration_positions)

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

MIDI_OffMagnet = layout_item(lmgr, Plate96, 'MIDI_Pipette')  # Assuming this is defined elsewhere in the layout

tips = tip_tracker_50uL = TrackedTips.from_prefix(
    tracker_id="TIP_50uLF_L",
    prefix="TIP_50uLF_L",
    volume_capacity=50,
    count=8,
    tip_type=Tip96,
    lmgr=lmgr,
    reset=True  # Reset the tracker state
)

with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()
    normal_logging(ham_int, os.getcwd())

    tracked_tip_pick_up_96(ham_int, tip_tracker_50uL)