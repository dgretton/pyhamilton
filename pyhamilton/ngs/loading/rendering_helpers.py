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



ARIAL_TTF = r"C:\Windows\Fonts\arial.ttf"

_FONT_CANDIDATES = [
    ARIAL_TTF,                                  # <- prioritize Arial
    "fonts/Inter-Regular.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


def draw_text_pillow(img_bgr: np.ndarray, text: str, org: Tuple[int, int],
                     font_path: Optional[str] = ARIAL_TTF, px: Union[int, float] = 18,
                     color: Tuple[int, int, int] = (0, 0, 0)) -> np.ndarray:
    """
    Draw TTF text with Pillow onto img_bgr IN-PLACE and also return img_bgr.
    - org is treated like OpenCV: (x, baseline_y). We adjust for ascent so
      the visual baseline matches your existing placement math.
    - px may be float; we coerce to int >= 1.
    """
    # 1) Coerce px
    px_i = max(1, int(round(px)))

    # 2) Resolve font path (fallback to Arial candidates if missing)
    fp = font_path if (font_path and Path(font_path).is_file()) else None
    if fp is None:
        for cand in _FONT_CANDIDATES:
            if Path(cand).is_file():
                fp = cand
                break
    if fp is None:
        # Last-resort fallback: use OpenCV so at least something draws
        scale = max(0.4, px_i / 32.0)
        cv2.putText(img_bgr, text, org, cv2.FONT_HERSHEY_DUPLEX, scale, color, 1, cv2.LINE_AA)
        return img_bgr

    # 3) Convert to PIL image (RGB), draw, convert back
    im = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype(fp, px_i)

    # Treat org as BASELINE like OpenCV
    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent, descent = (int(0.8 * px_i), int(0.2 * px_i))
    x, y_base = int(org[0]), int(org[1])
    y_top = y_base - ascent

    # Pillow is RGB; convert BGR color
    fill = (color[2], color[1], color[0])
    draw.text((x, y_top), text, font=font, fill=fill)

    # Write back IN-PLACE so callers don't need to assign
    out = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    img_bgr[:] = out
    return img_bgr


def _resolve_font_path(pref: Optional[str] = ARIAL_TTF) -> Optional[str]:
    """Pick a usable TTF path."""
    cands = [pref] + [p for p in _FONT_CANDIDATES if p != pref]
    for p in cands:
        if p and Path(p).is_file():
            return p
    return None

def _measure_text_pillow(text: str, font_path: Optional[str], px: Union[int, float]) -> Tuple[int, int, int]:
    """
    Return (width_px, ascent_px, descent_px) measured with Pillow.
    Falls back to OpenCV approx if a TTF can't be opened.
    """
    fp = _resolve_font_path(font_path)
    px_i = max(1, int(round(px)))
    if not fp:
        # Fallback: rough OpenCV approximation
        scale = max(0.4, px_i / 32.0)
        (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        return int(tw), int(th), int(base)

    font = ImageFont.truetype(fp, px_i)
    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent, descent = int(0.8 * px_i), int(0.2 * px_i)
    # getbbox is accurate (x0,y0,x1,y1)
    x0, y0, x1, y1 = font.getbbox(text)
    width = int(x1 - x0)
    return width, int(ascent), int(descent)


def _rescale_image(img: np.ndarray, scale: float) -> np.ndarray:
    """Scale with proper interpolation (AREA for downscale, CUBIC for upscale)."""
    if scale is None or abs(scale - 1.0) < 1e-6:
        return img
    h, w = img.shape[:2]
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
    return cv2.resize(img, (nw, nh), interpolation=interp)

def _ascii_label(s: str) -> str:
    repl = {"—": "-", "–": "-", "−": "-", "•": "-", "·": "-", "µ": "u", "°": " deg ", "\u00A0": " "}
    for k, v in repl.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s)
    return s.encode("ascii", "ignore").decode("ascii")

def _label_from_info_dict(info: Dict, *, unit_default: str, fallback: str) -> str:
    name = str(info.get("reagent") or fallback)
    unit = str(info.get("unit") or unit_default or "").strip()
    vol  = info.get("volume")
    if vol is None or vol == "":
        return _ascii_label(name)
    try:
        v = float(vol)
        vol_s = f"{v:.3f}".rstrip("0").rstrip(".")
    except Exception:
        vol_s = str(vol)
    txt = f"{name}, {vol_s} {unit}".strip()
    return _ascii_label(txt)

def _name_to_color_bgr(name: str) -> Tuple[int, int, int]:
    """Deterministic bright color for a given name (HSV→BGR)."""
    h = (hash(name) % 180)  # OpenCV H in [0,179]
    s, v = 200, 230
    hsv = np.uint8([[[h, s, v]]])
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0,0].tolist()
    return (int(bgr[0]), int(bgr[1]), int(bgr[2]))


