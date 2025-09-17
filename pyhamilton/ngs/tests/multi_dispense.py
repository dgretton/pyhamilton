from pyhamilton import (HamiltonInterface, LayoutManager, Reservoir60mL, TrackedTips, StackedResources, Tip96, Plate96, layout_item,
                        normal_logging)

import os

from pyhamilton_advanced import (shear_plate_96, double_aspirate_supernatant_96, ethanol_wash, pip_transfer, multi_dispense, 
                                    build_dispense_batches, batch_columnwise_positions, split_aspiration_positions)

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

# Perhaps import stack management

MIDI_OffMagnet = layout_item(lmgr, Plate96, 'MIDI_Pipette')  # Assuming this is defined elsewhere in the layout
MagBeads_Container = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0001')
ER_Mix = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0002')
EDTA = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0003')

tips = tip_tracker_300uL = TrackedTips.from_prefix(
    tracker_id="STF_L",
    prefix="STF_L",
    volume_capacity=300,
    count=3,
    tip_type=Tip96,
    lmgr=lmgr,
    reset=True  # Reset the tracker state
)


def condense_volumes(lst, max_volume):
    total = sum(lst)
    return [max_volume] * (total // max_volume) + ([total % max_volume] if 0 < total % max_volume >= min(lst) else [])


#dispense_positions = [(MIDI_OffMagnet, idx) for idx in range(96)]
#dispense_volumes = [50]*96  # Assuming 50 uL for each sample

#aspirate_positions = [(MagBeads_Container, idx) for idx in range(8)]

#aspirate_volumes = condense_volumes(dispense_volumes, 200)
#column_dispense_positions = batch_columnwise_positions(dispense_positions) # Batch dispense positions into columns of 8
#column_volumes_list = batch_columnwise_positions(dispense_volumes)

#column_aspiration_positions = batch_columnwise_positions(aspirate_positions) # Batch aspiration positions into columns of 8
#column_aspiration_volumes_list = batch_columnwise_positions(aspirate_volumes)

#column_aspiration_volumes = [300]*8
#batched_vols = build_dispense_batches(column_aspiration_volumes, column_dispense_positions, column_volumes_list)
#print("Batched Volumes:", batched_vols)

# Account for air transport volume in volume balance on the tips

# Automated liquid class detection with integrated scale
# TADM tool to pull up specific data for commands
# Resource loading and error-proofing user inputs
# Record every selection that the user makes in prompt windows
# Error handling/ recovery


# User prompts
## Radio buttons for step selection (start and stop)
## Input a worklist with list of samples
## Resource use calculations
## Visibility parameters for loading resources
## Specific tubes/ reagents on deck changing during run
## Variable start and stop selection


# step_list = [function_1, function_2, function_3, ...]
# for step in range(2,5):
    # step_list[step]()
# Valid ranges, decision branching based on sample type
# Start and stop points
# User prompts related to steps chosen and relevant instruments
# ODTC dynamic parameterization
# Intermediate plating patterns and logic
# Reagent plate creation specify tubes and volumes, reagent plate sequence specification
# Time speedup for reagent plating (volume excess usage tradeoff compared to timing)

# Firmware discussion with example
## Engineer firmware dispense command to prevent channel retract
## Firmware engine for custom commands (at what Z do you start, at what Z do you end)
## Mix by overturn
## Record that, go to bottom a configurable amount, aspirate a certain volume from there, go up to height and mix

# Data tracking for trouble shooting
## cLLD for height tracking
## TADM
## If you are dispensing and you know what the liquid height should be, go to a fixed height
## Aspirate from reagent tube with cLLD and dispense to fixed height in sample container
## Reload tips while ODTC is working and general pre-defined tip reload prompts

# Dead volume information management

# Loading and user prompts, specific kit information <- top priority for NGS internal 
# Counterparts in EMEA convince these/ train how to use Python

# Combined multi aspirate multi dispense for target volumes over the tip capacity in a single container

# Start with known liquid classes that work well and pulling from database, good starting points for liquid class selection
# Automated liquid class construction, correction curves for volumes
# Predefined heights and other parameters for specific operations like bead aspiration similar to how the transport controller works, override potential for users

# Pure Python tasks: randomizer, statistics, arbitrary data formats (xlsx, csv, JSON)
# Python library for reading different data formats

# Add tip support functionality (channel patterns, columnwise sequence inverting)''

# Highlight carrier X to simplify loading in loading dialog, other deck visibility functions (hxx 3D file, .x file)

# Pre and post dispense with multidispense to enhance accuracy

with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()
    normal_logging(ham_int, os.getcwd())
    aspiration_positions = [(MagBeads_Container, idx) for idx in range(8)]
    dispense_positions = [(MIDI_OffMagnet, idx) for idx in range(96)]
    volumes = [50]*96
#
    multi_dispense(ham_int, tips, aspiration_positions, dispense_positions, volumes, 
                 liquid_class = 'StandardVolumeFilter_Water_DispenseJet_Part')
    
    