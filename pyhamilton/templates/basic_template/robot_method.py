# -*- coding: utf-8 -*-
"""
Created on Sun Jul 17 21:12:47 2022

@author: stefa
"""
import os
import subprocess
import sys
from pathlib import Path


def _use_project_interpreter():
    """Hand this script to the project's own interpreter, if it is not already.

    `python robot_method.py` runs whatever python is first on PATH. On Windows
    that is often the Microsoft Store stub, or an older install that happens to
    carry an older pyhamilton -- which imports cleanly and runs the wrong code
    against a real robot. Rather than rely on remembering `uv run`, look for the
    .venv beside this file and hand the script over to it.

    Delete this block if you manage environments yourself.
    """
    if os.environ.get("PYHAMILTON_REEXEC"):
        return  # handed over once already; never loop
    here = Path(__file__).resolve()
    for folder in (here.parent, *here.parents):
        interpreter = folder / ".venv" / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not interpreter.exists():
            continue
        if Path(sys.executable).resolve() == interpreter.resolve():
            return  # already the right one
        print(f"[pyhamilton] re-running with {interpreter}")
        result = subprocess.run(
            [str(interpreter), str(here), *sys.argv[1:]],
            env={**os.environ, "PYHAMILTON_REEXEC": "1"})
        sys.exit(result.returncode)


_use_project_interpreter()

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
    with HamiltonInterface(windowed=True) as ham_int:
        normal_logging(ham_int, os.getcwd())
        initialize(ham_int)
        tip_pick_up(ham_int, tips_poss)
        aspirate(ham_int, aspiration_poss, vols_list, liquidClass = liq_class)
        dispense(ham_int, dispense_poss, vols_list, liquidClass = liq_class)
        tip_eject(ham_int, tips_poss)
