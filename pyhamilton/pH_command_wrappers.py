# -*- coding: utf-8 -*-
"""
Created on Sun Oct  2 15:40:58 2022

@author: stefa
"""
import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (PH_INIT, PH_REQ_BTRY, PH_MEASURE, PH_MEASURE_DYN, PH_REQ_CALIBRATION, PH_REQ_PROBE_DATA,
                        PH_REQ_TECH_DATA, PH_CALIBRATE)


def ph_initialize(ham, comport, simulate, asynch=False):
    cmd = ham.send_command(PH_INIT, Comport = comport, SimulationMode = simulate)
    module_id = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data=['step-return2'])
    return module_id

def ph_req_battery_data(ham, module_id):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(PH_REQ_BTRY, ModuleID = module_id)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data

def ph_measure(ham, module_id, temperature, probePattern):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(PH_MEASURE, ModuleID = module_id, Temperature = temperature, probePattern = probePattern)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data

def ph_measure_dynamic(ham, module_id, temperature, precision, timeout, probePattern):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(PH_MEASURE_DYN, ModuleID = module_id, Temperature = temperature,
                           Precision = precision, Timeout = timeout, probePattern = probePattern)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data

def ph_request_calibration(ham, module_id, probe_number):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4',
                     'step-return5', 'step-return6', 'step-return7', 'step-return8'
                     ]
    cmd = ham.send_command(PH_REQ_CALIBRATION, ModuleID = module_id, ProbeNumber = probe_number)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data


def ph_request_probe_data(ham, module_id):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4',
                     'step-return5'
                     ]
    cmd = ham.send_command(PH_REQ_PROBE_DATA, ModuleID = module_id)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data

def ph_request_technical_data(ham, module_id, hardware_number):
    return_fields = ['step-return1', 'step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(PH_REQ_TECH_DATA, ModuleID = module_id, HardwareNumber = hardware_number)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return data

def ph_calibrate(ham, module_id, cal_level, cal_value, cal_temperature, probe_pattern):
    cmd = ham.send_command(PH_CALIBRATE, ModuleID = module_id, CalibrationLevel = cal_level,
                           CalibrationValue = cal_value, CalibrationTemperature=cal_temperature,
                           probePattern = probe_pattern)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300)
    return data
