"""Live gate for HamiltonInterface.register_exception_table on a real STAR.

Walks an operator through every recovery path of the CO-RE gripper "plate not
found" case and prints PASS/FAIL per test. Exit code is 0 only if nothing failed.

Deck setup
  - One plate site with a sequence name in the layout (--site). Have a plate that
    fits your grip settings ready by hand. The operator adds and removes it when asked.
  - CO-RE gripper tools in their rack (--tool-seq, default from pyhamilton config).

Run (from the repo root)
  py -3.13 tests/live/live_exception_table.py --site <plate_site_sequence>
      [--grip-width 81] [--grip-height 5] [--width-before 90] [--gripper-channel 8]
      [--check-plate 0|1] [--windowed] [--no-init] [--only T1,T4]

  --fake runs the same tests against a simulated robot with scripted operator
  actions, to check the script itself without hardware.

Every test that can leave the gripper tool on the channels finishes with a cleanup:
the operator puts the plate back, then a get and a place return the plate and eject
the tool.
"""
import argparse
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pyhamilton.interface as interface  # noqa: E402
from pyhamilton import HamiltonInterface, INITIALIZE, GRIP_GET, GRIP_PLACE  # noqa: E402
from pyhamilton.defaultcmds import defaults_by_cmd  # noqa: E402
from pyhamilton.oemerr import LabwareError  # noqa: E402
from pyhamilton.error_handling import ExceptionTable, ErrorAction, prompt_with_countdown  # noqa: E402

PLATE_NOT_FOUND = 21  # VENUS main error 21, "Labware not Found Error"
STEP_TIMEOUT = 300


class TestFailure(Exception):
    pass


class OperatorAbort(Exception):
    pass


def check(cond, msg):
    if not cond:
        raise TestFailure(msg)


# ---------------------------------------------------------------- operator --

class LiveOperator:
    """Talks to the person at the robot through small topmost dialogs."""

    def __init__(self, site):
        self.site = site

    def _dialog(self, kind, title, msg):
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        try:
            return getattr(messagebox, kind)(title, msg, parent=root)
        finally:
            root.destroy()

    def tell(self, msg):
        if not self._dialog('askokcancel', 'Live test', msg + '\n\nOK to continue, Cancel to stop the suite.'):
            raise OperatorAbort()

    def ask_yes_no(self, msg):
        return self._dialog('askyesno', 'Live test', msg)

    def ensure_plate(self, present):
        state = 'a plate IS' if present else 'there is NO plate'
        self.tell(f'Make sure {state} at site "{self.site}".')

    def popup(self, scenario, seconds, on_timeout=ErrorAction.RETRY):
        """Show the real recovery popup. `scenario` is what the operator was briefed to do."""
        return prompt_with_countdown(
            title='Plate not found',
            message=f'No plate detected at "{self.site}".\n'
                    'Put a plate in position, then click Retry.',
            seconds=seconds, on_timeout=on_timeout)

    def brief(self, scenario, seconds):
        steps = {
            'click_retry': 'put the plate on the site, then click RETRY.',
            'timeout': f'put the plate on the site and DO NOT click anything. '
                       f'It should retry by itself after {seconds} s.',
            'click_abort': 'leave the site empty and click ABORT.',
        }
        self.tell(f'Next, the robot will fail to find a plate and a "Plate not found" '
                  f'popup will appear. When it does: {steps[scenario]}')


class FakeOperator:
    """Scripted operator for --fake runs; acts on the FakeRobot's deck state."""

    def __init__(self, robot):
        self.robot = robot

    def tell(self, msg):
        pass

    def ask_yes_no(self, msg):
        return False  # "did a VENUS dialog appear?" -> no

    def ensure_plate(self, present):
        if not self.robot.plate_in_gripper:
            self.robot.plate_on_site = present

    def brief(self, scenario, seconds):
        pass

    def popup(self, scenario, seconds, on_timeout=ErrorAction.RETRY):
        if scenario == 'click_abort':
            return ErrorAction.RAISE
        self.robot.plate_on_site = True
        return ErrorAction.RETRY if scenario == 'click_retry' else on_timeout


# ------------------------------------------------------------- fake robot --

