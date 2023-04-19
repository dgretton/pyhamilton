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
import IPython
from preprompt import complete
from voice import voice_to_text

liq_class = 'StandardVolumeFilter_Water_DispenseJet_Empty'

def assist(prompt, safe = False):
    response = complete(prompt)
    lines = response.split('\n')
    d = dict(locals(), **globals())
    for line in lines:
        print(line)
        if safe:
            input("Proceed?")
        exec(line, d, d)

lmgr = LayoutManager('deck.lay')
#plates = resource_list_with_prefix(lmgr, 'plate_', Plate96, 5)
tips_0 = layout_item(lmgr, Tip96, 'tips_0')
plate_0 = layout_item(lmgr, Plate96, 'plate_0')

liq_class = 'StandardVolumeFilter_Water_DispenseJet_Empty'



print("""Be careful! The assist() function uses an AI coding assistant to interpret
      natural language into PyHamilton code. Do not use this outside of simulation
      mode until you are familiar with how it works.""")


if __name__ == '__main__': 
    with HamiltonInterface(simulate=True) as ham_int:
        normal_logging(ham_int, os.getcwd())
        initialize(ham_int)
        IPython.embed()
        