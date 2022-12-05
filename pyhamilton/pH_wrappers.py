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
                        PH_WASHER_WASH, PH_WASHER_TERM, PH_DRYER_INIT, PH_DRYER_START, PH_DRYER_STOP, PH_DRYER_TERM)

DEFAULT_WAIT_ON_RESPONSE_TIMEOUT = 300  # seconds


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

