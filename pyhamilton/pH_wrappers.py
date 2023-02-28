# -*- coding: utf-8 -*-
"""
Created on Sun Oct  2 15:40:58 2022

@author: stefa
"""
import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (PH_INIT, PH_REQ_BTRY, PH_MEASURE, PH_MEASURE_DYN, PH_REQ_CALIBRATION, PH_REQ_PROBE_DATA,
                        PH_REQ_TECH_DATA, PH_CALIBRATE, PH_CALIBRATE_DYN, PH_TERM, PH_SLEEP, PH_WAKEUP, PH_WASHER_INIT,
                        PH_WASHER_WASH, PH_WASHER_TERM, PH_DRYER_INIT, PH_DRYER_START, PH_DRYER_STOP, PH_DRYER_TERM,
                        PHC_WASH, PHC_DRY, PHC_LOAD, PHC_SAVE)

from .interface import (PHC_INIT, PHC_SET_PARAMS, PHC_PICKUP, PHC_PARK, PHC_CAL, PHC_MEASURE_CYCLE)
from .liquid_handling_wrappers import compound_pos_str


DEFAULT_WAIT_ON_RESPONSE_TIMEOUT = 300  # seconds



### Controller functions ###

def ph_controller_initialize(ham, port_number, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PHC_INIT, PortNumber = port_number)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data=['step-return2'])
    return int(response.moduleID)

def ph_controller_parameters(ham, module_id, seq_gripper, seq_wash, seq_dry, transport_channels,wash_cycles,dry_cycles,dry_time,
                             raise_first_exception=True,
                             wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    
    cmd = ham.send_command(PHC_SET_PARAMS,
                           ModuleID = module_id,
                           seqGripper = seq_gripper,
                           seqWashPosition = seq_wash,
                           seqDryPosition = seq_dry,
                           TransportChannel = transport_channels,
                           WashCycles = wash_cycles,
                           DryCycles = dry_cycles,
                           DryTime = dry_time)
    
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)


def ph_controller_pickup(ham, module_id, seq_module, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PHC_PICKUP, ModuleID = module_id, seqModule = seq_module)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)
    
def ph_controller_park(ham, module_id, seq_module, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PHC_PARK, ModuleID = module_id, seqModule = seq_module)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)


def ph_controller_calibrate(ham, module_id, seq_module, seq_solution_1,seq_solution_2,seq_reference,
                           measure_time,calibration_time,measure_height, pH_solution_1, pH_solution_2,
                           pH_reference,temp_solution_1, temp_solution_2, temp_solution_ref, calibrate_dynamically,
                           raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    
    cmd = ham.send_command(PHC_CAL, ModuleID = module_id, seqModule = seq_module, seqCalibration1 = seq_solution_1, 
                           seqCalibration2 = seq_solution_2, seqReference = seq_reference, MeasureTime = measure_time,
                           CalibrationTime = calibration_time, MeasureHeight = measure_height, 
                           CalibrationValue1 = pH_solution_1, CalibrationValue2 = pH_solution_2, 
                           CalibrationValueRef = pH_reference, TempSoln1 = temp_solution_1, TempSoln2 = temp_solution_2,
                           TempSolnRef = temp_solution_ref, CalibrateDynamically = calibrate_dynamically)
    
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)


def ph_controller_measure_cycle(ham, module_id, pos, measure_height, probe_pattern, measure_time,temperature,
                             raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    
    return_fields = ['step-return2']
    labware_pos = compound_pos_str(pos)
    cmd = ham.send_command(PHC_MEASURE_CYCLE,
                           ModuleID = module_id,
                           MeasurePositions = labware_pos,
                           MeasureHeight = measure_height,
                           ProbePattern = probe_pattern,
                           MeasureTime = measure_time,
                           Temperature = temperature)
    
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, 
                                    timeout=wait_on_response_timeout, return_data = return_fields)
    
    pH_values = response.return_data[0].split(';')
    pH_values = [float(pH) for pH in pH_values]
    return pH_values

