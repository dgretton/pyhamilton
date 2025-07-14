# -*- coding: utf-8 -*-
"""
Created on Wed Mar  9 12:01:01 2022

@author: stefa
@author: yang
"""

import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface
from .deckresource import LayoutManager, ResourceType, Plate24, Plate96, Tip96
from .oemerr import PositionError
from .interface import (INITIALIZE, PICKUP, EJECT, ASPIRATE, DISPENSE, ISWAP_GET, ISWAP_PLACE, HEPA,
WASH96_EMPTY, PICKUP96, EJECT96, ASPIRATE96, DISPENSE96, ISWAP_MOVE, MOVE_SEQ, TILT_INIT, TILT_MOVE, GRIP_GET,
GRIP_MOVE, GRIP_PLACE, SET_ASP_PARAM, SET_DISP_PARAM)
from .liquid_class_dict import liquidclass_params_asp, liquidclass_params_dsp

def resource_list_with_prefix(layout_manager, prefix, res_class, num_ress, order_key=None, reverse=False):
    def name_from_line(line):
        field = LayoutManager.layline_objid(line)
        if field:
            return field
        return LayoutManager.layline_first_field(line)
    layline_test = lambda line: LayoutManager.field_starts_with(name_from_line(line), prefix)
    res_type = ResourceType(res_class, layline_test, name_from_line)
    res_list = [layout_manager.assign_unused_resource(res_type, order_key=order_key, reverse=reverse) for _ in range(num_ress)]
    return res_list

def layout_item(lmgr, item_class, item_name):
    return lmgr.assign_unused_resource(ResourceType(item_class, item_name))

def labware_pos_str(labware, idx):
    return labware.layout_name() + ', ' + labware.position_id(idx)

def compound_pos_str(pos_tuples):
    present_pos_tups = [pt for pt in pos_tuples if pt is not None]
    return ';'.join((labware_pos_str(labware, idx) for labware, idx in present_pos_tups))

def compound_pos_str_96(labware96):
    return ';'.join((labware_pos_str(labware96, idx) for idx in range(96)))

