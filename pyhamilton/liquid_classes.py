from enum import Enum, IntEnum
import json
from typing import Dict, Any, Optional, Union

from .interface import (COPY_LIQ_CLASS, SET_ASP_PARAM, SET_DISP_PARAM, SET_TIP_TYPE, SET_CORR_CURVE,
                        SET_DISP_MODE)
from .resources.enums import TipType
from .liquid_class_db import DispenseMode, check_liquid_class_exists, liquid_class_has_parameter, load_liquid_classes
import os

class AspirateParameter(Enum):
    FLOW_RATE = -533331950
    MIX_FLOW_RATE = -533331949
    AIR_TRANSPORT_VOLUME = -533331948
    BLOW_OUT_VOLUME = -533331947
    SWAP_SPEED = -533331946
    SETTLING_TIME = -533331945
    OVER_ASPIRATE_VOLUME = -533331936
    CLOT_RETRACT_HEIGHT = -533331935

class DispenseParameter(Enum):
    FLOW_RATE = -533331950
    MIX_FLOW_RATE = -533331949
    AIR_TRANSPORT_VOLUME = -533331948
    BLOW_OUT_VOLUME = -533331947
    SWAP_SPEED = -533331946
    SETTLING_TIME = -533331945
    STOP_FLOW_RATE = -533331920
    STOP_BACK_VOLUME = -533331919

aspirate_params_to_db = {
    'FLOW_RATE': 'AsFlowRate',
    'MIX_FLOW_RATE': 'AsMixFlowRate',
    'AIR_TRANSPORT_VOLUME': 'AsAirTransportVolume',
    'BLOW_OUT_VOLUME': 'AsBlowOutVolume',
    'SWAP_SPEED': 'AsSwapSpeed',
    'SETTLING_TIME': 'AsSettlingTime',
    'OVER_ASPIRATE_VOLUME': 'AsOverAspirateVolume',
    'CLOT_RETRACT_HEIGHT': 'AsClotRetractHeight',
}

dispense_params_to_db = {
    'FLOW_RATE': 'DsFlowRate',
    'MIX_FLOW_RATE': 'DsMixFlowRate',
    'AIR_TRANSPORT_VOLUME': 'DsAirTransportVolume',
    'BLOW_OUT_VOLUME': 'DsBlowOutVolume',
    'SWAP_SPEED': 'DsSwapSpeed',
    'SETTLING_TIME': 'DsSettlingTime',
    'STOP_FLOW_RATE': 'DsStopFlowRate',
    'STOP_BACK_VOLUME': 'DsStopBackVolume',
}


