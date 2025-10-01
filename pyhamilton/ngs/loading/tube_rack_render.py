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
from PIL import Image, ImageDraw, ImageFont, ImageTk
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

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
)



class TubeRackRenderer:

    def render_tube_rack_screen(
        self,
        tubes_count: int,
        tube_map: Dict[Union[int, str], Dict[str, Any]],
        *,
        reagent_units_default: str = "µL",
        width: int = 350,  # <<< REDUCED WIDTH (e.g., from 700 to 350)
        height_per_tube: int = 30,
        margin_left: int = 80,
        margin_right: int = 260,
        margin_v_base: int = 60,
        tube_radius: int = 14,
        font_scale: float = 0.40,
        font_thickness: int = 1,
        pad: int = 3,
        gap: int = 8,
        render_scale: float = 0.5,  # <<< REDUCED RENDER SCALE (e.g., from 1.25 to 0.8)
        zoom_y: float = 2.0,
        index_px: int = 14,
    ) -> np.ndarray:
        """
        Zoomed tube-rack screen (N tubes in one column). White background, grey rack,
        black text. (Implementation remains the same).
        """
        s = float(render_scale)
        zy = float(zoom_y)

        # ----------------------------------------------------
        # 1. Dynamic Scaling based on tubes_count
        # ----------------------------------------------------

        # Calculate total height based on number of tubes
        base_h = tubes_count * height_per_tube + 2 * margin_v_base

        W = int(round(width * s))
        H = int(round(base_h * s * zy)) # Total Canvas Height
        ml = int(round(margin_left * s))
        mr = int(round(margin_right * s))
        mv = int(round(margin_v_base * s * zy)) # Zoomed Vertical Margin
        r = int(round(tube_radius * s * zy))

        fs = font_scale * s * zy
        pt = max(1, int(round(pad * s)))
        gp = max(1, int(round(gap * s)))

        # Create the canvas (BGR format)
        canvas = np.full((H, W, 3), 255, np.uint8)

        rows = tubes_count
        usable_h = H - 2 * mv
        step_y = usable_h / rows
        cx = ml + r + int(round(10 * s)) 

        overlay_rects = []
        placed_label_rects = []

        # ----------------------------------------------------
        # 2. Rack and Title
        # ----------------------------------------------------

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

        occupied_count = len(tube_map)
        title = _ascii_label(f"Tube Rack ({tubes_count} capacity, {occupied_count} filled)")
        title_px = 16 # Keep base title size consistent
        # Assuming ARIAL_TTF is resolved or mocked appropriately
        draw_text_pillow(canvas, title, (ml, int(round(36 * s))), font_path=ARIAL_TTF, px=title_px, color=(0, 0, 0))

        overlay_rects.append(rack_rect)

        # Font resolution logic from original code:
        try:
            font_fp = ARIAL_TTF if Path(ARIAL_TTF).is_file() else next((p for p in _FONT_CANDIDATES if Path(p).is_file()), None)
        except Exception:
            font_fp = None
        # End Font resolution logic

        # ----------------------------------------------------
        # 3. Draw tubes + indexes + labels
        # ----------------------------------------------------

        for i in range(rows):
            y = int(round(mv + (i + 0.5) * step_y))
            display_key = f"{i+1:02d}"

            info = tube_map.get(str(i))
            if not info:
                info = tube_map.get(i)
            
            if not info:
                color = (200, 200, 200) # Neutral grey for empty tube
                label_text = ""
            else:
                color = _name_to_color_bgr(info.get("reagent", display_key))
                label_text = _label_from_info_dict(info, unit_default=reagent_units_default, fallback=display_key)

            # Draw the tube circle
            cv2.circle(canvas, (cx, y), r, color, thickness=-1)
            cv2.circle(canvas, (cx, y), r, (30, 30, 30), thickness=max(1, int(round(1 * s))))

            # Tube circle bbox as avoidance
            x1, y1 = cx - r, y - r
            x2, y2 = cx + r, y + r
            overlay_rects.append((x1, y1, x2, y2))

            # Tube index (left of rack)
            idx_px = max(10, int(round(index_px * s)))
            idx_x = max(8, rack_rect[0] - int(round(18 * s)))
            draw_text_pillow(canvas, display_key, (idx_x, y + int(round(6 * s))), font_path=font_fp or ARIAL_TTF, px=idx_px, color=(0, 0, 0))

            # Reagent label (RIGHT of rack)
            if info:
                label_px = title_px # Base size for label text
                tw, ascent, descent = _measure_text_pillow(label_text, font_fp or ARIAL_TTF, label_px)
                lw = tw + 2 * pt + 3 
                lh = ascent + descent + 2 * pt

                y_base = int(round(y + (ascent - descent) / 2.0))
                tlx = rack_rect[2] + max(gp, int(round(10 * s)))
                tly = y_base - ascent - pt

                pushed = 0 
                step_x = max(6, int(round(10 * s)))
                max_push = int(round(300 * s))
                rect = (tlx, tly, tlx + lw, tly + lh)
                while (_intersects_any(rect, overlay_rects) or _intersects_any(rect, placed_label_rects)) and pushed < max_push:
                    tlx += step_x
                    pushed += step_x
                    rect = (tlx, tly, tlx + lw, tly + lh)

                org = (tlx + pt, y_base)
                draw_text_pillow(canvas, label_text, org, font_path=font_fp or ARIAL_TTF, px=label_px, color=(0, 0, 0))
                placed_label_rects.append(rect)

        # ----------------------------------------------------
        # 4. Final Trim
        # ----------------------------------------------------
        content_rights = [x2 for (_, _, x2, _) in overlay_rects] + [x2 for (_, _, x2, _) in placed_label_rects] or [cx + r]
        used_right = max(content_rights)
        pad_right = int(round(24 * s))
        new_W = min(W, max(ml + 2 * r + pad_right, used_right + pad_right))
        if new_W < W:
            canvas = canvas[:, :new_W].copy()

        return canvas
    
    # ----------------------------------------------------------------------
    # NEW: OpenCV Display Method (Replacing show_tk_scrollable)
    # ----------------------------------------------------------------------

    def show_tkinter_modal(
            self,
            img_bgr: np.ndarray,
            parent: tk.Tk | tk.Toplevel,
            window_name: str = "Tube Rack Visualization",
        ) -> None:
        from tkinter import ttk, messagebox
        
        modal = tk.Toplevel(parent)
        modal.title(window_name)
        modal.transient(parent)
        modal.resizable(True, True)

        main_frame = ttk.Frame(modal)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Scrollbar and Canvas
        vscrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL)
        vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas = tk.Canvas(main_frame, yscrollcommand=vscrollbar.set,
                        width=img_bgr.shape[1], height=min(img_bgr.shape[0], 600))
        canvas.pack(side=tk.LEFT, fill="both", expand=True)

        vscrollbar.config(command=canvas.yview)

        # Inner frame for image
        image_frame = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=image_frame, anchor="nw")

        try:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            tk_photo = ImageTk.PhotoImage(pil_img)
        except Exception as e:
            messagebox.showerror("Image Conversion Error", f"Could not convert image for display: {e}")
            modal.destroy()
            return

        img_label = tk.Label(image_frame, image=tk_photo)
        img_label.pack()
        img_label.image = tk_photo  # Keep reference

        image_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"))
        canvas.yview_moveto(0)

        # Close handler (X button and Escape key)
        def close_window():
            modal.destroy()

        modal.bind('<Escape>', lambda e: close_window())
        modal.protocol("WM_DELETE_WINDOW", close_window)

        # Modal blocking
        modal.grab_set()

        # Center modal over parent
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        modal.update_idletasks()
        modal_w = modal.winfo_width()
        modal_h = modal.winfo_height()

        new_x = parent_x + (parent_w - modal_w) // 2
        new_y = parent_y + (parent_h - modal_h) // 2

        modal.geometry(f'+{new_x}+{new_y}')

        # Block execution until modal is closed
        parent.wait_window(modal)
