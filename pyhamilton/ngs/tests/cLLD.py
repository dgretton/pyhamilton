from pyhamilton import (HamiltonInterface, LayoutManager, ResourceType, Plate24, Plate96, Tip96, resource_list_with_prefix, 
                        layout_item, DeckResource, Reservoir60mL, get_liquid_class_volume)

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')
    
    
# Example usage of layout_item
tips = layout_item(lmgr, Tip96, 'TIP_50uLF_L_0001')  # Example tip rack
ElutionBuffer_Trough = layout_item(lmgr, Reservoir60mL, 'rgt_cont_60ml_BC_A00_0002')  # Example elution trough

liquid_class = 'Tip_50ulFilter_Water_DispenseSurface_Empty'  # Example liquid class
vol_capacity = get_liquid_class_volume(liquid_class)  # Fetch the volume for the liquid class

with HamiltonInterface(windowed=True) as ham_int:
    ham_int.initialize()
    ham_int.tip_pick_up([(tips, 0)])  # Pick up the first tip from the tip rack
    response = ham_int.aspirate([(ElutionBuffer_Trough, 0)], [0], liquidClass=liquid_class, capacitiveLLD=1)
    print(f'Liquid heights after aspirate: {response.liquidHeights}')
    print('Liquid volume')
    print(response.liquidVolumes)

# Parallel to ODTC:
# Plate out reagents
# Book in a partial plate asynchronously
# Book in a full plate asynchronously?

# Ask Matt about reagent volumes

# TSO 500 HT asking RNA DNA etc mix and match
# Can handle worklist with multiple plates including partial plates of both RNA and DNA
# Specific kit they want to run routinely on these two vantages (up to PCR, past PCR, huge custom setup)

# NC department of health double ODTC
# NGS multiple bottleneck steps: tip reloads, pipetting, 5 HHSs, 2 ODTCs
# Protocols for hybridization steps: 4-24 hours, ODTC bound by scheduler

# STAR with two ODTCs (qPCR)

# Restart error recovery halfway through reagent dispense into plate

# Venus scheduler lock-in for a single run

# General asynchronous method kickoff with scheduling and resource occupancy