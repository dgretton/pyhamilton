# -*- coding: utf-8 -*-
"""
Created on Sun Feb 12 18:56:58 2023

@author: stefa
"""

import sys, os, time, logging, importlib
from threading import Thread

from functools import partial

from .interface import HamiltonInterface

from .interface import (MPE2_IP, MPE2_COM, MPE2_CLAMP, MPE2_COL_PLACED,
                        MPE2_COL_REMOVED, MPE2_DISCONNECT, MPE2_INIT,
                        MPE2_INIT_PARAMS, MPE2_DISCONNECT, MPE2_FIL_PLACED,
                        MPE2_FIL_REMOVED, MPE2_FIL_TO_COL, MPE2_FIL_TO_WASTE,
                        MPE2_FLUSH,MPE2_EVAP, MPE2_EVAP_END, MPE2_EVAP_RATE, 
                        MPE2_PRIME, MPE2_HEATER_STATUS, MPE2_TEMP_RANGE, MPE2_GET_VAC,
                        MPE2_MEAS_EMPTY, MPE2_MEAS_FULL, MPE2_DISPENSE,
                        MPE2_GET_PRESS, MPE2_RETRIEVE_FIL, MPE2_START_VAC, MPE2_STOP_VAC)


def mpe2_connect_ip(ham, instrument_name, port_number, simulation_mode, options = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_IP, InstrumentName=instrument_name, PortNumber=port_number, SimulationMode=simulation_mode, Options=options)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    result = response.return_data[0]
    return result

def mpe2_connect_com(ham, com_port, baud_rate, simulation_mode, options = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_COM, ComPort=com_port, BaudRate=baud_rate, SimulationMode=simulation_mode, Options=options)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_clamp_filter_plate(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_CLAMP, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_collection_plate_placed(ham, device_id, collection_plate_height, offset_from_nozzles):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_COL_PLACED, DeviceID=device_id, CollectionPlateHeight=collection_plate_height, OffsetFromNozzles=offset_from_nozzles)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_collection_plate_removed(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_COL_REMOVED, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_disconnect(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_DISCONNECT, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_initialize(ham, device_id):
    cmd = ham.send_command(MPE2_INIT, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_initialize_with_params(ham, device_id, smart, waste_container_id, vacuum_run_time, disable_vacuum_check):
    cmd = ham.send_command(MPE2_INIT_PARAMS, DeviceID=device_id, Smart=smart, WasteContainerID=waste_container_id, VacuumRunTime=vacuum_run_time, DisableVacuumCheck=disable_vacuum_check)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_filter_plate_placed(ham, device_id, filter_height, nozzle_height):
    cmd = ham.send_command(MPE2_FIL_PLACED, DeviceID=device_id, FilterHeight=filter_height, NozzleHeight=nozzle_height)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_filter_plate_removed(ham, device_id):
    cmd = ham.send_command(MPE2_FIL_REMOVED, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_process_filter_to_collection_plate(ham, device_id, control_points, return_plate_to_integration_area=''):
    cmd = ham.send_command(MPE2_FIL_TO_COL, DeviceID=device_id, ControlPoints=control_points, ReturnPlateToIntegrationArea=return_plate_to_integration_area)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_process_filter_to_waste_container(ham, device_id, control_points, return_plate_to_integration_area='', waste_container_id='', disable_vacuum_check=''):
    cmd = ham.send_command(MPE2_FIL_TO_WASTE, DeviceID=device_id, ControlPoints=control_points, ReturnPlateToIntegrationArea=return_plate_to_integration_area, WasteContainerID=waste_container_id, DisableVacuumCheck=disable_vacuum_check)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_retrieve_filter_plate(ham, device_id):
    cmd = ham.send_command(MPE2_RETRIEVE_FIL, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_start_mpe_vacuum(ham, device_id, waste_container_id='', disable_vacuum_check=''):
    cmd = ham.send_command(MPE2_START_VAC, DeviceID=device_id, WasteContainerID=waste_container_id, DisableVacuumCheck=disable_vacuum_check)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_stop_vacuum(ham, device_id):
    cmd = ham.send_command(MPE2_STOP_VAC, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_get_vacuum_status(ham, device_id):
    cmd = ham.send_command(MPE2_GET_VAC, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_get_pressure_readings(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_GET_PRESS, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_dispense(ham, device_id, source_id, well_volume, flow_rate_aspirate, flow_rate_dispense, needle_offset):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_DISPENSE, DeviceID=device_id, SourceID=source_id, WellVolume=well_volume, FlowRateAspirate=flow_rate_aspirate, FlowRateDispense=flow_rate_dispense, NeedleOffset=needle_offset)
    response = ham.wait_on_response(cmd, raise_first_exception=True,  return_data=return_field)
    return response

def mpe2_prime(ham, device_id, source_id, well_volume, flow_rate, waste_container_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_PRIME, DeviceID=device_id, SourceID=source_id, WellVolume=well_volume, FlowRate=flow_rate, WasteContainerID=waste_container_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True,  return_data=return_field)
    return response

def mpe2_flush(ham, device_id, well_volume, flow_rate, waste_container_id):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_FLUSH, DeviceID=device_id, WellVolume=well_volume, FlowRate=flow_rate, WasteContainerID=waste_container_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, return_data=return_field)
    return response

def mpe2_evaporate(ham, device_id, plate_height, needle_offset, well_depth, evaporator_travel_distance, evaporate_time):
    return_field = ['step-return2']
    cmd = ham.send_command(MPE2_EVAP, DeviceID=device_id, PlateHeight=plate_height, NeedleOffset=needle_offset, WellDepth=well_depth, EvaporatorTravelDistance=evaporator_travel_distance, EvaporateTime=evaporate_time)
    response = ham.wait_on_response(cmd, raise_first_exception=True,  return_data=return_field)
    return response


def mpe2_evaporate_with_rate(ham, device_id, plate_height, needle_offset, well_depth, evaporator_travel_distance, evaporate_time, follow_rate):
    cmd = ham.send_command(MPE2_EVAP_RATE, DeviceID=device_id, PlateHeight=plate_height, NeedleOffset=needle_offset, WellDepth=well_depth, EvaporatorTravelDistance=evaporator_travel_distance, EvaporateTime=evaporate_time, FollowRate=follow_rate)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_evaporate_end(ham, device_id, timeout):
    cmd = ham.send_command(MPE2_EVAP_END, DeviceID=device_id, Timeout=timeout)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_get_temperature_range(ham, device_id):
    cmd = ham.send_command(MPE2_TEMP_RANGE, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_get_heater_status(ham, device_id, reset):
    cmd = ham.send_command(MPE2_HEATER_STATUS, DeviceID=device_id, Reset=reset)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response

def mpe2_get_heater_range(ham, device_id, reset):
    cmd = ham.send_command(MPE2_TEMP_RANGE, DeviceID=device_id, Reset=reset)
    response = ham.wait_on_response(cmd, raise_first_exception=True)
    return response



