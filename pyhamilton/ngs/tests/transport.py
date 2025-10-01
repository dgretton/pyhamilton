from pyhamilton import HamiltonInterface, LayoutManager, Reservoir60mL, Tip96, layout_item, Plate96
from pyhamilton_advanced import transport_resource, GripDirection, GrippedResource, GripperParams



lmgr = LayoutManager('PacBio_MultiPlexLibraryPrepDeck_v1.2.lay')

HSP_Pipette2 = layout_item(lmgr, Plate96, 'HSP_Pipette2')

HHS2_HSP = layout_item(lmgr, Plate96, 'HHS2_HSP')


with HamiltonInterface(windowed=True, simulating=False) as ham_int:
    ham_int.initialize()

    # HSP Pipette 2 to HHS2 HSP
    transport_resource(ham_int, HSP_Pipette2.layout_name(), HHS2_HSP.layout_name(), core_gripper=True, resource_type=GrippedResource.PCR)
