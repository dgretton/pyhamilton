# -*- coding: utf-8 -*-
"""
Created on Wed Oct  5 07:52:56 2022

@author: stefa
"""

import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (CENT_INIT, CENT_STATUS, CENT_CENT)


def centrifuge_initialize(ham, label, node_name, simulate, always_init):
    cmd = ham.send_command(CENT_INIT, Label = label, NodeName = node_name,
                           SimulationMode = simulate, AlwaysInitialize = always_init)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=300)


def centrifuge_get_drive_status(ham, label):
    return_fields = ['step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(CENT_STATUS, Label = label)
    outputs = ham.wait_on_response(cmd, raise_first_exception=True, timeout=300, return_data = return_fields)
    return outputs


def centrifuge_set_run(ham, label, array_speed, array_acceleration,
                   array_duration, deceleration, close_cover, 
                   direction, present_position):
    
    if not all([201 < speed < 4200 for speed in array_speed]):
        raise ValueError('Speed must be between 201 and 4200 rpm')
    
    if not all([1000 < acc < 6500 for acc in array_acceleration]):
        raise ValueError('Acceleration must be between 1000 and 6500 rpm^2')

    if not all([0 < dur < 2700 for dur in array_duration]):
        raise ValueError('Duration must be greater than 2700 seconds')
        
    if not 1000 < deceleration < 6500:
        raise ValueError('Deceleration must be between 1000 and 6500')
        
    array_acceleration = ','.join(map(str, array_acceleration))
    array_duration = ','.join(map(str, array_duration))
    array_speed = ','.join(map(str, array_speed))

    
    cmd = ham.send_command(CENT_CENT, Label = label, ArraySpeed = array_speed, 
                           ArrayAcceleration = array_acceleration, ArrayDuration = array_duration,
                           Deceleration = deceleration, CloseCoverAtEnd = close_cover, 
                           Direction = direction, PresentPosition = present_position)
    
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=300)






