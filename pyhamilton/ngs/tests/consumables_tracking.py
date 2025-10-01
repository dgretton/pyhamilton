from pyhamilton import DeckResource, layout_item, LayoutManager, HamiltonInterface, Plate96, Reservoir60mL, FalconCarrier24, Plate96, TrackedTips,Tip96
from pyhamilton_advanced import tracked_volume_aspirate, ReagentTrackedReservoir60mL, multi_dispense

if __name__ == "__main__":
    lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

    HSP_OffMagnet = layout_item(lmgr, Plate96, 'HSP_Pipette')
    HSP_positions = [(HSP_OffMagnet, i) for i in range(96)]
    tracked_tips_300uL = TrackedTips.from_prefix(
        tracker_id="STF_L",
        volume_capacity=300,
        prefix="STF_L",
        count=8,
        tip_type=Tip96,
        lmgr=lmgr)


    magbeads = layout_item(lmgr, ReagentTrackedReservoir60mL, 'rgt_cont_60ml_BC_A00_0001')
    magbead_positions = magbeads.assign_reagent_map('magbeads', range(8))


    with HamiltonInterface(simulating=True, windowed=False) as ham_int:
        multi_dispense(ham_int, tracked_tips_300uL, magbead_positions, HSP_positions, [50]*96, liquid_class='StandardVolumeFilter_Water_DispenseJet_Empty')

    print(magbeads.calculate_required_reagent_volume('magbeads'))