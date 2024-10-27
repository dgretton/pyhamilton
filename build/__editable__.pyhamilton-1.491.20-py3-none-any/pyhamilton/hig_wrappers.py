# -*- coding: utf-8 -*-
"""
Created on Fri Feb 10 00:01:53 2023

@author: stefa
"""

import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (HIG_CONNECT, HIG_DISCONNECT, HIG_HOME, HIG_SPIN,
                        HIG_SPINWAIT, HIG_OPEN, HIG_CLOSE, HIG_SPINNING,
                        HIG_ABORT)

std_timeout = 5


def hig_connect(ham, device_id, adapter_device_id, simulation_mode):
    return_field = ['step-return2']
    cmd = ham.send_command(HIG_CONNECT, DeviceID=device_id, AdapterDeviceID = adapter_device_id, SimulationMode = simulation_mode)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def hig_disconnect(ham):
    cmd = ham.send_command(HIG_DISCONNECT)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    return response

def hig_home(ham):
    cmd = ham.send_command(HIG_HOME)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    result = response.return_data[0]
    return result

def hig_spin(ham, Gs, acceleration_pct, deceleration_pct, time):
    cmd = ham.send_command(HIG_SPIN, RotationalGs = Gs, AccelPercent = acceleration_pct, 
                                    DecelPercent = deceleration_pct)
    response = ham.wait_on_response(cmd, raise_first_exception=True, 
                                    timeout = time + std_timeout)
    return response

def hig_spin_and_wait(ham, Gs, acceleration, deceleration, time):
    cmd = ham.send_command(HIG_SPINWAIT)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    return response

def hig_open_shield(ham, bucket_index):
    cmd = ham.send_command(HIG_OPEN, BucketIndex = bucket_index)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    return response

def hig_close_shield(ham):
    cmd = ham.send_command(HIG_CLOSE)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    return response

def hig_is_spinning(ham):
    return_field = ['step-return2']
    cmd = ham.send_command(HIG_SPINNING)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    result = response.return_data[0]
    return result

def hig_home(ham):
    cmd = ham.send_command(HIG_ABORT)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)
    return response