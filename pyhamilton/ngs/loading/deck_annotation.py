import cv2
import numpy as np
import json
import sys
import tkinter as tk
from tkinter import simpledialog, messagebox, Toplevel, Button, Label, StringVar, OptionMenu
from typing import Tuple, Dict, List, Optional

# ---------- helpers ----------

def load_image(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"Could not read image: {path}")
    # Ensure uint8, C-contiguous
    if img.dtype != np.uint8:
        img = img.astype(np.uint8)
    if not img.flags["C_CONTIGUOUS"]:
        img = np.ascontiguousarray(img)
    # If grayscale, promote to BGR
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img

def _match_color_to_channels(color_bgr: Tuple[int,int,int], channels: int) -> Tuple[int,...]:
    if channels == 1:
        g = int(round(sum(color_bgr)/3))
        return (g,)
    if channels == 3:
        return color_bgr
    if channels == 4:
        return (*color_bgr, 255)
    raise ValueError(f"Unsupported channel count: {channels}")

def draw_transparent_rect(img: np.ndarray,
                          pt1: Tuple[int,int],
                          pt2: Tuple[int,int],
                          color_bgr: Tuple[int,int,int] = (0,0,255),
                          alpha: float = 0.35,
                          thickness: int = -1) -> None:
    overlay = img.copy()
    color = _match_color_to_channels(color_bgr, img.shape[2])
    cv2.rectangle(overlay, pt1, pt2, color, thickness)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, dst=img)

def put_text_safe(img: np.ndarray,
                  text: str,
                  org: Tuple[int,int],
                  scale: float = 0.6,
                  color_bgr: Tuple[int,int,int] = (255,255,255),
                  thickness: int = 1,
                  bg_bgr: Tuple[int,int,int] | None = (0,0,0),
                  bg_alpha: float = 0.5,
                  pad: int = 4) -> None:
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x, y = org
    if bg_bgr is not None:
        x1, y1 = x - pad, y - th - pad
        x2, y2 = x + tw + pad, y + baseline + pad
        x1, y1 = max(0, x1), max(0, y1)
        overlay = img.copy()
        bg_color = _match_color_to_channels(bg_bgr, img.shape[2])
        cv2.rectangle(overlay, (x1, y1), (x2, y2), bg_color, thickness=-1)
        cv2.addWeighted(overlay, bg_alpha, img, 1 - bg_alpha, 0, dst=img)

    color = _match_color_to_channels(color_bgr, img.shape[2])[:3]
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)

# ---------- Tkinter Dialog Classes ----------

