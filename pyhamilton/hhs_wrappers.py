import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface

from .interface import (HHS_BEGIN_MONITORING, HHS_CREATE_STAR_DEVICE, HHS_CREATE_USB_DEVICE,
    HHS_END_MONITORING, HHS_GET_FIRMWARE_VERSION, HHS_GET_SERIAL_NUM, HHS_GET_SHAKER_PARAM, HHS_GET_SHAKER_SPEED,
    HHS_GET_TEMP_PARAM, HHS_GET_TEMP, HHS_GET_TEMP_STATE, HHS_SEND_FIRMWARE_CMD, HHS_SET_PLATE_LOCK,
    HHS_SET_SHAKER_PARAM, HHS_SET_SIMULATION, HHS_SET_TEMP_PARAM, HHS_SET_USB_TRC, HHS_START_ALL_SHAKER,
    HHS_START_ALL_SHAKER_TIMED, HHS_START_SHAKER, HHS_START_SHAKER_TIMED, HHS_START_TEMP_CTRL, HHS_STOP_ALL_SHAKER,
    HHS_STOP_SHAKER, HHS_STOP_TEMP_CTRL, HHS_TERMINATE, HHS_WAIT_FOR_SHAKER, HHS_WAIT_FOR_TEMP_CTRL)

std_timeout = 5

def hhs_begin_monitoring(ham, device_number, tolerance_range, interval, action):
    cmd = ham.send_command(HHS_BEGIN_MONITORING, deviceNumber = device_number, \
            shakingToleranceRange = tolerance_range, sampleInterval = interval, action = action)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)


def hhs_create_star_device(ham, used_node, star_device='ML_STAR'):
    return_field = ['step-return2']
    cmd = ham.send_command(HHS_CREATE_STAR_DEVICE, starDevice = star_device, usedNode = used_node)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_field)
    device_number = response.return_data[0]
    return device_number


def hhs_create_usb_device(ham, used_node):
    cmd = ham.send_command(HHS_CREATE_USB_DEVICE, usedNode = used_node)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    device_number = response.return_data[0]
    return device_number

def hhs_end_monitoring(ham, device_number):
    cmd = ham.send_command(HHS_END_MONITORING, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    monitor_result = response.return_data[0]
    return monitor_result

def hhs_get_firmware_version(ham, device_number):
    cmd = ham.send_command(HHS_GET_FIRMWARE_VERSION, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    monitor_result = response.return_data[0]
    return monitor_result

def hhs_get_serial_num(ham, device_number):
    cmd = ham.send_command(HHS_GET_SERIAL_NUM, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    serial_number = response.return_data[0]
    return serial_number

def hhs_get_shaker_param(ham, device_number):
    return_fields = ['step-return2', 'step-return3']
    cmd = ham.send_command(HHS_GET_SHAKER_PARAM, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_fields)
    params = response.return_data[0:1]
    return params

def hhs_get_shaker_speed(ham, device_number):
    cmd = ham.send_command(HHS_GET_SHAKER_SPEED, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    shaker_speed = response.return_data[0]
    return shaker_speed

def hhs_get_temp_param(ham, device_number):
    return_fields = ['step-return2', 'step-return3', 'step-return4']
    cmd = ham.send_command(HHS_GET_TEMP_PARAM, deviceNumber = device_number)
    data = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=return_fields)
    '''***Check STAR_OEM_noFan to verify step return 4'''
    return data

def hhs_get_temp(ham, device_number):
    cmd = ham.send_command(HHS_GET_TEMP, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    temp = response.return_data[0]
    return temp

def hhs_get_temp_state(ham, device_number):
    cmd = ham.send_command(HHS_GET_TEMP_STATE, deviceNumber = device_number)
    response = ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout, return_data=['step-return2'])
    temp_state = response.return_data[0]
    return temp_state








def hhs_send_firmware_cmd(ham, device_number, command, parameter):
    '''*** ValueError: Assert valid command "HHS_SendFirmwareCommand" failed: command name "TA" does not match
        Probably need to get example commands from Hamilton'''
    cmd = ham.send_command(HHS_SEND_FIRMWARE_CMD, deviceNumber=device_number, command=command, parameter=parameter)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)



def hhs_set_plate_lock(ham, device_number, plate_lock):
    cmd = ham.send_command(HHS_SET_PLATE_LOCK, deviceNumber=device_number, plateLock=plate_lock)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_set_shaker_param(ham, device_number, shaking_direction, shaking_acc_ramp):
    cmd = ham.send_command(HHS_SET_SHAKER_PARAM, deviceNumber=device_number, shakingDirection=shaking_direction, \
            shakingAccRamp=shaking_acc_ramp)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_set_simulation(ham, simulate):
    cmd = ham.send_command(HHS_SET_SIMULATION, simulate=simulate)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_set_temp_param(ham, device_number, start_timeout, tolerance_range, security_range):
    cmd = ham.send_command(HHS_SET_TEMP_PARAM, deviceNumber=device_number, startTimeout=start_timeout, \
            toleranceRange=tolerance_range, securityRange=security_range)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_set_usb_trace(ham, trace):
    cmd = ham.send_command(HHS_SET_USB_TRC, trace=trace)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)



def hhs_start_all_shaker(ham, shaking_speed):
    '''*** trace: complete with error: node not initialized'''
    cmd = ham.send_command(HHS_START_ALL_SHAKER, shakingSpeed=shaking_speed)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)


def hhs_start_all_shaker_timed(ham, shaking_speed, shaking_time):
    '''*** trace: complete with error: node not initialized'''
    cmd = ham.send_command(HHS_START_ALL_SHAKER_TIMED, shakingSpeed=shaking_speed, shakingTime=shaking_time)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_start_shaker(ham, device_number, shaking_speed):
    cmd = ham.send_command(HHS_START_SHAKER, deviceNumber=device_number, shakingSpeed=shaking_speed)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_start_shaker_timed(ham, device_number, shaking_speed, shaking_time):
    cmd = ham.send_command(HHS_START_SHAKER_TIMED, deviceNumber=device_number, shakingSpeed=shaking_speed, \
            shakingTime=shaking_time)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_start_temp_ctrl(ham, device_number, temp, wait_for_temp_reached):
    cmd = ham.send_command(HHS_START_TEMP_CTRL, deviceNumber=device_number, temperature=temp, \
            waitForTempReached=wait_for_temp_reached)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)



def hhs_stop_all_shakers(ham):
    '''*** trace: complete with error: node not initialized'''
    cmd = ham.send_command(HHS_STOP_ALL_SHAKER)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_stop_shaker(ham, device_number):
    cmd = ham.send_command(HHS_STOP_SHAKER, deviceNumber=device_number)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_stop_temp_ctrl(ham, device_number):
    cmd = ham.send_command(HHS_STOP_TEMP_CTRL, deviceNumber=device_number)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_terminate(ham):
    cmd = ham.send_command(HHS_TERMINATE)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_wait_for_shaker(ham, device_number):
    cmd = ham.send_command(HHS_WAIT_FOR_SHAKER, deviceNumber=device_number)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)

def hhs_wait_for_temp_ctrl(ham, device_number):
    cmd = ham.send_command(HHS_WAIT_FOR_TEMP_CTRL, deviceNumber=device_number)
    ham.wait_on_response(cmd, raise_first_exception=True, timeout=std_timeout)