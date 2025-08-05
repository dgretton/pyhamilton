# -*- coding: utf-8 -*-
"""
Created on Wed Mar  9 12:01:01 2022

@author: stefa
@author: yang
"""

import sys, os, time, logging, importlib
from threading import Thread

from .interface import HamiltonInterface
from .deckresource import LayoutManager, ResourceType, Plate24, Plate96, Tip96, resource_list_with_prefix, layout_item, DeckResource
from .oemerr import PositionError
from .interface import (INITIALIZE, PICKUP, EJECT, ASPIRATE, DISPENSE, ISWAP_GET, ISWAP_PLACE, HEPA,
WASH96_EMPTY, PICKUP96, EJECT96, ASPIRATE96, DISPENSE96, ISWAP_MOVE, MOVE_SEQ, TILT_INIT, TILT_MOVE, GRIP_GET,
GRIP_MOVE, GRIP_PLACE, SET_ASP_PARAM, SET_DISP_PARAM)
from .liquid_class_dict import liquidclass_params_asp, liquidclass_params_dsp
from .managed_resources import TrackedTips
from typing import List, Tuple
from .defaults import defaults

cfg = defaults()



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


def move_plate(ham, source_plate, target_plate, CmplxGetDict=None, CmplxPlaceDict=None, inversion=None, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.move_plate(source_plate, target_plate, CmplxGetDict, CmplxPlaceDict, inversion, **more_options)

def move_by_seq(ham, source_plate_seq, target_plate_seq, CmplxGetDict=None, CmplxPlaceDict=None, grip_height=0, inversion=None, gripForce=2, width_before=132, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.move_by_seq(source_plate_seq, target_plate_seq, CmplxGetDict, CmplxPlaceDict, grip_height, inversion, gripForce, width_before, **more_options)

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
    """Legacy wrapper for backward compatibility"""
    return ham_int.aspirate_96(plate96, vol, **more_options)

def dispense_96(ham_int, plate96, vol, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.dispense_96(plate96, vol, **more_options)

def aspirate_384_quadrant(ham_int, plate384, quadrant, vol, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.aspirate_384_quadrant(plate384, quadrant, vol, **more_options)

def dispense_384_quadrant(ham_int, plate384, quadrant, vol, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham_int.dispense_384_quadrant(plate384, quadrant, vol, **more_options)


def set_aspirate_parameter(ham_int, LiquidClass, Parameter, Value):
    param_key = liquidclass_params_asp[Parameter]
    cid = ham_int.send_command(SET_ASP_PARAM, LiquidClass = LiquidClass, Parameter = param_key, Value = Value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def set_dispense_parameter(ham_int, LiquidClass, Parameter, Value):
    param_key = liquidclass_params_dsp[Parameter]
    cid = ham_int.send_command(SET_DISP_PARAM, LiquidClass = LiquidClass, Parameter = param_key, Value = Value)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)


def move_sequence(ham_int, sequence, xDisplacement=0, yDisplacement=0, zDisplacement=0):
    """Legacy wrapper for backward compatibility"""
    return ham_int.move_sequence(sequence, xDisplacement, yDisplacement, zDisplacement)

def tilt_module_initialize(ham_int, module_name, comport, trace_level, simulate):
    cid = ham_int.send_command(TILT_INIT, ModuleName = module_name, 
                         Comport = comport, 
                         TraceLevel = trace_level, 
                         Simulate = simulate)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)
    
def tilt_module_move(ham_int, module_name, angle):
    cid = ham_int.send_command(TILT_MOVE, ModuleName = module_name, Angle = angle)
    ham_int.wait_on_response(cid, raise_first_exception=True, timeout=120)

def get_plate_gripper_seq(ham, source_plate_seq, gripHeight, gripWidth, openWidth, lid, tool_sequence, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.get_plate_gripper_seq(source_plate_seq, gripHeight, gripWidth, openWidth, lid, tool_sequence, **more_options)

def move_plate_gripper_seq(ham, dest_plate_seq, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.move_plate_gripper_seq(dest_plate_seq, **more_options)
    
def place_plate_gripper_seq(ham, dest_plate_seq, tool_sequence, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.place_plate_gripper_seq(dest_plate_seq, tool_sequence, **more_options)

def move_plate_gripper(ham, dest_poss, **more_options):
    """Legacy wrapper for backward compatibility"""
    return ham.move_plate_gripper(dest_poss, **more_options)


def move_plate_using_gripper(ham_int: HamiltonInterface, source: str, destination: str, gripHeight: float, gripWidth: float = 81, 
                             openWidth: float = 87, lid: bool = False, tool_sequence: str = cfg.core_gripper_sequence, 
                             gripForce: int = 8, ejectToolWhenFinish: int = 1, gripperToolChannel: int = 5):

    ham_int.get_plate_gripper_seq(source, gripHeight, gripWidth, openWidth, lid, tool_sequence, 
                                  gripForce=gripForce, gripperToolChannel=gripperToolChannel)

    ham_int.place_plate_gripper_seq(destination, tool_sequence=tool_sequence, ejectToolWhenFinish=ejectToolWhenFinish)

def tracked_tip_pick_up(ham_int: HamiltonInterface, tips_tracker: TrackedTips, n: int) -> List[Tuple[DeckResource, int]]:
    """
    Pick up `n` tips from the tracker, marking them as occupied.
    Returns a list of (DeckResource, position_within_rack).
    """


    if n > tips_tracker.count_remaining():
        raise ValueError(f"Only {tips_tracker.count_remaining()} tips available; {n} requested.")
    
    tips_poss = tips_tracker.fetch_next(n)
    try:
        print("Picking up tips at positions:")
        print(tips_poss)
        ham_int.tip_pick_up(tips_poss)
    except Exception as e:
        tips_tracker.mark_occupied(tips_poss)
        raise e
    return tips_poss

def tracked_tip_eject(ham_int: HamiltonInterface, tips_tracker: TrackedTips, eject_poss: List[Tuple[DeckResource, int]]):
    """
    Eject tips from the tracker, marking them as free.
    If `eject_positions` is None, eject all tips in the tracker.
    """

    ham_int.tip_eject(eject_poss)
    tips_tracker.mark_occupied(eject_poss, occupied=True)

    return eject_poss

def tracked_tip_pick_up_96(ham_int: HamiltonInterface, tips_tracker: TrackedTips):
    """
    Pick up `n` tips from the tracker, marking them as occupied.
    Returns a list of (DeckResource, position_within_rack).
    """

    tip_rack = tips_tracker.fetch_rack()
    ham_int.tip_pick_up_96(tip_rack)



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
