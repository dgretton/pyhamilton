from pyhamilton import HamiltonInterface, LayoutManager, Plate96, Tip96, TrackedTips, layout_item, Waste96
from pyhamilton_advanced import pip_transfer, ethanol_wash, double_aspirate_supernatant_96

if __name__ == "__main__":
    with HamiltonInterface(windowed=True, simulating=False) as ham_int:

        lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')
        
        tracked_tips_300uL = TrackedTips.from_prefix(
                                tracker_id="STF_L",
                                volume_capacity=300,
                                prefix="STF_L",
                                count=8,
                                tip_type=Tip96,
                                lmgr=lmgr)

        MIDI_Pipette = layout_item(lmgr, Plate96, 'MIDI_Pipette')
        HHS5_MIDI = layout_item(lmgr, Plate96, 'HHS5_MIDI')
        MIDI_OnMagnet = layout_item(lmgr, Plate96, 'MIDI_OnMagnet')
        LiquidWaste = layout_item(lmgr, Waste96, 'LiquidWaste_MPH')

        first_volume = 50
        second_volume = 25

        ham_int.initialize()

        double_aspirate_supernatant_96(ham_int, 
                                       tips = tracked_tips_300uL, 
                                       source_plate = MIDI_OnMagnet, 
                                       waste_container = LiquidWaste,
                                       first_volume = first_volume, 
                                       second_volume = second_volume, 
                                       aspiration_height = 0,
                                       liquid_class = 'StandardVolumeFilter_Water_DispenseJet_Empty')