def _norm_key(k: str) -> str:
    return k.strip().lower().replace("\\", "/")

def _ensure_bgr(img: np.ndarray) -> np.ndarray:
    """Ensure a 3-channel BGR image for overlay; convert if BGRA or gray."""
    if img is None:
        raise ValueError("Base image is None (could not load).")
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    return img

def _draw_transparent_rect(
    canvas_bgr: np.ndarray,
    p1: Tuple[int, int],
    p2: Tuple[int, int],
    color_bgr: Tuple[int, int, int],
    alpha: float = 0.35,
    thickness: int = -1,
) -> None:
    """Draw a filled/outlined transparent rectangle."""
    overlay = canvas_bgr.copy()
    cv2.rectangle(overlay, p1, p2, color_bgr, thickness=thickness)
    cv2.addWeighted(overlay, alpha, canvas_bgr, 1 - alpha, 0, dst=canvas_bgr)

def _draw_transparent_polygon(
    canvas_bgr: np.ndarray,
    points: List[Tuple[int, int]],
    color_bgr: Tuple[int, int, int],
    alpha: float = 0.35,
) -> None:
    """Draw a filled transparent polygon defined by points."""
    overlay = canvas_bgr.copy()
    
    # Convert points list to a numpy array for OpenCV
    pts = np.array(points, np.int32)
    # Reshape for fillPoly: array of polygons, where each polygon is an array of points
    pts = pts.reshape((-1, 1, 2))
    
    # Draw the filled polygon onto the overlay
    cv2.fillPoly(overlay, [pts], color_bgr)
    
    # Blend the overlay with the original canvas for transparency
    cv2.addWeighted(overlay, alpha, canvas_bgr, 1 - alpha, 0, dst=canvas_bgr)


def _rect_xyxy(p1, p2) -> Tuple[int, int, int, int]:
    x1, y1 = p1; x2, y2 = p2
    if x2 < x1: x1, x2 = x2, x1
    if y2 < y1: y1, y2 = y2, y1
    return (int(x1), int(y1), int(x2), int(y2))

def _rect_overlap_area(a, b) -> int:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0, min(ay2, by2) - max(ay1, by1))
    return iw * ih

def _intersects_any(r, rects) -> bool:
    return any(_rect_overlap_area(r, q) > 0 for q in rects)

def _fan_offsets(max_shift: int, step: int):
    # 0, +step, -step, +2*step, -2*step, ...
    yield 0
    s = step
    while s <= max_shift:
        yield s
        yield -s
        s += step

def _fmt_volume(vol: Any, unit_default: str) -> str:
    if vol is None or vol == "":
        return ""
    try:
        v = float(vol)
    except Exception:
        return _ascii_label(str(vol))  # <-- ensure ascii even for strings
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return _ascii_label(f"{s} {unit_default}".strip())  # <-- changed

def _preferred_side_for_key(key_norm: str) -> str:
    """
    For vessel IDs like rgt_60ml_0005 -> 'left', 0006+ -> 'right'.
    Ethanol should label on the RIGHT. Defaults to 'left' otherwise.
    """
    k = key_norm.strip().lower()
    if k == "ethanol":
        return "right"

    try:
        if k.startswith("rgt_60ml_"):
            idx_str = k.rsplit("_", 1)[-1]
            idx = int(idx_str)  # "0005" -> 5
            return "left" if idx <= 5 else "right"
    except Exception:
        pass
    return "left"


