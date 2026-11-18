"""Offline tests for HamiltonInterface.register_exception_table.

The robot is replaced by a fake HTTP handler that answers each command from a
script of responses, so these run anywhere. See tests/live/ for the robot gate.
"""
import json

import pytest

import pyhamilton.interface as interface
from pyhamilton.interface import HamiltonInterface, GRIP_GET
from pyhamilton.oemerr import LabwareError, HardwareError
from pyhamilton.error_handling import ExceptionTable, ErrorAction


def step_response(err_flag, main_err):
    # Block format per VENUS "General step result format":
    # ErrFlag[Num,MainErr,SlaveErr,RecoveryBtnId,StepData,LabwareName,LabwarePos
    return json.dumps({
        'command': 'STAR-return', 'step-name': 'gripGet', 'id': 'x',
        'step-return1': f'{err_flag}[1,{main_err},0,0,,plate_site,1',
        'step-return2': '', 'step-return3': '', 'step-return4': '',
    })


PLATE_MISSING = step_response(1, 21)   # error 21 = Labware not Found
HARDWARE = step_response(1, 2)
OK = step_response(0, 0)


@pytest.fixture
def robot(monkeypatch):
    """A HamiltonInterface wired to a scripted fake server. Set robot.script first."""
    sent, script = [], []

    class FakeServer:
        @staticmethod
        def send_str(s):
            sent.append(json.loads(s))

        @staticmethod
        def pop_response(_id):
            return script.pop(0) if script else None

    monkeypatch.setattr(interface, 'HamiltonServerHandler', FakeServer)
    ham = object.__new__(HamiltonInterface)  # skip __init__: no server thread or VENUS
    ham.simulating = False
    ham.debug = False
    ham.active = True
    ham.logger = None
    ham.log_queue = []
    ham.exception_table = None
    ham._sent_cmds = {}
    ham.sent, ham.script = sent, script
    return ham


def grip_get(ham, timeout=2):
    cid = ham.send_command(GRIP_GET, plateSequence='plate_site', checkPlate=1)
    return ham.wait_on_response(cid, raise_first_exception=True, timeout=timeout)


def table_with(handler, error=LabwareError, commands=('gripGet',), max_attempts=5):
    table = ExceptionTable()
    table.register(error, handler, commands=commands, max_attempts=max_attempts)
    return table


def test_no_table_raises_as_before(robot):
    robot.script[:] = [PLATE_MISSING]
    with pytest.raises(LabwareError):
        grip_get(robot)
    assert len(robot.sent) == 1


def test_retry_resends_identical_command_with_new_id(robot):
    robot.script[:] = [PLATE_MISSING, OK]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY))
    grip_get(robot)
    first, second = robot.sent
    assert first['id'] != second['id']
    assert {**first, 'id': None} == {**second, 'id': None}


def test_retry_until_success(robot):
    robot.script[:] = [PLATE_MISSING, PLATE_MISSING, OK]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY))
    grip_get(robot)
    assert len(robot.sent) == 3


def test_handler_receives_context(robot):
    seen = []
    robot.script[:] = [PLATE_MISSING, OK]
    robot.register_exception_table(table_with(lambda ctx: seen.append(ctx) or ErrorAction.RETRY))
    grip_get(robot)
    (ctx,) = seen
    assert isinstance(ctx.error, LabwareError)
    assert ctx.command == 'gripGet'
    assert ctx.cmd['plateSequence'] == 'plate_site'
    assert ctx.attempt == 1
    assert ctx.response.parsed_return[0]['mainErrField'] == 21
    assert ctx.ham_int is robot


def test_raise_action_reraises(robot):
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RAISE))
    with pytest.raises(LabwareError):
        grip_get(robot)
    assert len(robot.sent) == 1


def test_handler_returning_none_reraises(robot):
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table_with(lambda ctx: None))
    with pytest.raises(LabwareError):
        grip_get(robot)


def test_skip_returns_failed_response(robot):
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.SKIP))
    response = grip_get(robot)
    assert response.parsed_return[0]['mainErrField'] == 21


def test_max_attempts_stops_retrying(robot):
    calls = []
    robot.script[:] = [PLATE_MISSING] * 10
    robot.register_exception_table(
        table_with(lambda ctx: calls.append(ctx.attempt) or ErrorAction.RETRY, max_attempts=2))
    with pytest.raises(LabwareError):
        grip_get(robot)
    assert calls == [1, 2]
    assert len(robot.sent) == 3


def test_unmatched_error_type_raises(robot):
    robot.script[:] = [HARDWARE]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY))
    with pytest.raises(HardwareError):
        grip_get(robot)
    assert len(robot.sent) == 1


def test_command_filter_excludes_other_commands(robot):
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY, commands=['iSwapGet']))
    with pytest.raises(LabwareError):
        grip_get(robot)


def test_different_error_on_retry_goes_back_through_table(robot):
    seen = []
    robot.script[:] = [PLATE_MISSING, HARDWARE]
    table = table_with(lambda ctx: seen.append(type(ctx.error)) or ErrorAction.RETRY)
    robot.register_exception_table(table)
    with pytest.raises(HardwareError):
        grip_get(robot)
    assert seen == [LabwareError]


def test_first_matching_rule_wins(robot):
    order = []
    table = ExceptionTable()
    table.register(LabwareError, lambda ctx: order.append('specific') or ErrorAction.SKIP)
    table.register(Exception, lambda ctx: order.append('catch-all') or ErrorAction.RAISE)
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table)
    grip_get(robot)
    assert order == ['specific']


def test_success_never_calls_handler(robot):
    calls = []
    robot.script[:] = [OK]
    robot.register_exception_table(table_with(lambda ctx: calls.append(1)))
    grip_get(robot)
    assert calls == []


def test_without_raise_first_exception_table_is_bypassed(robot):
    calls = []
    robot.script[:] = [PLATE_MISSING]
    robot.register_exception_table(table_with(lambda ctx: calls.append(1) or ErrorAction.RETRY))
    cid = robot.send_command(GRIP_GET, plateSequence='plate_site')
    robot.wait_on_response(cid, raise_first_exception=False, timeout=2)
    assert calls == [] and len(robot.sent) == 1


def test_sent_commands_are_not_retained(robot):
    robot.script[:] = [PLATE_MISSING, OK]
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY))
    grip_get(robot)
    assert robot._sent_cmds == {}


def test_unregistering_table(robot):
    robot.register_exception_table(table_with(lambda ctx: ErrorAction.RETRY))
    robot.register_exception_table(None)
    robot.script[:] = [PLATE_MISSING]
    with pytest.raises(LabwareError):
        grip_get(robot)
