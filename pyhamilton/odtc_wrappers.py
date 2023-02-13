# -*- coding: utf-8 -*-
"""
Created on Mon Jan 23 23:25:49 2023

@author: stefa
"""

import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (ODTC_ABORT, ODTC_CONNECT, ODTC_INIT, ODTC_CLOSE, 
                        ODTC_PRTCL, ODTC_EVAL, ODTC_EXCT, ODTC_STATUS, 
                        ODTC_OPEN, ODTC_READ, ODTC_RESET, ODTC_STOP, ODTC_TERM)

std_timeout = 5


def odtc_abort(ham, device_id, lock_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_ABORT, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_connect(ham, simulation_mode, local_ip, device_ip, device_port = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_CONNECT, LocalIP=local_ip, DeviceIP=device_ip, DevicePort=device_port, SimulationMode=simulation_mode)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    device_id = int(response.return_data[0])
    return device_id

def odtc_initialize(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_INIT, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_close_door(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_CLOSE, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_download_protocol(ham, device_id, protocol_file, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_PRTCL, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_evaluate_error(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_EVAL, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_execute_protocol(ham, device_id, method_name, priority, lock_id = ''):
    
    if not 0 < priority < 10001:
        raise ValueError("Date provided can't be in the past")
    
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_EXCT, DeviceID=device_id, LockID=lock_id, MethodName=method_name, Priority=priority)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_get_status(ham, device_id):

    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5',
                     'step-return6', 'step-return7', 'step-return8']
    cmd = ham.send_command(ODTC_STATUS, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_fields)
    
    if ham.simulate:
        return ['Simulation_mode_placeholder']*len(return_fields)
    else:
        result = response.return_data
        return result

def odtc_open_door(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_OPEN, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_read_actual_temperature(ham, device_id, lock_id = ''):
    return_fields = ['step-return2', 'step-return3']
    cmd = ham.send_command(ODTC_READ, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_fields)
    if ham.simulate:
        return ['Simulation_mode_placeholder']*len(return_fields)
    else:
        result = response.return_data
        return result

def odtc_reset(ham, device_id, simulation_mode, timeout, str_device_id = '', pms_id = '', lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_RESET, DeviceID=device_id, LockID=lock_id, SimulationMode=simulation_mode, TimeToWait=timeout, strDeviceID=str_device_id, PMSID=pms_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_stop_method(ham, device_id, lock_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_STOP, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def odtc_terminate(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_TERM, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

