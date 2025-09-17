from pyhamilton import (HamiltonInterface, LayoutManager, Reservoir60mL, TrackedTips, StackedResources, Tip96, Plate96, layout_item,
                        normal_logging, hhs_create_star_device, hhs_create_usb_device,
                        hhs_set_temp_param, hhs_start_temp_ctrl, hhs_stop_temp_ctrl, hhs_set_simulation,hhs_get_temp,
                        hhs_start_shaker, hhs_stop_shaker)

import os
import time
from pyhamilton_advanced import shear_plate_96, double_aspirate_supernatant_96, ethanol_wash, pip_transfer, mix_plate

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

class HHS:

    def __init__(self, node, sequence):
        self.node = node
        self._sequence = sequence

    def layout_name(self):
        return self._sequence
    
    def node(self):
        return self.node

HHS_MIDI_1 = HHS(node=4, sequence="HHS4_MIDI")
HHS_MIDI_2 = HHS(node=5, sequence="HHS5_MIDI")
HHS_MIDI_3 = HHS(node=3, sequence="HHS3_MIDI")

HHS_HSP_1 = HHS(node=1, sequence="HHS1_HSP")
HHS_HSP_2 = HHS(node=2, sequence="HHS2_HSP")


def initialize_hhs(simulation):
    with HamiltonInterface(windowed=True, simulating=False) as ham_int:
        ham_int.initialize()
        normal_logging(ham_int, os.getcwd())
        
        hhs_set_simulation(ham_int, 0)  # Set simulation mode if needed
        for node in range(1,5):
            hhs_create_usb_device(ham_int, node)
            print(f"Created USB device for ML_STAR {node}")
            print("Shaking node for 5 seconds")
            hhs_start_shaker(ham_int, node, 1000)
            time.sleep(5)
            hhs_stop_shaker(ham_int, node)


# This works
with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()
    normal_logging(ham_int, os.getcwd())
    
    initialize_hhs(simulation=False)