def _best_label_box_outside(
    canvas_shape,
    anchor_rect_xyxy,
    text: str,
    *,
    anchor_poly_points: Optional[List[Tuple[int, int]]] = None,
    avoid_rects,
    avoid_labels,
    pad: int = 3,
    gap: int = 6,
    max_shift: int = 140,
    step: int = 10,
    font = cv2.FONT_HERSHEY_SIMPLEX,
    scale: float = 0.40,
    thickness: int = 1,
    preferred_side: str = "left",
    # NEW:
    text_engine: str = "opencv",          # "opencv" | "pillow"
    font_path: Optional[str] = None,
    font_px: Union[int, float] = 16,
    box_extra: int = 2,                   # tiny extra pixels so bg never truncates text
):
    """
    Choose a label box OUTSIDE the overlay that avoids intersecting any overlay or prior labels.
    Side priority uses `preferred_side`: if 'left' -> LEFT, ABOVE, BELOW, RIGHT;
    if 'right' -> RIGHT, ABOVE, BELOW, LEFT. Falls back to least-overlapping candidate.
    """
    H, W = canvas_shape[:2]

    if text_engine.lower() == "pillow":
        tw, ascent, descent = _measure_text_pillow(text, font_path, font_px)
        th, base = ascent, descent        # match draw_text_pillow (org = baseline)
    else:
        (tw, th), base = cv2.getTextSize(text, font, scale, thickness)

    lw = tw + 2 * pad + int(box_extra)
    lh = th + base + 2 * pad

    x1, y1, x2, y2 = anchor_rect_xyxy
    xc = (x1 + x2) // 2
    yc = (y1 + y2) // 2

    def clamp_tl(tlx, tly):
        tlx = int(np.clip(tlx, 0, max(0, W - lw)))
        tly = int(np.clip(tly, 0, max(0, H - lh)))
        return tlx, tly

    def rect_from_tl(tlx, tly):
        return (tlx, tly, tlx + lw, tly + lh)

    def score(rect):
        ox = sum(_rect_overlap_area(rect, r) for r in avoid_rects)
        lx = sum(_rect_overlap_area(rect, r) for r in avoid_labels)
        x1r, y1r, x2r, y2r = rect
        oob = 0
        if x1r < 0: oob += -x1r
        if y1r < 0: oob += -y1r
        if x2r > W: oob += x2r - W
        if y2r > H: oob += y2r - H
        
        # --- MODIFIED DISTANCE METRIC TO USE POLYGON POINTS ---
        if anchor_poly_points:
            # Calculate minimum Euclidean distance from the label candidate box to the polygon.
            dist = _min_distance_to_polygon(rect, anchor_poly_points)
        else:
            # Fallback to the original distance metric (Manhattan distance between rectangles)
            # x1, y1, x2, y2 are from anchor_rect_xyxy
            dx = max(0, x1 - x2r, x1 - x1r, x1r - x2, x2r - x2)
            dy = max(0, y1 - y2r, y1 - y1r, y1r - y2, y2r - y2)
            dist = dx + dy
            
        # Total score: (Overlap) * high_penalty + (Out-of-Bounds) * low_penalty + (Distance)
        return (ox + lx) * 1000 + oob * 100 + dist
        # --- END MODIFIED DISTANCE METRIC ---

    best = None
    candidates_tried = []

    # Build the side order based on preference
    order = ["left", "above", "below", "right"] if (preferred_side.lower() == "left") \
            else ["right", "above", "below", "left"]

    for side in order:
        if side == "left":
            
            # --- NEW EDGE-SLIDING SEARCH ---
            # Replace the old search around (base_tlx, yc) with a search that slides 
            # the label down the vertical extent, dynamically calculating tlx.
            
            slide_step = lh # Use label height as a safe step size for vertical movement
            if slide_step == 0: slide_step = 10 

            # Iterate through a vertical search range (full canvas for max flexibility)
            for tly in range(0, H, slide_step):
                
                # Define the vertical strip corresponding to the label's height.
                y_min, y_max = tly, tly + lh
                
                # Find the LEFTMOST X-coordinate of the polygon that is vertically aligned with the label.
                poly_x_at_y = _find_poly_edge_x(anchor_poly_points, y_min, y_max, "left")
                
                if poly_x_at_y is None:
                    continue # No relevant polygon part found at this height.

                # Calculate the X-position for the label based on this tight edge
                base_tlx = poly_x_at_y - gap - lw
                
                # The label position is now base_tlx, tly. No need for further vertical offsets.
                
                # Clamp X and Y to the canvas boundaries
                tlx, tly = clamp_tl(base_tlx, tly)

                # Check if the result is completely off-canvas
                if tlx + lw <= 0 or tly + lh <= 0:
                    continue

                rect = rect_from_tl(tlx, tly); candidates_tried.append(rect)
                
                # --- ORIGINAL GREEDY RETURN ---
                if not _intersects_any(rect, avoid_rects) and not _intersects_any(rect, avoid_labels):
                    org = (tlx + pad, tly + pad + th)
                    return rect, org

        elif side == "right":
            base_tlx = x2 + gap
            if base_tlx + lw <= W:
                for dy in _fan_offsets(max_shift, step):
                    tly = yc - lh // 2 + dy
                    tlx, tly = clamp_tl(base_tlx, tly)
                    rect = rect_from_tl(tlx, tly); candidates_tried.append(rect)
                    if not _intersects_any(rect, avoid_rects) and not _intersects_any(rect, avoid_labels):
                        org = (tlx + pad, tly + pad + th)
                        return rect, org

        elif side == "above":
            base_tly = y1 - gap - lh
            if base_tly >= 0:
                for dx in _fan_offsets(max_shift, step):
                    tlx = xc - lw // 2 + dx
                    tlx, tly = clamp_tl(tlx, base_tly)
                    rect = rect_from_tl(tlx, tly); candidates_tried.append(rect)
                    if not _intersects_any(rect, avoid_rects) and not _intersects_any(rect, avoid_labels):
                        org = (tlx + pad, tly + pad + th)
                        return rect, org

        elif side == "below":
            base_tly = y2 + gap
            if base_tly + lh <= H:
                for dx in _fan_offsets(max_shift, step):
                    tlx = xc - lw // 2 + dx
                    tlx, tly = clamp_tl(tlx, base_tly)
                    rect = rect_from_tl(tlx, tly); candidates_tried.append(rect)
                    if not _intersects_any(rect, avoid_rects) and not _intersects_any(rect, avoid_labels):
                        org = (tlx + pad, tly + pad + th)
                        return rect, org

    # No perfect candidate — pick the least-overlapping one
    for rect in candidates_tried:
        s = score(rect)
        if best is None or s < best[0]:
            best = (s, rect)

    if best is None:
        tlx, tly = 0, 0
        rect = rect_from_tl(tlx, tly)
    else:
        rect = best[1]
    tlx, tly, _, _ = rect
    org = (tlx + pad, tly + pad + th)
    return rect, org