def copy_liquid_class(ham_int, template_liquid_class: str, new_liquid_class: str):
    """Copy an existing liquid class to create a new one."""
    cid = ham_int.send_command(COPY_LIQ_CLASS, 
                              TemplateLiquidClass=template_liquid_class, 
                              NewLiquidClass=new_liquid_class)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def set_aspirate_parameter(ham_int, liquid_class: str, parameter: AspirateParameter, value: Any):
    """Set an aspirate parameter for a liquid class using enum."""
    cid = ham_int.send_command(SET_ASP_PARAM, 
                              LiquidClass=liquid_class, 
                              Parameter=parameter.value, 
                              Value=value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def set_dispense_parameter(ham_int, liquid_class: str, parameter: DispenseParameter, value: Any):
    """Set a dispense parameter for a liquid class using enum."""
    cid = ham_int.send_command(SET_DISP_PARAM, 
                              LiquidClass=liquid_class, 
                              Parameter=parameter.value, 
                              Value=value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def set_tip_type(ham_int, liquid_class: str, tip_type: int):
    """Set the tip type for a liquid class."""
    cid = ham_int.send_command(SET_TIP_TYPE, 
                              LiquidClass=liquid_class, 
                              TipType=tip_type)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def set_dispense_mode(ham_int, liquid_class: str, dispense_mode: int):
    """Set the dispense mode for a liquid class."""
    cid = ham_int.send_command(SET_DISP_MODE, 
                              LiquidClass=liquid_class, 
                              DispenseMode=dispense_mode)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def set_correction_curve(ham_int, liquid_class: str, nominal_array: list, corrected_array: list):
    """Set the correction curve for a liquid class."""
    cid = ham_int.send_command(SET_CORR_CURVE, 
                              LiquidClass=liquid_class, 
                              NominalArray=nominal_array, 
                              CorrectedArray=corrected_array)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)



def validate_liquid_class_definitions(definitions: list):
    """
    Validate the structure of a list of liquid class definitions.
    
    Args:
        definitions: A list of dictionaries representing liquid class definitions.

    Raises:
        ValueError: If the structure is invalid or missing required fields.
    """
    if not isinstance(definitions, list):
        raise ValueError("Input must be a list of liquid class definitions.")

    # Required top-level keys for each liquid class definition
    required_top_level_keys = ["name", "aspirate", "dispense", "tip_type", "dispense_mode"]
    required_tip_keys = ["volume", "has_filter"]
    
    # Required aspirate and dispense parameters
    required_aspirate_params = [param.name for param in AspirateParameter]
    required_dispense_params = [param.name for param in DispenseParameter]

    for i, definition in enumerate(definitions):
        if not isinstance(definition, dict):
            raise ValueError(f"Definition at index {i} must be a dictionary.")

        for key in required_top_level_keys:
            if key not in definition:
                raise ValueError(f"Definition for liquid class '{definition.get('name', 'unknown')}' is missing the required field: '{key}'.")
        
        tip_type_info = definition["tip_type"]
        for key in required_tip_keys:
            if key not in tip_type_info:
                raise ValueError(f"Definition for liquid class '{definition['name']}' is missing the required tip_type field: '{key}'.")

        aspirate_params = definition["aspirate"]
        for param in required_aspirate_params:
            if param not in aspirate_params:
                raise ValueError(f"Liquid class '{definition['name']}' is missing required aspirate parameter: '{param}'.")
        
        dispense_params = definition["dispense"]
        for param in required_dispense_params:
            if param not in dispense_params:
                raise ValueError(f"Liquid class '{definition['name']}' is missing required dispense parameter: '{param}'.")

        # Validate dispense mode
        dispense_mode = definition["dispense_mode"]
        if not isinstance(dispense_mode, str):
            raise ValueError(f"Liquid class '{definition['name']}' dispense_mode must be a string.")
        
        try:
            DispenseMode.from_string(dispense_mode)
        except ValueError as e:
            raise ValueError(f"Liquid class '{definition['name']}' has invalid dispense_mode: {e}")


def create_liquid_class_from_dict(
    ham_int,
    definitions: Union[list, dict]
):
    """
    Core logic: create new liquid classes from a dict/list of definitions.

    Args:
        ham_int: Hamilton interface object
        definitions: List (or single dict) of liquid class definitions
    """
    # Normalize single dict into list
    if isinstance(definitions, dict):
        definitions = [definitions]
    elif not isinstance(definitions, list):
        raise TypeError("definitions must be a dict or list of dicts")

    validate_liquid_class_definitions(definitions)



    for definition in definitions:
        new_liquid_class = definition["name"]

        if not check_liquid_class_exists(new_liquid_class):
            template_liquid_class = "Tip_50ulFilter_Water_DispenseSurface_Empty"  # default template
        else:
            print(f"Liquid class '{new_liquid_class}' already exists. It will be overwritten.")
            template_liquid_class = new_liquid_class  # overwrite existing
        parameters = {
            "aspirate": definition["aspirate"],
            "dispense": definition["dispense"]
        }
        tip_info = definition["tip_type"]
        dispense_mode_str = definition["dispense_mode"]
        correction_curve = definition.get("correction_curve")

        # Step 2: Copy the template liquid class
        copy_liquid_class(ham_int, template_liquid_class, new_liquid_class)

        # Step 3: Set aspirate parameters
        for param_name, value in parameters["aspirate"].items():
            try:
                aspirate_param = AspirateParameter[param_name.upper()]
                cache_param_name = aspirate_params_to_db.get(param_name.upper())
                if not liquid_class_has_parameter(new_liquid_class, cache_param_name, value):
                    set_aspirate_parameter(ham_int, new_liquid_class, aspirate_param, value)
            except KeyError:
                print(f"Warning: Unknown aspirate parameter '{param_name}' for '{new_liquid_class}' ignored.")

        # Step 4: Set dispense parameters
        for param_name, value in parameters["dispense"].items():
            try:
                dispense_param = DispenseParameter[param_name.upper()]
                cache_param_name = dispense_params_to_db.get(param_name.upper())
                if not liquid_class_has_parameter(new_liquid_class, cache_param_name, value):
                    set_dispense_parameter(ham_int, new_liquid_class, dispense_param, value)
            except KeyError:
                print(f"Warning: Unknown dispense parameter '{param_name}' for '{new_liquid_class}' ignored.")

        # Step 5: Determine and set the tip type
        volume = tip_info["volume"]
        has_filter = tip_info["has_filter"]

        selected_tip = None
        for tip_enum in TipType:
            if tip_enum.volume == volume:
                if has_filter == tip_enum.has_filter and not tip_enum.is_needle:
                    selected_tip = tip_enum
                    break

        if selected_tip:
            set_tip_type(ham_int, new_liquid_class, selected_tip.value)
            print(f"Set tip type to {selected_tip.name} for liquid class '{new_liquid_class}'.")
        else:
            raise ValueError(f"Could not find a suitable tip type for volume {volume} with filter={has_filter}.")

        # Step 6: Set dispense mode
        try:
            dispense_mode_enum = DispenseMode.from_string(dispense_mode_str)
            set_dispense_mode(ham_int, new_liquid_class, dispense_mode_enum.to_code())
            print(f"Set dispense mode to '{dispense_mode_str}' for liquid class '{new_liquid_class}'.")
        except ValueError as e:
            raise ValueError(f"Invalid dispense mode for liquid class '{new_liquid_class}': {e}")

        # Step 7: Set correction curve if provided
        if correction_curve:
            if "nominal" in correction_curve and "corrected" in correction_curve:
                set_correction_curve(
                    ham_int, new_liquid_class,
                    correction_curve["nominal"],
                    correction_curve["corrected"]
                )
                print(f"Set correction curve for liquid class '{new_liquid_class}'.")
            else:
                raise ValueError(f"Correction curve for '{new_liquid_class}' requires both 'nominal' and 'corrected' arrays.")

        print(f"Successfully configured liquid class '{new_liquid_class}' from template '{template_liquid_class}'.")


def create_liquid_class_from_json(
    ham_int,
    json_path: str
):
    """
    Wrapper: load JSON from file and pass it into create_liquid_class_from_dict.

    Args:
        ham_int: Hamilton interface object
        json_path: Path to a JSON file containing one or more liquid class definitions
    """
    if not os.path.isfile(json_path):
        raise FileNotFoundError(f"File not found: {json_path}")
    
    with open(json_path, 'r') as f:
        definitions = json.load(f)

    return create_liquid_class_from_dict(ham_int, definitions)
