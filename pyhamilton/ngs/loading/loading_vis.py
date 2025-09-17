# loading_vis.py
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


ARIAL_TTF = r"C:\Windows\Fonts\arial.ttf"

_FONT_CANDIDATES = [
    ARIAL_TTF,                                  # <- prioritize Arial
    "fonts/Inter-Regular.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]


# ------------------------- Data Models -------------------------

@dataclass
class Region:
    name: str
    top_left: Tuple[int, int]
    bottom_right: Tuple[int, int]
    color_bgr: Tuple[int, int, int]

    @classmethod
    def from_dict(cls, name: str, d: Dict) -> "Region":
        return cls(
            name=name,
            top_left=tuple(map(int, d["top_left"])),
            bottom_right=tuple(map(int, d["bottom_right"])),
            color_bgr=tuple(map(int, d.get("color", (0, 0, 255)))),
        )




# ------------------------- Helpers -------------------------



# ---- ADD: helpers for ASCII labels and colors ----

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
    name = str(info.get("name") or fallback)
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
        dx = max(0, x1 - x2r, x1 - x1r, x1r - x2, x2r - x2)
        dy = max(0, y1 - y2r, y1 - y1r, y1r - y2, y2r - y2)
        dist = dx + dy
        return (ox + lx) * 1000 + oob * 100 + dist

    best = None
    candidates_tried = []

    # Build the side order based on preference
    order = ["left", "above", "below", "right"] if (preferred_side.lower() == "left") \
            else ["right", "above", "below", "left"]

    for side in order:
        if side == "left":
            base_tlx = x1 - gap - lw
            if base_tlx >= 0:
                for dy in _fan_offsets(max_shift, step):
                    tly = yc - lh // 2 + dy
                    tlx, tly = clamp_tl(base_tlx, tly)
                    rect = rect_from_tl(tlx, tly); candidates_tried.append(rect)
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

class ReagentVessel:
    def __init__(self, name: str):
        self.name = name
    
    def layout_name(self):
        return self.name
        

# ------------------------- Visualization -------------------------

class LoadingVis:
    """
    Visualizer that:
      - Loads the base deck image and region metadata from your overlay JSON
      - Optionally loads reagent names/volumes from a separate map JSON
      - Renders overlays only for the vessels you pass in
      - Places labels outside overlays with collision avoidance
      - Offers resizable OpenCV/Tk viewers
    """

    def __init__(
        self,
        image_path_override: Optional[Union[str, Path]] = None,
        scale_to_json_dims: bool = True,
        parent=None,
        *,
        origin_offset: Tuple[int, int] = (0, 0),
        reagent_data: Optional[Union[str, Path, Dict]] = None,
        tip_data: Optional[Union[str, Path, Dict]] = None,
        auto_crop: Union[bool, str] = False,
        crop_margin: int = 12,
    ):
        """
        Parameters
        ----------
        data : str|Path|dict
            Path to overlay JSON or already-parsed dict (with image_path, image_dimensions, regions).
        image_path_override : str|Path|None
            If provided, use this image path instead of the JSON's "image_path".
        scale_to_json_dims : bool
            If True and the JSON provides image_dimensions, resize the base image to match.
        origin_offset : (ox, oy)
            Shift all region coordinates by this offset at load time.
        reagent_data : str|Path|dict|None
            Path/dict with reagent mapping (vessel -> {name, volume, unit}).
        auto_crop : False | "regions" | "uniform"
            Optional cropping to remove borders (see helpers below).
        crop_margin : int
            Padding when auto_crop="regions".
        """

        path = os.path.join(os.path.dirname(__file__), "deck_regions.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._raw = data

        self.parent = parent


        # Resolve base image path
        json_image_path = data.get("image_path")
        if image_path_override:
            img_path = Path(image_path_override)
        else:
            if json_image_path:
                # Resolve image path relative to the same directory as the JSON file
                json_dir = Path(__file__).parent
                # Handle both forward and backward slashes, normalize the path
                normalized_path = json_image_path.replace("\\", "/").lstrip("./")
                img_path = json_dir / normalized_path
                print(f"DEBUG: Looking for image at: {img_path.absolute()}")
                print(f"DEBUG: Image exists: {img_path.exists()}")
            else:
                img_path = Path("")

        self.base_img_bgr = _ensure_bgr(cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED))
        if self.base_img_bgr is None:
            print(f"DEBUG: Failed to load image from: {img_path.absolute()}")
            print(f"DEBUG: Current working directory: {Path.cwd()}")
            print(f"DEBUG: __file__ directory: {Path(__file__).parent}")
            print(f"DEBUG: JSON image_path value: '{json_image_path}'")
            raise FileNotFoundError(f"Could not read base image: {img_path}")       
        # Resize to declared dimensions in the overlay JSON
        dims = data.get("image_dimensions") or {}
        w_decl, h_decl = int(dims.get("width", 0)), int(dims.get("height", 0))
        if scale_to_json_dims and w_decl > 0 and h_decl > 0:
            h0, w0 = self.base_img_bgr.shape[:2]
            if (w0, h0) != (w_decl, h_decl):
                self.base_img_bgr = cv2.resize(self.base_img_bgr, (w_decl, h_decl), interpolation=cv2.INTER_AREA)

        # Parse and normalize regions
        self.regions: Dict[str, Region] = {}
        for name, rd in (data.get("regions") or {}).items():
            region = Region.from_dict(name=name, d=rd)
            self.regions[_norm_key(name)] = region

        # Optional global shift if your JSON coords need nudging
        if origin_offset != (0, 0):
            self._shift_regions(origin_offset)

        # Optional auto-crop to kill borders or trim to content
        if auto_crop:
            if auto_crop == "regions":
                self._crop_to_regions(crop_margin)
            elif auto_crop == "uniform":
                self._auto_trim_uniform_borders(tol=3, max_crop=400)
            else:
                raise ValueError("auto_crop must be False | 'regions' | 'uniform'")

        # ---- Reagent map ----
        self.reagent_units_default: str = "mL"
        self.reagent_map: Dict[str, Dict[str, Any]] = {}
        if reagent_data is not None:
            self._load_reagent_map(reagent_data)

        if tip_data is not None:
            self._load_tip_data(tip_data)


    # ---------- Private utilities ----------

    def _shift_regions(self, offset: Tuple[int, int]) -> None:
        ox, oy = offset
        for r in self.regions.values():
            x1, y1 = r.top_left
            x2, y2 = r.bottom_right
            r.top_left = (x1 + ox, y1 + oy)
            r.bottom_right = (x2 + ox, y2 + oy)

    def _crop_to_regions(self, margin: int = 12) -> None:
        xs1, ys1, xs2, ys2 = [], [], [], []
        for r in self.regions.values():
            x1, y1 = r.top_left
            x2, y2 = r.bottom_right
            if x2 < x1: x1, x2 = x2, x1
            if y2 < y1: y1, y2 = y2, y1
            xs1.append(x1); ys1.append(y1); xs2.append(x2); ys2.append(y2)
        if not xs1:
            return
        H, W = self.base_img_bgr.shape[:2]
        x1 = max(0, min(xs1) - margin)
        y1 = max(0, min(ys1) - margin)
        x2 = min(W, max(xs2) + margin)
        y2 = min(H, max(ys2) + margin)
        self.base_img_bgr = self.base_img_bgr[y1:y2, x1:x2].copy()
        self._shift_regions((-x1, -y1))

    def _auto_trim_uniform_borders(self, tol: int = 3, max_crop: int = 400) -> None:
        """
        Trim uniform-color borders (e.g., white/near-white) from all sides, up to max_crop px.
        Keeps overall framing; good when PNG has baked-in whitespace.
        """
        img = self.base_img_bgr
        H, W = img.shape[:2]
        corners = np.array([img[0,0], img[0,-1], img[-1,0], img[-1,-1]], dtype=np.int16)
        bg = np.median(corners, axis=0)
        diff = np.abs(img.astype(np.int16) - bg[None,None,:]).sum(axis=2)

        def edge_strip(vals):
            # count uniform rows/cols from the edge inwards
            count = 0
            for v in vals:
                if v.mean() <= tol: count += 1
                else: break
            return min(count, max_crop)

        top = edge_strip(diff[:max_crop])
        bottom = edge_strip(diff[::-1][:max_crop])
        left = edge_strip(diff[:, :max_crop].transpose(1,0))
        right = edge_strip(diff[:, ::-1][:,:max_crop].transpose(1,0))

        y1 = top
        y2 = H - bottom
        x1 = left
        x2 = W - right

        if x2 - x1 < 50 or y2 - y1 < 50:
            return  # don't over-trim tiny images

        self.base_img_bgr = img[y1:y2, x1:x2].copy()
        self._shift_regions((-x1, -y1))

    def _create_vessels_from_data(self) -> List[DeckResource]:
        """
        Create vessel objects based on the reagent data loaded.
        This replaces the need to pass vessels externally.
        """
        vessels = []
        
        # Create vessels for each entry in reagent_map that has a corresponding region
        for vessel_key in self.reagent_map.keys():
            if vessel_key in self.regions:
                # Create a simple vessel object with the layout name
                vessel = ReagentVessel(name=self.regions[vessel_key].name)
                vessels.append(vessel)
        
        return vessels


    def _load_reagent_map(self, reagent_data: Union[str, Path, Dict]) -> None:
        """
        Load reagent map that handles both the new position-based format from 
        generate_reagent_summary() and the original complex format.
        """
        if isinstance(reagent_data, (str, Path)):
            with open(reagent_data, "r", encoding="utf-8") as f:
                d = json.load(f)
        else:
            d = reagent_data

        # Default unit used when an entry omits its own "unit"
        self.reagent_units_default = str(d.get("units_default", "mL"))

        # Initialize all the maps that LoadingVis expects
        self.reagent_map: Dict[str, Dict[str, Any]] = {}
        self.tube_rack24_map: Dict[int, Dict[str, Any]] = {}  # Integer keys
        self.plate96_map: Dict[int, Dict[str, Any]] = {}     # Integer keys
        
        # Process each vessel in the data
        for vessel_name, vessel_data in d.items():
            if vessel_name == "units_default":
                continue
                
            vessel_key = _norm_key(vessel_name)
            
            # Check if this is the new position-based format
            if isinstance(vessel_data, dict) and all(isinstance(k, (int, str)) and str(k).isdigit() for k in vessel_data.keys()):
                # New position-based format: vessel_name -> {pos: {reagent, volume, unit}}
                vessel_name_lower = vessel_name.lower()
                
                if "cpac" in vessel_name_lower:
                    # CPAC plate data
                    for pos_str, reagent_info in vessel_data.items():
                        pos = int(pos_str)
                        self.plate96_map[pos] = {
                            "name": reagent_info["reagent"],
                            "volume": reagent_info["volume"],
                            "unit": reagent_info["unit"]
                        }
                    self.has_cpac = True
                    # Add to reagent_map for deck overlay
                    self.reagent_map[vessel_key] = {"name": "CPAC", "volume": None, "unit": self.reagent_units_default}
                    
                elif "smp_car" in vessel_name_lower or "tube" in vessel_name_lower:
                    # Tube rack data
                    for pos_str, reagent_info in vessel_data.items():
                        pos = int(pos_str)
                        self.tube_rack24_map[pos] = {
                            "name": reagent_info["reagent"],
                            "volume": reagent_info["volume"], 
                            "unit": reagent_info["unit"]
                        }
                    
                else:
                    # Main reagent vessels (60mL troughs) - combine all reagents for deck label
                    reagent_names = []
                    total_volume = 0
                    units = []
                    
                    for pos_str, reagent_info in vessel_data.items():
                        reagent_names.append(reagent_info["reagent"])
                        total_volume += reagent_info["volume"]
                        units.append(reagent_info["unit"])
                    
                    if reagent_names:
                        # Use the most common unit, or first one if tied
                        unit = max(set(units), key=units.count) if units else self.reagent_units_default
                        
                        self.reagent_map[vessel_key] = {
                            "name": " + ".join(reagent_names) if len(reagent_names) > 1 else reagent_names[0],
                            "volume": total_volume,
                            "unit": unit
                        }
            
            # Handle old "vessels" format if present
            elif vessel_name == "vessels" and isinstance(vessel_data, dict):
                for sub_vessel_name, reagents in vessel_data.items():
                    sub_vessel_key = _norm_key(sub_vessel_name)
                    
                    if len(reagents) == 1:
                        reagent_name, info = next(iter(reagents.items()))
                        if isinstance(info, dict):
                            self.reagent_map[sub_vessel_key] = {
                                "name": info.get("name", reagent_name),
                                "volume": info.get("volume"),
                                "unit": info.get("unit", self.reagent_units_default)
                            }
                    else:
                        # Multiple reagents - combine names
                        active_reagents = [(name, info) for name, info in reagents.items() 
                                        if (isinstance(info, dict) and info.get("volume", 0) > 0)]
                        
                        if active_reagents:
                            names = [info.get("name", name) for name, info in active_reagents]
                            total_vol = sum(info.get("volume", 0) for name, info in active_reagents)
                            
                            self.reagent_map[sub_vessel_key] = {
                                "name": " + ".join(names),
                                "volume": total_vol,
                                "unit": self.reagent_units_default
                            }
            
            # Handle other direct vessel entries (like specific tube rack or CPAC entries)
            elif isinstance(vessel_data, dict):
                # Check for tube rack or plate data by vessel name
                if vessel_key.startswith("smp_car") or "tube" in vessel_key:
                    for k, info in vessel_data.items():
                        key = int(k)
                        self.tube_rack24_map[key] = info if isinstance(info, dict) else {"name": str(info)}
                elif vessel_key.startswith("cpac") or "cpac" in vessel_key:
                    for k, info in vessel_data.items():
                        key = int(k)
                        self.plate96_map[key] = info if isinstance(info, dict) else {"name": str(info)}
                    self.has_cpac = True
                    # Add to reagent_map for deck overlay
                    self.reagent_map[vessel_key] = {"name": "CPAC", "volume": None, "unit": self.reagent_units_default}

        # Handle legacy Ethanol (top-level)
        eth = d.get("Ethanol") or d.get("ethanol")
        if isinstance(eth, dict):
            self.reagent_map["ethanol"] = {
                "name": eth.get("name", "Ethanol"),
                "volume": eth.get("volume"),
                "unit": eth.get("unit", self.reagent_units_default),
            }
            self.has_ethanol = True
            # Also check for other ethanol vessel naming patterns
            ethanol_keys = ["rgt_ethanol", "rgt ethanol"]
            for possible_key in ethanol_keys:
                norm_key = _norm_key(possible_key)
                if norm_key not in self.reagent_map:
                    self.reagent_map[norm_key] = {
                        "name": "Ethanol",
                        "volume": None,
                        "unit": self.reagent_units_default
                    }


    def show_consumables_summary(
        self,
        title: str = "Consumables Summary",
        min_size: Tuple[int, int] = (700, 500),
        offset: Tuple[int, int] = (100, 100),
    ) -> None:
        """
        Show a text-based consumables summary window before the visual dialogues.
        """
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        root = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        root.title(title)
        root.geometry(f"{min_size[0]}x{min_size[1]}+{offset[0]}+{offset[1]}")
        root.resizable(True, True)

        # Create main frame with padding
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Protocol Consumables Summary", 
                            font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 15))

        # Create scrollable text widget
        text_widget = scrolledtext.ScrolledText(
            main_frame, 
            wrap=tk.WORD, 
            font=('Consolas', 10),
            bg='white',
            fg='black',
            padx=10,
            pady=10
        )
        text_widget.pack(fill="both", expand=True, pady=(0, 15))

        # Generate summary text
        summary_text = self._generate_consumables_summary()
        text_widget.insert(tk.END, summary_text)
        text_widget.config(state=tk.DISABLED)  # Make read-only

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 0))

        # Variable to track if OK was clicked
        ok_clicked = False

        def on_ok():
            nonlocal ok_clicked
            ok_clicked = True
            root.quit()  # Exit mainloop but don't destroy window yet

        def on_close():
            nonlocal ok_clicked
            ok_clicked = True
            root.quit()

        ok_button = ttk.Button(
            button_frame, 
            text="OK", 
            command=on_ok
        )
        ok_button.pack(side="right")

        # Handle window close button (X)
        root.protocol("WM_DELETE_WINDOW", on_close)

        # Center the window, show it, and wait for user interaction
        root.update_idletasks()
        if self.parent is None:
            root.mainloop()
        
        # Clean up - destroy the window after mainloop exits
        try:
            root.destroy()
        except tk.TclError:
            pass  # Window already destroyed

    def _generate_consumables_summary(self) -> str:
        """Generate formatted text summary of all consumables."""
        lines = []
        lines.append("=" * 80)
        lines.append("PROTOCOL CONSUMABLES REQUIRED")
        lines.append("=" * 80)
        lines.append("")

        # Deck reagent vessels (60mL troughs)
        deck_vessels = []
        for vessel_key, reagent_info in self.reagent_map.items():
            # Skip tube rack and plate entries
            if not (vessel_key.startswith("smp_car") or "cpac" in vessel_key or "tube" in vessel_key):
                deck_vessels.append((vessel_key, reagent_info))

        if deck_vessels:
            lines.append("DECK REAGENT VESSELS (60mL Troughs)")
            lines.append("-" * 50)
            for vessel_key, reagent_info in sorted(deck_vessels):
                name = reagent_info.get("name", vessel_key)
                volume = reagent_info.get("volume")
                unit = reagent_info.get("unit", self.reagent_units_default)
                
                # Format vessel identifier nicely
                vessel_display = vessel_key.replace("_", " ").title()
                if vessel_key.startswith("rgt_cont_60ml"):
                    # Extract position number for cleaner display
                    parts = vessel_key.split("_")
                    if len(parts) >= 5:
                        pos = parts[-1]
                        vessel_display = f"60mL Trough Position {pos}"
                
                lines.append(f"  {vessel_display}:")
                lines.append(f"    Reagent: {name}")
                if volume is not None and volume > 0:
                    lines.append(f"    Volume:  {volume:,.3f} {unit}".rstrip("0").replace(".000", ""))
                else:
                    lines.append(f"    Volume:  TBD")
                lines.append("")
            lines.append("")

        # Tube rack reagents
        if hasattr(self, 'tube_rack24_map') and self.tube_rack24_map:
            lines.append("TUBE RACK (24-Position)")
            lines.append("-" * 30)
            lines.append("Position  Reagent                    Volume")
            lines.append("--------  -------------------------  ---------------")
            
            for pos in sorted(self.tube_rack24_map.keys()):
                reagent_info = self.tube_rack24_map[pos]
                name = reagent_info.get("name", f"Position {pos+1}")
                volume = reagent_info.get("volume")
                unit = reagent_info.get("unit", self.reagent_units_default)
                
                pos_str = f"{pos+1:02d}"
                name_str = name[:25]  # Truncate if too long
                
                if volume is not None:
                    try:
                        vol_num = float(volume)
                        if vol_num > 0:
                            vol_str = f"{vol_num:,.3f} {unit}".rstrip("0").replace(".000", "")
                        else:
                            vol_str = "TBD"
                    except (ValueError, TypeError):
                        vol_str = str(volume)
                else:
                    vol_str = "TBD"
                    
                lines.append(f"  {pos_str:>6}  {name_str:<25}  {vol_str}")
            lines.append("")

        # 96-well plate reagents
        if hasattr(self, 'plate96_map') and self.plate96_map:
            lines.append("96-WELL PLATE (CPAC)")
            lines.append("-" * 25)
            lines.append("Well   Reagent                    Volume")
            lines.append("-----  -------------------------  ---------------")
            
            # Convert positions to well notation and sort
            well_entries = []
            for pos, reagent_info in self.plate96_map.items():
                # Convert position to well notation (A1, B1, etc.)
                row = pos % 8  # 0-7
                col = pos // 8  # 0-11
                well_notation = f"{chr(ord('A') + row)}{col + 1}"
                well_entries.append((well_notation, reagent_info))
            
            # Sort by column first, then row (A1, A2, ... B1, B2, ...)
            well_entries.sort(key=lambda x: (int(x[0][1:]), x[0][0]))
            
            for well_notation, reagent_info in well_entries:
                name = reagent_info.get("name", well_notation)
                volume = reagent_info.get("volume")
                unit = reagent_info.get("unit", self.reagent_units_default)
                
                name_str = name[:25]  # Truncate if too long
                
                if volume is not None:
                    try:
                        vol_num = float(volume)
                        if vol_num > 0:
                            vol_str = f"{vol_num:,.3f} {unit}".rstrip("0").replace(".000", "")
                        else:
                            vol_str = "TBD"
                    except (ValueError, TypeError):
                        vol_str = str(volume)
                else:
                    vol_str = "TBD"
                    
                lines.append(f"  {well_notation:>4}   {name_str:<25}  {vol_str}")
            lines.append("")

        # Summary statistics
        lines.append("SUMMARY")
        lines.append("-" * 15)
        
        deck_count = len(deck_vessels)
        tube_count = len(self.tube_rack24_map) if hasattr(self, 'tube_rack24_map') else 0
        plate_count = len(self.plate96_map) if hasattr(self, 'plate96_map') else 0
        
        lines.append(f"Deck vessels required:     {deck_count}")
        lines.append(f"Tube rack positions used:  {tube_count}/24")
        lines.append(f"Plate wells used:          {plate_count}/96")
        lines.append(f"Total reagent containers:  {deck_count + tube_count + plate_count}")
        lines.append("")
        
        lines.append("NOTE: Ensure all reagents are prepared and loaded before")
        lines.append("      starting the protocol. TBD volumes should be determined")
        lines.append("      based on your specific protocol requirements.")
        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _load_tip_data(self, tip_data: Union[str, Path, Dict]) -> None:
        """
        Load tip consumption data and store for visualization.
        """
        if isinstance(tip_data, (str, Path)):
            with open(tip_data, "r", encoding="utf-8") as f:
                d = json.load(f)
        else:
            d = tip_data
        
        self.tip_data = d
        self.has_tip_data = bool(d.get("tip_trackers"))

    def show_tips_summary(
        self,
        title: str = "Tip Consumption Summary",
        min_size: Tuple[int, int] = (800, 600),
        offset: Tuple[int, int] = (200, 150),
    ) -> None:
        """
        Show tip consumption summary window.
        """
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        if not hasattr(self, 'tip_data') or not self.tip_data:
            print("No tip data available for display")
            return

        root = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        root.title(title)
        root.geometry(f"{min_size[0]}x{min_size[1]}+{offset[0]}+{offset[1]}")
        root.resizable(True, True)

        # Create main frame with padding
        main_frame = ttk.Frame(root, padding="20")
        main_frame.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Tip Consumption Report", 
                            font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 15))

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill="both", expand=True, pady=(0, 15))

        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Summary")
        
        summary_text = scrolledtext.ScrolledText(
            summary_frame, 
            wrap=tk.WORD, 
            font=('Consolas', 10),
            bg='white',
            fg='black',
            padx=10,
            pady=10
        )
        summary_text.pack(fill="both", expand=True)
        
        # Generate and insert summary
        summary_content = self._generate_tip_summary()
        summary_text.insert(tk.END, summary_content)
        summary_text.config(state=tk.DISABLED)

        # Details tab
        details_frame = ttk.Frame(notebook)
        notebook.add(details_frame, text="Rack Details")
        
        # Create treeview for detailed rack information
        tree_frame = ttk.Frame(details_frame)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Treeview with scrollbars
        tree_scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
        tree_scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        tree = ttk.Treeview(tree_frame, 
                        columns=("Tracker", "Capacity", "Total", "Used", "Remaining", "Usage%"),
                        show="tree headings",
                        yscrollcommand=tree_scroll_y.set,
                        xscrollcommand=tree_scroll_x.set)
        
        tree_scroll_y.config(command=tree.yview)
        tree_scroll_x.config(command=tree.xview)
        
        # Configure columns
        tree.heading("#0", text="Rack Name")
        tree.heading("Tracker", text="Tracker")
        tree.heading("Capacity", text="Capacity (µL)")
        tree.heading("Total", text="Total Tips")
        tree.heading("Used", text="Tips Used")
        tree.heading("Remaining", text="Tips Remaining") 
        tree.heading("Usage%", text="Usage %")
        
        tree.column("#0", width=200)
        tree.column("Tracker", width=150)
        tree.column("Capacity", width=100)
        tree.column("Total", width=80)
        tree.column("Used", width=80)
        tree.column("Remaining", width=100)
        tree.column("Usage%", width=80)
        
        # Populate tree with tip data
        self._populate_tip_tree(tree)
        
        tree.pack(fill="both", expand=True)
        tree_scroll_y.pack(side="right", fill="y")
        tree_scroll_x.pack(side="bottom", fill="x")

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")

        ok_clicked = False

        def on_ok():
            nonlocal ok_clicked
            ok_clicked = True
            root.quit()

        def on_close():
            nonlocal ok_clicked
            ok_clicked = True
            root.quit()

        ok_button = ttk.Button(button_frame, text="OK", command=on_ok)
        ok_button.pack(side="right")

        root.protocol("WM_DELETE_WINDOW", on_close)
        root.update_idletasks()
        if self.parent is None:
            root.mainloop()
        
        try:
            root.destroy()
        except tk.TclError:
            pass

    def _generate_tip_summary(self) -> str:
        """Generate formatted text summary of tip consumption."""
        if not hasattr(self, 'tip_data') or not self.tip_data:
            return "No tip data available."
        
        lines = []
        lines.append("=" * 80)
        lines.append("TIP CONSUMPTION SUMMARY")
        lines.append("=" * 80)
        
        if "report_generated" in self.tip_data:
            from datetime import datetime
            try:
                report_time = datetime.fromisoformat(self.tip_data["report_generated"])
                lines.append(f"Generated: {report_time.strftime('%Y-%m-%d %H:%M:%S')}")
            except:
                lines.append(f"Generated: {self.tip_data['report_generated']}")
        lines.append("")
        
        # Overall summary
        summary = self.tip_data.get("summary", {})
        lines.append("OVERALL STATISTICS")
        lines.append("-" * 30)
        lines.append(f"Total Trackers:        {summary.get('total_trackers', 0)}")
        lines.append(f"Total Tip Capacity:    {summary.get('total_tips_capacity', 0):,}")
        lines.append(f"Tips Consumed:         {summary.get('total_tips_consumed', 0):,}")
        lines.append(f"Tips Remaining:        {summary.get('total_tips_available', 0):,}")
        lines.append(f"Overall Usage Rate:    {summary.get('overall_consumption_rate', 0):.1f}%")
        lines.append("")
        
        # Individual trackers
        trackers = self.tip_data.get("tip_trackers", {})
        if trackers:
            lines.append("TRACKER DETAILS")
            lines.append("=" * 50)
            
            for tracker_key, tracker_data in trackers.items():
                lines.append(f"Tracker: {tracker_data.get('tracker_id', tracker_key)}")
                lines.append("-" * 40)
                lines.append(f"Volume Capacity:  {tracker_data.get('volume_capacity', 'Unknown')} µL")
                lines.append(f"Total Tips:       {tracker_data.get('total_tips', 0):,}")
                lines.append(f"Tips Consumed:    {tracker_data.get('tips_consumed', 0):,} ({tracker_data.get('consumption_rate', 0):.1f}%)")
                lines.append(f"Tips Remaining:   {tracker_data.get('tips_remaining', 0):,}")
                lines.append(f"Number of Racks:  {tracker_data.get('num_racks', 0)}")
                lines.append("")
                
                # Rack breakdown if multiple racks
                racks = tracker_data.get("racks", [])
                if len(racks) > 1:
                    lines.append("  Rack Breakdown:")
                    for rack in racks:
                        lines.append(f"    {rack.get('name', 'Unknown')}: "
                                f"{rack.get('tips_consumed', 0)}/{rack.get('total_tips', 0)} consumed "
                                f"({rack.get('consumption_rate', 0):.1f}%)")
                    lines.append("")
        
        lines.append("=" * 80)
        lines.append("NOTE: Ensure adequate tip supply is available before starting protocol.")
        lines.append("Consider having backup tip boxes ready for long protocols.")
        
        return "\n".join(lines)

    def _populate_tip_tree(self, tree):
        """Populate the treeview with tip rack details."""
        if not hasattr(self, 'tip_data') or not self.tip_data:
            return
        
        trackers = self.tip_data.get("tip_trackers", {})
        
        for tracker_key, tracker_data in trackers.items():
            tracker_id = tracker_data.get('tracker_id', tracker_key)
            
            # Add tracker as parent node
            tracker_node = tree.insert("", "end", text=f"Tracker: {tracker_id}", 
                                    values=("", f"{tracker_data.get('volume_capacity', 0)}", 
                                            f"{tracker_data.get('total_tips', 0):,}",
                                            f"{tracker_data.get('tips_consumed', 0):,}",
                                            f"{tracker_data.get('tips_remaining', 0):,}",
                                            f"{tracker_data.get('consumption_rate', 0):.1f}%"))
            
            # Add individual racks as children
            racks = tracker_data.get("racks", [])
            for rack in racks:
                tree.insert(tracker_node, "end", text=f"  {rack.get('name', 'Unknown Rack')}", 
                        values=(tracker_id, f"{tracker_data.get('volume_capacity', 0)}",
                                f"{rack.get('total_tips', 0)}",
                                f"{rack.get('tips_consumed', 0)}",
                                f"{rack.get('tips_remaining', 0)}",
                                f"{rack.get('consumption_rate', 0):.1f}%"))

    @property 
    def has_tip_consumption_data(self) -> bool:
        """Check if tip consumption data is loaded."""
        return hasattr(self, 'tip_data') and bool(self.tip_data.get('tip_trackers'))


    def render_tube_rack_24_screen(
        self,
        *,
        width: int = 700,
        height: int = 1000,
        margin_left: int = 80,
        margin_right: int = 260,   # space for label gutter
        margin_v: int = 60,
        tube_radius: int = 14,
        font_scale: float = 0.40,
        font_thickness: int = 1,
        pad: int = 3,
        gap: int = 8,
        render_scale: float = 1.25,   # draw a bit larger for crisp edges/text
        zoom_y: float = 2.0,          # 2× vertical zoom
        index_px: int = 14,           # readable tube index size
    ) -> np.ndarray:
        """
        Zoomed tube-rack screen (24 tubes in one column). White background, grey rack,
        black text. Reagent labels are vertically aligned to their tube centers and
        only pushed horizontally if needed to avoid overlaps.
        """
        s = float(render_scale)
        zy = float(zoom_y)

        # Scales
        W = int(round(width * s))
        H = int(round(height * s * zy))
        ml = int(round(margin_left * s))
        mr = int(round(margin_right * s))
        mv = int(round(margin_v * s * zy))
        r  = int(round(tube_radius * s * zy))

        fs = font_scale * s * zy      # OpenCV-fallback metric (not used for drawing)
        pt = max(1, int(round(pad * s)))
        gp = max(1, int(round(gap * s)))

        canvas = np.full((H, W, 3), 255, np.uint8)

        rows = 24
        usable_h = H - 2 * mv
        step_y = usable_h / rows
        cx = ml + r + int(round(10 * s))  # tube center x

        overlay_rects = []
        placed_label_rects = []

        # --- Grey rack background behind the tubes ---
        rack_pad_x = int(round(20 * s))
        rack_pad_y = int(round(12 * s))
        rack_x1 = cx - r - rack_pad_x
        rack_x2 = cx + r + rack_pad_x
        rack_y1 = mv - rack_pad_y
        rack_y2 = mv + rows * step_y + rack_pad_y
        rack_y2 = int(round(rack_y2))
        rack_rect = (max(0, int(rack_x1)), max(0, int(rack_y1)), min(W, int(rack_x2)), min(H, int(rack_y2)))
        cv2.rectangle(canvas, (rack_rect[0], rack_rect[1]), (rack_rect[2], rack_rect[3]), (230, 230, 230), thickness=-1)

        # Title
        title = _ascii_label("Tube Rack (24) - provide reagents")
        title_px = 16
        draw_text_pillow(canvas, title, (ml, int(round(36 * s))), font_path=ARIAL_TTF, px=title_px, color=(0, 0, 0))

        # Avoid placing labels on top of the rack or tube circles
        overlay_rects.append(rack_rect)

        # Font to use for labels/indices
        try:
            font_fp = ARIAL_TTF if Path(ARIAL_TTF).is_file() else next((p for p in _FONT_CANDIDATES if Path(p).is_file()), None)
        except Exception:
            font_fp = None

        # --- Draw tubes + indexes + labels (with vertical alignment) ---
        for i in range(rows):
            y = int(round(mv + (i + 0.5) * step_y))
            display_key = f"{i+1:02d}"  # Display as "01", "02", etc.

            # Tube - use integer key for lookup
            info = self.tube_rack24_map.get(i)
            color = (200, 200, 200) if not info else _name_to_color_bgr(info.get("name", display_key))
            cv2.circle(canvas, (cx, y), r, color, thickness=-1)
            cv2.circle(canvas, (cx, y), r, (30, 30, 30), thickness=max(1, int(round(1 * s))))

            # Tube circle bbox as avoidance
            x1, y1 = cx - r, y - r
            x2, y2 = cx + r, y + r
            overlay_rects.append((x1, y1, x2, y2))

            # Tube index (left of rack) - display the formatted version
            idx_px = max(10, int(round(index_px * s)))
            idx_x  = max(8, rack_rect[0] - int(round(18 * s)))
            draw_text_pillow(canvas, display_key, (idx_x, y + int(round(6 * s))), font_path=font_fp or ARIAL_TTF, px=idx_px, color=(0, 0, 0))

            # Reagent label (RIGHT of rack), vertically aligned to tube center
            if info:
                label_text = _label_from_info_dict(info, unit_default=self.reagent_units_default, fallback=display_key)

                # Measure with Pillow to get ascent/descent for exact baseline alignment
                tw, ascent, descent = _measure_text_pillow(label_text, font_fp or ARIAL_TTF, title_px)
                lw = tw + 2 * pt + 3                      # +3px safety
                lh = ascent + descent + 2 * pt

                # Baseline aligned to the tube center:
                y_base = int(round(y + (ascent - descent) / 2.0))
                # Start to the right of the rack, then push horizontally if needed
                tlx = rack_rect[2] + max(gp, int(round(10 * s)))
                tly = y_base - ascent - pt

                # Keep vertical position fixed; only push right to avoid overlaps
                step_x = max(6, int(round(10 * s)))
                max_push = int(round(300 * s))
                pushed = 0
                rect = (tlx, tly, tlx + lw, tly + lh)
                while (_intersects_any(rect, overlay_rects) or _intersects_any(rect, placed_label_rects)) and pushed <= max_push:
                    tlx += step_x
                    pushed += step_x
                    rect = (tlx, tly, tlx + lw, tly + lh)

                # Draw just the text (no black box for the rack list)
                org = (tlx + pt, y_base)
                draw_text_pillow(canvas, label_text, org, font_path=font_fp or ARIAL_TTF, px=title_px, color=(0, 0, 0))
                placed_label_rects.append(rect)

        # Trim right whitespace to content
        content_rights = [x2 for (_, _, x2, _) in overlay_rects] + [x2 for (_, _, x2, _) in placed_label_rects] or [cx + r]
        used_right = max(content_rights)
        pad_right  = int(round(24 * s))
        new_W = min(W, max(ml + 2 * r + pad_right, used_right + pad_right))
        if new_W < W:
            canvas = canvas[:, :new_W].copy()

        return canvas


    def render_plate_96_screen(
        self,
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
        render_scale: float = 1.25,   # draw larger for crisp text
        output_scale: float = 1.0,    # final scale (keep 1.0 for this screen)
    ) -> np.ndarray:
        """
        Programmatic screen: 96-well plate (12x8). Uses integer indices internally
        but displays well notation (A1, B1, etc.) for the user.
        """
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

        # title
        title = _ascii_label("CPAC - provide reagents")
        label_px = 16
        draw_text_pillow(
            canvas, title, (ml, int(round(36 * s))),
            font_path=ARIAL_TTF,   # <- use Arial
            px=label_px,           # <- integer pixel height, not a 0.xx scale
            color=(0, 0, 0)        # BGR (black on white screens), or (255,255,255) if needed
        )
        # grid origin
        origin_x = ml
        origin_y = mt

        # outer border
        cv2.rectangle(canvas, (origin_x, origin_y), (origin_x + cols*cw, origin_y + rows*ch), (0,0,0), max(1, int(round(2*s))))

        # internal grid
        for c in range(1, cols):
            x = origin_x + c * cw
            cv2.line(canvas, (x, origin_y), (x, origin_y + rows*ch), (200,200,200), gt)
        for r in range(1, rows):
            y = origin_y + r * ch
            cv2.line(canvas, (origin_x, y), (origin_x + cols*cw, y), (200,200,200), gt)

        # headers
        for c in range(cols):
            label = str(c+1)
            tx = origin_x + c*cw + cw//2 - int(round(6*s))*len(label)//2
            draw_text_pillow(
                canvas, label, (tx, origin_y - int(round(12*s))),
                font_path=ARIAL_TTF,   # <- use Arial
                px=label_px,           # <- integer pixel height, not a 0.xx scale
                color=(0, 0, 0)        # BGR (black on white screens), or (255,255,255) if needed
            )
        row_letters = "ABCDEFGH"
        for r in range(rows):
            label = row_letters[r]
            ty = origin_y + r*ch + ch//2 + int(round(6*s))//2
            draw_text_pillow(
                canvas, label, (origin_x - int(round(28*s)), ty),
                font_path=ARIAL_TTF,   # <- use Arial
                px=label_px,           # <- integer pixel height, not a 0.xx scale
                color=(0, 0, 0)        # BGR (black on white screens), or (255,255,255) if needed
            )

        # wells (colored only, NO labels near wells)
        filled_entries = []  # list of (well_notation, info, color, pos)
        for r in range(rows):
            for c in range(cols):
                cx = origin_x + c*cw + cw//2
                cy = origin_y + r*ch + ch//2
                pos = c * rows + r  # FIXED: Column-first indexing (c * rows + r)
                well_notation = f"{row_letters[r]}{c+1}"  # Display format
                
                # Use integer key for lookup
                info = self.plate96_map.get(pos)
                color = (220, 220, 220) if not info else _name_to_color_bgr(info.get("name", well_notation))
                cv2.circle(canvas, (cx, cy), wr, color, thickness=-1)
                cv2.circle(canvas, (cx, cy), wr, (40,40,40), thickness=max(1, int(round(1*s))))
                if info:
                    filled_entries.append((well_notation, info, color, pos))

        # legend separator
        x_gutter = origin_x + cols*cw + int(round(4 * s))

        # legend items
        # sort by position (integer order)
        def _well_sort_key_column_first(entry):
            well_notation, info, color, pos = entry
            row = ord(well_notation[0]) - ord('A')  # A=0, B=1, etc.
            col = int(well_notation[1:]) - 1        # 1=0, 2=1, etc.
            return (col, row)  # Sort by column first, then row

        filled_entries.sort(key=_well_sort_key_column_first)

        # layout
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

            # text: "A1: Name - 100 uL"
            label_text = _label_from_info_dict(info, unit_default=self.reagent_units_default, fallback=well_notation)
            legend_text = _ascii_label(f"{well_notation}: {label_text}")
            org = (x + sw + int(round(10*s)), y + sh - max(1, int(round(2*s))))
            draw_text_pillow(
                canvas, legend_text, org,
                font_path=ARIAL_TTF,   # <- use Arial
                px=label_px,           # <- integer pixel height, not a 0.xx scale
                color=(0, 0, 0)        # BGR (black on white screens), or (255,255,255) if needed
            )

        final = _rescale_image(canvas, output_scale / s)
        return final
    # ---------- Public API ----------

    def render(
        self,
        vessels: Optional[List[DeckResource]] = None,  # Make optional
        *,
        alpha: float = 0.35,
        draw_labels: bool = True,
        label_from: str = "label_then_entity",
        copy_base: bool = True,
        prefer_reagent_map: bool = True,
        # NEW knobs:
        font_scale: float = 0.40,        # retained for OpenCV fallback use
        font_thickness: int = 1,
        pad: int = 3,                    # smaller padding
        gap: int = 6,                    # distance from overlay to label box
    ) -> np.ndarray:
        """
        Render overlays. If no vessels provided, automatically create them from reagent data.
        """
        canvas = self.base_img_bgr.copy() if copy_base else self.base_img_bgr

        # Auto-create vessels if none provided
        if vessels is None:
            vessels = self._create_vessels_from_data()

        # Rest of the method stays the same...
        items = []  # (region, color_bgr, label_text)
        for v in vessels:
            key_norm = _norm_key(v.layout_name())
            region = self.regions.get(key_norm)
            if not region:
                continue
            
            color = region.color_bgr

            # Generate label text from reagent map if available
            if prefer_reagent_map and key_norm in self.reagent_map:
                reagent_info = self.reagent_map[key_norm]
                name = reagent_info.get("name", region.name)
                volume = reagent_info.get("volume")
                unit = reagent_info.get("unit", self.reagent_units_default)
                
                # Special aliases for specific vessels
                if key_norm.startswith("cpac") or "cpac" in key_norm:
                    label_text = _ascii_label("CPAC")
                elif key_norm == "ethanol" or "ethanol" in key_norm:
                    label_text = _ascii_label("Ethanol")
                elif volume is not None and volume > 0:
                    # Format volume nicely for other vessels
                    try:
                        vol_num = float(volume)
                        vol_str = f"{vol_num:.3f}".rstrip("0").rstrip(".")
                    except (ValueError, TypeError):
                        vol_str = str(volume)
                    
                    label_text = _ascii_label(f"{name}, {vol_str} {unit}")
                else:
                    label_text = _ascii_label(name)
            else:
                # Fallback to region name
                label_text = _ascii_label(region.name)
            
            items.append((region, color, label_text))

        # Draw overlay rectangles first
        for region, color, _ in items:
            _draw_transparent_rect(canvas, region.top_left, region.bottom_right, color, alpha=alpha, thickness=-1)

        if not draw_labels:
            return canvas

        # Build avoidance sets
        overlay_rects = [_rect_xyxy(r.top_left, r.bottom_right) for (r, _, _) in items]
        placed_label_rects = []

        # Use the same font + px for measuring and drawing
        label_px = 16
        try:
            font_fp = ARIAL_TTF if Path(ARIAL_TTF).is_file() else next(
                (p for p in _FONT_CANDIDATES if Path(p).is_file()), None
            )
        except Exception:
            font_fp = None

        # Place/draw labels with collision avoidance (no connecting lines)
        for region, color, label_text in items:
            anchor_xyxy = _rect_xyxy(region.top_left, region.bottom_right)

            # Decide side from vessel ID
            preferred_side = _preferred_side_for_key(_norm_key(region.name))

            label_rect, org = _best_label_box_outside(
                canvas.shape,
                anchor_xyxy,
                label_text,
                avoid_rects=overlay_rects,
                avoid_labels=placed_label_rects,
                pad=4,
                gap=6,
                max_shift=160,
                step=10,
                preferred_side=preferred_side,
                text_engine="pillow",
                font_path=font_fp,
                font_px=label_px,
                box_extra=3,
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=font_scale,
                thickness=font_thickness,
            )
            x1, y1, x2, y2 = label_rect
            cv2.rectangle(canvas, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)

            draw_text_pillow(
                canvas, label_text, org,
                font_path=font_fp or ARIAL_TTF,
                px=label_px,
                color=(255, 255, 255)
            )
            placed_label_rects.append(label_rect)

        return canvas
    
    def show(
        self,
        img_bgr: np.ndarray,
        window_name: str = "LoadingVis",
        scale: Optional[float] = None,
        wait_ms: int = 0,
        resizable: bool = True,
    ) -> None:
        """
        Show the image in an OpenCV window. If resizable=True, creates a WINDOW_NORMAL
        (drag handles) and sizes it to the image.
        """
        disp = img_bgr
        if scale and scale > 0:
            h, w = img_bgr.shape[:2]
            disp = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        if resizable:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_EXPANDED)
            h0, w0 = disp.shape[:2]
            cv2.resizeWindow(window_name, w0, h0)
        else:
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

        cv2.imshow(window_name, disp)
        cv2.waitKey(wait_ms)

    def show_tk_scrollable(
        self,
        img_bgr: np.ndarray,
        title: str = "Tube Rack",
        viewport: Tuple[int, int] = (800, 700),   # requested window size
        offset: Tuple[int, int] = (360, 160),     # <— NEW: screen position (x, y)
        shrink_to_image_width: bool = True,       # <— NEW: avoid right whitespace
    ) -> None:
        import tkinter as tk
        from PIL import Image, ImageTk

        # Convert once
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_src = Image.fromarray(img_rgb)
        W, H = pil_src.size

        root = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        root.title(title)
        root.resizable(True, True)

        req_w, req_h = viewport
        view_w = min(req_w, W) if shrink_to_image_width else req_w  # << keep window no wider than image
        view_h = req_h

        # Position the window to the right a bit
        win_x, win_y = offset
        root.geometry(f"{view_w}x{view_h}+{win_x}+{win_y}")

        # Scrollbar + canvas
        vbar = tk.Scrollbar(root, orient="vertical")
        vbar.pack(side="right", fill="y")

        canvas = tk.Canvas(root, width=view_w, height=view_h, highlightthickness=0, bd=0, bg="white")
        canvas.pack(side="left", fill="both", expand=True)

        vbar.config(command=canvas.yview)
        canvas.config(yscrollcommand=vbar.set)

        # Put the full image in the canvas; set scrollregion to full image size
        photo = ImageTk.PhotoImage(pil_src)
        img_id = canvas.create_image(0, 0, image=photo, anchor="nw")
        canvas.image = photo
        canvas.config(scrollregion=(0, 0, W, H))

        # Mouse wheel support
        def _on_mousewheel(event):
            # Windows / Mac
            delta = -1 * int(getattr(event, "delta", 0) / 120)  # typical 120-step ticks
            canvas.yview_scroll(delta, "units")
        def _on_linux_scroll(event):
            # Linux buttons 4/5
            delta = -1 if event.num == 4 else 1
            canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)       # Windows/Mac
        canvas.bind_all("<Button-4>", _on_linux_scroll)       # Linux up
        canvas.bind_all("<Button-5>", _on_linux_scroll)       # Linux down

        if self.parent is None:
            root.mainloop()


    def show_tk(
        self,
        img_bgr: np.ndarray,
        title: str = "LoadingVis",
        parent=None,
        min_size: Tuple[int,int] = (600, 400),
    ) -> None:
        """
        Optional Tk viewer that resizes content with the window (requires Pillow).
        """
        import tkinter as tk
        from PIL import Image, ImageTk

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_src = Image.fromarray(img_rgb)

        root = parent if parent is not None else (tk.Toplevel(self.parent) if self.parent else tk.Tk())
        root.title(title)
        root.minsize(*min_size)
        root.resizable(True, True)

        canvas = tk.Canvas(root, highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)

        photo = ImageTk.PhotoImage(pil_src)
        img_id = canvas.create_image(0, 0, image=photo, anchor="nw")
        canvas.image = photo  # keep ref

        def on_resize(ev):
            if ev.width < 2 or ev.height < 2:
                return
            resized = pil_src.resize((ev.width, ev.height), Image.LANCZOS)
            photo2 = ImageTk.PhotoImage(resized)
            canvas.itemconfigure(img_id, image=photo2)
            canvas.config(width=ev.width, height=ev.height)
            canvas.image = photo2  # keep ref

        canvas.bind("<Configure>", on_resize)

        if self.parent is None:
            root.mainloop()

    def save(self, img_bgr: np.ndarray, out_path: Union[str, Path]) -> None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(out_path), img_bgr):
            raise IOError(f"Failed to write image to {out_path}")

    def missing_for(self, vessels: List[DeckResource]) -> List[str]:
        """Return entity names that don't have a matching region."""
        missing = []
        for v in vessels:
            if _norm_key(v.layout_name()) not in self.regions:
                missing.append(v.layout_name())
        return missing

    @property
    def has_tube_rack_data(self) -> bool:
        """Check if there's any actual reagent data in the tube rack."""
        return bool(self.tube_rack24_map)


    def show_dialogues(
        self,
        vessels: Optional[List[DeckResource]] = None,
        *,
        # --- NEW: Summary stage options ---
        summary_enabled: bool = True,
        summary_title: str = "Consumables Summary", 
        summary_size: Tuple[int, int] = (700, 500),
        summary_offset: Tuple[int, int] = (100, 100),
        
        # --- Deck stage options ---
        deck_enabled: bool = True,
        deck_window_name: str = "Deck",
        deck_alpha: float = 0.40,
        deck_draw_labels: bool = True,
        deck_prefer_reagent_map: bool = True,
        deck_scale: float = 1.0,
        deck_resizable: bool = True,

        tips_enabled: bool = True, 
        tips_title: str = "Tip Consumption Summary",
        tips_size: Tuple[int, int] = (800, 600), 
        tips_offset: Tuple[int, int] = (200, 150),

        # --- Tube rack stage options ---
        tube_enabled: bool = True,  # Will be auto-disabled if no data
        tube_title: str = "Tube Rack (Scrollable)",
        tube_render_scale: float = 1.25,
        tube_zoom_y: float = 1.5,
        tube_viewport: Tuple[int, int] = (800, 700),
        tube_offset: Tuple[int, int] = (360, 60),

        # --- Plate stage options ---
        plate_enabled: bool = True,
        plate_window_name: str = "96-well Plate",
        plate_render_scale: float = 1.25,
        plate_output_scale: float = 1.0,
        plate_scale_in_window: float = 1.0,
        plate_resizable: bool = True,

        # --- Cleanup ---
        destroy_windows: bool = True,
    ) -> None:
        """
        Show visualization stages. Now includes consumables summary first.
        """
        import cv2

        # Auto-create vessels if none provided
        if vessels is None:
            vessels = self._create_vessels_from_data()

        # Auto-disable tube rack if no data
        show_tube_rack = tube_enabled and self.has_tube_rack_data

        show_tips = tips_enabled and self.has_tip_consumption_data

        # 0) Consumables summary (NEW - first stage)
        if summary_enabled:
            self.show_consumables_summary(
                title=summary_title,
                min_size=summary_size,
                offset=summary_offset
            )

        if show_tips:
            self.show_tips_summary(
                title=tips_title,
                min_size=tips_size,
                offset=tips_offset
            )

        # 1) Deck overlay (OpenCV window)
        if deck_enabled:
            img_deck = self.render(
                vessels,
                alpha=deck_alpha,
                draw_labels=deck_draw_labels,
                prefer_reagent_map=deck_prefer_reagent_map,
            )

            # Only add tube rack label if we're going to show the tube rack screen
            if show_tube_rack:
                text = _ascii_label("24 Tube Rack")
                label_px = 16
                pad = 4
                x, y_base = 600, 370

                try:
                    font_fp = ARIAL_TTF if Path(ARIAL_TTF).is_file() else next(
                        (p for p in _FONT_CANDIDATES if Path(p).is_file()), None
                    )
                except Exception:
                    font_fp = None

                if font_fp:
                    # Add the tube rack label with Pillow
                    from PIL import Image, ImageDraw, ImageFont
                    im = Image.fromarray(cv2.cvtColor(img_deck, cv2.COLOR_BGR2RGB))
                    draw = ImageDraw.Draw(im)
                    font = ImageFont.truetype(font_fp, label_px)
                    try:
                        ascent, descent = font.getmetrics()
                    except Exception:
                        ascent, descent = int(0.8 * label_px), int(0.2 * label_px)
                    y_top = y_base - ascent
                    try:
                        x0, y0, x1, y1 = draw.textbbox((x, y_top), text, font=font)
                    except Exception:
                        w, h = draw.textsize(text, font=font)
                        x0, y0, x1, y1 = x, y_top, x + w, y_top + h
                    x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
                    draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0))
                    draw.text((x, y_top), text, font=font, fill=(255, 255, 255))
                    img_deck = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
                else:
                    # OpenCV fallback
                    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
                    x0, y0 = x - pad, y_base - th - pad
                    x1, y1 = x + tw + pad, y_base + base + pad
                    cv2.rectangle(img_deck, (x0, y0), (x1, y1), (0, 0, 0), thickness=-1)
                    cv2.putText(img_deck, text, (x, y_base), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)

            # Show the deck window
            self.show(img_deck, window_name=deck_window_name,
                    scale=deck_scale, wait_ms=0, resizable=deck_resizable)
            if destroy_windows:
                try:
                    cv2.destroyWindow(deck_window_name)
                except Exception:
                    pass

        # 2) Tube rack (scrollable Tk window) - only if there's data
        if show_tube_rack:
            img_tubes = self.render_tube_rack_24_screen(
                render_scale=tube_render_scale,
                zoom_y=tube_zoom_y,
            )
            self.show_tk_scrollable(
                img_tubes,
                title=tube_title,
                viewport=tube_viewport,
                offset=tube_offset,
            )

        # 3) 96-well plate (OpenCV window)
        if plate_enabled:
            img_plate = self.render_plate_96_screen(
                render_scale=plate_render_scale,
                output_scale=plate_output_scale,
            )
            self.show(img_plate, window_name=plate_window_name,
                    scale=plate_scale_in_window, wait_ms=0, resizable=plate_resizable)
            if destroy_windows:
                try:
                    cv2.destroyWindow(plate_window_name)
                except Exception:
                    pass

    def ShowDialogues(self, *args, **kwargs):
        """PascalCase alias."""
        return self.show_dialogues(*args, **kwargs)



# ------------------------- Example Usage -------------------------

if __name__ == "__main__":
    vis = LoadingVis(
        reagent_data="deck_loads.json",
        origin_offset=(0, 0),
        auto_crop=False,
    )


    class ReagentVessel:
        def __init__(self, name):
            self.name = name

        def layout_name(self):
            return self.name

    magbeads = ReagentVessel('rgt_cont_60ml_BC_A00_0001')
    buffer_a = ReagentVessel('rgt_cont_60ml_BC_A00_0003')
    buffer_b = ReagentVessel('rgt_cont_60ml_BC_A00_0005')

    vessels = [
        magbeads,
        buffer_a,
        buffer_b
    ]

    # One-shot sequence
    vis.ShowDialogues(
        tube_offset=(360, 60),           # nudge the scrollable window to the right
        tube_viewport=(800, 700),        # fixed window size; scroll to see the rest
        deck_window_name="Deck",
        plate_window_name="96-well Plate",
    )
