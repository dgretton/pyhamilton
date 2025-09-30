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
from ...resources import DeckResource
from pathlib import Path
import tkinter as tk
from .plate_96_render import render_plate_96
from .tube_rack_render import TubeRackRenderer
from .rendering_helpers import (
    ARIAL_TTF,
    _FONT_CANDIDATES,
    draw_text_pillow,
    _best_label_box_outside,
    _resolve_font_path,
    _measure_text_pillow,
    _rescale_image,
    _ascii_label,
    _label_from_info_dict,
    _name_to_color_bgr,
    _norm_key,
    _ensure_bgr,
    _draw_transparent_rect,
    _draw_transparent_polygon,
    _rect_xyxy,
    _rect_overlap_area,
    _intersects_any,
    _fan_offsets,
    _fmt_volume,
    _preferred_side_for_key,
    _get_polygon_min_area_rect_center_and_bbox,
)





# ------------------------- Data Models -------------------------

@dataclass
class Region:
    name: str
    points: List[Tuple[int, int]] # <--- NEW FIELD
    top_left: Tuple[int, int]
    bottom_right: Tuple[int, int]
    color_bgr: Tuple[int, int, int]

    @classmethod
    def from_dict(cls, name: str, d: Dict) -> "Region":
        # New format uses 'points' to define a polygon. We calculate the bounding box.
        if "points" not in d:
            raise ValueError(f"Region '{name}' is missing 'points' key in data.")

        # Store the points array directly
        points = d["points"] # <--- RETAIN POINTS DATA

        # Calculate bounding box (min_x, min_y) and (max_x, max_y)
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        top_left = (int(min_x), int(min_y))
        bottom_right = (int(max_x), int(max_y))

        # New format uses 'color' for BGR color
        color_bgr = tuple(map(int, d.get("color", (0, 0, 255))))

        return cls(
            name=name,
            points=points, # <--- PASS POINTS TO CONSTRUCTOR
            top_left=top_left,
            bottom_right=bottom_right,
            color_bgr=color_bgr,
        )



