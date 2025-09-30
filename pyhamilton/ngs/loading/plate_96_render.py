from __future__ import annotations
import os
import unicodedata
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata  # (top-level import)
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyhamilton_advanced.consumables import ReagentTrackedReservoir60mL
from pyhamilton import layout_item, LayoutManager, DeckResource
from pathlib import Path
import tkinter as tk
from .rendering_helpers import (
    ARIAL_TTF,
    _FONT_CANDIDATES,
    _best_label_box_outside,
    _measure_text_pillow,
    _resolve_font_path,
    _rescale_image,
    draw_text_pillow,
    _ascii_label,
    _name_to_color_bgr,
)


def render_plate_96(
    plate_key: str,
    plate_data: Dict[int, Dict[str, Any]],
    unit_default: str,
    *,
    cols: int = 12,
    rows: int = 8,                # A..H
    cell_w: int = 48,
    cell_h: int = 48,
    margin_left: int = 80,
    margin_top: int = 80,
    margin_right: int = 320,      # wider legend gutter
    margin_bottom: int = 60,
    well_radius: int = 14,
    grid_thickness: int = 1,
    font_scale: float = 0.40,
    font_thickness: int = 1,
    pad: int = 3,
    gap: int = 6,
    render_scale: float = 1.25,    # draw larger for crisp text
    output_scale: float = 1.0,     # final scale (keep 1.0 for this screen)
) -> np.ndarray:
    """
    96-well plate (12x8). Renders the plate reagent map.
    """
    
    # --- Input Handling ---
    if not plate_data:
        s = float(render_scale)
        width  = int(round((margin_left + cols * cell_w + margin_right) * s))
        height = int(round((margin_top + rows * cell_h + margin_bottom) * s))
        canvas = np.full((height, width, 3), 255, np.uint8)
        title = _ascii_label(f"Plate {plate_key} - No Reagent Data")
        label_px = 16
        draw_text_pillow(
            canvas, title, (int(round(margin_left * s)), int(round(36 * s))),
            font_path=ARIAL_TTF,
            px=label_px,
            color=(0, 0, 0)
        )
        return canvas

    # --- Scaling ---
    s = float(render_scale)
    cw = int(round(cell_w * s)); ch = int(round(cell_h * s))
    ml = int(round(margin_left * s)); mt = int(round(margin_top * s))
    mr = int(round(margin_right * s)); mb = int(round(margin_bottom * s))
    wr = int(round(well_radius * s))
    gt = max(1, int(round(grid_thickness * s)))
    fs = font_scale * s
    pt = max(1, int(round(pad * s)))
    gp = max(1, int(round(gap * s)))

    width  = ml + cols * cw + mr
    height = mt + rows * ch + mb
    canvas = np.full((height, width, 3), 255, np.uint8)

    # --- Title ---
    title = _ascii_label(f"{plate_key} - Reagent Map")
    label_px = 16
    draw_text_pillow(
        canvas, title, (ml, int(round(36 * s))),
        font_path=ARIAL_TTF,
        px=label_px,
        color=(0, 0, 0)
    )
    
    # --- Grid Drawing ---
    origin_x = ml
    origin_y = mt

    # Outer border
    cv2.rectangle(canvas, (origin_x, origin_y), (origin_x + cols*cw, origin_y + rows*ch), (0,0,0), max(1, int(round(2*s))))

    # Internal grid
    for c in range(1, cols):
        x = origin_x + c * cw
        cv2.line(canvas, (x, origin_y), (x, origin_y + rows*ch), (200,200,200), gt)
    for r in range(1, rows):
        y = origin_y + r * ch
        cv2.line(canvas, (origin_x, y), (origin_x + cols*cw, y), (200,200,200), gt)

    # Headers
    for c in range(cols):
        label = str(c+1)
        tx = origin_x + c*cw + cw//2 - int(round(6*s))*len(label)//2
        draw_text_pillow(
            canvas, label, (tx, origin_y - int(round(12*s))),
            font_path=ARIAL_TTF,
            px=label_px,
            color=(0, 0, 0)
        )
    row_letters = "ABCDEFGH"
    for r in range(rows):
        label = row_letters[r]
        ty = origin_y + r*ch + ch//2 + int(round(6*s))//2
        draw_text_pillow(
            canvas, label, (origin_x - int(round(28*s)), ty),
            font_path=ARIAL_TTF,
            px=label_px,
            color=(0, 0, 0)
        )

    # --- Wells and Legend Data Collection ---
    filled_entries = []  # list of (well_notation, info, color, pos)
    for r in range(rows):
        for c in range(cols):
            cx = origin_x + c*cw + cw//2
            cy = origin_y + r*ch + ch//2
            pos = c * rows + r  # Column-first indexing (0=A1, 1=B1, ..., 8=A2)
            well_notation = f"{row_letters[r]}{c+1}"
            info = plate_data.get(str(pos)) 
            color = (220, 220, 220) if not info else _name_to_color_bgr(info.get("reagent", well_notation))
            cv2.circle(canvas, (cx, cy), wr, color, thickness=-1)
            cv2.circle(canvas, (cx, cy), wr, (40,40,40), thickness=max(1, int(round(1*s))))
            if info:
                filled_entries.append((well_notation, info, color, pos))

    # --- Legend Drawing ---
    x_gutter = origin_x + cols*cw + int(round(4 * s))

    # Sort by position (integer order)
    filled_entries.sort(key=lambda entry: entry[3])

    # layout calculations
    col_start_x = x_gutter + int(round(12 * s))
    y0 = mt
    # measure line height once
    (_, th), base = cv2.getTextSize("Ag", cv2.FONT_HERSHEY_SIMPLEX, fs, font_thickness)
    line_h = th + base + 2*pt
    sw, sh = int(round(18 * s)), int(round(12 * s))     # swatch size
    col_w = max(int(round(240 * s)), sw + int(round(10*s)) + int(round(180*s)))

    max_rows = max(1, (height - y0 - int(round(10*s))) // line_h)

    for idx, (well_notation, info, color, pos) in enumerate(filled_entries):
        col = idx // max_rows
        row = idx % max_rows
        x = col_start_x + col * col_w
        y = y0 + row * line_h

        # swatch
        cv2.rectangle(canvas, (x, y), (x + sw, y + sh), color, thickness=-1)
        cv2.rectangle(canvas, (x, y), (x + sw, y + sh), (30,30,30), thickness=max(1, int(round(1*s))))

        # text: "A1: Name, 100 uL"
        reagent_name = info.get("reagent", well_notation)
        volume = info.get("volume")
        unit = info.get("unit", unit_default)
        
        try:
            vol_num = float(volume)
            vol_str = f"{vol_num:.3f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            vol_str = str(volume)
        
        label_text = f"{reagent_name}, {vol_str} {unit}"

        legend_text = _ascii_label(f"{well_notation}: {label_text}")
        org = (x + sw + int(round(10*s)), y + sh - max(1, int(round(2*s))))
        draw_text_pillow(
            canvas, legend_text, org,
            font_path=ARIAL_TTF,
            px=label_px,
            color=(0, 0, 0)
        )

    final = _rescale_image(canvas, output_scale / render_scale)
    return final

def _draw_text_simple(canvas: np.ndarray, text: str, pos: Tuple[int, int], size: int, color: Tuple[int, int, int]) -> None:
    """Simple text drawing using OpenCV (fallback when Pillow not available)."""
    cv2.putText(canvas, text, pos, cv2.FONT_HERSHEY_SIMPLEX, size/20.0, color, 1, cv2.LINE_AA)