class ColorDialog:
    def __init__(self, parent):
        self.result = None
        self.dialog = Toplevel(parent)
        self.dialog.title("Select Region Color")
        self.dialog.geometry("300x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Available colors
        self.color_options = {
            'Red': (0, 0, 255),
            'Green': (0, 255, 0),
            'Blue': (255, 0, 0),
            'Yellow': (0, 255, 255),
            'Magenta': (255, 0, 255),
            'Cyan': (255, 255, 0),
            'Purple': (128, 0, 255),
            'Orange': (0, 165, 255),
            'White': (255, 255, 255),
            'Light Gray': (192, 192, 192),
            'Dark Gray': (128, 128, 128),
            'Pink': (203, 192, 255),
            'Light Blue': (255, 255, 128),
            'Light Green': (128, 255, 128),
        }
        
        Label(self.dialog, text="Choose a color:", font=("Arial", 12)).pack(pady=10)
        
        # Create color buttons
        for color_name, color_value in self.color_options.items():
            # Convert BGR to RGB for display
            rgb = (color_value[2], color_value[1], color_value[0])
            hex_color = '#{:02x}{:02x}{:02x}'.format(*rgb)
            
            btn = Button(self.dialog, text=color_name, bg=hex_color, 
                        command=lambda cv=color_value: self.select_color(cv),
                        width=20, height=1)
            # Set text color based on brightness
            brightness = sum(rgb) / 3
            text_color = "black" if brightness > 128 else "white"
            btn.config(fg=text_color)
            btn.pack(pady=2)
        
        # Cancel button
        Button(self.dialog, text="Cancel", command=self.cancel, width=20).pack(pady=10)
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def select_color(self, color_value):
        self.result = color_value
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()

class RegionNameDialog:
    def __init__(self, parent, existing_names, pt1, pt2):
        self.result = None
        self.dialog = Toplevel(parent)
        self.dialog.title("Name Region")
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        width = pt2[0] - pt1[0]
        height = pt2[1] - pt1[1]
        
        # Info label
        info_text = f"New region: ({pt1[0]}, {pt1[1]}) to ({pt2[0]}, {pt2[1]})\nSize: {width} x {height} pixels"
        Label(self.dialog, text=info_text, font=("Arial", 10)).pack(pady=10)
        
        # Name entry
        Label(self.dialog, text="Enter region name:", font=("Arial", 11)).pack(pady=5)
        
        self.entry = tk.Entry(self.dialog, width=40, font=("Arial", 11))
        self.entry.pack(pady=5)
        self.entry.focus_set()
        
        self.existing_names = existing_names
        
        # Buttons frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        Button(button_frame, text="OK", command=self.ok_clicked, width=10).pack(side=tk.LEFT, padx=5)
        Button(button_frame, text="Cancel", command=self.cancel, width=10).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to OK
        self.entry.bind('<Return>', lambda e: self.ok_clicked())
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
    
    def ok_clicked(self):
        name = self.entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Name cannot be empty!", parent=self.dialog)
            return
        
        if name in self.existing_names:
            if not messagebox.askyesno("Confirm", f"Region '{name}' already exists. Overwrite?", parent=self.dialog):
                return
        
        self.result = name
        self.dialog.destroy()
    
    def cancel(self):
        self.dialog.destroy()

# ---------- Region Annotation Tool ----------

class RegionAnnotationTool:
    def __init__(self, img_path: str, regions_file: str = None):
        self.img_path = img_path
        self.regions_file = regions_file or img_path.replace('.png', '_regions.json').replace('.jpg', '_regions.json')
        
        self.original_img = load_image(img_path)
        self.display_img = self.original_img.copy()
        
        # Start with empty regions
        self.regions = {}
        
        # Current drawing state
        self.current_region_start = None
        self.drawing = False
        self.temp_end = None
        
        # Initialize Tkinter root (hidden)
        self.root = tk.Tk()
        self.root.withdraw()
        
        self.window_name = f"Region Annotation Tool - {img_path}"
        
    def load_regions(self) -> Dict[str, Dict]:
        """Load existing regions from JSON file"""
        try:
            with open(self.regions_file, 'r') as f:
                data = json.load(f)
                return data.get('regions', {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def save_regions(self):
        """Save regions to JSON file"""
        data = {
            'image_path': self.img_path,
            'image_dimensions': {
                'width': self.original_img.shape[1],
                'height': self.original_img.shape[0]
            },
            'regions': self.regions
        }
        
        with open(self.regions_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved {len(self.regions)} regions to {self.regions_file}")
    
    def get_region_color(self, region_data: Dict) -> Tuple[int, int, int]:
        """Get color for a region from its data"""
        return tuple(region_data.get('color', [255, 0, 0]))
    
    def redraw_image(self):
        """Redraw the image with all current regions"""
        self.display_img = self.original_img.copy()
        
        # Draw all existing regions (no labels on the image)
        for region_name, region_data in self.regions.items():
            pt1 = tuple(region_data['top_left'])
            pt2 = tuple(region_data['bottom_right'])
            color = self.get_region_color(region_data)
            
            # Draw only transparent rectangle (no border, no label)
            draw_transparent_rect(self.display_img, pt1, pt2, color, alpha=0.3)
        
        # Draw current region being drawn (thin white outline only)
        if self.drawing and self.current_region_start and self.temp_end:
            cv2.rectangle(self.display_img, self.current_region_start, self.temp_end, (255, 255, 255), 1)
            # Draw size info while drawing
            w = abs(self.temp_end[0] - self.current_region_start[0])
            h = abs(self.temp_end[1] - self.current_region_start[1])
            size_text = f"{w}x{h}"
            put_text_safe(self.display_img, size_text, 
                         (self.current_region_start[0], self.current_region_start[1] - 25),
                         scale=0.4, color_bgr=(255, 255, 255))
        
        # Show region count in top-left corner
        region_count_text = f"REGIONS: {len(self.regions)}"
        put_text_safe(self.display_img, region_count_text, (10, 25), 
                     scale=0.6, color_bgr=(255, 255, 255), 
                     bg_bgr=(0, 0, 0), bg_alpha=0.7)
        
        cv2.imshow(self.window_name, self.display_img)
    
    def get_region_name_and_color(self, pt1: Tuple[int, int], pt2: Tuple[int, int]) -> Optional[Tuple[str, Tuple[int, int, int]]]:
        """Get region name and color from user using Tkinter dialogs"""
        # Make sure root window is updated
        self.root.update()
        self.root.deiconify()  # Show the root window temporarily
        
        # Get color first
        color_dialog = ColorDialog(self.root)
        self.root.wait_window(color_dialog.dialog)
        
        if color_dialog.result is None:
            self.root.withdraw()  # Hide root window again
            return None
        
        selected_color = color_dialog.result
        
        # Get name
        name_dialog = RegionNameDialog(self.root, list(self.regions.keys()), pt1, pt2)
        self.root.wait_window(name_dialog.dialog)
        
        self.root.withdraw()  # Hide root window again
        
        if name_dialog.result is None:
            return None
        
        return (name_dialog.result, selected_color)
    
    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_region_start = (x, y)
            self.drawing = True
            
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            self.temp_end = (x, y)
            self.redraw_image()
            
        elif event == cv2.EVENT_LBUTTONUP and self.drawing:
            self.drawing = False
            end_point = (x, y)
            
            # Check for minimum size
            if (abs(end_point[0] - self.current_region_start[0]) < 10 or 
                abs(end_point[1] - self.current_region_start[1]) < 10):
                print("Region too small, skipping...")
                self.redraw_image()
                return
            
            # Normalize coordinates
            pt1 = (min(self.current_region_start[0], end_point[0]),
                   min(self.current_region_start[1], end_point[1]))
            pt2 = (max(self.current_region_start[0], end_point[0]),
                   max(self.current_region_start[1], end_point[1]))
            
            # Get region name and color using Tkinter dialogs
            result = self.get_region_name_and_color(pt1, pt2)
            if result:
                region_name, selected_color = result
                self.regions[region_name] = {
                    'top_left': list(pt1),
                    'bottom_right': list(pt2),
                    'width': pt2[0] - pt1[0],
                    'height': pt2[1] - pt1[1],
                    'center': [(pt1[0] + pt2[0]) // 2, (pt1[1] + pt2[1]) // 2],
                    'color': list(selected_color)
                }
                print(f"Added region '{region_name}'")
                self.save_regions()
            
            self.redraw_image()
            
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Right click to delete region
            self.delete_region_at(x, y)
    
    def delete_region_at(self, x: int, y: int):
        """Delete region that contains the clicked point"""
        for region_name, region_data in list(self.regions.items()):
            pt1 = tuple(region_data['top_left'])
            pt2 = tuple(region_data['bottom_right'])
            
            if pt1[0] <= x <= pt2[0] and pt1[1] <= y <= pt2[1]:
                self.root.deiconify()  # Show root temporarily for messagebox
                if messagebox.askyesno("Delete Region", f"Delete region '{region_name}'?", parent=self.root):
                    del self.regions[region_name]
                    print(f"Deleted region '{region_name}'")
                    self.save_regions()
                    self.redraw_image()
                self.root.withdraw()  # Hide root again
                break
    
    def print_help(self):
        print("\n" + "="*60)
        print("REGION ANNOTATION TOOL CONTROLS:")
        print("="*60)
        print("• Left click + drag: Create new rectangular region")
        print("• Right click: Delete region (click inside region)")
        print("• 'o': Open/load existing regions from JSON file")
        print("• 'h': Show this help")
        print("• 'l': List all current regions")
        print("• 's': Save regions to JSON")
        print("• 'r': Reset/clear all regions")
        print("• 'q': Quit and save")
        print("="*60)
        print(f"Regions will be saved to: {self.regions_file}")
        print("="*60 + "\n")
    
    def list_regions(self):
        """Print all current regions"""
        print(f"\nCurrent regions ({len(self.regions)}):")
        print("-" * 50)
        for name, data in self.regions.items():
            print(f"'{name}': {data['top_left']} to {data['bottom_right']} "
                  f"({data['width']}x{data['height']})")
        print("-" * 50 + "\n")
    
    def load_existing_regions(self):
        """Load existing regions from JSON file"""
        loaded_regions = self.load_regions()
        if loaded_regions:
            self.regions = loaded_regions
            print(f"Loaded {len(self.regions)} regions from {self.regions_file}")
            self.redraw_image()
        else:
            print("No existing regions found or failed to load.")
    
    def run(self):
        """Run the interactive annotation tool"""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        
        self.print_help()
        print("Starting with clean slate - no regions loaded.")
        print("Press 'o' to load existing regions if needed.")
        self.redraw_image()
        
        while True:
            # Process Tkinter events
            self.root.update_idletasks()
            self.root.update()
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('o'):
                self.load_existing_regions()
            elif key == ord('h'):
                self.print_help()
            elif key == ord('l'):
                self.list_regions()
            elif key == ord('s'):
                self.save_regions()
            elif key == ord('r'):
                self.root.deiconify()  # Show root temporarily for messagebox
                if messagebox.askyesno("Clear All Regions", "Clear all regions? This cannot be undone!", parent=self.root):
                    self.regions = {}
                    self.save_regions()
                    self.redraw_image()
                    print("All regions cleared!")
                self.root.withdraw()  # Hide root again
        
        cv2.destroyAllWindows()
        self.root.destroy()
        print(f"\nFinal regions saved to: {self.regions_file}")

# ---------- Usage Functions ----------

def load_regions_from_json(json_file: str) -> Dict[str, Dict]:
    """Load regions from JSON file for programmatic use"""
    with open(json_file, 'r') as f:
        data = json.load(f)
    return data.get('regions', {})

def annotate_image_with_regions(img_path: str, regions_file: str = None, output_path: str = None, show_labels: bool = True):
    """Create annotated image using saved regions
    
    Args:
        img_path: Path to the image
        regions_file: Path to regions JSON file
        output_path: Path for output image
        show_labels: Whether to show region names on the image (default: True)
    """
    if regions_file is None:
        regions_file = img_path.replace('.png', '_regions.json').replace('.jpg', '_regions.json')
    
    if output_path is None:
        output_path = img_path.replace('.png', '_annotated.png').replace('.jpg', '_annotated.jpg')
    
    img = load_image(img_path)
    regions = load_regions_from_json(regions_file)
    
    for region_name, region_data in regions.items():
        pt1 = tuple(region_data['top_left'])
        pt2 = tuple(region_data['bottom_right'])
        color = tuple(region_data.get('color', [255, 0, 0]))
        
        # Draw transparent rectangle
        draw_transparent_rect(img, pt1, pt2, color, alpha=0.3)
        
        # Optionally add labels
        if show_labels:
            label_pos = (pt1[0], pt1[1] - 5)
            put_text_safe(img, region_name, label_pos, scale=0.5, 
                         color_bgr=(255, 255, 255), bg_bgr=color, bg_alpha=0.8)
    
    cv2.imwrite(output_path, img)
    print(f"Annotated image saved to: {output_path}")

# ---------- Main ----------

def main():
    if len(sys.argv) < 2:
        print("Usage: python annotation_tool.py <image_path> [regions_file]")
        print("Example: python annotation_tool.py deck.png")
        print("Example: python annotation_tool.py deck.png custom_regions.json")
        return
    
    img_path = sys.argv[1]
    regions_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    tool = RegionAnnotationTool(img_path, regions_file)
    tool.run()

if __name__ == "__main__":
    main()