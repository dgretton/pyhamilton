
import os
from pyhamilton import (HamiltonInterface, hhs_create_usb_device, hhs_set_simulation, normal_logging, odtc_execute_protocol, 
                        odtc_get_status, odtc_open_door, odtc_close_door, Plate96, Tip96, TrackedTips,
                        hhs_start_shaker, hhs_stop_shaker, layout_item, LayoutManager, Reservoir60mL,
                        StackedResources)
                 
from pyhamilton_advanced import (shear_plate_96, pip_mix, mix_plate, double_aspirate_supernatant_96,
                                 transfer_96, multi_dispense, pip_transfer, ethanol_wash, multi_dispense,
                                 transport_resource, GripDirection, GrippedResource, GripperParams)


import time

def magnetic_bead_cleanup():
    pass

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

MIDI_Pipette = layout_item(lmgr, Plate96, 'MIDI_Pipette')
HHS5_MIDI = layout_item(lmgr, Plate96, 'HHS5_MIDI')
MIDI_OnMagnet = layout_item(lmgr, Plate96, 'MIDI_OnMagnet')
LiquidWaste = layout_item(lmgr, Plate96, 'LiquidWaste_MPH')

#Ethanol80 = layout_item(lmgr, Plate96, 'Ethanol80')

#RGT_50 = layout_item(lmgr, Reservoir60mL, 'RGT_50')
#Ethanol80 = [(RGT_50, 1)] # Position 1, 2mL tube
#QIAseq_Beads = [(RGT_50, 5)] # Position 5, 2mL tube
#Nuclease_Free_Water_positions = [(RGT_50, 7)] # Position 10, 2mL tube

HSP_Stack = StackedResources.from_prefix(
                        tracker_id="HSP_L",
                        prefix="HSP_L",
                        count=4,
                        reset=True)

Lid_Stack = StackedResources.from_prefix(
                        tracker_id="LID_L",
                        prefix="LID_L",
                        count=2,
                        reset=True)

MIDI_Stack = StackedResources.from_prefix(
                        tracker_id="MIDI_L",
                        prefix="MIDI_L",
                        count=4,
                        reset=True)

tracked_tips_50uL = TrackedTips.from_prefix(
                        tracker_id="TIP_50uLF_L",
                        volume_capacity=50,
                        prefix="TIP_50uLF_L",
                        count=8,
                        tip_type=Tip96, 
                        lmgr=lmgr)


tracked_tips_300uL = TrackedTips.from_prefix(
                        tracker_id="STF_L",
                        volume_capacity=300,
                        prefix="STF_L",
                        count=8,
                        tip_type=Tip96,
                        lmgr=lmgr)

tracked_tips_1000uL = TrackedTips.from_prefix(
                        tracker_id="HTF_L",
                        volume_capacity=1000,
                        prefix="HTF_L",
                        count=2,
                        tip_type=Tip96,
                        lmgr=lmgr)


num_samples = 24

class HHS:

    def __init__(self, node, layout_name):
        self.node = node
        self.layout_name = layout_name


HHS_MIDI_1 = HHS(node=4, layout_name="HHS4_MIDI")
HHS_MIDI_2 = HHS(node=5, layout_name="HHS5_MIDI")
HHS_MIDI_3 = HHS(node=3, layout_name="HHS3_MIDI")

HHS_HSP_1 = HHS(node=1, layout_name="HHS1_HSP")
HHS_HSP_2 = HHS(node=2, layout_name="HHS2_HSP")


def initialize_hhs(ham_int, simulating):
        
        hhs_set_simulation(ham_int, simulating)  # Set simulation mode if needed
        for node in range(1,5):
            hhs_create_usb_device(ham_int, node)
            print(f"Created USB device for ML_STAR {node}")