def _get_polygon_min_area_rect_center_and_bbox(points: List[Tuple[int, int]]) -> Tuple[Tuple[int, int, int, int], Tuple[int, int]]:
    """
    Calculates the tight axis-aligned bounding box and the center of the 
    minimum-area rotating rectangle (MinAreaRect) of a polygon's convex hull.
    Returns: (xyxy_bbox, (cx, cy))
    """
    if not points:
        return (0, 0, 0, 0), (0, 0)
    
    # 1. Convert points to numpy array
    pts = np.array(points, dtype=np.int32)

    # 2. Get the Convex Hull
    # The convex hull simplifies the irregular shape to its outermost boundary points,
    # which is ideal for finding a representative center/rectangle.
    hull = cv2.convexHull(pts)

    # 3. Calculate the Minimum Area Rotating Rectangle (MinAreaRect)
    rect = cv2.minAreaRect(hull)
    
    # 4. Extract the center (cx, cy) from the MinAreaRect
    (cx_float, cy_float), (w, h), angle = rect
    cx, cy = int(round(cx_float)), int(round(cy_float))

    # 5. Calculate the Tight Axis-Aligned Bounding Box (for collision check)
    x_coords = pts[:, 0]
    y_coords = pts[:, 1]
    x1, y1 = np.min(x_coords), np.min(y_coords)
    x2, y2 = np.max(x_coords), np.max(y_coords)
    xyxy_bbox = (int(x1), int(y1), int(x2), int(y2))
        
    return xyxy_bbox, (cx, cy)

def _min_distance_to_polygon(rect_xyxy: Tuple[int, int, int, int], poly_points: List[Tuple[int, int]]) -> float:
    """
    Calculates an approximation of the minimum distance from the label rectangle 
    to the boundary of the polygon defined by poly_points.
    
    This uses the minimum Manhattan distance from any point in the polygon 
    to the closest edge of the label rectangle.
    """
    if not poly_points:
        return 99999
        
    x1r, y1r, x2r, y2r = rect_xyxy
    
    # 1. Define the rectangular area outside the polygon (i.e., the distance to the edge)
    # The distance between two rectangles A (polygon points) and R (label rect)
    # is the sum of the horizontal and vertical separations.
    
    min_dist = float('inf')

    # Calculate distance from each polygon point to the rectangle's boundary
    for px, py in poly_points:
        # dx is the shortest distance from px to the vertical extent of the rect
        dx = 0
        if px < x1r:
            dx = x1r - px
        elif px > x2r:
            dx = px - x2r
            
        # dy is the shortest distance from py to the horizontal extent of the rect
        dy = 0
        if py < y1r:
            dy = y1r - py
        elif py > y2r:
            dy = py - y2r
        
        # We use Euclidean distance for a smoother metric, but Manhattan (dx+dy) works too.
        # Euclidean:
        dist = np.sqrt(dx**2 + dy**2)
        
        # Manhattan:
        # dist = dx + dy 

        min_dist = min(min_dist, dist)
        
    return min_dist

def _find_poly_edge_x(poly_points: List[Tuple[int, int]], y_min: int, y_max: int, side: str) -> Optional[int]:
    """
    Finds the min (for 'left') or max (for 'right') X-coordinate of the polygon
    for all points whose Y-coordinate is between y_min and y_max.
    """
    relevant_x = []
    # NOTE: This is an approximation using polygon vertices, not edges, 
    # but it is a massive improvement over using the full AABB's x1/x2.
    for px, py in poly_points:
        if y_min <= py <= y_max:
            relevant_x.append(px)

    if not relevant_x:
        return None
        
    if side == "left":
        return min(relevant_x)
    elif side == "right":
        return max(relevant_x)
    return None