def ph_controller_wash(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PHC_WASH, ModuleID = module_id)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_controller_dry(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PHC_DRY, ModuleID = module_id)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_controller_loadconfig(ham, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5']
    cmd = ham.send_command(PHC_LOAD)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, 
                                    timeout=wait_on_response_timeout, return_data = return_fields)
    return response

def ph_controller_saveconfig(ham, bluetooth_port, num_wash_cycles, num_dry_cycles, dry_time, 
                             raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    
    cmd = ham.send_command(PHC_SAVE, BluetoothPort = bluetooth_port, NumWashCycles = num_wash_cycles,
                           NumDryCycles = num_dry_cycles, DryTime = dry_time)
    
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, 
                                    timeout=wait_on_response_timeout)
    return response

### Low-level functions ###

def ph_initialize(ham, comport, simulate, asynch=False, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_INIT, Comport = comport, SimulationMode = simulate)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data=['step-return2'])
    return int(response.moduleID)

def ph_req_battery_data(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5']
    cmd = ham.send_command(PH_REQ_BTRY, ModuleID = module_id)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data

def ph_measure(ham, module_id, temperature, probePattern, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5']
    cmd = ham.send_command(PH_MEASURE, ModuleID = module_id, Temperature = temperature, probePattern = probePattern)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data

def ph_measure_dynamic(ham, module_id, temperature, precision, timeout, probePattern, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5']
    cmd = ham.send_command(PH_MEASURE_DYN, ModuleID = module_id, Temperature = temperature,
                           Precision = precision, Timeout = timeout, probePattern = probePattern)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data

def ph_request_calibration(ham, module_id, probe_number, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5',
                     'step-return6', 'step-return7', 'step-return8', 'step-return9'
                     ]
    cmd = ham.send_command(PH_REQ_CALIBRATION, ModuleID = module_id, ProbeNumber = probe_number)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data


def ph_request_probe_data(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5',
                     'step-return6'
                     ]
    cmd = ham.send_command(PH_REQ_PROBE_DATA, ModuleID = module_id)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data

def ph_request_technical_data(ham, module_id, hardware_number, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5']
    cmd = ham.send_command(PH_REQ_TECH_DATA, ModuleID = module_id, HardwareNumber = hardware_number)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data = return_fields)
    return response.return_data

def ph_calibrate(ham, module_id, cal_level, cal_value, cal_temperature, probe_pattern, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_CALIBRATE, ModuleID = module_id, CalibrationLevel = cal_level,
                           CalibrationValue = cal_value, CalibrationTemperature=cal_temperature,
                           probePattern = probe_pattern)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)
    return response

def ph_calibrate_dynamically(ham, module_id, variance, timeout, cal_level, cal_value, cal_temperature, probe_pattern, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_CALIBRATE_DYN, ModuleID = module_id, Variance = variance, Timeout = timeout,
                           CalibrationLevel = cal_level, CalibrationValue = cal_value,
                           CalibrationTemperature=cal_temperature, probePattern = probe_pattern)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)
    return response


def ph_wakeup(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_WAKEUP, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_sleep(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_SLEEP, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_washer_initialize(ham, comport, simulate, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_WASHER_INIT, Comport = comport, SimulationMode = simulate)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data=['step-return2'])
    return int(response.moduleID)

def ph_washer_wash(ham, module_id, cycle_num, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_WASHER_WASH, ModuleID = module_id, CycleNumber = cycle_num)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_washer_terminate(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_WASHER_TERM, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_dryer_initialize(ham, comport, simulate, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_DRYER_INIT, Comport = comport, SimulationMode = simulate)
    response = ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout, return_data=['step-return2'])
    return int(response.moduleID)

def ph_dryer_start(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_DRYER_START, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_dryer_stop(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_DRYER_STOP, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

def ph_dryer_terminate(ham, module_id, raise_first_exception=True, wait_on_response_timeout=DEFAULT_WAIT_ON_RESPONSE_TIMEOUT):
    cmd = ham.send_command(PH_DRYER_TERM, ModuleID = module_id)
    return ham.wait_on_response(cmd, raise_first_exception=raise_first_exception, timeout=wait_on_response_timeout)

