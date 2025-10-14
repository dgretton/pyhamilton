from ..interface import HamiltonInterface
from ..resources import DeckResource, ResourceType,layout_item, LayoutManager
from ..resources import BulkReagentPlate, FalconCarrier24, EppiCarrier32, Reservoir60mL, Plate24, Plate96
from pathlib import Path
import json

class VolumeConsumptionTracker:
    def __init__(self, num_positions):
        self.initial_volumes = {k:v for k,v in [(idx, 0) for idx in range(num_positions)]}
        self.volumes = self.initial_volumes.copy()

    def aspirate_volume(self, well_index, volume):
        self.volumes[well_index] += volume

class TrackedContainer:
    """Base class for any tracked container type with volume bookkeeping."""

    def __init__(self):
        pass

    def aspirate_volume(self, well_index, volume):
        """Subtract volume from one or more wells. 
        Must be overridden in subclasses."""
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement aspirate_volume()"
        )

class TrackedReagentVessel(TrackedContainer):
    def __init__(self, *args, **kwargs):
        self.reagent_map = {}
   
    def assign_reagent_map(self, reagent_name: str, positions: list[int]) -> list[tuple[TrackedContainer, int]]:
        '''
        Assigns reagent positions for a specific reagent and returns the tuple of (container, position) for each position
        so we can pass the output to aspirate functions.
        '''
        self.reagent_map[reagent_name] = positions
        return self.reagent_positions(reagent_name)
    

    
    def reset_volumes(self):
        """
        Resets all volume trackers in the container to 0.
        """
        self.volumes = {pos: 0 for pos in self.volumes}

    def calculate_required_reagent_volume(self, reagent_name: str):
        # Use the negative volume from the tracker to determine reagent consumption for this tracked resource
        # return -self.volumes[self.reagent_map[reagent_name]]
        # Above won't work because self.reagent_map[reagent_name] is a list of positions, we want to do a list comprehension

        # Right now this only handles single-well reagents but should be extended to handle reagents distributed across
        # Multiple wells
        return -sum(self.volumes[pos] for pos in self.reagent_map[reagent_name]) + self.dead_volume

    def all_required_reagent_volumes(self):
        return {self.layout_name(): {reagent: self.calculate_required_reagent_volume(reagent) for reagent in self.reagent_map}}

    def reagent_positions(self, reagent_name):
        # List comprehension of form [(self, pos) for pos in self.reagent_map[reagent_name]]
        return [(self, pos) for pos in self.reagent_map[reagent_name]]
    

