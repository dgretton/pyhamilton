from pyhamilton import (HamiltonInterface, LayoutManager, Tip96, TrackedTips, resource_list_with_prefix, 
                        Tip96, Plate96, ResourceType, tip_pick_up, DeckResource, 
                        tracked_tip_pick_up, tracked_tip_pick_up_96, StackedResources, move_plate_using_gripper)

from pyhamilton_advanced import (transport_resource, GripDirection, GrippedResource, GripperParams)


BioRadHardShell_Stack = StackedResources.from_prefix("BioRadHardShell_Stack", "BioRadHardShell_Stack", 3)
AbgeneMIDI_Stack = StackedResources.from_prefix("AbgeneMIDI_Stack1", "AbgeneMIDI_Stack1", 3)

lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

# TODO: Don't eject core gripper tool between pickups

with HamiltonInterface(windowed=True) as ham_int:
    ham_int.initialize()
    for _ in range(3):
        plate_seq = AbgeneMIDI_Stack.fetch_next()
        transport_resource(ham_int, plate_seq, 'HHS3_MIDI', resource_type=GrippedResource.MIDI, 
                           stack=True, core_gripper=True)