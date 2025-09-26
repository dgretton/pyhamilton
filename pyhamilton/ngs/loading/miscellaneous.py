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
