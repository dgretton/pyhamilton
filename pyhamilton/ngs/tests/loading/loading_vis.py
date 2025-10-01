# loading_vis.py

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import cv2
import numpy as np





# ------------------------- Example Usage -------------------------

if __name__ == "__main__":
    # Replace 'regions.json' with your file path, or pass the dict directly to LoadingVis(...)
    json_path = "deck_regions.json"

    vis = LoadingVis(json_path)

    # Selectively render only these overlays (case-insensitive keys):
    vessels = [
        ReagentVessel("RGT_60mL_0001"),
        ReagentVessel("Rgt_60mL_0002", label="Buffer A"),
        ReagentVessel("Rgt_60mL_0005", override_color_bgr=(0, 128, 255)),
        ReagentVessel("CPAC"),
        ReagentVessel("Ethanol"),
        # ReagentVessel("does_not_exist")  # silently skipped
    ]

    img = vis.render(vessels, alpha=0.4, draw_labels=True)
    vis.show(img, scale=0.75, wait_ms=0)
    # vis.save(img, "out/selection.png")