class FakeRobot:
    """Minimal CO-RE gripper model answering pyhamilton commands like VENUS would."""

    def __init__(self):
        self.plate_on_site = False
        self.plate_in_gripper = False
        self.tool_on_channels = False
        self.responses = {}

    def _block(self, main_err):
        flag = 1 if main_err else 0
        return f'{flag}[1,{main_err},0,0,,plate_site,1'

    def send_str(self, raw):
        cmd = json.loads(raw)
        name, err = cmd['command'], 0
        if name == 'gripGet':
            self.tool_on_channels = True  # VENUS skips this if the tools are already on
            if self.plate_on_site:
                self.plate_on_site, self.plate_in_gripper = False, True
            else:
                err = PLATE_NOT_FOUND
        elif name == 'gripPlace':
            if self.plate_in_gripper:
                self.plate_in_gripper, self.plate_on_site = False, True
            if cmd.get('ejectToolWhenFinish', 1):
                self.tool_on_channels = False
        self.responses[cmd['id']] = json.dumps({
            'command': 'STAR-return', 'step-name': name, 'id': cmd['id'],
            'step-return1': self._block(err), 'step-return2': '',
            'step-return3': '', 'step-return4': ''})

    def pop_response(self, id):
        return self.responses.pop(id, None)


def fake_interface(robot):
    class Handler:
        send_str = staticmethod(robot.send_str)
        pop_response = staticmethod(robot.pop_response)
    interface.HamiltonServerHandler = Handler
    ham = object.__new__(HamiltonInterface)
    ham.simulating = False
    ham.debug = False
    ham.active = True
    ham.logger = None
    ham.log_queue = []
    ham.exception_table = None
    ham._sent_cmds = {}
    return ham


# ------------------------------------------------------------------ tests --

