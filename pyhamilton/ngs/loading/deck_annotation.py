import numpy as np
import json
import sys
import os
import tkinter as tk
from tkinter import filedialog, colorchooser, ttk, messagebox
from PIL import Image, ImageTk, ImageDraw
from typing import Tuple

# ---------- User Configuration ----------
ALPHA = 0.5  # Transparency of polygon fill
POINT_RADIUS = 3  # Smaller radius for corner points
POINT_COLOR = (0, 0, 0)  # Black (RGB)
TABLE_WIDTH = 400  # Increased width for new column
TABLE_HEIGHT_ROWS = 20

# Resource types
RESOURCE_TYPES = [
    "Reservoir",
    "96-well plate", 
    "24-well plate",
    "32-tube rack",
    "24-tube rack"
]

# ---------- Globals ----------
regions = []
current_points = []
dragging_point_idx = -1
dragging_region_idx = -1
base_img_pil = None
tk_photo_image = None
canvas = None
image_path = None
json_path = None
treeview = None
name_entry_edit = None
type_combo_edit = None

# ---------- Helpers ----------
def load_image_pil(path: str):
    try:
        return Image.open(path).convert('RGB')
    except FileNotFoundError:
        return None

def load_regions_from_json(path: str):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return []

    loaded = []
    for name, info in data.items():
        # NEW: Skip metadata keys like "image_path" and "image_dimensions"
        if name in ["image_path", "image_dimensions"]:
            continue

        loaded.append({
            "name": name,
            "points": [tuple(int(c) for c in p) for p in info["points"]],
            "color": tuple(info.get("color", (255, 255, 255))),
            "resource_type": info.get("resource_type", "Reservoir")  # Default to Reservoir
        })
    return loaded

def save_regions_to_json(path: str, regions_list: list, image_path_str: str, img_dims: Tuple[int, int]):
    """
    Saves regions data along with image metadata to a JSON file.
    """
    save_data = {}
    
    # NEW: Include image path and dimensions in the JSON
    save_data["image_path"] = os.path.basename(image_path_str) # Save only the file name
    save_data["image_dimensions"] = {
        "width": img_dims[0],
        "height": img_dims[1]
    }
    
    for region in regions_list:
        save_data[region['name']] = {
            "points": region["points"],
            "color": region["color"],
            "resource_type": region.get("resource_type", "Reservoir")
        }
    with open(path, 'w') as f:
        json.dump(save_data, f, indent=4)

