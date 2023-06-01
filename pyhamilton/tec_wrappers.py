# -*- coding: utf-8 -*-
"""
Created on Tue May 30 21:44:03 2023

@author: stefa
"""
from .interface import TEC_INIT, TEC_START, TEC_SET_TARGET, TEC_STOP, TEC_TERMINATE
import logging

def initialize_tec(ham, controller_id, simulating):
    logging.info('Initializing TEC ' + str(controller_id) )
    cid = ham.send_command(TEC_INIT, ControllerID=controller_id, SimulationMode=simulating)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def set_target_tec(ham, target_temp, controller_id, device_id):
    logging.info('Set target temperature ' + str(controller_id) +' '+ str(device_id)+' to '+str(target_temp)+' degrees C')
    cid = ham.send_command(TEC_SET_TARGET, TargetTemperature=target_temp, ControllerID=controller_id, DeviceID=device_id)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def start_control_tec(ham, controller_id, device_id):
    logging.info('Starting temperature control '+str(controller_id)+' '+str(device_id))
    cid=ham.send_command(TEC_START, ControllerID=controller_id, DeviceID=device_id)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def stop_control_tec(ham, controller_id, device_id):
    logging.info('Ending temperature control '+str(controller_id)+' '+str(device_id))
    cid=ham.send_command(TEC_STOP, ControllerID=controller_id, DeviceID=device_id)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def terminate_tec(ham, stop_all_devices):
    logging.info('Terminating TEC')
    cid=ham.send_command(TEC_TERMINATE, StopAllDevices=stop_all_devices)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