class Suite:
    def __init__(self, ham, op, args, fake):
        self.ham, self.op, self.args, self.fake = ham, op, args, fake
        self.results = []
        self.sends = []
        real_send = ham.send_command

        def counting_send(*a, **kw):
            cid = real_send(*a, **kw)
            self.sends.append(kw.get('command') or (a[0].cmd_name if a else None))
            return cid
        ham.send_command = counting_send

    # helpers -------------------------------------------------------------
    def grip_get(self, raise_first=True):
        a = self.args
        cid = self.ham.send_command(
            GRIP_GET, plateSequence=a.site, toolSequence=a.tool_seq, gripWidth=a.grip_width,
            gripHeight=a.grip_height, widthBefore=a.width_before,
            gripperToolChannel=a.gripper_channel, gripForce=a.grip_force,
            transportMode=0, checkPlate=a.check_plate)
        return self.ham.wait_on_response(cid, raise_first_exception=raise_first, timeout=STEP_TIMEOUT)

    def grip_place(self):
        cid = self.ham.send_command(GRIP_PLACE, plateSequence=self.args.site,
                                    toolSequence=self.args.tool_seq, ejectToolWhenFinish=1)
        return self.ham.wait_on_response(cid, raise_first_exception=True, timeout=STEP_TIMEOUT)

    def table(self, handler, max_attempts=5):
        t = ExceptionTable()
        t.register(LabwareError, handler, commands=['gripGet'], max_attempts=max_attempts)
        self.ham.register_exception_table(t)
        return t

    def cleanup(self):
        """Return plate and tool to their racks after a test that ended mid-transport."""
        self.ham.register_exception_table(None)
        self.op.ensure_plate(True)
        self.grip_get()
        self.grip_place()

    def gripget_sends(self):
        return sum(1 for s in self.sends if s == 'gripGet')

    # tests ---------------------------------------------------------------
    def t1_detection(self):
        """No table: empty site returns error 21 / LabwareError, no VENUS dialog."""
        self.ham.register_exception_table(None)
        self.op.ensure_plate(False)
        start = time.time()
        response = self.grip_get(raise_first=False)
        elapsed = time.time() - start
        codes = [b['mainErrField'] for b in (response.parsed_return or [])]
        check(PLATE_NOT_FOUND in codes, f'expected main error 21 in step return, got {codes} '
                                        f'(raw: {response.raw})')
        try:
            response.raise_first_exception()
            raise TestFailure('raise_first_exception did not raise')
        except LabwareError:
            pass
        check(not self.op.ask_yes_no('Did a VENUS error dialog (Repeat / Cancel / Abort) appear '
                                     'during that step?'),
              'VENUS showed its own error dialog, so errors do not reach Python directly')
        return f'main error {codes}, step returned in {elapsed:.0f} s'

    def t2_retry_with_tool_on(self):
        """After a failed get (tool may still be on the channels), a get and place succeed."""
        self.op.ensure_plate(True)
        self.grip_get()
        self.grip_place()
        return 'get + place succeeded after the failed get'

    def t3_raise(self):
        """Table returns RAISE: LabwareError reaches the script, handler sees the right context."""
        seen = []
        self.table(lambda ctx: seen.append(ctx) or ErrorAction.RAISE)
        self.op.ensure_plate(False)
        try:
            self.grip_get()
            raise TestFailure('gripGet on an empty site did not raise')
        except LabwareError:
            pass
        check(len(seen) == 1, f'handler called {len(seen)} times, expected 1')
        ctx = seen[0]
        check(ctx.command == 'gripGet' and ctx.attempt == 1, f'bad context {ctx.command}/{ctx.attempt}')
        codes = [b['mainErrField'] for b in ctx.response.parsed_return]
        check(PLATE_NOT_FOUND in codes, f'context response codes {codes}')
        self.cleanup()
        return 'raised LabwareError, handler called once with correct context'

    def _popup_test(self, scenario, seconds, expect_success):
        calls = []

        def handler(ctx):
            calls.append(time.time())
            t0 = time.time()
            action = self.op.popup(scenario, seconds)
            calls[-1] = time.time() - t0
            return action
        self.table(handler)
        self.op.ensure_plate(False)
        self.op.brief(scenario, seconds)
        before = self.gripget_sends()
        try:
            self.grip_get()
            succeeded = True
        except LabwareError:
            succeeded = False
        sends = self.gripget_sends() - before
        check(len(calls) == 1, f'popup shown {len(calls)} times, expected 1')
        if expect_success:
            check(succeeded, 'gripGet still failed after the operator added the plate')
            check(sends == 2, f'expected 2 gripGet sends, got {sends}')
            self.ham.register_exception_table(None)
            self.grip_place()
        else:
            check(not succeeded, 'expected LabwareError after Abort')
            check(sends == 1, f'expected 1 gripGet send, got {sends}')
            self.cleanup()
        return calls[0]

    def t4_popup_retry(self):
        """Popup, operator adds plate and clicks Retry: the same gripGet succeeds."""
        waited = self._popup_test('click_retry', 120, expect_success=True)
        return f'retried after the operator clicked ({waited:.0f} s in popup)'

    def t5_popup_timeout(self):
        """Popup, operator adds plate without clicking: timer runs out and it retries."""
        secs = self.args.timeout_seconds
        waited = self._popup_test('timeout', secs, expect_success=True)
        if not self.fake:
            check(waited >= secs - 2, f'popup closed after {waited:.0f} s, before the {secs} s timer')
        return f'auto-retried after {waited:.0f} s'

    def t6_popup_abort(self):
        """Popup, operator clicks Abort: LabwareError reaches the script."""
        self._popup_test('click_abort', 120, expect_success=False)
        return 'raised LabwareError after Abort'

    def t7_attempt_limit(self):
        """Handler always retries with no plate: stops at max_attempts and raises."""
        attempts = []
        self.table(lambda ctx: attempts.append(ctx.attempt) or ErrorAction.RETRY, max_attempts=2)
        self.op.ensure_plate(False)
        before = self.gripget_sends()
        try:
            self.grip_get()
            raise TestFailure('expected LabwareError after the attempt limit')
        except LabwareError:
            pass
        sends = self.gripget_sends() - before
        check(attempts == [1, 2], f'handler attempts {attempts}, expected [1, 2]')
        check(sends == 3, f'expected 3 gripGet sends, got {sends}')
        self.cleanup()
        return 'raised after 3 sends (attempts 1 and 2 retried, 3rd refused)'

    def t8_public_method(self):
        """Hook covers the public wrapper get_plate_gripper_seq / place_plate_gripper_seq."""
        a = self.args
        self.table(lambda ctx: self.op.popup('click_retry', 120))
        self.op.ensure_plate(False)
        self.op.brief('click_retry', 120)
        self.ham.get_plate_gripper_seq(a.site, a.grip_height, a.grip_width, a.width_before,
                                       False, a.tool_seq, a.grip_force,
                                       checkPlate=a.check_plate, gripperToolChannel=a.gripper_channel)
        self.ham.register_exception_table(None)
        self.ham.place_plate_gripper_seq(a.site, a.tool_seq)
        return 'wrapper recovered through the table'

    def t9_no_error_path(self):
        """Table registered, plate present: normal get/place, handler never called."""
        calls = []
        self.table(lambda ctx: calls.append(1) or ErrorAction.RAISE)
        self.op.ensure_plate(True)
        self.grip_get()
        self.grip_place()
        check(calls == [], 'handler was called on a successful step')
        self.ham.register_exception_table(None)
        return 'no handler calls'

    TESTS = [
        ('T1', 't1_detection'), ('T2', 't2_retry_with_tool_on'), ('T3', 't3_raise'),
        ('T4', 't4_popup_retry'), ('T5', 't5_popup_timeout'), ('T6', 't6_popup_abort'),
        ('T7', 't7_attempt_limit'), ('T8', 't8_public_method'), ('T9', 't9_no_error_path'),
    ]

    def run(self, only):
        tests = list(self.TESTS)
        if only:
            tests = [t for t in tests if t[0] in only]
        for tid, meth in tests:
            fn = getattr(self, meth)
            doc = fn.__doc__.strip()
            print(f'\n[{tid}] {doc}')
            try:
                detail = fn()
                status = 'PASS'
            except OperatorAbort:
                self.results.append((tid, 'STOP', 'operator stopped the suite'))
                print('  stopped by operator')
                break
            except TestFailure as e:
                status, detail = 'FAIL', str(e)
            except Exception as e:
                status, detail = 'FAIL', f'{type(e).__name__}: {e}'
                traceback.print_exc()
            self.results.append((tid, status, detail))
            print(f'  {status}: {detail}')
            if status == 'FAIL' and not self.fake:
                try:
                    self.op.tell(f'{tid} failed: {detail}\n\nReset the deck by hand (plate on site, '
                                 'gripper tools in their rack) before continuing.')
                except OperatorAbort:
                    break
        self.ham.register_exception_table(None)
        return self.results