def cells_384_to_1536(well, idx):
    return (well%16)*2+(well//16)*64+idx%2+(idx//2)*32

def cells_96_to_384(well, idx):
    return well*2+idx%2+(idx//2)*16+16*(well//8)

def wells_384_to_96(x):
    plate = x%2 + 2*((x//16)%2)
    well = x//2 - (x//16)*8 + (x//32)*8
    return plate, well

def get_cells_from_position_384(well):
    return [cells_384_to_1536(well, i) for i in range(4)]

def get_cells_from_position_96(well):
    return [cells_96_to_384(well, i) for i in range(4)]

def get_384w_quadrant(quadrant):
    return [cells_96_to_384(idx, quadrant) for idx in range(96)]
    
def compound_pos_str_384_quad(labware384, quadrant):
    return ';'.join((labware_pos_str(labware384, idx) for idx in get_384w_quadrant(quadrant)))


def initialize(ham, asynch=False):
    logging.info('initialize: ' + ('a' if asynch else '') + 'synchronously initialize the robot')
    cmd = ham.send_command(INITIALIZE)
    if not asynch:
        ham.wait_on_response(cmd, raise_first_exception=True, timeout=300)
    return cmd

def hepa_on(ham, speed=15, asynch=False, **more_options):
    logging.info('hepa_on: turn on HEPA filter at ' + str(speed) + '% capacity' +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    cmd = ham.send_command(HEPA, fanSpeed=speed, **more_options)
    if not asynch:
        ham.wait_on_response(cmd, raise_first_exception=True)
    return 

def wash_empty_refill(ham, asynch=False, **more_options):
    logging.info('wash_empty_refill: empty the washer' +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    cmd = ham.send_command(WASH96_EMPTY, **more_options)
    if not asynch:
        ham.wait_on_response(cmd, raise_first_exception=True)
    return cmd


def move_plate(ham, source_plate, target_plate, CmplxGetDict = None, CmplxPlaceDict = None, inversion = None, **more_options):
    
    logging.info('move_plate: Moving plate ' + source_plate.layout_name() + ' to ' + target_plate.layout_name())
    src_pos = labware_pos_str(source_plate, 0)
    trgt_pos = labware_pos_str(target_plate, 0)
    
    if not inversion:
        try_inversions=(0,1)
    else:
        try_inversions = (inversion,)
    
    getCmplxMvmnt, getRetractDist, getLiftUpHeight, getOrientation = (0, 0.0, 20.0, 1)
    placeCmplxMvmnt, placeRetractDist, placeLiftUpHeight, placeOrientation = (0, 0.0, 20.0, 1)
    
    
    if CmplxGetDict:
        getCmplxMvmnt = 1
        getRetractDist = CmplxGetDict['retractDist']
        getLiftUpHeight = CmplxGetDict['liftUpHeight']
        getOrientation = CmplxGetDict['labwareOrientation']
    
    if CmplxPlaceDict:
        placeCmplxMvmnt = 1
        placeRetractDist = CmplxPlaceDict['retractDist']
        placeLiftUpHeight = CmplxPlaceDict['liftUpHeight']
        placeOrientation = CmplxPlaceDict['labwareOrientation']

    for inv in try_inversions:    
        cid = ham.send_command(ISWAP_GET, 
                               plateLabwarePositions=src_pos, 
                               inverseGrip=inv, 
                               movementType = getCmplxMvmnt,
                               retractDistance = getRetractDist,
                               liftUpHeight = getLiftUpHeight,
                               labwareOrientation = getOrientation,
                               **more_options
                               )
        try:
            ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
            break
        except PositionError:
            print("trying inverse")
            pass

    cid = ham.send_command(ISWAP_PLACE, 
                           plateLabwarePositions=trgt_pos, 
                           movementType = placeCmplxMvmnt, 
                           retractDistance = placeRetractDist,
                           liftUpHeight = placeLiftUpHeight,
                           labwareOrientation = placeOrientation
                           )
    try:
        ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
    except PositionError:
        raise IOError


def move_by_seq(ham, source_plate_seq, target_plate_seq, CmplxGetDict = None, CmplxPlaceDict = None, grip_height = 0, inversion=None, gripForce = 2, width_before = 132, **more_options):
    logging.info('move_lid_by_seq: Moving plate ' + source_plate_seq + ' to ' + target_plate_seq)
    
    if not inversion:
        try_inversions=(0,1)
    else:
        try_inversions = (inversion,)

    getCmplxMvmnt, getRetractDist, getLiftUpHeight, getOrientation = (0, 0.0, 20.0, 1)
    placeCmplxMvmnt, placeRetractDist, placeLiftUpHeight, placeOrientation = (0, 0.0, 20.0, 1)
    
    
    if CmplxGetDict:
        getCmplxMvmnt = 1
        getRetractDist = CmplxGetDict['retractDist']
        getLiftUpHeight = CmplxGetDict['liftUpHeight']
        getOrientation = CmplxGetDict['labwareOrientation']
    
    if CmplxPlaceDict:
        placeCmplxMvmnt = 1
        placeRetractDist = CmplxPlaceDict['retractDist']
        placeLiftUpHeight = CmplxPlaceDict['liftUpHeight']
        placeOrientation = CmplxPlaceDict['labwareOrientation']

    
    for inv in try_inversions:
        cid = ham.send_command(ISWAP_GET, plateSequence=source_plate_seq, 
                                gripHeight=grip_height, 
                                gripForce=gripForce, 
                                inverseGrip=inv,
                                transportMode=0, 
                                widthBefore = width_before,
                                movementType = placeCmplxMvmnt, 
                                retractDistance = placeRetractDist,
                                liftUpHeight = placeLiftUpHeight,
                                labwareOrientation = placeOrientation,
                                **more_options)
        try:
            ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
            break
        except PositionError:
            pass
    else:
        raise IOError
    cid = ham.send_command(ISWAP_PLACE, 
                            plateSequence=target_plate_seq,
                            movementType = placeCmplxMvmnt, 
                            retractDistance = placeRetractDist,
                            liftUpHeight = placeLiftUpHeight,
                            labwareOrientation = placeOrientation
                            )
    try:
        r = ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
    except PositionError:
        raise IOError

def channel_var(pos_tuples):
    ch_var = ['0']*16
    for i, pos_tup in enumerate(pos_tuples):
        if pos_tup is not None:
            ch_var[i] = '1'
    return ''.join(ch_var)

def tip_pick_up(ham_int, pos_tuples, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.tip_pick_up(pos_tuples, **more_options)

def tip_eject(ham_int, pos_tuples=None, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.tip_eject(pos_tuples, **more_options)

def assert_parallel_nones(list1, list2):
    """Legacy wrapper for backward compatibility"""
    return HamiltonInterface._assert_parallel_nones(list1, list2)

default_liq_class = 'HighVolumeFilter_Water_DispenseJet_Empty_with_transport_vol'

def aspirate(ham_int, pos_tuples, vols, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.aspirate(pos_tuples, vols, **more_options)

def dispense(ham_int, pos_tuples, vols, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.dispense(pos_tuples, vols, **more_options)
    

def tip_pick_up_96(ham_int, tip96, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.tip_pick_up_96(tip96, **more_options)

def tip_eject_96(ham_int, tip96=None, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.tip_eject_96(tip96, **more_options)

def aspirate_96(ham_int, plate96, vol, **more_options):
    logging.info('aspirate_96: Aspirate volume ' + str(vol) + ' from ' + plate96.layout_name() +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    if 'liquidClass' not in more_options:
        more_options.update({'liquidClass':default_liq_class})
    ham_int.wait_on_response(ham_int.send_command(ASPIRATE96,
        labwarePositions=compound_pos_str_96(plate96),
        aspirateVolume=vol,
        **more_options), raise_first_exception=True)

def dispense_96(ham_int, plate96, vol, **more_options):
    logging.info('dispense_96: Dispense volume ' + str(vol) + ' into ' + plate96.layout_name() +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    if 'liquidClass' not in more_options:
        more_options.update({'liquidClass':default_liq_class})
    ham_int.wait_on_response(ham_int.send_command(DISPENSE96,
        labwarePositions=compound_pos_str_96(plate96),
        dispenseVolume=vol,
        **more_options), raise_first_exception=True)

def aspirate_384_quadrant(ham_int, plate384, quadrant, vol, **more_options):
    logging.info('aspirate_96: Aspirate volume ' + str(vol) + ' from ' + plate384.layout_name() +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    if 'liquidClass' not in more_options:
        more_options.update({'liquidClass':default_liq_class})
    ham_int.wait_on_response(ham_int.send_command(ASPIRATE96,
        labwarePositions=compound_pos_str_384_quad(plate384, quadrant),
        aspirateVolume=vol,
        **more_options), raise_first_exception=True)

def dispense_384_quadrant(ham_int, plate384, quadrant, vol, **more_options):
    logging.info('dispense_96: Dispense volume ' + str(vol) + ' into ' + plate384.layout_name() +
            ('' if not more_options else ' with extra options ' + str(more_options)))
    if 'liquidClass' not in more_options:
        more_options.update({'liquidClass':default_liq_class})
    ham_int.wait_on_response(ham_int.send_command(DISPENSE96,
        labwarePositions=compound_pos_str_384_quad(plate384, quadrant),
        dispenseVolume=vol,
        **more_options), raise_first_exception=True)       


def set_aspirate_parameter(ham_int, LiquidClass, Parameter, Value):
    param_key = liquidclass_params_asp[Parameter]
    cid = ham_int.send_command(SET_ASP_PARAM, LiquidClass = LiquidClass, Parameter = param_key, Value = Value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def set_dispense_parameter(ham_int, LiquidClass, Parameter, Value):
    param_key = liquidclass_params_dsp[Parameter]
    cid = ham_int.send_command(SET_DISP_PARAM, LiquidClass = LiquidClass, Parameter = param_key, Value = Value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def move_sequence(ham_int, sequence, xDisplacement=0, yDisplacement=0, zDisplacement=0):
    cid = ham_int.send_command(MOVE_SEQ, inputSequence=sequence, xDisplacement=xDisplacement, yDisplacement=yDisplacement, zDisplacement=zDisplacement)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def tilt_module_initialize(ham_int, module_name, comport, trace_level, simulate):
    cid = ham_int.send_command(TILT_INIT, ModuleName = module_name, 
                         Comport = comport, 
                         TraceLevel = trace_level, 
                         Simulate = simulate)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)
    
def tilt_module_move(ham_int, module_name, angle):
    cid = ham_int.send_command(TILT_MOVE, ModuleName = module_name, Angle = angle)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def get_plate_gripper_seq(ham, source_plate_seq,  gripHeight, gripWidth, openWidth, lid, tool_sequence, **more_options):
    logging.info('get_plate: Getting plate ' + source_plate_seq )
    
    if lid:
        cid = ham.send_command(GRIP_GET, plateSequence=source_plate_seq, transportMode=1, gripHeight=gripHeight, gripWidth=gripWidth, widthBefore=openWidth, toolSequence=tool_sequence)
    else:
        cid = ham.send_command(GRIP_GET, plateSequence=source_plate_seq, transportMode=0, gripHeight=gripHeight, gripWidth=gripWidth, widthBefore=openWidth, toolSequence=tool_sequence)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def move_plate_gripper_seq(ham, dest_plate_seq, **more_options):
    logging.info('move_plate: Moving plate ' + dest_plate_seq)
    cid = ham.send_command(GRIP_MOVE, plateSequence=dest_plate_seq)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)
    
def place_plate_gripper_seq(ham, dest_plate_seq, tool_sequence, **more_options):
    logging.info('place_plate: Placing plate ' + dest_plate_seq )
    cid = ham.send_command(GRIP_PLACE, plateSequence=dest_plate_seq, toolSequence=tool_sequence)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)

def move_plate_gripper(ham, dest_poss, **more_options):
    labware_poss = compound_pos_str(dest_poss)
    #logging.info('move_plate: Moving plate ' + dest_plate_seq)
    cid = ham.send_command(GRIP_MOVE, plateLabwarePositions=labware_poss, **more_options)
    ham.wait_on_response(cid, raise_first_exception=True, timeout=120)


class StderrLogger:
    def __init__(self, level):
        self.level = level
        self.stderr = sys.stderr

    def write(self, message):
        self.stderr.write(message)
        if message.strip():
            self.level(message.replace('\n', ''))

def add_stderr_logging(logger_name=None):
    logger = logging.getLogger(logger_name) # root logger if None
    sys.stderr = StderrLogger(logger.error)
    
def normal_logging(ham_int, method_local_dir):
    for handler in logging.root.handlers[:]:
        print(handler)
        logging.root.removeHandler(handler)
    logging.getLogger('parse').setLevel(logging.CRITICAL)
    local_log_dir = os.path.join(method_local_dir, 'log')
    if not os.path.exists(local_log_dir):
        os.mkdir(local_log_dir)
    main_logfile = os.path.join(local_log_dir, 'main.log')
    logging.basicConfig(filename=main_logfile, level=logging.DEBUG, format='[%(asctime)s] %(name)s %(levelname)s %(message)s')
    logger = logging.getLogger(__name__)
    add_stderr_logging()
    import __main__
    for banner_line in log_banner('Begin execution of ' + __main__.__file__):
        logging.info(banner_line)
    ham_int.set_log_dir(os.path.join(local_log_dir, 'hamilton.log'))
    ham_int.json_logger.set_log_dir(os.path.join(local_log_dir, 'robot_json.log'))


def run_async(funcs):
    def go():
        try:
            iter(funcs)
        except TypeError:
            funcs()
            return
        for func in funcs:
            func()
    func_thread = Thread(target=go, daemon=True)
    func_thread.start()
    return func_thread

def run_async_dict(func):
    logging.info("running async line 427 pace_util_stefan_dev.py")
    def go():
        func['function'](func['arguments'])
        return
    func_thread = Thread(target=go, daemon=True)
    func_thread.start()
    return func_thread


def yield_in_chunks(sliceable, n):
    sliceable = list(sliceable)
    start_pos = 0
    end_pos = n
    while start_pos < len(sliceable):
        yield sliceable[start_pos:end_pos]
        start_pos, end_pos = end_pos, end_pos + n

def log_banner(banner_text):
    l = len(banner_text)
    margin = 5
    width = l + 2*margin + 2
    return ['#'*width,
            '#' + ' '*(width - 2) + '#',
            '#' + ' '*margin + banner_text + ' '*margin + '#',
            '#' + ' '*(width - 2) + '#',
            '#'*width]
