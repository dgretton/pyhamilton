from ..consumables import generate_reagent_summary, generate_tip_use_summary
from ..ngs.loading import LoadingVis
from ..liquid_handling_wrappers import TipSupportTracker


class Protocol:

    def __init__(self):
        self.num_samples = 0
        self.sample_volume = 0
        self.simulation = False
        self.tracked_reagent_vessels = {}  # Add this to store tracked vessels
        self.simulation_completed = False  # Track if simulation has been run
        self.loading_dialogues_completed = False  # Track if loading dialogues have been shown

    def prompt_step_selection(self):
        """
        Prompt user to select which protocol steps to run using checkboxes.
        """
        import tkinter as tk
        from tkinter import ttk
        import sys


        selected_methods = []
        action_taken = None  # Track which action was taken

        def validate_inputs():
            """Validate the input fields and return error message if invalid."""
            try:
                num_samples = int(samples_var.get())
                sample_volume = float(volume_var.get())
                
                if num_samples <= 0:
                    return "Number of samples must be greater than 0"
                if sample_volume <= 0:
                    return "Sample volume must be greater than 0"
                
                return None
            except ValueError:
                return "Please enter valid numbers for samples and volume"

        def get_selected_steps():
            """Get the currently selected steps."""
            steps = []
            for i, (_, method_name) in enumerate(self.available_steps):
                if checkbox_vars[i].get():
                    steps.append(method_name)
            return steps

        def update_protocol_params():
            """Update protocol parameters from input fields."""
            self.num_samples = int(samples_var.get())
            self.sample_volume = float(volume_var.get())

        def on_submit():
            nonlocal action_taken
            # Validate inputs first
            error_msg = validate_inputs()
            if error_msg:
                warning_label.config(text=error_msg, foreground="red")
                return
            
            # Check if at least one step is selected
            steps = get_selected_steps()
            if not steps:
                warning_label.config(text="Please select at least one step!", foreground="red")
                return
            
            # Check prerequisites for running live protocol
            if not self.simulation_completed:
                warning_label.config(text="Please run 'Simulate & Calculate' first before running live protocol!", foreground="red")
                return
                
            if not self.loading_dialogues_completed:
                warning_label.config(text="Please complete loading dialogues before running live protocol!", foreground="red")
                return
            
            # Update protocol with input values
            update_protocol_params()
            selected_methods.extend(steps)
            action_taken = "run"
            
            warning_label.config(text="", foreground="red")  # Clear any previous warnings
            root.destroy()

        def on_loading_dialogues():
            """Show loading dialogues and mark as completed."""
            if not self.simulation_completed:
                warning_label.config(text="Please run 'Simulate & Calculate' first!", foreground="red")
                return

            # Show status message before launching dialogues
            warning_label.config(text="Showing loading dialogues...", foreground="blue")
            root.update()

            # Show loading dialogues - let exceptions bubble up for debugging
            self.show_loading_dialogues(parent=root)

            # Mark loading dialogues as completed
            self.loading_dialogues_completed = True

            # Don’t update warning_label here since the widget may no longer exist
            # Just update the button states instead
            update_button_states()

        def update_button_states():
            """Update button states based on completion status."""
            # Enable/disable run button based on prerequisites
            if self.simulation_completed and self.loading_dialogues_completed:
                run_button.config(state="normal")
                status_label.config(text="✓ Ready to run live protocol", foreground="green")
            elif self.simulation_completed:
                run_button.config(state="disabled")
                loading_button.config(state="normal")
                status_label.config(text="✓ Simulation complete - Next: Show loading dialogues", foreground="blue")
            else:
                run_button.config(state="disabled")
                loading_button.config(state="disabled")
                status_label.config(text="Next: Run simulation", foreground="orange")

        def on_simulate():
            nonlocal action_taken
            # Validate inputs first
            error_msg = validate_inputs()
            if error_msg:
                warning_label.config(text=error_msg, foreground="red")
                return
            
            # Check if at least one step is selected
            steps = get_selected_steps()
            if not steps:
                warning_label.config(text="Please select at least one step!", foreground="red")
                return
            
            # Update protocol with input values
            update_protocol_params()
            
            try:
                # Show status message
                warning_label.config(text="Running simulation...", foreground="blue")
                root.update()
                
                # Run simulation
                print("Simulating protocol...")
                self.run_selected_steps(steps, simulation=True)
                
                # Generate reagent summary
                output_file = "reagent_summary.json"
                generate_reagent_summary(self.tracked_reagent_vessels, output_file=output_file)
                tip_summary = generate_tip_use_summary(self.tracked_tips, output_file="tip_summary.json")

                # Mark simulation as completed
                self.simulation_completed = True
                
                # Show success message
                warning_label.config(text=f"Simulation complete! Reagent summary saved to {output_file}", 
                                   foreground="green")
                
                print(f"Simulation complete. Reagent summary saved to {output_file}")
                
                # Update button states
                update_button_states()
                
            except Exception as e:
                import traceback
                full_traceback = traceback.format_exc()
                warning_label.config(text=f"Simulation failed: {str(e)}", foreground="red")
                print(f"Simulation error - Full traceback:")
                print(full_traceback)
                
        def on_select_all():
            for var in checkbox_vars:
                var.set(True)

        def on_clear_all():
            for var in checkbox_vars:
                var.set(False)

        def on_cancel():
            root.destroy()
            sys.exit("Protocol cancelled by user")

        def update_info_label():
            """Update the info label when input values change."""
            try:
                num_samples = int(samples_var.get()) if samples_var.get() else self.num_samples
                sample_volume = float(volume_var.get()) if volume_var.get() else self.sample_volume
            except ValueError:
                num_samples = self.num_samples
                sample_volume = self.sample_volume
            
            info_label.config(
                text=f"Samples: {num_samples} | Volume: {sample_volume}µL | Mode: {'Simulation' if self.simulation else 'Live'}"
            )

        root = tk.Tk()
        root.title("PacBio HiFiPlex Protocol - Step Selection")
        root.geometry("550x650")  # Increased height for new elements
        root.resizable(True, True)

        style = ttk.Style()
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Info.TLabel', font=('Arial', 10))

        main_frame = ttk.Frame(root, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        title_label = ttk.Label(main_frame, text="Select Protocol Steps to Execute",
                                style='Title.TLabel')
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Input section
        input_frame = ttk.LabelFrame(main_frame, text="Protocol Parameters", padding="10")
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Number of samples input
        ttk.Label(input_frame, text="Number of Samples:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        samples_var = tk.StringVar(value=str(self.num_samples) if self.num_samples > 0 else "")
        samples_entry = ttk.Entry(input_frame, textvariable=samples_var, width=15)
        samples_entry.grid(row=0, column=1, sticky="w")
        samples_entry.bind('<KeyRelease>', lambda e: update_info_label())

        # Sample volume input
        ttk.Label(input_frame, text="Sample Volume (µL):").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(5, 0))
        volume_var = tk.StringVar(value=str(self.sample_volume) if self.sample_volume > 0 else "")
        volume_entry = ttk.Entry(input_frame, textvariable=volume_var, width=15)
        volume_entry.grid(row=1, column=1, sticky="w", pady=(5, 0))
        volume_entry.bind('<KeyRelease>', lambda e: update_info_label())

        # Info label (now dynamically updated)
        info_label = ttk.Label(main_frame,
                            text=f"Samples: {self.num_samples} | Volume: {self.sample_volume}µL | Mode: {'Simulation' if self.simulation else 'Live'}",
                            style='Info.TLabel')
        info_label.grid(row=2, column=0, columnspan=2, pady=(10, 15))

        ttk.Separator(main_frame, orient='horizontal').grid(row=3, column=0, columnspan=2,
                                                        sticky="ew", pady=(0, 10))

        checkbox_frame = ttk.LabelFrame(main_frame, text="Available Steps", padding="10")
        checkbox_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 10))

        # Use 2 columns: step number + checkbox
        checkbox_vars = []
        for i, (display_name, _) in enumerate(self.available_steps):
            var = tk.BooleanVar(value=True)
            checkbox_vars.append(var)

            step_number = ttk.Label(checkbox_frame, text=f"Step {i+1}:", font=('Arial', 9))
            step_number.grid(row=i, column=0, sticky="w", padx=(0, 10))

            checkbox = ttk.Checkbutton(checkbox_frame, text=display_name, variable=var)
            checkbox.grid(row=i, column=1, sticky="w")

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))

        ttk.Button(button_frame, text="Select All", command=on_select_all).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Clear All", command=on_clear_all).grid(row=0, column=1, padx=5)

        warning_label = ttk.Label(main_frame, text="", foreground="red")
        warning_label.grid(row=6, column=0, columnspan=2, pady=(10, 0))

        # Status label for workflow progress
        status_label = ttk.Label(main_frame, text="Next: Run simulation", foreground="orange", 
                                font=('Arial', 9, 'italic'))
        status_label.grid(row=7, column=0, columnspan=2, pady=(5, 0))

        ttk.Separator(main_frame, orient='horizontal').grid(row=8, column=0, columnspan=2,
                                                        sticky="ew", pady=(10, 10))

        # Action buttons frame - now with 4 buttons
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=9, column=0, columnspan=2, pady=(10, 0))

        # Create buttons with initial states
        simulate_button = ttk.Button(action_frame, text="1. Simulate & Calculate", command=on_simulate)
        simulate_button.grid(row=0, column=0, padx=3)
        
        loading_button = ttk.Button(action_frame, text="2. Loading Dialogues", command=on_loading_dialogues, state="disabled")
        loading_button.grid(row=0, column=1, padx=3)
        
        run_button = ttk.Button(action_frame, text="3. Run Live Protocol", command=on_submit, state="disabled")
        run_button.grid(row=0, column=2, padx=3)
        
        ttk.Button(action_frame, text="Cancel", command=on_cancel).grid(row=0, column=3, padx=3)

        # Center window
        root.update_idletasks()
        width, height = root.winfo_width(), root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        root.mainloop()
        
        # Return selected methods only if "Run Selected Steps" was clicked
        if action_taken == "run":
            return selected_methods
        else:
            return []

    def reset_tracked_resources(self):
        """Reset all tracked resources to initial state."""
        for tips in self.tracked_tips:
            tips.reset_all()
        self.tip_support = TipSupportTracker(self.tip_support.resource)

    def run_selected_steps(self, steps: list, simulation: bool = True, windowed: bool = False, persistent: bool = False):
        # Perhaps we can implement some additional logic here but this seems fine for now
        self.simulation = simulation
        self.windowed = windowed
        self.persistent = persistent
        self.reset_tracked_resources()
        for step in steps:
            getattr(self, step)()

    def run_protocol(self, simulating=False, output_file="reagent_summary.json"):
        """Simulate the protocol and calculate consumables."""
        print("Simulating protocol...")

        steps = self.prompt_step_selection()
        if steps:  # Only run if steps were selected and "Run" was clicked
            self.run_selected_steps(steps, simulation=False, windowed=True, persistent=True)
            generate_reagent_summary(self.tracked_reagent_vessels, output_file=output_file)


    def show_loading_dialogues(self, parent=None):
        """Show loading dialogues during protocol execution."""
        
        vis = LoadingVis(
            reagent_data="reagent_summary.json",
            tip_data="tip_summary.json",
            origin_offset=(0, 0),
            auto_crop=False,
            parent=parent
        )

        vis.ShowDialogues(
            tube_offset=(360, 60),           # nudge the scrollable window to the right
            tube_viewport=(800, 700),        # fixed window size; scroll to see the rest
            deck_window_name="Deck",
            plate_window_name="96-well Plate",
        )