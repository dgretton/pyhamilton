from pyhamilton import HamiltonInterface
from itertools import groupby

def check_volumes_in_troughs(ham_int: HamiltonInterface, aspiration_positions, liquid_class):
    trough_volumes = []

    aspiration_positions.sort(key=lambda x: x[0].layout_name())
    troughs = [list(group) for _, group in groupby(aspiration_positions, key=lambda x: x[0])]

    for trough_positions in troughs:
        vols = [0 if pos is not None else None for pos in trough_positions]
        print(trough_positions)
        response = ham_int.aspirate(trough_positions, vols, liquidClass=liquid_class, capacitiveLLD=1)
        print(response.liquidVolumes)
        volume = min(response.liquidVolumes)
        trough_volumes.append((trough_positions, volume))
    return trough_volumes

def select_trough(ham_int: HamiltonInterface, aspiration_positions, volume, liquid_class, prealiquot_volume, postaliquot_volume):
    trough_volumes = check_volumes_in_troughs(ham_int, aspiration_positions, liquid_class)
    for trough_positions, vol in trough_volumes:
        if abs(vol) >= (volume + prealiquot_volume + postaliquot_volume): # We have to do abs because Venus simulator insanely returns negative volumes
            return trough_positions
    return None

def prompt_insufficient_volume(ham_int, troughs, volume):
    pass

def accumulate_residual_volume(ham_int, troughs, volumes):
    return
    total_volume = 0
    for trough in troughs:
        heights = ham_int.aspirate(trough)
        vol = trough.height_to_volume(heights)
        total_volume += vol
    return total_volume

def manage_multiple_troughs(ham_int, aspiration_positions, volume, liquid_class, prealiquot_volume, postaliquot_volume, check_volumes=True):
    performed_additional_volume_transfer = False
    trough = select_trough(ham_int, aspiration_positions, volume, liquid_class, prealiquot_volume, postaliquot_volume)
    if trough is None: # No trough has enough volume
        # volumes = prompt_insufficient_volume(ham_int, troughs, volume)
        performed_additional_volume_transfer = accumulate_residual_volume(ham_int, aspiration_positions, volume)
        trough = select_trough(ham_int, aspiration_positions, volume, liquid_class, prealiquot_volume, postaliquot_volume)
    else:
        return trough, performed_additional_volume_transfer