class ReagentTrackedPlate96(Plate96, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        Plate96.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {k:v for k,v in [(idx, 0) for idx in range(96)]}
        self.dead_volume = kwargs.get('dead_volume', 10) # uL


    def aspirate_volume(self, well_index, volume):
        self.volumes[well_index] -= volume
    
class ReagentTrackedBulkPlate(BulkReagentPlate, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        Plate96.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {0: 0}
        self.dead_volume = 100

    # The plate is a single container, so we subtract all volumes from one element in the tracker. This overrides the base method.
    def aspirate_volume(self, well_index, volume):
        self.volumes[0] -= volume
    
    # We return the plate object itself so we can pass it to 96 channel commands. This overrides the base method
    def assign_reagent_map(self, reagent_name, positions):
        self.reagent_map[reagent_name] = positions
        return self
    
    def calculate_required_reagent_volume(self, reagent_name):
        # Use the negative volume from the tracker to determine reagent consumption for this tracked resource
        return -self.volumes[0] + self.dead_volume

class ReagentTrackedPlate24(Plate24, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        Plate24.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {k:v for k,v in [(idx, 0) for idx in range(24)]}
        self.dead_volume = kwargs.get('dead_volume', 20) # uL


    def aspirate_volume(self, well_index, volume):
        self.volumes[well_index] -= volume

class ReagentTrackedReservoir60mL(Reservoir60mL, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        Reservoir60mL.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {0: 0}
        self.dead_volume = kwargs.get('dead_volume', 200) # uL

    # The 60mL trough is a single well, so we subtract all volumes from one element in the tracker. This overrides the base method.
    def aspirate_volume(self, well_index, volume):
        self.volumes[0] -= volume

    def calculate_required_reagent_volume(self, reagent_name):
        # Use the negative volume from the tracker to determine reagent consumption for this tracked resource
        return -self.volumes[0] + self.dead_volume


    def height_to_volume(self, height):
        pass

class ReagentTrackedFalconCarrier24(FalconCarrier24, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        FalconCarrier24.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {k:v for k,v in [(idx, 0) for idx in range(24)]}
        self.dead_volume = kwargs.get('dead_volume', 10) # uL


    def aspirate_volume(self, well_index, volume):
        self.volumes[well_index] -= volume

class ReagentTrackedEppiCarrier32(EppiCarrier32, TrackedReagentVessel):
    def __init__(self, *args, **kwargs):
        EppiCarrier32.__init__(self, *args, **kwargs)
        TrackedReagentVessel.__init__(self)
        self.volumes = {k:v for k,v in [(idx, 0) for idx in range(32)]}
        self.dead_volume = kwargs.get('dead_volume', 10) # uL


    def aspirate_volume(self, well_index, volume):
        self.volumes[well_index] -= volume


# Helper function to get the class name of an object
def get_class_name(obj):
    """Returns the name of the object's class as a string."""
    return type(obj).__name__

def generate_reagent_summary(tracked_vessels: list, units_default: str = "uL", output_file: str = None):
    """
    Generates a summary of reagent consumption from a list of tracked vessels.
    Now also includes vessels with custom labels even if they have no reagent consumption.
    """
    summary = {"units_default": units_default}
    
    for vessel in tracked_vessels:
        vessel_name = vessel.layout_name()

        if isinstance(vessel, TrackedReagentVessel):
            vessel_data = vessel.all_required_reagent_volumes()[vessel_name]
        else:
            vessel_data = {}

        # Check if vessel has a custom label
        has_custom_label = hasattr(vessel, 'custom_label') and vessel.custom_label is not None
        
        # Skip vessels with no reagents AND no custom label
        if not has_custom_label and (not vessel_data or all(vol <= 0 for vol in vessel_data.values())):
            continue
        
        summary[vessel_name] = {
            "class_name": get_class_name(vessel),
            "positions": {}
        }
        
        # Add custom label if present
        if has_custom_label:
            summary[vessel_name]["custom_label"] = vessel.custom_label
        
        # For each reagent in this vessel, find which positions it occupies
        for reagent_name, total_volume in vessel_data.items():
            if total_volume <= 0:
                continue
                
            # Get the positions where this reagent is located
            reagent_positions = vessel.reagent_map.get(reagent_name, [])
            
            for pos in reagent_positions:
                # Get the volume consumed from this specific position
                pos_volume = -vessel.volumes.get(pos, 0) if vessel.volumes.get(pos, 0) < 0 else 0
                
                if pos_volume > 0:
                    summary[vessel_name]["positions"][pos] = {
                        "reagent": reagent_name,
                        "volume": pos_volume,
                        "unit": "uL"
                    }
    
    # Write to JSON file if output_file is specified
    if output_file:
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"Reagent summary written to {output_file}")
    
    return summary


def generate_tip_use_summary(tracked_tips_list, output_file=None):
    """
    Generate tip consumption summary data from TrackedTips objects.
    
    Parameters
    ----------
    tracked_tips_list : list[TrackedTips]
        List of TrackedTips objects to analyze
        
    Returns
    -------
    dict
        Summary data structure with consumption details for LoadingVis
    """
    from datetime import datetime
    
    report_data = {
        "report_generated": datetime.now().isoformat(),
        "tip_trackers": {},
        "summary": {
            "total_trackers": len(tracked_tips_list),
            "total_tips_available": 0,
            "total_tips_consumed": 0,
            "total_tips_capacity": 0,
            "overall_consumption_rate": 0.0
        }
    }
    
    for i, tracker in enumerate(tracked_tips_list, 1):
        # Calculate consumption metrics for this tracker
        total_tips = tracker.total_tips()
        remaining_tips = tracker.count_remaining()
        consumed_tips = total_tips - remaining_tips
        consumption_rate = (consumed_tips / total_tips * 100) if total_tips > 0 else 0
        
        # Update summary totals
        report_data["summary"]["total_tips_capacity"] += total_tips
        report_data["summary"]["total_tips_available"] += remaining_tips
        report_data["summary"]["total_tips_consumed"] += consumed_tips
        
        # Analyze by rack
        rack_details = []
        rack_start_idx = 0
        
        for rack in tracker.tip_racks:
            rack_total = rack._num_items
            rack_occupied = sum(1 for j in range(rack_total) 
                              if tracker.is_occupied(rack_start_idx + j))
            rack_consumed = rack_total - rack_occupied
            rack_consumption_rate = (rack_consumed / rack_total * 100) if rack_total > 0 else 0
            
            rack_info = {
                "name": rack.layout_name(),
                "total_tips": rack_total,
                "tips_consumed": rack_consumed,
                "tips_remaining": rack_occupied,
                "consumption_rate": round(rack_consumption_rate, 1)
            }
            rack_details.append(rack_info)
            rack_start_idx += rack_total
        
        # Store tracker data
        tracker_data = {
            "tracker_id": tracker.tracker_id,
            "volume_capacity": tracker.volume_capacity,
            "total_tips": total_tips,
            "tips_consumed": consumed_tips,
            "tips_remaining": remaining_tips,
            "consumption_rate": round(consumption_rate, 1),
            "num_racks": len(tracker.tip_racks),
            "racks": rack_details
        }
        report_data["tip_trackers"][f"tracker_{i}"] = tracker_data
    
    # Calculate overall summary
    total_capacity = report_data["summary"]["total_tips_capacity"]
    total_consumed = report_data["summary"]["total_tips_consumed"]
    if total_capacity > 0:
        overall_rate = (total_consumed / total_capacity * 100)
        report_data["summary"]["overall_consumption_rate"] = round(overall_rate, 1)

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report_data, f)

    return report_data


def tracked_volume_aspirate(ham_int: HamiltonInterface, plate_poss: list[tuple[TrackedContainer, int]], vols: list, **kwargs):
    response = ham_int.aspirate(plate_poss, vols, **kwargs)
    filtered_pairs = [(pos, vol) for pos, vol in zip(plate_poss, vols) if pos is not None]
    plate_poss, vols = zip(*filtered_pairs) if filtered_pairs else ([], [])
    
    try:
        for (plate, well_index), vol in zip(plate_poss, vols):
            plate.aspirate_volume(well_index, vol)
    except AttributeError:
        return response
    
    return response

def tracked_volume_aspirate_96(ham_int: HamiltonInterface, plate: TrackedContainer, vol: int, **kwargs):
    ham_int.aspirate_96(plate, vol, **kwargs)
    
    try: # In case the plate doesn't implement aspirate_volume, we just skip it
        for well_idx in range(96):
            plate.aspirate_volume(well_idx, vol)
    except AttributeError:
        return