# -*- coding: utf-8 -*-
"""
Created on Mon Jan 23 23:25:49 2023

@author: stefa
"""

import sys, os, time, logging, importlib
from threading import Thread
from dataclasses import dataclass

from ..interface import HamiltonInterface, HamiltonResponse

from ..interface import (ODTC_ABORT, ODTC_CONNECT, ODTC_INIT, ODTC_CLOSE, 
                        ODTC_PRTCL, ODTC_EVAL, ODTC_EXCT, ODTC_STATUS, 
                        ODTC_OPEN, ODTC_READ, ODTC_RESET, ODTC_STOP, ODTC_TERM)

std_timeout = 60


def odtc_abort(ham, device_id, lock_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_ABORT, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_connect(ham, simulation_mode, local_ip, device_ip, device_port = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_CONNECT, LocalIP=local_ip, DeviceIP=device_ip, DevicePort=device_port, SimulationMode=simulation_mode)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    if response == 0 and not ham.simulating:
        raise RuntimeError("Failed to connect to ODTC device")
    if ham.simulating:
        return 1  # Simulated device ID
    else:
        device_id = int(response.return_data[0])
    return device_id

def odtc_initialize(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_INIT, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_close_door(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_CLOSE, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_download_protocol(ham, device_id, protocol_file, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_PRTCL, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_evaluate_error(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_EVAL, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_execute_protocol(ham, device_id, method_name, priority=1, lock_id = '', simulating=False):
    
    if not 0 < priority < 10001:
        raise ValueError("Date provided can't be in the past")
    
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_EXCT, DeviceID=device_id, LockID=lock_id, MethodName=method_name, Priority=priority)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)

    @dataclass
    class ODTCExecuteResponse:
        duration: float     
        resultID: int
        raw: HamiltonResponse  # keep the raw object if callers need extras

    if simulating:
        return ODTCExecuteResponse(duration=0.0, resultID=0, raw=response)
    else:
        return ODTCExecuteResponse(duration=response.return_data[0], resultID=response.return_data[1], raw=response)

def odtc_get_status(ham, device_id):

    return_fields = ['step-return2', 'step-return3', 'step-return4', 'step-return5',
                     'step-return6', 'step-return7', 'step-return8']
    cmd = ham.send_command(ODTC_STATUS, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_fields)
    
    @dataclass
    class ODTCStatusResponse:
        '''
        'startup', 'resetting', 'standby', 'idle', 'busy', 'paused', 'errorhandling', 
        'inerror', 'asynchpaused', 'pauserequested', 'processing', 'responsewaiting'
        '''
        state: str
        raw: HamiltonResponse # keep the raw object if callers need extras


    if ham.simulating:
        #return ['Simulation_mode_placeholder']*len(return_fields)
        return ODTCStatusResponse(state='Simulation_mode_placeholder', raw=response)
    else:
        result = ODTCStatusResponse(
            state=response.return_data[0],
            raw=response
        )
        return result

def odtc_open_door(ham, device_id, lock_id = ''):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_OPEN, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

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
    return response

def odtc_stop_method(ham, device_id, lock_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_STOP, DeviceID=device_id, LockID=lock_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_terminate(ham, device_id):
    return_field = ['step-return2']
    cmd = ham.send_command(ODTC_TERM, DeviceID=device_id)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    return response

def odtc_wait_for_idle(ham, device_id, check_interval=5, max_wait=3000, simulating=False):
    '''
    Waits until the ODTC device is in 'idle' state.
    
    Parameters:
        ham (HamiltonInterface): The Hamilton interface instance.
        device_id (int): The ID of the ODTC device.
        check_interval (int): Time in seconds between status checks.
        max_wait (int): Maximum time in seconds to wait before raising a TimeoutError.
    
    Raises:
        TimeoutError: If the device does not reach 'idle' state within max_wait time.
    '''
    if simulating:
        return
    
    start_time = time.time()
    while True:
        status = odtc_get_status(ham, device_id)
        if status.state == 'idle':
            return
        elif time.time() - start_time > max_wait:
            raise TimeoutError(f"ODTC device {device_id} did not reach 'idle' state within {max_wait} seconds.")
        time.sleep(check_interval)
