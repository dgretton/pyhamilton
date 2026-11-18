"""Protocol-specific error recovery for HamiltonInterface.

Register an `ExceptionTable` on a running interface and any step error raised by a
command that waits with `raise_first_exception=True` (which is every high-level
method on `HamiltonInterface`) is routed through it before it reaches your script.
A handler decides whether to retry the exact same command, skip it, or let the
error raise as usual.

    from pyhamilton import HamiltonInterface, ExceptionTable, prompt_with_countdown, LabwareError

    table = ExceptionTable()

    @table.on(LabwareError, commands=['gripGet'])
    def plate_not_found(ctx):
        return prompt_with_countdown(
            title='Plate not found',
            message=f'No plate detected at {ctx.cmd.get("plateSequence", "?")}.\\n'
                    'Put a plate in position, then click Retry.',
            seconds=120)

    with HamiltonInterface(windowed=True) as ham_int:
        ham_int.register_exception_table(table)
        ham_int.get_plate_gripper_seq(...)

Behaviour of the VENUS side, verified from the installed STAR_OEM_toolkit.stp and
the VENUS help (HxGruCommandEnu.chm):

- CO-RE Grip Get (ZSwapGetPlate) can only raise main errors 10, 3, 2, 21, 999, 7
  and 8. Error 21, "Labware not Found Error", is pyhamilton's `LabwareError`
  (not `NoLabwareError`); a missing plate is expected to be this one.
- A failed grip on an empty site raises with the default `checkPlate=0`.
  `checkPlate=1` only adds a plate check before gripping.
- Every ZSwapGetPlate error has timeout 0 with Cancel as the first recovery, so
  VENUS cancels at once without showing its own dialog, and the error reaches Python.
- A retried gripGet is safe while the gripper tool is still on the channels: VENUS
  skips the tool pick-up when the tools are already picked up.
- CO-RE Grip Place (ZSwapPlacePlate) is different: errors 2 and 21 use an infinite
  timeout, so VENUS shows its own blocking dialog and the error only reaches Python
  after someone clicks it.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Iterable, Optional


class ErrorAction(Enum):
    RETRY = 'retry'    # resend the same command and wait again
    SKIP = 'skip'      # swallow the error; the method returns as if the step succeeded
    RAISE = 'raise'    # re-raise the original error (default when nothing matches)


@dataclass
class ErrorContext:
    """Everything a handler needs to decide what to do."""
    error: Exception          # the pyhamilton exception, e.g. NoLabwareError()
    command: str              # command name, e.g. 'gripGet'
    cmd: dict                 # the full command dict that was sent
    response: Any             # the HamiltonResponse (parsed_return has per-channel codes)
    attempt: int              # 1 on the first failure, 2 after one retry, ...
    ham_int: Any              # the HamiltonInterface, if the handler needs to send commands


Handler = Callable[[ErrorContext], Optional[ErrorAction]]


@dataclass
class _Rule:
    error_types: tuple
    commands: Optional[frozenset]
    handler: Handler
    max_attempts: int


class ExceptionTable:
    """An ordered list of (error type, command filter) -> handler rules.

    The first rule whose error type and command filter both match wins. A handler
    that returns None is treated as RAISE.
    """

    def __init__(self):
        self._rules = []

    def register(self, error_types, handler: Handler, commands: Iterable[str] = None, max_attempts: int = 5):
        """Add a rule.

        Args:
          error_types: an exception class or tuple of classes (subclasses match too).
          handler: called with an ErrorContext, returns an ErrorAction.
          commands: optional command names to restrict the rule to, e.g. ['gripGet'].
          max_attempts: once a command has failed this many times, the error raises
            regardless of what the handler says.
        """
        if not isinstance(error_types, tuple):
            error_types = (error_types,)
        cmds = frozenset(commands) if commands is not None else None
        self._rules.append(_Rule(error_types, cmds, handler, max_attempts))
        return handler

    def on(self, *error_types, commands: Iterable[str] = None, max_attempts: int = 5):
        """Decorator form of `register`."""
        def deco(handler):
            return self.register(tuple(error_types), handler, commands, max_attempts)
        return deco

    def resolve(self, ctx: ErrorContext) -> ErrorAction:
        for rule in self._rules:
            if not isinstance(ctx.error, rule.error_types):
                continue
            if rule.commands is not None and ctx.command not in rule.commands:
                continue
            if ctx.attempt > rule.max_attempts:
                return ErrorAction.RAISE
            action = rule.handler(ctx)
            return action if isinstance(action, ErrorAction) else ErrorAction.RAISE
        return ErrorAction.RAISE


def prompt_with_countdown(title, message, seconds=120, on_timeout=ErrorAction.RETRY,
                          retry_label='Retry', abort_label='Abort', allow_skip=False):
    """Show a topmost window with a countdown and return the operator's choice.

    Buttons: Retry -> ErrorAction.RETRY, Abort -> ErrorAction.RAISE,
    optional Skip -> ErrorAction.SKIP. When the timer runs out, returns `on_timeout`.
    Closing the window counts as Abort.
    """
    import tkinter as tk

    result = {'action': ErrorAction.RAISE}
    root = tk.Tk()
    root.title(title)
    root.attributes('-topmost', True)
    root.resizable(False, False)
    root.protocol('WM_DELETE_WINDOW', lambda: finish(ErrorAction.RAISE))

    tk.Label(root, text=message, justify='left', wraplength=420,
             font=('Segoe UI', 11), padx=20, pady=15).pack()
    countdown = tk.Label(root, font=('Segoe UI', 20, 'bold'), pady=5)
    countdown.pack()
    timeout_text = {ErrorAction.RETRY: 'retrying', ErrorAction.SKIP: 'skipping',
                    ErrorAction.RAISE: 'aborting'}[on_timeout]
    tk.Label(root, text=f'Automatically {timeout_text} when the timer ends.',
             font=('Segoe UI', 9), fg='gray30').pack()

    buttons = tk.Frame(root, pady=15)
    buttons.pack()

    def finish(action):
        result['action'] = action
        root.destroy()

    tk.Button(buttons, text=retry_label, width=12,
              command=lambda: finish(ErrorAction.RETRY)).pack(side='left', padx=6)
    if allow_skip:
        tk.Button(buttons, text='Skip', width=12,
                  command=lambda: finish(ErrorAction.SKIP)).pack(side='left', padx=6)
    tk.Button(buttons, text=abort_label, width=12,
              command=lambda: finish(ErrorAction.RAISE)).pack(side='left', padx=6)

    remaining = [int(seconds)]

    def tick():
        if remaining[0] <= 0:
            finish(on_timeout)
            return
        m, s = divmod(remaining[0], 60)
        countdown.config(text=f'{m}:{s:02d}')
        remaining[0] -= 1
        root.after(1000, tick)

    tick()
    root.lift()
    root.focus_force()
    root.mainloop()
    return result['action']
