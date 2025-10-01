from pyhamilton import (HamiltonInterface, LayoutManager, ResourceType, Plate24, Plate96, Tip96, 
                        move_plate_using_gripper, resource_list_with_prefix, layout_item)


lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

# Perhaps import stack management

with HamiltonInterface(windowed=True) as ham_int:
    ham_int.initialize()

    move_plate_using_gripper(ham_int, 'AbgeneMIDI_Stack1_0001', 'MIDI_OnMagnet', gripHeight=5)
