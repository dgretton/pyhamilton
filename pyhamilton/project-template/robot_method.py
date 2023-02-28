# -*- coding: utf-8 -*-
"""
Created on Sun Jul 17 21:12:47 2022

@author: stefa
"""
import os
from pyhamilton import (HamiltonInterface,  LayoutManager, 
 Plate96, Tip96, initialize, tip_pick_up, tip_eject, 
 aspirate, dispense,  oemerr, resource_list_with_prefix, normal_logging,
 layout_item)

liq_class = 'StandardVolumeFilter_Water_DispenseJet_Empty'



lmgr = LayoutManager('deck.lay')
plates = resource_list_with_prefix(lmgr, 'plate_', Plate96, 5)
tips = layout_item(lmgr, Tip96, 'tips_0')
liq_class = 'StandardVolumeFilter_Water_DispenseJet_Empty'

aspiration_poss = [(plates[0], x) for x in range(8)]
dispense_poss = [(plates[0], x) for x in range(8,16)]
vols_list = [100]*8


tips_poss = [(tips, x) for x in range(8)]


if __name__ == '__main__': 
    with HamiltonInterface(simulate=True) as ham_int:
        normal_logging(ham_int, os.getcwd())
        initialize(ham_int)
        tip_pick_up(ham_int, tips_poss)
        aspirate(ham_int, aspiration_poss, vols_list, liquidClass = liq_class)
        dispense(ham_int, dispense_poss, vols_list, liquidClass = liq_class)
        tip_eject(ham_int, tips_poss)