def draw_all_elements(canvas):
    global tk_photo_image

    overlay = Image.new('RGBA', base_img_pil.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for region in regions:
        r, g, b = region['color']
        fill = (r, g, b, int(ALPHA * 255))
        draw.polygon(region['points'], fill=fill)

        for x, y in region['points']:
            draw.ellipse((x-POINT_RADIUS, y-POINT_RADIUS, x+POINT_RADIUS, y+POINT_RADIUS),
                          fill=POINT_COLOR, outline=POINT_COLOR)

    for x, y in current_points:
        draw.ellipse((x-POINT_RADIUS, y-POINT_RADIUS, x+POINT_RADIUS, y+POINT_RADIUS),
                          fill=(0, 255, 0), outline=(0, 255, 0))

    composite = Image.alpha_composite(base_img_pil.convert('RGBA'), overlay)
    tk_photo_image = ImageTk.PhotoImage(composite)
    canvas.create_image(0, 0, image=tk_photo_image, anchor='nw')
    canvas.image = tk_photo_image

def get_closest_point_index(mouse_pos, points, thresh=5):
    for i, p in enumerate(points):
        if np.linalg.norm(np.array(mouse_pos) - np.array(p)) < thresh:
            return i
    return -1

# ---------- Event Handlers ----------
def on_mouse_down(event):
    global dragging_point_idx, dragging_region_idx

    dragging_point_idx = -1
    dragging_region_idx = -1

    for i, region in enumerate(regions):
        idx = get_closest_point_index((event.x, event.y), region['points'])
        if idx != -1:
            dragging_point_idx = idx
            dragging_region_idx = i
            break

    if dragging_region_idx == -1:
        current_points.append((event.x, event.y))
        draw_all_elements(canvas)
        if len(current_points) >= 4:
            regions.append({
                "name": f"Region_{len(regions)+1}",
                "points": list(current_points),
                "color": (255, 255, 255),
                "resource_type": "Reservoir"  # Default type
            })
            current_points.clear()
            draw_all_elements(canvas)
            update_treeview()

def on_mouse_right_click(event):
    """
    Clears the list of pending points on a right-click.
    """
    global current_points
    if current_points:
        current_points.clear()
        draw_all_elements(canvas)


def on_mouse_up(event):
    global dragging_point_idx, dragging_region_idx
    dragging_point_idx = -1
    dragging_region_idx = -1

def on_mouse_move(event):
    if dragging_point_idx != -1 and dragging_region_idx != -1:
        regions[dragging_region_idx]['points'][dragging_point_idx] = (event.x, event.y)
        draw_all_elements(canvas)

def on_key_press(event, root):
    if event.keysym == 's':
        save_json()
    elif event.keysym == 'q':
        root.quit()

def save_json():
    # NEW: Pass image path and dimensions to save_regions_to_json
    if base_img_pil:
        dims = base_img_pil.size
    else:
        dims = (0, 0) # Fallback if image isn't loaded
        
    save_regions_to_json(json_path, regions, image_path, dims)
    messagebox.showinfo("Saved", f"Regions saved to {os.path.basename(json_path)}")

def update_treeview():
    for i in treeview.get_children():
        treeview.delete(i)
    
    for i, region in enumerate(regions):
        resource_type = region.get("resource_type", "Reservoir")
        item_id = treeview.insert("", "end", iid=i, values=(region["name"], "", resource_type))
        r, g, b = region["color"]
        color_hex = f'#{r:02x}{g:02x}{b:02x}'
        treeview.tag_configure(f'color{i}', background=color_hex)
        treeview.item(item_id, tags=(f'color{i}',))

def on_treeview_click(event):
    global name_entry_edit, type_combo_edit
    
    # Clean up any existing editors
    if name_entry_edit and name_entry_edit.winfo_exists():
        name_entry_edit.destroy()
        name_entry_edit = None
    if type_combo_edit and type_combo_edit.winfo_exists():
        type_combo_edit.destroy()
        type_combo_edit = None
    
    item_id = treeview.identify_row(event.y)
    if not item_id:
        return
    column = treeview.identify_column(event.x)
    
    if column == '#1':  # Name column
        edit_name(item_id)
    elif column == '#2':  # Color column
        edit_color(item_id)
    elif column == '#3':  # Resource Type column
        edit_resource_type(item_id)

def edit_name(item_id):
    global name_entry_edit
    if name_entry_edit and name_entry_edit.winfo_exists():
        name_entry_edit.destroy()
    bbox = treeview.bbox(item_id, "#1")
    if not bbox:
        return
    x, y, w, h = bbox
    current = treeview.item(item_id, 'values')[0]
    name_entry_edit = ttk.Entry(treeview)
    name_entry_edit.insert(0, current)
    name_entry_edit.bind("<Return>", lambda e: set_name(item_id))
    name_entry_edit.bind("<FocusOut>", lambda e: set_name(item_id))
    name_entry_edit.place(x=x, y=y, width=w, height=h)
    name_entry_edit.focus_set()

def set_name(item_id):
    global name_entry_edit
    if not name_entry_edit or not name_entry_edit.winfo_exists():
        return
    new_name = name_entry_edit.get()
    regions[int(item_id)]['name'] = new_name
    current_values = list(treeview.item(item_id, 'values'))
    current_values[0] = new_name
    treeview.item(item_id, values=tuple(current_values))
    name_entry_edit.destroy()
    name_entry_edit = None

def edit_color(item_id):
    r, g, b = regions[int(item_id)]['color']
    color_code = colorchooser.askcolor(initialcolor=f'#{r:02x}{g:02x}{b:02x}')
    if color_code[0]:
        regions[int(item_id)]['color'] = tuple(int(c) for c in color_code[0])
        update_treeview()
        draw_all_elements(canvas)

def edit_resource_type(item_id):
    global type_combo_edit
    if type_combo_edit and type_combo_edit.winfo_exists():
        type_combo_edit.destroy()
    bbox = treeview.bbox(item_id, "#3")
    if not bbox:
        return
    x, y, w, h = bbox
    current = regions[int(item_id)].get("resource_type", "Reservoir")
    
    type_combo_edit = ttk.Combobox(treeview, values=RESOURCE_TYPES, state="readonly")
    type_combo_edit.set(current)
    type_combo_edit.bind("<<ComboboxSelected>>", lambda e: set_resource_type(item_id))
    type_combo_edit.bind("<FocusOut>", lambda e: set_resource_type(item_id))
    type_combo_edit.place(x=x, y=y, width=w, height=h)
    type_combo_edit.focus_set()

def set_resource_type(item_id):
    global type_combo_edit
    if not type_combo_edit or not type_combo_edit.winfo_exists():
        return
    new_type = type_combo_edit.get()
    regions[int(item_id)]['resource_type'] = new_type
    current_values = list(treeview.item(item_id, 'values'))
    current_values[2] = new_type
    treeview.item(item_id, values=tuple(current_values))
    type_combo_edit.destroy()
    type_combo_edit = None

def delete_selected_region():
    selected = treeview.selection()
    if selected:
        item_id = selected[0]
        idx = int(item_id)
        del regions[idx]
        update_treeview()
        draw_all_elements(canvas)

# ---------- Main ----------
def main():
    global canvas, image_path, json_path, base_img_pil, regions, treeview, style

    root = tk.Tk()
    root.title("Deck Annotation")
    
    style = ttk.Style()
    style.configure("Treeview", background="white", fieldbackground="white")
    style.map('Treeview',
              background=[('selected', 'white')],
              foreground=[('selected', 'black')])

    if len(sys.argv) < 2:
        image_path = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not image_path:
            sys.exit(0)
    else:
        image_path = sys.argv[1]

    json_path = os.path.splitext(image_path)[0] + "_regions.json"
    base_img_pil = load_image_pil(image_path)
    regions = load_regions_from_json(json_path)

    # Create main frame
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Create paned window
    paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL, sashwidth=5)
    paned.pack(fill=tk.BOTH, expand=True)

    # Left panel with fixed width
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, minsize=TABLE_WIDTH, width=TABLE_WIDTH)
    
    # Create treeview with three columns
    treeview = ttk.Treeview(left_frame, columns=("Name", "Color", "Type"), show="headings", height=TABLE_HEIGHT_ROWS)
    treeview.heading("Name", text="Name")
    treeview.heading("Color", text="Color")
    treeview.heading("Type", text="Resource Type")
    treeview.column("Name", width=150)
    treeview.column("Color", width=50, anchor="center")
    treeview.column("Type", width=150)
    treeview.bind("<Double-1>", on_treeview_click)
    treeview.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Button frame
    button_frame = ttk.Frame(left_frame)
    button_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Save button
    save_btn = ttk.Button(button_frame, text="Save to JSON", command=save_json)
    save_btn.pack(side=tk.LEFT, padx=2)
    
    # Delete button
    delete_btn = ttk.Button(button_frame, text="Delete Selected", command=delete_selected_region)
    delete_btn.pack(side=tk.LEFT, padx=2)
    
    # Instructions label
    instructions = ttk.Label(left_frame, text="Keys: S=Save, Q=Quit\nDouble-click cells to edit", 
                             font=("Arial", 9), foreground="gray")
    instructions.pack(pady=5)
    
    update_treeview()

    # Right panel with canvas
    right_frame = ttk.Frame(paned)
    paned.add(right_frame)
    
    # Create scrollable canvas frame
    canvas_frame = ttk.Frame(right_frame)
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas with exact image dimensions
    canvas = tk.Canvas(canvas_frame, width=base_img_pil.width, height=base_img_pil.height, 
                         highlightthickness=0, bd=0)
    
    # Add scrollbars if needed
    v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
    h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=canvas.xview)
    
    canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
    canvas.configure(scrollregion=(0, 0, base_img_pil.width, base_img_pil.height))
    
    # Pack scrollbars and canvas
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # Bind events
    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    canvas.bind("<B1-Motion>", on_mouse_move)
    canvas.bind("<Button-3>", on_mouse_right_click)
    root.bind("<Key>", lambda e: on_key_press(e, root))

    # Draw initial elements
    draw_all_elements(canvas)
    
    # Calculate optimal window size
    window_width = TABLE_WIDTH + base_img_pil.width + 50  # Extra space for scrollbars and padding
    window_height = min(base_img_pil.height + 50, 800)  # Cap at 800px height
    
    # Set window size to fit content
    root.geometry(f"{min(window_width, 1400)}x{window_height}")
    
    # Center window on screen
    root.update_idletasks()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width - root.winfo_width()) // 2
    y = (screen_height - root.winfo_height()) // 2
    root.geometry(f"+{x}+{y}")
    
    root.mainloop()

if __name__ == "__main__":
    main()