if __name__ == "__main__":
    with HamiltonInterface(windowed=True, simulating=False) as ham_int:
        # Magnetic bead cleanup workflow (assuming beads already bound to samples)
        # Starting with samples + beads already mixed in MIDI_Pipette

        ham_int.initialize()  # Initialize the HamiltonInterface
        initialize_hhs(ham_int, simulating=False)  # Initialize the HHS modules

        # Step 1: Transport to shaker for initial mixing
        transport_resource(ham_int, MIDI_Pipette.layout_name(), HHS_MIDI_1.layout_name, 
                        resource_type=GrippedResource.MIDI, core_gripper=True)
    
        # Step 2: Shake to ensure proper bead binding
        hhs_start_shaker(ham_int, HHS_MIDI_1.node, shaking_speed=1000)  # 1000 RPM for 30 seconds
        time.sleep(30)
        hhs_stop_shaker(ham_int, HHS_MIDI_1.node)

        # Step 3: Transport to magnetic separation
        transport_resource(ham_int, HHS_MIDI_1.layout_name, 'MIDI_OnMagnet', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

"""         # Step 4: Wait for magnetic separation
        time.sleep(60)  # Allow beads to settle

        # Step 5: Remove supernatant (unbound material)
        supernatant_removal_volume = 50  # Adjust as needed
        double_aspirate_supernatant_96(ham_int, tracked_tips_300uL, MIDI_OnMagnet, LiquidWaste,
                                    supernatant_removal_volume,
                                    liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                                    aspirate_height_from_bottom=1)

        # Step 6: First ethanol wash
        # Move back to shaker for wash
        transport_resource(ham_int, 'MIDI_OnMagnet', 'HHS5_MIDI', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        # Add ethanol
        hhs5_positions = [(HHS5_MIDI, idx) for idx in range(num_samples)]
        post_shear_etoh_wash_volume = 200  # Adjust as needed
        pip_transfer(ham_int, tracked_tips_300uL, Ethanol80, hhs5_positions, 
                [post_shear_etoh_wash_volume] * num_samples,
                liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                aspirate_height_from_bottom=1, dispense_height_from_bottom=1)

        # Shake with ethanol
        hhs_start_shaker(ham_int, 'HHS5_MIDI', 1000, 30)
        time.sleep(30)
        hhs_stop_shaker(ham_int, 'HHS5_MIDI')

        # Back to magnet
        transport_resource(ham_int, 'HHS5_MIDI', 'MIDI_OnMagnet', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        # Wait for separation
        time.sleep(60)

        # Remove ethanol supernatant
        double_aspirate_supernatant_96(ham_int, tracked_tips_300uL, magnet_positions, 
                                    post_shear_etoh_wash_volume + 10,  # Remove slightly more
                                    liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                                    aspirate_height_from_bottom=1)

        # Step 7: Second ethanol wash (repeat of step 6)
        transport_resource(ham_int, 'MIDI_OnMagnet', 'HHS5_MIDI', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        pip_transfer(ham_int, tracked_tips_300uL, Ethanol80, hhs5_positions, 
                [post_shear_etoh_wash_volume] * num_samples,
                liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                aspirate_height_from_bottom=1, dispense_height_from_bottom=1)

        hhs_start_shaker(ham_int, 'HHS5_MIDI', 1000, 30)
        time.sleep(30)
        hhs_stop_shaker(ham_int, 'HHS5_MIDI')

        transport_resource(ham_int, 'HHS5_MIDI', 'MIDI_OnMagnet', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        time.sleep(60)

        double_aspirate_supernatant_96(ham_int, tracked_tips_300uL, magnet_positions, 
                                    post_shear_etoh_wash_volume + 10,
                                    liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                                    aspirate_height_from_bottom=1)

        # Step 8: Air dry beads
        transport_resource(ham_int, 'MIDI_OnMagnet', 'HHS5_MIDI', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        time.sleep(300)  # Air dry for 5 minutes

        # Step 9: Elution
        # Add elution buffer
        pip_transfer(ham_int, tracked_tips_300uL, NucleaseFreeWater, hhs5_positions, 
                [post_shear_elution_buffer_volume] * num_samples,
                liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                aspirate_height_from_bottom=1, dispense_height_from_bottom=1)

        # Mix with elution buffer
        pip_mix(ham_int, tracked_tips_300uL, hhs5_positions, post_shear_elution_buffer_volume, 
            mix_cycles=10, liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
            mix_height_from_bottom=1)

        # Shake for elution
        hhs_start_shaker(ham_int, 'HHS5_MIDI', 1000, 30)
        time.sleep(30)
        hhs_stop_shaker(ham_int, 'HHS5_MIDI')

        # Final magnetic separation
        transport_resource(ham_int, 'HHS5_MIDI', 'MIDI_OnMagnet', 
                        grip_direction=GripDirection.FRONT, resource_type=GrippedResource.MIDI, 
                        core_gripper=True)

        time.sleep(60)

        # Step 10: Collect eluted samples
        # Get fresh plate for clean samples
        transport_resource(ham_int, HSP_Stack.fetch_next(), 'HSP_Pipette2', 
                        resource_type=GrippedResource.PCR, core_gripper=True)

        hsp_positions = [(HSP_Pipette2, idx) for idx in range(num_samples)]

        # Transfer eluted samples to clean plate
        transfer_96(ham_int, tracked_tips_300uL, magnet_positions, hsp_positions, 
                [post_shear_elution_volume] * num_samples,
                liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty', 
                aspirate_height_from_bottom=1, dispense_height_from_bottom=1)

        # Step 11: Cleanup - move waste plate
        transport_resource(ham_int, 'MIDI_OnMagnet', 'MIDI_Waste', 
                        resource_type=GrippedResource.MIDI, core_gripper=True)
 """