def main():
    grip = defaults_by_cmd['gripGet'][1]
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--site', default='plate_site', help='plate site sequence name in the layout')
    p.add_argument('--tool-seq', default=grip['toolSequence'])
    p.add_argument('--grip-width', type=float, default=grip['gripWidth'])
    p.add_argument('--grip-height', type=float, default=grip['gripHeight'])
    p.add_argument('--width-before', type=float, default=grip['widthBefore'])
    p.add_argument('--gripper-channel', type=int, default=grip['gripperToolChannel'])
    p.add_argument('--grip-force', type=int, default=grip['gripForce'])
    p.add_argument('--timeout-seconds', type=int, default=30, help='popup timer for T5')
    p.add_argument('--only', default='', help='comma-separated test ids, e.g. T1,T4')
    p.add_argument('--check-plate', type=int, choices=(0, 1), default=grip['checkPlate'],
                   help='gripGet checkPlate (default: pyhamilton default, 0)')
    p.add_argument('--windowed', action='store_true')
    p.add_argument('--no-init', action='store_true')
    p.add_argument('--fake', action='store_true', help='simulated robot, scripted operator')
    p.add_argument('--report', help='write results as JSON to this path')
    args = p.parse_args()
    only = {t.strip().upper() for t in args.only.split(',') if t.strip()}

    if args.fake:
        robot = FakeRobot()
        ham = fake_interface(robot)
        results = Suite(ham, FakeOperator(robot), args, fake=True).run(only)
    else:
        print(f'Live run on site "{args.site}" with tools "{args.tool_seq}", grip width '
              f'{args.grip_width} mm, height {args.grip_height} mm, open {args.width_before} mm.')
        with HamiltonInterface(windowed=args.windowed) as ham:
            if not args.no_init:
                ham.wait_on_response(ham.send_command(INITIALIZE), raise_first_exception=True,
                                     timeout=STEP_TIMEOUT)
            op = LiveOperator(args.site)
            op.tell('Gripper tools must be in their rack and the site ready to take a plate. '
                    'Keep a plate within reach. Starting the suite.')
            results = Suite(ham, op, args, fake=False).run(only)

    print('\n' + '=' * 72)
    for tid, status, detail in results:
        print(f'{tid:<4} {status:<5} {detail}')
    failed = [r for r in results if r[1] in ('FAIL', 'STOP')]
    print('=' * 72)
    print('GATE: ' + ('FAILED' if failed else 'PASSED') + f' ({len(results)} tests run)')
    if args.report:
        with open(args.report, 'w') as f:
            json.dump([dict(id=t, status=s, detail=d) for t, s, d in results], f, indent=2)
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