# ---- ADD: helpers for ASCII labels and colors ----


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
            if parent is None:
                raise ValueError("LoadingVis requires a parent Tk window when called from GUI context")
        
            self.parent = parent

            # Define the expected directory and file paths relative to the CWD
            loading_dir = Path.cwd() / "loading"
            json_file_name = "deck_regions.json"
            json_file_path = loading_dir / json_file_name

            # 1. Check for 'loading' subdirectory and 'deck_regions.json'
            if not loading_dir.is_dir():
                raise FileNotFoundError(
                    f"Could not find the **'loading'** folder in the current directory: {Path.cwd()}. "
                    "Please ensure you have a 'loading' subdirectory containing "
                    "your annotated files, typically **'deck.png'** and **'deck_regions.json'**."
                )
            
            if not json_file_path.is_file():
                raise FileNotFoundError(
                    f"Could not find overlay JSON at: {json_file_path}. "
                    "Please ensure **'deck_regions.json'** exists inside the **'loading'** folder. "
                    "Run deck-annotator deck.png to create it."
                )

            with open(json_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._raw = data

            # 2. Resolve base image path
            json_image_path = data.get("image_path")
            if image_path_override:
                img_path = Path(image_path_override)
            else:
                if json_image_path:
                    # Resolve image path relative to the 'loading' directory
                    normalized_path = json_image_path.replace("\\", "/").lstrip("./")
                    img_path = loading_dir / normalized_path
                else:
                    img_path = Path("") # Will likely fail to load, caught below

            # 3. Load the image
            self.base_img_bgr = _ensure_bgr(cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED))
            if self.base_img_bgr is None:
                if json_image_path and not Path(img_path).exists():
                    raise FileNotFoundError(
                        f"The image '{json_image_path}' specified in the JSON file "
                        f"was not found in the **'loading'** directory: {loading_dir}"
                    )
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
            metadata_keys = {"image_path", "image_dimensions", "regions"} 
            
            for name, rd in data.items():
                if name in metadata_keys or not isinstance(rd, dict) or "points" not in rd:
                    continue
                
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
            self.tube_racks_map: Dict[str, Dict[int, Dict[str, Any]]] = {}
            self.plate96_map: Dict[str, Dict[int, Dict[str, Any]]] = {}
            if reagent_data is not None:
                self._load_reagent_map(reagent_data)
            
            # Assuming this property is set by another loading method or defaults to False
            self.has_tip_consumption_data = False 

    # ---------- Private utilities ----------

    def _shift_regions(self, offset: Tuple[int, int]) -> None:
        ox, oy = offset
        for r in self.regions.values():
            x1, y1 = r.top_left
            x2, y2 = r.bottom_right
            r.top_left = (x1 + ox, y1 + oy)
            r.bottom_right = (x2 + ox, y2 + oy)
            r.points = [
                (p[0] + ox, p[1] + oy) for p in r.points
            ]

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
        """
        img = self.base_img_bgr
        H, W = img.shape[:2]
        corners = np.array([img[0,0], img[0,-1], img[-1,0], img[-1,-1]], dtype=np.int16)
        bg = np.median(corners, axis=0)
        diff = np.abs(img.astype(np.int16) - bg[None,None,:]).sum(axis=2)

        def edge_strip(vals):
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
            return 

        self.base_img_bgr = img[y1:y2, x1:x2].copy()
        self._shift_regions((-x1, -y1))

    def _apply_alias_rules(self, region_name) -> str:
        if 'CPAC' in region_name.upper():
            return 'CPAC'
        elif region_name=='CAR_VIALS_SMALL':
            return '32-tube rack'
        else:
            return None

    def _create_vessels_from_data(self) -> List[DeckResource]:
        """
        Create vessel objects based on the reagent data loaded.
        """
        vessels = []
        all_keys = set(self.reagent_map.keys()) | set(self.plate96_map.keys()) | set(self.tube_racks_map.keys())
        
        for vessel_key in all_keys:
            if vessel_key in self.regions:
                vessel = ReagentVessel(name=self.regions[vessel_key].name)
                vessels.append(vessel)
        
        return vessels


    def _load_reagent_map(self, reagent_data: Union[str, Path, Dict]) -> None:
        """
        Load reagent map.
        """
        if isinstance(reagent_data, (str, Path)):
            with open(reagent_data, "r", encoding="utf-8") as f:
                d = json.load(f)
        else:
            d = reagent_data

        self.reagent_units_default = str(d.get("units_default", "mL"))
        self.reagent_map: Dict[str, Dict[str, Any]] = {}
        self.tube_racks_map: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.plate96_map: Dict[str, Dict[int, Dict[str, Any]]] = {}

        
        for vessel_name, vessel_data in d.items():
            if vessel_name in ("units_default", "version"):
                continue
                
            vessel_key = _norm_key(vessel_name)
            pos_map = vessel_data.get("positions") if isinstance(vessel_data, dict) else None
            vessel_class_name = vessel_data.get('class_name', '')
            
            if 'Plate96' in vessel_class_name:
                self.plate96_map.update({vessel_key: vessel_data.get('positions', {})})

            elif 'TubeRack' in vessel_class_name or 'EppiCarrier' in vessel_class_name:
                self.tube_racks_map.update({vessel_key: {'positions': vessel_data.get('positions', {}), 
                                                'class_name': vessel_class_name}})
            
            if pos_map is not None and not ('Plate96' in vessel_class_name or 'TubeRack' in vessel_class_name or 'EppiCarrier' in vessel_class_name):
                reagent_names = []
                total_volume = 0
                units = []
                    
                for pos_str, reagent_info in pos_map.items():
                    reagent_names.append(reagent_info["reagent"])
                    total_volume += reagent_info["volume"]
                    units.append(reagent_info["unit"])
                    
                if reagent_names:
                    unit = max(set(units), key=units.count) if units else self.reagent_units_default
                        
                    self.reagent_map[vessel_key] = {
                        "name": vessel_key if len(reagent_names) > 1 else reagent_names[0],
                        "volume": total_volume if len(reagent_names) == 1 else None,
                        "unit": unit if len(reagent_names) == 1 else None
                    }
            

    # ---------- Public API ----------

    def render(
        self,
        vessels: Optional[List[DeckResource]] = None,
        *,
        alpha: float = 0.35,
        draw_labels: bool = True,
        label_from: str = "label_then_entity",
        copy_base: bool = True,
        prefer_reagent_map: bool = True,
        font_scale: float = 0.40,
        font_thickness: int = 1,
        pad: int = 3,
        gap: int = 6,
    ) -> np.ndarray:
        """
        Render overlays. If no vessels provided, automatically create them from reagent data.
        """
        canvas = self.base_img_bgr.copy() if copy_base else self.base_img_bgr

        if vessels is None:
            vessels = self._create_vessels_from_data()

        items = []  # (region, color_bgr, label_text)
        for v in vessels:
            key_norm = _norm_key(v.layout_name())
            region = self.regions.get(key_norm)
            if not region:
                continue
            
            color = region.color_bgr

            if prefer_reagent_map and key_norm in self.reagent_map:
                reagent_info = self.reagent_map[key_norm]
                name = reagent_info.get("name", region.name)
                volume = reagent_info.get("volume")
                unit = reagent_info.get("unit", self.reagent_units_default)
                
                if volume is not None and volume > 0:
                    try:
                        vol_num = float(volume)
                        vol_str = f"{vol_num:.3f}".rstrip("0").rstrip(".")
                    except (ValueError, TypeError):
                        vol_str = str(volume)
                    
                    label_text = _ascii_label(f"{name}, {vol_str} {unit}")
                else:
                    alias_label = self._apply_alias_rules(key_norm)
                    if alias_label:
                        label_text = _ascii_label(alias_label)
                    else:
                        label_text = _ascii_label(name)
            else:
                alias_label = self._apply_alias_rules(region.name)
                if alias_label:
                    label_text = _ascii_label(alias_label)
                else:
                    label_text = _ascii_label(region.name)
            
            items.append((region, color, label_text))

        for region, color, _ in items:
            _draw_transparent_polygon(
                canvas, region.points, color, alpha=alpha
            )
        if not draw_labels:
            return canvas

        overlay_rects = [_rect_xyxy(r.top_left, r.bottom_right) for (r, _, _) in items]
        placed_label_rects = []
        label_px = 16
        try:
            font_fp = ARIAL_TTF if Path(ARIAL_TTF).is_file() else next(
                (p for p in _FONT_CANDIDATES if Path(p).is_file()), None
            )
        except Exception:
            font_fp = None

        for region, color, label_text in items:
            print(f"Placing label '{label_text}' for region '{region.name}'")

            polygon_bbox, min_area_center = _get_polygon_min_area_rect_center_and_bbox(region.points)
            
            anchor_xyxy = _rect_xyxy(region.top_left, region.bottom_right)
            anchor_poly_points = region.points # Pass the actual points!

            preferred_side = _preferred_side_for_key(_norm_key(region.name))

            label_rect, org = _best_label_box_outside(
                canvas.shape,
                anchor_xyxy,
                label_text,
                anchor_poly_points=anchor_poly_points,
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
        Show the image in an OpenCV window.
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
        return bool(self.tube_racks_map)

    
    def _cleanup_cv_windows(self, deck_window_name, plate_enabled):
        """Destroy OpenCV windows."""
        try:
            cv2.destroyWindow(deck_window_name)
        except Exception:
            pass
        
        if plate_enabled:
            for plate_key in self.plate96_map.keys():
                window_name = f"{plate_key} - Plate Reagent Map"
                try:
                    cv2.destroyWindow(window_name)
                except Exception:
                    pass

    def show_dialogues(
        self,
        vessels: Optional[List[DeckResource]] = None,
        *,
        # --- NEW: Summary stage options (not fully implemented in methods, but included for completeness) ---
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
        tube_enabled: bool = True,
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
        Show visualization stages and block until the last Tkinter window is closed.
        """
        import cv2
        import tkinter as tk
        import traceback # needed for error reporting


        if vessels is None:
            vessels = self._create_vessels_from_data()

        # Check if we need a Tk root to host the Toplevels
        # 1) Deck overlay (OpenCV window)
        if deck_enabled:
            img_deck = self.render(
                vessels,
                alpha=deck_alpha,
                draw_labels=deck_draw_labels,
                prefer_reagent_map=deck_prefer_reagent_map,
            )
            self.show(img_deck, window_name=deck_window_name,
                      scale=deck_scale, wait_ms=0, resizable=deck_resizable)
            
        # 2) 96-well Plate view (OpenCV)
        if plate_enabled:
            for plate_key in self.plate96_map.keys():
                plate_data = self.plate96_map.get(plate_key, {})
                img_plate = render_plate_96(
                    plate_key,
                    plate_data,
                    self.reagent_units_default,
                    render_scale=plate_render_scale,
                    output_scale=plate_output_scale,
                )
                window_name = f"{plate_key} - Plate Reagent Map"
                self.show(img_plate, 
                          window_name=window_name,
                          scale=plate_scale_in_window, 
                          wait_ms=0, 
                          resizable=plate_resizable)
        
        # 3) Tube rack view (Tkinter modal)
        if tube_enabled and self.tube_racks_map:
            renderer = TubeRackRenderer()

            
            for rack_key in self.tube_racks_map.keys():
                tube_dictionary = self.tube_racks_map.get(rack_key, {})
                # tubes_count logic remains the same
                tubes_count = 32 if '32' in tube_dictionary.get('class_name', '') else 24 if '24' in tube_dictionary.get('class_name', '') else len(tube_dictionary)
                tube_data = tube_dictionary.get('positions', {})

                if tubes_count == 0: continue

                try:
                    # 2. Render the image (Returns a BGR numpy array)
                    img_tube = renderer.render_tube_rack_screen(
                        tubes_count=tubes_count,
                        tube_map=tube_data,
                        reagent_units_default=self.reagent_units_default,
                        render_scale=tube_render_scale,
                        zoom_y=tube_zoom_y,
                    )
                    
                    # 3. Define window name
                    window_name = f"{rack_key} - Tube Rack Reagent Map"
                    
                    renderer.show_tkinter_modal(
                        img_bgr=img_tube,
                        window_name=window_name,
                        parent=self.parent 
                    )

                    
                except Exception as e:
                    # You might want to use a more robust logger here
                    # traceback.print_exc() # Use this if 'traceback' is imported
                    print(f"Error rendering/showing rack {rack_key}: {e}")
        
        if destroy_windows:
            self._cleanup_cv_windows(deck_window_name, plate_enabled)



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