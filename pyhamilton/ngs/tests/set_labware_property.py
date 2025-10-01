from pyhamilton import HamiltonInterface, TipType

with HamiltonInterface(simulating=False, windowed=True) as ham_int:
    ham_int.initialize()
    ham_int.set_labware_property('TipSupport_0001', 'MlStarCore96TipRack', TipType.uL_300)