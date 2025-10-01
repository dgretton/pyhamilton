from pyhamilton import (HamiltonInterface, LayoutManager, Plate96, Tip96, hhs_set_simulation, move_plate_using_gripper, 
                        hhs_create_star_device, hhs_create_usb_device, hhs_set_temp_param, 
                        hhs_start_temp_ctrl, hhs_stop_temp_ctrl, hhs_start_shaker, hhs_stop_shaker, TrackedTips, 
                        StackedResources, Reservoir60mL, FalconCarrier24, normal_logging, layout_item)


from pyhamilton_advanced import (shear_plate_96, double_aspirate_supernatant_96, pip_mix, mix_plate, 
                                 transfer_96, multi_dispense, pip_transfer, ethanol_wash, multi_dispense,
                                 transport_resource, GripDirection,GrippedResource,GripperParams)
import time
import os


# DNA Shearing
lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

MIDI_OnMagnet = layout_item(lmgr, Plate96, 'MIDI_OnMagnet')
MIDI_OffMagnet = layout_item(lmgr, Plate96, 'MIDI_Pipette')
LiquidWaste = layout_item(lmgr, Plate96, 'LiquidWaste')
EthanolReservoir = layout_item(lmgr, Plate96, 'RGT_Ethanol')
ConsumableWaste = layout_item(lmgr, Plate96, 'MIDI_Waste')

HSP_Adapters = layout_item(lmgr, Plate96, 'HSP_Adapters')

HSP_Plate = layout_item(lmgr, Plate96, 'HSP_Pipette')

HSP_Plate_2 = layout_item(lmgr, Plate96, 'HSP_Pipette2')

MagBeads_Container = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0001')
magbead_positions = [(MagBeads_Container, i) for i in range(8)]  # Assuming 8 positions for beads

ElutionBuffer_Container = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0002')
post_shear_elution_buffer_positions = [(ElutionBuffer_Container, i) for i in range(8)]  # Assuming 8 positions for beads

CPAC_Reagent_Plate = layout_item(lmgr, Plate96, 'CPAC_HSP_0001')
ER_Mix_positions = [(CPAC_Reagent_Plate, i) for i in range(8)]  # Assuming 8 positions for ER Mix
RGT_LigMix_positions = [(CPAC_Reagent_Plate, i) for i in range(8,16)]  # Plated in positions 8 to 15

EDTA = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0003')

PoolingTubes = layout_item(lmgr, FalconCarrier24, 'SMP_CAR_24_15x75_A00_0001')

HSP_Stack = StackedResources.from_prefix(
                        tracker_id="HSP_L",
                        prefix="HSP_L",
                        count=8)

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

sample_volume = 50 # Adjust as needed, get user input
magbead_mix_volume = 1000
post_shear_magbead_volume = sample_volume
first_supernatant_removal_volume = sample_volume * 2  # Assuming 20% more than sample volume
supernatant_removal_volume = sample_volume + post_shear_magbead_volume
m1_mix_volume = min(sample_volume*1.6, 1000)
post_shear_etoh_wash_volume = 200
post_shear_elution_buffer_volume = 30
post_shear_elution_volume = 25.5  # Volume for shear elution

if sample_volume > 130:
    pass
else:
    pass


# PyHamilton To-dos:
# - Implement Stacking logic (done)
# - HHS integration (done)
# - Autoloader integration (testing)
# - ODTC integration (external to Venus)
# - Get liquid class data from .NET/ CLR (done)
# - Implement reagent and consumables projection

# - CPAC integration (external to Venus)
# - ODTC integration (external to Venus)

# Add volume calculations
# Add logging and recording of liquid heights/ volumes from cLLD

def estimate_tip_consumption(num_samples: int):
    '''
    I think we can run the method in simulation to make an estimate?
    '''
    pass

num_samples = 96  # Example number of samples, adjust as needed
tips_needed = estimate_tip_consumption(num_samples)

def initialize(simulation=True):
    with HamiltonInterface(simulating=False, server_mode=True, windowed=True, persistent = True) as ham_int:
        ham_int.initialize()
        normal_logging(ham_int, os.getcwd())
        
        hhs_set_simulation(ham_int, 1)  # Set simulation mode if needed
        hhs1 = hhs_create_usb_device(ham_int, 'ML_STAR', 1)
        hhs2 = hhs_create_usb_device(ham_int, 'ML_STAR', 1)
        hhs3 = hhs_create_usb_device(ham_int, 'ML_STAR', 1)



def BeadCleanup(num_samples, sample_volume, starting_from=0):
    with HamiltonInterface(simulating=False,server_mode=True, windowed=True, persistent=True) as ham_int:

        ham_int.initialize()
        
        # Add magbeads to MIDI Off Magnet plate
        magbead_positions = [(MagBeads_Container, i) for i in range(8)]
        MIDI_OffMagnet_positions = [(MIDI_OffMagnet, i) for i in range(num_samples)]
        
        pip_transfer(ham_int, tracked_tips_300uL, magbead_positions, MIDI_OffMagnet_positions,
                     [post_shear_magbead_volume] * num_samples, liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty',
                     aspirate_height_from_bottom=1, dispense_height_from_bottom=1)

        # Transport MIDI Off Magnet plate to HHS5_MIDI
        transport_resource(ham_int, MIDI_OffMagnet.layout_name(), 'HHS5_MIDI', resource_type=GrippedResource.MIDI, core_gripper=True)

        # Shake HHS
        hhs_start_shaker(ham_int, 1, 1000, 10)  # Start shaker at 1000 RPM for 10 seconds
        time.sleep(10)  # Wait for shaking to complete
        hhs_stop_shaker(ham_int, 1)  # Stop shaker

        # Transport HHS5_MIDI to MIDI On Magnet
        transport_resource(ham_int, 1, MIDI_OnMagnet.layout_name(), resource_type=GrippedResource.MIDI, core_gripper=True)



if __name__ == "__main__":
    num_samples = 96