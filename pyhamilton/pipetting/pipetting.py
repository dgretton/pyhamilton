from .trough_manager import manage_multiple_troughs
from pyhamilton_advanced.consumables import tracked_volume_aspirate, tracked_volume_aspirate_96
import time
from pyhamilton import (HamiltonInterface, LayoutManager, StackedResources, TrackedTips, 
                        tracked_tip_pick_up, tracked_tip_pick_up_96, get_liquid_class_volume, DeckResource, 
                        TipSupportTracker, tip_support_pickup_columns)

from typing import List, Tuple, Iterable, List


def prewet_tips(ham_int, tip_type, dispense_mode):
    pass

def condense_volumes(lst, vol, max_volume):
    total = sum(lst)
    return [max_volume] * (total // max_volume) + ([total % max_volume] if 0 < total % max_volume >= vol else [])


def get_fitting_dispense_positions(asp_vols, disp_vols, disp_pos):
    running_total = [0] * len(asp_vols)
    result = []

    for pos_block, vol_block in zip(disp_pos, disp_vols):
        new_total = [a + b for a, b in zip(running_total, vol_block)]
        if all(v <= a for v, a in zip(new_total, asp_vols)):
            running_total = new_total
            result.append((pos_block, vol_block))
        else:
            break

    return result

# Now build full batch list
def build_dispense_batches(aspiration_volumes, all_dispense_positions, all_dispense_volumes):
    '''
    Batch together multiple dispenses from a single aspiration based on tip volume capacity.

    Returns:
        List of tuples: (batch, aspiration_volumes)
        where batch = list of (positions, volumes)
              aspiration_volumes = list of total volumes needed per tip
    '''
    batches = []

    disp_vols = all_dispense_volumes[:]
    disp_pos  = all_dispense_positions[:]

    while disp_vols:
        batch_positions = get_fitting_dispense_positions(aspiration_volumes, disp_vols, disp_pos)
        if not batch_positions:
            raise ValueError("Remaining dispenses exceed available aspiration volume. Check tip capacity.")

        n = len(batch_positions)
        batch = batch_positions

        # Calculate how much volume per tip will be needed for this batch
        num_tips = len(batch[0][1])  # assuming 8 tips
        batch_asp_vols = [0] * num_tips
        for _, column_volumes in batch:
            for i in range(num_tips):
                batch_asp_vols[i] += column_volumes[i]

        batches.append((batch, batch_asp_vols))

        disp_vols = disp_vols[n:]
        disp_pos  = disp_pos[n:]

    return batches

def distribute_positions_to_channel_ops(positions_to_distribute, reference_positions):
    '''
    Expand the larger list of positions into a list of lists so we can sequentially operate on those positions
    using each of the channels. Use when there are <8 positions to aspirate or dispense from.

    Example:
    aspiration_positions = [(plate, 0), (plate, 1)]
    dispense_positions = [(plate, 0), (plate, 1), (plate, 2), (plate, 3), (plate, 4), (plate, 5), (plate, 6), (plate, 7)]

    Output:
    [
        [(plate, 0), (plate, 1), None, None, None, None, None, None],
        [None, None, (plate, 0), (plate, 1), None, None, None, None],
        [None, None, None, None, (plate, 0), (plate, 1), None, None],
        [None, None, None, None, None, None, (plate, 0), (plate, 1)],
    ]
    '''
    # Sanity check: the set of positions to distribute must not exceed the total channel slots
    if len(positions_to_distribute) > len(reference_positions):
        raise ValueError("Positions to distribute must be less than or equal to reference positions")

    num_reference_positions = len(reference_positions)        # e.g. 8 channels on a pipette head
    num_positions_to_distribute = len(positions_to_distribute) # e.g. 2 wells to transfer
    result = []

    # Slide the smaller set across the larger channel frame in steps
    # Step size = number of positions to distribute (so each group is aligned together)
    for i in range(0, num_reference_positions, num_positions_to_distribute):
        # Start with a "blank" row (all channels set to None)
        row = [None] * num_reference_positions

        # Place the positions into this row, offset by i
        for j, pos in enumerate(positions_to_distribute):
            if i + j < num_reference_positions:  # don’t go past the channel frame
                row[i + j] = pos

        # Add this row to the list of operation sets
        result.append(row)

    return result

def print_transfers(source_wells, destination_wells, vols):
    for source_well_tuple, destination_well_tuple, destination_vol in zip(source_wells, destination_wells, vols):
        if destination_well_tuple:
            dest_plate, dest_well_idx = destination_well_tuple
        else:
            dest_plate, dest_well_idx = None, None
                    
        source_plate, source_well_idx = source_well_tuple
        dest_plate_name = dest_plate.layout_name()
        source_plate_name = source_plate.layout_name()
        print("Dispensing " + str(destination_vol) + " from " + str(source_plate_name) + " well " + str(source_well_idx) + " to " + str(dest_plate_name) + " well " + str(dest_well_idx))
    print("\n")


def batch_columnwise_positions(positions):
    '''
    Convert a list into a list of lists where each sublist is length 8 or less
    '''
    return [positions[i:i + 8] for i in range(0, len(positions), 8)]

def split_volumes_by_max_volume(volumes, max_volume):
    result = []
    remaining = volumes[:]
    
    while any(v > 0 for v in remaining):
        current = []
        for i, vol in enumerate(remaining):
            if vol > 0:
                use = min(vol, max_volume)
                current.append(use)
                remaining[i] -= use
            else:
                current.append(0)
        result.append(current)
    
    return result

def set_parallel_nones(positions, reference):
    '''
    Set None values in the positions list to match the reference list.
    '''
    # Copy the original positions to avoid modifying the input
    modified_positions = positions.copy()
    for i, ref in enumerate(reference):
        if ref is None:
            modified_positions[i] = None
    return modified_positions

def pip_transfer(ham_int: HamiltonInterface, tips: List[Tuple[DeckResource, int]] | TrackedTips, source_positions: List[Tuple[DeckResource, int]], 
                    dispense_positions: List[Tuple[DeckResource, int]], volumes: List[float], liquid_class: str, prewet_cycles=0,
                    mix_cycles=0, prewet_volume=0, vol_mix_dispense=0, aspiration_height=0,
                    dispense_height=0, tip_exchange_during_transfer=True,
                    liquid_following_aspiration=False, liquid_following_dispense=False):
    '''
    Transfer liquid from source positions to dispense positions using pipetting. Handles pipetting logic for
    unmatched lengths of source and dispense positions.

    Arguments:
    - ham_int: HamiltonInterface instance
    - tips: List of tuples (DeckResource, int) or TrackedTips instance
    - source_positions: List of tuples (DeckResource, int) for aspiration positions

        Example: [ (source_plate, 1), (source_plate, 2), (source_plate, 3)... ]

    - dispense_positions: List of tuples (DeckResource, int) for dispense positions

        Example: [ (dest_plate, 1), (dest_plate, 2), (dest_plate, 3)... ]

    - volumes: List of volumes to dispense (should be matched to dispense_positions)
    '''


    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    if max(volumes) > liquid_class_vol_capacity:
        raise ValueError(f"Volume exceeds tip capacity: {max(volumes)} > {liquid_class_vol_capacity}")

    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")


    if len(source_positions) > 8:
        raise ValueError("Source positions cannot exceed 8 with single aspiration.")

    aspirate_capacitative_LLD = 5 if aspiration_height == 0 else 0

    total_volume_needed = 0 # Calculate total volume needed for the transfer
    performed_additional_volume_transfer = False
    #if aspirate_capacitative_LLD != 0:
    #    troughs, performed_additional_volume_transfer = manage_multiple_troughs(ham_int, source_positions, total_volume_needed, liquid_class, 0, 0, check_volumes=True)

    aspirate_mode = 2 if performed_additional_volume_transfer else 0

    column_dispense_positions = batch_columnwise_positions(dispense_positions) # Batch dispense positions into lists of length eight
    column_volumes_list = batch_columnwise_positions(volumes) # Batch volumes into lists of length eight

    for column, column_volumes in zip(column_dispense_positions, column_volumes_list):
        if isinstance(tips, TrackedTips):
            num_tips = len([pos for pos in column if pos is not None])
            tracked_tip_pick_up(ham_int, tips, num_tips)
        else:
            ham_int.tip_pick_up(tips)

        aspiration_positions = distribute_positions_to_channel_ops(source_positions, column) # Aspirate sequentially because container has <8 positions
        for positions in aspiration_positions:
            vols = set_parallel_nones(column_volumes, positions)
            response = tracked_volume_aspirate(ham_int, positions, vols, liquidClass=liquid_class,
                                    mixCycles=0, mixVolume=0,
                                    liquidHeight=aspiration_height,
                                    capacitiveLLD=aspirate_capacitative_LLD, aspirateMode=aspirate_mode,
                                    submergeDepth=2)

            aspirate_heights = response.liquidHeights

        dispense_capacitative_LLD = 2 if dispense_height == 0 else 0
        response = ham_int.dispense(column, column_volumes, liquidClass=liquid_class, 
                                    mixCycles=mix_cycles, mixVolume=vol_mix_dispense,
                                    liquidHeight=dispense_height,
                                    capacitiveLLD=dispense_capacitative_LLD,
                                    liquidFollowing=liquid_following_dispense)
        
        dispense_heights = response.liquidHeights

        ham_int.tip_eject()

def pip_pool(ham_int: HamiltonInterface, tips: List[Tuple[DeckResource, int]] | TrackedTips, source_positions: List[Tuple[DeckResource, int]], 
                    dispense_positions: List[Tuple[DeckResource, int]], volumes: List[float], liquid_class: str, prewet_cycles=0,
                    mix_cycles=0, prewet_volume=0, vol_mix_dispense=0, aspiration_height=0,
                    dispense_height=0, tip_exchange_during_transfer=True,
                    liquid_following_aspiration=False, liquid_following_dispense=False):
    '''
    Transfer liquid from source positions to dispense positions using pipetting. Handles pipetting logic for
    unmatched lengths of source and dispense positions.

    Arguments:
    - ham_int: HamiltonInterface instance
    - tips: List of tuples (DeckResource, int) or TrackedTips instance
    - source_positions: List of tuples (DeckResource, int) for aspiration positions

        Example: [ (source_plate, 1), (source_plate, 2), (source_plate, 3)... ]

    - dispense_positions: List of tuples (DeckResource, int) for dispense positions

        Example: [ (dest_plate, 1), (dest_plate, 2), (dest_plate, 3)... ]

    - volumes: List of volumes to dispense (should be matched to dispense_positions)
    '''


    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    if max(volumes) > liquid_class_vol_capacity:
        raise ValueError(f"Volume exceeds tip capacity: {max(volumes)} > {liquid_class_vol_capacity}")

    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")


    if len(dispense_positions) > 8:
        raise ValueError("Dispense positions cannot exceed 8 with single aspiration.")

    aspirate_capacitative_LLD = 5 if aspiration_height == 0 else 0

    column_aspirate_positions = batch_columnwise_positions(source_positions) # Batch source positions into lists of length eight
    column_volumes_list = batch_columnwise_positions(volumes) # Batch volumes into lists of length eight

    for column, column_volumes in zip(column_aspirate_positions, column_volumes_list):
        if isinstance(tips, TrackedTips):
            num_tips = len([pos for pos in column if pos is not None])
            tracked_tip_pick_up(ham_int, tips, num_tips)
        else:
            ham_int.tip_pick_up(tips)

        vols = set_parallel_nones(column_volumes, column)
        response = ham_int.aspirate(column, vols, liquidClass=liquid_class,
                                mixCycles=0, mixVolume=0,
                                liquidHeight=aspiration_height,
                                capacitiveLLD=aspirate_capacitative_LLD, aspirateMode=2,
                                submergeDepth=2)


        channel_mapped_dispense_positions = distribute_positions_to_channel_ops(dispense_positions, column) # Aspirate sequentially because container has <8 positions
        for positions in channel_mapped_dispense_positions:
            vols = set_parallel_nones(column_volumes, positions)

            aspirate_heights = response.liquidHeights

            dispense_capacitative_LLD = 2 if dispense_height == 0 else 0
            response = ham_int.dispense(positions, vols, liquidClass=liquid_class, 
                                        mixCycles=mix_cycles, mixVolume=vol_mix_dispense,
                                        liquidHeight=dispense_height,
                                        capacitiveLLD=dispense_capacitative_LLD,
                                        liquidFollowing=liquid_following_dispense)
            
            dispense_heights = response.liquidHeights

            ham_int.tip_eject()


def shear_plate_96(ham_int: HamiltonInterface, tips:List[Tuple[DeckResource, int]] | TrackedTips, plate:DeckResource, 
                   mixing_volume:float, mix_cycles:int, liquid_class:str,  liquid_height=0):
    '''
    Shear DNA in plate with 96 channel head.
    '''
    if isinstance(tips, TrackedTips):
        tracked_tip_pick_up_96(ham_int, tips)
    else:
        ham_int.tip_pick_up_96(tips)



    cLLD = 1 if liquid_height == 0 else 0
    volume = 0
    ham_int.aspirate_96(plate, volume, liquid_class,mix_volume = mixing_volume, mix_cycles=mix_cycles, liquid_height=liquid_height, capacitative_LLD=cLLD)

    ham_int.tip_eject_96()


def mix_plate(ham_int: HamiltonInterface, tips:List[Tuple[DeckResource, int]] | TrackedTips, tip_support, num_samples,
               plate:DeckResource, mixing_volume:float, mix_cycles:int, liquid_class:str, liquid_height:float=0):
    '''
    Mix plate with 96 channel head.
    '''
    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")
    
    if mixing_volume > liquid_class_vol_capacity:
        raise ValueError(f"Mixing volume exceeds tip capacity: {mixing_volume} > {liquid_class_vol_capacity}")

    mph_tip_pickup_support(ham_int, tips, tip_support, num_tips=num_samples)

    cLLD, liquidFollowing = (5, True) if liquid_height == 0 else (0, False)
    ham_int.aspirate_96(plate, 0, liquidClass=liquid_class, mixCycles=mix_cycles, mixVolume=mixing_volume,
                        liquidHeight=liquid_height, capacitiveLLD=cLLD, liquidFollowing=liquidFollowing)

    ham_int.tip_eject_96()


def multi_dispense(ham_int: HamiltonInterface, tips:List[Tuple[DeckResource, int]] | TrackedTips,
                   source_positions:List[Tuple[DeckResource, int]], dispense_positions:List[Tuple[DeckResource, int]],
                   volumes:List[float], liquid_class:str, pre_dispense_volume = 0, post_dispense_volume = 0,
                   post_dispense_to_source = False, mix_cycles=0, aspiration_height=0, dispense_height=0):
    '''
    Dispenses a reagent across multiple columns for each aspiration. This is useful for quickly plating out reagent from a source trough.

    source_positions: A list of tuples specifying the source positions for aspiration.
    Example: [ (source_plate, 1), (source_plate, 2), (source_plate, 3)... ]

    dispense_positions: A list of tuples specifying the destination positions for dispensing.
    Example: [ (dest_plate, 1), (dest_plate, 2), (dest_plate, 3)... ]
    '''

    max_volume_tips = get_liquid_class_volume(liquid_class)  # Fetch the volume for the liquid class

    column_dispense_positions = batch_columnwise_positions(dispense_positions) # Batch dispense positions into lists of length eight
    column_dispense_volumes = batch_columnwise_positions(volumes) # Batch volumes into lists of length eight

    max_channel_volumes = [max_volume_tips]*8 # Placeholder that can be changed to different numbers of channels
    dispense_batches = build_dispense_batches(max_channel_volumes, column_dispense_positions, column_dispense_volumes)

    for batch, batch_aspiration_volumes in dispense_batches:
        
        if isinstance(tips, TrackedTips):
            if tips.volume_capacity != get_liquid_class_volume(liquid_class, nominal=True):
                raise ValueError(f"Tip type does not match liquid class: {tips.volume_capacity} != {get_liquid_class_volume(liquid_class, nominal=True)}")
            tracked_tip_pick_up(ham_int, tips, n=8)  # Pick up tips for the first column of the batch
        else:
            ham_int.pick_up_tips(tips)
        
        aspiration_positions = distribute_positions_to_channel_ops(source_positions, batch[0][0]) # First column of first batch
        

        for positions in aspiration_positions:
            vols = set_parallel_nones(batch_aspiration_volumes, positions)

            vols = [
                (v + pre_dispense_volume + post_dispense_volume) if v is not None else None
                for v in vols
            ]

            cLLD = 5 if aspiration_height == 0 else 0

            tracked_volume_aspirate(ham_int, positions, vols, liquidClass=liquid_class,
                                    mixCycles=0, mixVolume=0,
                                    liquidHeight=aspiration_height,
                                    capacitiveLLD=cLLD, aspirateMode=2,
                                    submergeDepth=2)
            
            if pre_dispense_volume > 0:
                pre_dispense_vols = [pre_dispense_volume for v in vols if v is not None]
                ham_int.dispense(positions, pre_dispense_vols, liquidClass=liquid_class, liquidHeight=dispense_height)

        for column, column_volumes in batch:
            response = ham_int.dispense(column, column_volumes, liquidClass=liquid_class,
                                        mixCycles=mix_cycles, mixVolume=0,
                                        liquidHeight=dispense_height,
                                        capacitiveLLD=0,
                                        liquidFollowing=0)
            
        if post_dispense_volume > 0 and post_dispense_to_source:
            post_dispense_vols = [post_dispense_volume for v in vols if v is not None]
            ham_int.dispense(positions, post_dispense_vols, liquidClass=liquid_class, liquidHeight=dispense_height)


        ham_int.tip_eject()


def multi_aspirate(ham_int: HamiltonInterface, tips:List[Tuple[DeckResource, int]] | TrackedTips, 
                   source_positions:List[Tuple[DeckResource, int]], dispense_positions:List[Tuple[DeckResource, int]], 
                   num_aspiration_cycles:int, volumes:List[float], liquid_class:str, mix_cycles=0, aspiration_height=0):
    '''
    Plate out a reagent in volumes greater than the tip capacity with an outer loop over aspirations and an inner loop over dispenses.
    This works for plating out reagent from a source trough.
    '''
    
    max_volume_tips = get_liquid_class_volume(liquid_class)  # Fetch the volume for the liquid class


    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")

    column_dispense_positions = batch_columnwise_positions(dispense_positions) # Batch dispense positions into lists of length eight
    column_dispense_volumes = batch_columnwise_positions(volumes) # Batch volumes into lists of length eight

    max_channel_volumes = [max_volume_tips]*8
    dispense_batches = build_dispense_batches(max_channel_volumes, column_dispense_positions, column_dispense_volumes)

    for aspiration_cycle in range(num_aspiration_cycles):
        if isinstance(tips, TrackedTips):
            if tips.volume_capacity != get_liquid_class_volume(liquid_class, nominal=True):
                raise ValueError(f"Tip type does not match liquid class: {tips.volume_capacity} != {get_liquid_class_volume(liquid_class, nominal=True)}")
            tracked_tip_pick_up(ham_int, tips, n=8)

        else:
            ham_int.pick_up_tips(tips)

        aspiration_positions = distribute_positions_to_channel_ops(source_positions, column_dispense_positions[0]) # First column of first batch, fix this later
        split_column_volumes = distribute_positions_to_channel_ops(volumes, column_dispense_positions[0])
        for positions, vols in zip(aspiration_positions, split_column_volumes):
            vols = set_parallel_nones(volumes, positions)
            tracked_volume_aspirate(ham_int, aspiration_positions, vols, liquidClass=liquid_class,
                                    mixCycles=0, mixVolume=0,
                                    liquidHeight=aspiration_height,
                                    capacitiveLLD=1, aspirateMode=2,
                                    submergeDepth=2)

        for batch, batch_aspiration_volumes in dispense_batches:
            for column, column_volumes in batch:
                response = ham_int.dispense(column, column_volumes, liquidClass=liquid_class,
                                            mixCycles=0, mixVolume=0,
                                            liquidHeight=0,
                                            capacitiveLLD=0,
                                            liquidFollowing=0)

def mph_tip_pickup_support(ham_int: HamiltonInterface, tips: TrackedTips, tip_support: TipSupportTracker, num_tips: int):
    '''
    Pick up tips using the multi-channel head from a tip support resource. Requires TrackedTips to be specified in
    case the tips loaded on the support have to be switched out.
    '''
    if isinstance(tips, TrackedTips):
        num_columns = num_tips//8 + 1*(num_tips % 8 > 0)
        tip_support_pickup_columns(ham_int, tips, tip_support, num_columns)
    else:
        ham_int.tip_pick_up_96(tips)

def transfer_96(ham_int: HamiltonInterface, tips:List[Tuple[DeckResource,int]]|TrackedTips, tip_support:TipSupportTracker, num_samples:int, 
                source_plate:DeckResource, target_plate:DeckResource, volume:float, liquid_class:str, 
                aspiration_mix_cycles:int=0, aspiration_mix_volume:float=0, aspiration_height:float=0,  
                dispense_mix_cycles:int=0, dispense_mix_volume:float=0, dispense_height:float=0):
    '''
    Dispense to multiple positions with 96 channel head.
    '''

    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    if volume > liquid_class_vol_capacity:
        raise ValueError(f"Volume exceeds tip capacity: {volume} > {liquid_class_vol_capacity}")
    
    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")


    mph_tip_pickup_support(ham_int, tips, tip_support, num_tips=num_samples)

    tracked_volume_aspirate_96(ham_int, source_plate, volume, liquidClass=liquid_class, mixCycles=aspiration_mix_cycles,
                                mixVolume=aspiration_mix_volume, liquidHeight=aspiration_height)
    
    ham_int.dispense_96(target_plate, volume, liquidClass=liquid_class, liquidHeight=dispense_height, 
                        mixCycles=dispense_mix_cycles, mixVolume=dispense_mix_volume)
    
    ham_int.tip_eject_96()


def double_aspirate_supernatant_96(ham_int: HamiltonInterface, tips: TrackedTips, tip_support: TipSupportTracker, num_samples:int,
                                    source_plate: DeckResource, destination_plate: DeckResource, first_volume: float, second_volume: float, 
                                    liquid_class: str, first_aspiration_height: float=0, second_aspiration_height: float=0, mix_cycles=0, dispense_height=0):
    '''
    Double aspiration to remove supernatant from a plate with 96 channel head. Double aspiration is used to
    allow residual liquid to settle between aspirations.
    '''

    # Potentially adjust sequence position by 3mm? Yes, because we have to stop liquid following 3mm from the bottom

    liquid_class_vol_capacity = get_liquid_class_volume(liquid_class, nominal=True)  # Fetch the volume for the liquid class
    volume = first_volume + second_volume
    
    if volume > liquid_class_vol_capacity:
        raise ValueError(f"Volume exceeds tip capacity: {volume} > {liquid_class_vol_capacity}")

    if tips.volume_capacity != liquid_class_vol_capacity:
        raise ValueError(f"Liquid class does not match tip capacity: {liquid_class_vol_capacity} != {tips.volume_capacity}")


    mph_tip_pickup_support(ham_int, tips, tip_support, num_tips=num_samples)

    ham_int.aspirate_96(source_plate, first_volume, liquidClass=liquid_class, mixCycles=mix_cycles,
                        capacitiveLLD=1, liquidFollowing=True, aspirateMode=2, submergeDepth=0.5)  # First aspiration uses cLLD and liquid following

    ham_int.aspirate_96(source_plate, second_volume, liquidClass=liquid_class, mixCycles=mix_cycles, 
                        liquidHeight=second_aspiration_height, capacitiveLLD=0, aspirateMode=1) # Second aspiration uses fixed height, no liquid following

    total_volume = first_volume + second_volume
    ham_int.dispense_96(destination_plate, total_volume, liquidClass=liquid_class, liquidHeight=dispense_height, dispenseMode=4)

    ham_int.tip_eject_96()


def ethanol_wash(ham_int: HamiltonInterface, tips: TrackedTips, tip_support: TipSupportTracker, num_samples: int, 
                 ethanol_plate: DeckResource, magnet_plate: DeckResource, waste_plate: DeckResource, wash_volume: float, 
                 first_removal_volume: float, second_removal_volume: float, liquid_class: str, mix_cycles=0, liquid_height=0):

    ''' Wash beads with ethanol twice and then remove supernatant.'''

    mph_tip_pickup_support(ham_int, tips, tip_support, num_tips=num_samples)

    # First ethanol wash
    tracked_volume_aspirate_96(ham_int, ethanol_plate, wash_volume, liquidClass=liquid_class, mixCycles=mix_cycles, liquidHeight=liquid_height, capacitiveLLD=1, submergeDepth=2)
    ham_int.dispense_96(magnet_plate, wash_volume, liquidClass=liquid_class, dispenseMode=4, liquidHeight=10, airTransportRetractDist=5)
    ham_int.tip_eject_96()

    time.sleep(5)  # Brief incubation

    # Remove supernatant with remove volume
    # Specify heights?
    double_aspirate_supernatant_96(ham_int, tips, tip_support, num_samples, magnet_plate, waste_plate, 
                                    first_removal_volume, second_removal_volume,
                                    liquid_class=liquid_class, mix_cycles=mix_cycles, dispense_height=3)


def pip_mix(ham_int: HamiltonInterface, tips: TrackedTips, positions_to_mix: List[Tuple[DeckResource, int]], liquid_class: str,
            mix_volume: float, mix_cycles=0, liquid_height=0):
    '''
    Mix only without aspiration or dispense. Need to change this so it loops over columns.
    '''

    if isinstance(tips, TrackedTips):
        if tips.volume_capacity != get_liquid_class_volume(liquid_class, nominal=True):
            raise ValueError(f"Tip type does not match liquid class: {tips.volume_capacity} != {get_liquid_class_volume(liquid_class, nominal=True)}")
        tracked_tip_pick_up(ham_int, tips, n=8)  # Pick up tips for the first column of the batch
    else:
        ham_int.tip_pick_up(tips)

    # Let's batch positions to mix into columns of 8
    mixing_columns = batch_columnwise_positions(positions_to_mix)

    for col in mixing_columns:
        col = col + [None]*(8 - len(col))  # Pad to length 8
        # Create a volume list of zeros where col is not None and None where col is None
        zero_vols = [0 if pos is not None else None for pos in col]
        response = ham_int.aspirate(col, zero_vols, liquidClass=liquid_class, mixVolume=0, mixCycles=0, liquidHeight=0, capacitiveLLD=1)
        volumes = response.liquidVolumes

        mixing_volume = min(volumes)*0.75 # Calculate mixing volume based on volume in container


        capacitative_LLD, liquidFollowing = (5, True) if liquid_height==0 else (0, False)

        ham_int.aspirate(col, zero_vols, liquidClass=liquid_class, mixVolume=mixing_volume, mixCycles=mix_cycles, 
                     liquidHeight=liquid_height, capacitiveLLD=capacitative_LLD, liquidFollowing=liquidFollowing)

        ham_int.tip_eject()


# Delete everything below??
def aspirate_all_for_stamp(ham_int, tips, source_plate, volume, liquid_class,
                          mix_cycles=0, liquid_height=0):
    '''
    Aspirate all from a plate with 96 channel head for stamping.
    '''
    ham_int.tip_pick_up_96(tips)
    ham_int.aspirate_96(source_plate, volume, liquid_class, mix_cycles=mix_cycles, 
                        liquid_height=liquid_height, capacitative_LLD=5, aspirateMode=2, submergeDepth=0.5)
    ham_int.dispense_96(source_plate, volume, liquid_class, liquidHeight=liquid_height, dispenseMode=4)
    ham_int.eject_tips_96()


def aspirate_all(ham_int, tips, source_plate, volume, liquid_class,
                 mix_cycles=0, liquid_height=0):
    '''
    Aspirate all from a plate with 96 channel head.
    '''
    ham_int.pick_up_tips_96(tips)
    ham_int.aspirate_96(source_plate, volume, liquid_class, mix_cycles=mix_cycles, 
                        liquid_height=liquid_height, capacitative_LLD=5)
    ham_int.eject_tips_96()



if __name__ == "__main__":
    pass