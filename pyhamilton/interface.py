import sys

if 'win32' in sys.platform:
    import win32gui, win32con

import time, json, signal, os, requests, string, logging, subprocess
from dataclasses import dataclass, field
from enum import auto, Enum, unique
from parse import parse
from waiter import wait, suppress
from http import server
from threading import Thread
from multiprocessing import Process
from pyhamilton import OEM_RUN_EXE_PATH, OEM_HSL_PATH
from .oemerr import * #TODO: specify
from .defaultcmds import defaults_by_cmd

class HamiltonCmdTemplate:
    """
    Formatter object to create valid `pyhamilton` command dicts.

    Use of this class to assemble JSON pyhamilton commands enables keyword access to command attributes, which cuts down on string literals. It also helps to fail malformed commands early, before they are sent.

    Several default `HamiltonCmdTemplate`s are defined in `pyhamilton.defaultcmds`, such as `INITIALIZE`, `ASPIRATE`, and `DISPENSE`. Casual users will most likely never need to manually instantiate a HamiltonCmdTemplate.
    """

    @staticmethod
    def unique_id():
        """Return a "uniqe" hexadecimal string (`'0x...'`) based on time of call."""
        return hex(int((time.time()%3600e4)*1e6))

    def __init__(self, cmd_name, params_list):
        """
        Creates a `HamiltonCmdTemplate` with a command name and required parameters.

        The command name must be one of the command names accepted by the
        `pyhamilton` interpreter and a list of expected parameters for this command.

        Args:
          cmd_name (str): One of the set of string literals recognized as command names
            by the `pyhamilton` interpreter, e.g. `'mph96Dispense'`. See `pyhamilton.defaultcmds` for examples.
          params_list (list): exact list of string parameters that must have associated
            values for the command to be valid, other than those that are always present
            (`'command'` and `'id'`)
        """
        self.cmd_name = cmd_name
        self.params_list = params_list
        if cmd_name in defaults_by_cmd:
            const_name, default_dict = defaults_by_cmd[cmd_name]
            self.defaults = {k:v for k, v in default_dict.items() if v is not None}
        else:
            self.defaults = {}

    def assemble_cmd(self, *args, **kwargs):
        """
        Use keyword args to assemble this command. Default values auto-filled.

        Args:
          kwargs (dict): map of any parameters (str) to values that should be different
            from the defaults supplied for this command in `pyhamilton.defaultcmds`
        """
        if args:
            raise ValueError('assemble_cmd can only take keyword arguments.')
        assembled_cmd = {'command':self.cmd_name, 'id':HamiltonCmdTemplate.unique_id()}
        assembled_cmd.update(self.defaults)
        assembled_cmd.update(kwargs)
        self.assert_valid_cmd(assembled_cmd)
        return assembled_cmd

    def assert_valid_cmd(self, cmd_dict):
        """Validate a finished command. Do nothing if it is valid.

        `ValueError` will be raised if the supplied command did not have all required
        parameters for this command, as well as values for keys `'id'` and `'command'`, which
        are always required.

        Args:
          cmd_dict (dict): A fully assembled `pyhamilton` command

        Raises:
          ValueError: The command dict is not ready to send. Specifics of mismatch
            summarized in exception description.
        """
        prefix = 'Assert valid command "' + self.cmd_name + '" failed: '
        if 'id' not in cmd_dict:
            raise ValueError(prefix + 'no key "id"')
        if 'command' not in cmd_dict:
            raise ValueError(prefix + 'no key "command"')
        if cmd_dict['command'] != self.cmd_name:
            raise ValueError(prefix + 'command name "' + cmd_dict['command'] + '" does not match')
        needs = set(['command', 'id'])
        needs.update(self.params_list)
        givens = set(cmd_dict.keys())
        if givens != needs:
            prints = [prefix + 'template parameter keys (left) do not match given keys (right)\n']
            q_mark = ' (?)  '
            l_col_space = 4
            r_col_space = max((len(key) for key in needs)) + len(q_mark) + 1
            needs_l = sorted(list(needs))
            givens_l = sorted(list(givens))
            while needs_l or givens_l:
                if needs_l:
                    lval = needs_l.pop(0)
                    if lval not in givens:
                        lval = q_mark + lval
                else:
                    lval = ''
                if givens_l:
                    rval = givens_l.pop(0)
                    if rval not in needs:
                        rval = q_mark + rval
                else:
                    rval = ''
                prints.append(' '*l_col_space + lval + ' '*(r_col_space - len(lval)) + rval)
            raise ValueError('\n'.join(prints))

_builtin_templates_by_cmd = {}

for cmd in defaults_by_cmd:
    const_name, default_dict = defaults_by_cmd[cmd]
    const_template = HamiltonCmdTemplate(cmd, list(default_dict.keys()))
    globals()[const_name] = const_template
    _builtin_templates_by_cmd[cmd] = const_template

def _make_new_hamilton_serv_handler(resp_indexing_fn):
    """Make HTTP request handler to aggregate responses according to an index function.

    A new class is defined each time, bound to a specific indexing function, to keep it
    agnostic to any particular indexing scheme. In practice, the current implementation
    uses the value of the key 'id'; that is the scheme for the `pyhamilton` interpreter.

    Attributes:
      indexed_responses (dict): aggregated responses received by this handler, keyed by
        the values returned by `resp_indexing_fn`.

    Args:
      resp_indexing_fn (Callable[[str], Hashable]): Called on every response body (str)
        to extract a hashable index. Later, the response can be retrieved by this index
        from `indexed_responses`.

    """

    class HamiltonServerHandler(server.BaseHTTPRequestHandler):
        _send_queue = []
        indexed_responses = {}
        indexing_fn = resp_indexing_fn
        MAX_QUEUED_RESPONSES = 1000

        @staticmethod
        def send_str(cmd_str):
            if not isinstance(cmd_str, b''.__class__):
                if isinstance(cmd_str, ''.__class__):
                    cmd_str = cmd_str.encode()
                else:
                    raise ValueError('send_command can only send strings, not ' + str(cmd_str))
            HamiltonServerHandler._send_queue.append(cmd_str)

        @staticmethod
        def has_queued_cmds():
            return bool(HamiltonServerHandler._send_queue)

        @staticmethod
        def pop_response(idx):
            ir = HamiltonServerHandler.indexed_responses
            return None if idx not in ir else ir.pop(idx).decode()

        def _set_headers(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/HTML')
            self.end_headers()

        def do_GET(self):
            sq = HamiltonServerHandler._send_queue
            response_to_send = sq.pop(0) if sq else b''
            self._set_headers()
            self.wfile.write(response_to_send)

        def do_HEAD(self):
            self._set_headers()

        def do_POST(self):
            content_len = int(self.headers.get('content-length', 0))
            post_body = self.rfile.read(content_len)
            self._set_headers()
            self.wfile.write(b'<html><body><h1>POST!</h1></body></html>')
            ir = HamiltonServerHandler.indexed_responses
            index = HamiltonServerHandler.indexing_fn(post_body)
            if index is None:
                return
            ir[index] = post_body

        def log_message(self, *args, **kwargs):
            pass

    return HamiltonServerHandler

def run_hamilton_process():
    """Start the interpreter in a separate python process.

    Starts the pyhamilton interpreter, which is an HSL file to be passed to the
    RunHSLExecutor.exe executable from Hamilton. This should always be done in a
    separate python process using the subprocess module, not a Thread.
    """
    import clr
    from pyhamilton import OEM_STAR_PATH, OEM_HSL_PATH
    clr.AddReference(os.path.join(OEM_STAR_PATH, 'RunHSLExecutor'))
    clr.AddReference(os.path.join(OEM_STAR_PATH, 'HSLHttp'))
    try:
        from RunHSLExecutor import Class1
    except ModuleNotFoundError:
        raise RuntimeError('RunHSLExecutor DLLs successfully located, but an internal '
                           'error prevented import as a CLR module. You might be '
                           'missing the standard Hamilton software suite HSL '
                           'executables, their DLLs may not be registered with Windows, '
                           'or they may not be located in the expected system '
                           'directory.')
    C = Class1()
    C.StartMethod(OEM_HSL_PATH)
    try:
        while True:
            pass # Send external signal to end process
    except:
        pass

@unique
class HamiltonResponseStatus(Enum):
    """
    List of global Hamilton response status

    Inheritance
    -----------
        Enum

    Attributes
    ----------
    FAILED : enum.auto
        command failure is reported or parsing error has been detected
    SUCCESS : enum.auto
        command and parsing successful
    UNKNOWN : enum.auto
        indecisive state
    """
    FAILED = auto()
    SUCCESS = auto()
    UNKNOWN = auto()

@dataclass
class HamiltonResponse:
    """
    A class to represent the Venus server response

    Attributes
    ----------
    status: HamiltonResponseStatus
        Response status (failed, success or unknown)
    return_data: list | str
        Extracted values from specific field response
    moduleID: str
        ID of module from "step-return2" field
    parsed_return: any
        Represent "step-return1" field value
    raw: any
        Original server response

    Methods
    -------
    _compute_status()
        Compute the status based on step-return1 field from raw response

    _return_data()
        Contain values of requested fields

    _moduleID()
        Return Module ID (step-return2)

    _parse_return():
        Parse values from "step-return1" field

    digest(fields)
        Populate this object's attributes

    raise_first_exception()
        Evaluate which exception to raise


    Raises
    ------
        HamiltonStepError: Errors in steps executed by VENUS software
        HamiltonReturnParseError: Server response parsing failed
        InvalidErrCodeError: Unknown server response error code

    """
    status: HamiltonResponseStatus = HamiltonResponseStatus.UNKNOWN
    return_data: list = field(default_factory=list)
    moduleID: str = ""
    parsed_return: any = None
    raw: any = None

    def _compute_status(self):
        is_unknown = 'step-return1' not in self.raw
        if is_unknown:
            return HamiltonResponseStatus.UNKNOWN

        response = json.loads(self.raw)['step-return1']

        is_success = response == 1 or           \
            (
                isinstance(response, str) and   \
                len(response) == 1 and          \
                response[0] == '1'
            ) or                                \
            (
                isinstance(response, str) and   \
                len(response) > 1 and           \
                response[0] == '0'
            )
        is_failed = response == 0 or            \
            (
                isinstance(response, str) and   \
                len(response) == 1 and          \
                response[0] != '1'
            ) or                                \
            (
                isinstance(response, str) and   \
                len(response.strip()) > 1 and   \
                response.strip()[0] != '0'
            )

        if is_failed:
            return HamiltonResponseStatus.FAILED

        if is_success:
            return HamiltonResponseStatus.SUCCESS

        return HamiltonResponseStatus.UNKNOWN

    def _return_data(self, fields):
        response = json.loads(self.raw)
        if not fields or (isinstance(fields, str) and fields not in response):
            return []
        if isinstance(fields, str) and fields in response:
                return [response[fields]]

        return [response[field] for field in fields if field in response]

    def _moduleID(self):
        moduleID_field_name = "step-return2"
        if moduleID_field_name not in self.raw:
            return ""
        response = json.loads(self.raw)
        return str(response[moduleID_field_name])

    def _parse_return(self):
        return_field = "step-return1"
        field_names = [
            "{numField:d}",
            "{mainErrField:d}",
            "{slaveErr:d}",
            "{recoveryBtnId:d}",
            "{stepData}",
            "{labwareName:w}",
            "{labwarePos}"
        ]
        if return_field not in self.raw:
            return None

        response = json.loads(self.raw)[return_field]
        block_available = isinstance(response, str) and '[' in response and ',' in response
        if not block_available:
            return None

        blocks = [r for r in response.split('[')[1:]]
        if not blocks:
            return None

        parsed = [
            parse(
                ",".join(field_names[:block.count(',') + 1]),
                ",".join([' ' if item == '' else item for item in block.split(',') ])) for block in blocks
        ]
        if not parsed:
            return None

        if all([p is None for p in parsed]):
            return None
        return [p.named for p in parsed if p]

    def digest(self, fields=None):
        self.status = self._compute_status()
        self.return_data = self._return_data(fields=fields)
        self.moduleID = self._moduleID()
        self.parsed_return = self._parse_return()

    def raise_first_exception(self):
        isSuccessStatus = self.status == HamiltonResponseStatus.SUCCESS and '[' not in self.raw
        if isSuccessStatus:
            return

        isHamiltonStepError = HamiltonResponseStatus.FAILED and '[' not in self.raw
        if isHamiltonStepError:
            raise HamiltonStepError('Hamilton step did not execute correctly; no error code given. ( response: ' + self.raw + ' )')

        isHamiltonReturnParseError = '[' in self.raw and (self.parsed_return is None or self.parsed_return == [])
        if isHamiltonReturnParseError:
            raise HamiltonReturnParseError(self.raw)

        reportedErrorCodes = [p['mainErrField'] for p in self.parsed_return if p['mainErrField'] != 0]
        isSuccessStatus = self.status == HamiltonResponseStatus.SUCCESS and len(reportedErrorCodes) == 0
        if isSuccessStatus:
            return

        isFailedStatusNoReportedErrorCode = self.status == HamiltonResponseStatus.FAILED and len(reportedErrorCodes) == 0
        if isFailedStatusNoReportedErrorCode:
            raise HamiltonReturnParseError('Hamilton step did not execute correctly; no error code found. ( response: ' + self.raw + ' )')

        firstErrorCode = reportedErrorCodes[0]
        isFirstExceptionKnown = firstErrorCode in HAMILTON_ERROR_MAP
        if isFirstExceptionKnown:
            raise HAMILTON_ERROR_MAP[firstErrorCode]()

        if HamiltonResponseStatus.FAILED:
            raise InvalidErrCodeError(f'Unknown error code: {firstErrorCode}')

        if HamiltonResponseStatus.SUCCESS:
            raise HamiltonReturnParseError('Inconsistency: Venus returns SUCCESS while error code {firstErrorCode} found! ( response: ' + self.raw + ' )')


class HamiltonInterface:
    """Main class to automatically set up and tear down an interface to a Hamilton robot.

    HamiltonInterface is the primary class offered by this module. It creates a Hamilton
    HSL background process running the `pyhamilton` interpreter, along with a `localhost`
    connection to act as a bridge. It is recommended to create a `HamiltonInterface` using
    a `with:` block to ensure proper startup and shutdown of its async components, even if
    exceptions are raised. It may be used with explicit `start()` and `stop()` calls.

      Typical usage:

      ```
      with HamiltonInterface() as ham_int:
          cmd_id = ham_int.send_command(INITIALIZE)
          ...
          response = ham_int.wait_on_response(cmd_id)
          ...
      ```
    """

    known_templates = _builtin_templates_by_cmd
    default_port = 3221
    default_address = '127.0.0.1' # localhost

    class HamiltonServerThread(Thread):
        """Private threaded local HTTP server with graceful shutdown flag."""

        def __init__(self, address, port):
            Thread.__init__(self)
            self.server_address = (address, port)
            self.should_continue = True
            self.exited = False
            def index_on_resp_id(response_str):
                try:
                    response = json.loads(response_str)
                    if 'id' in response:
                        return response['id']
                    return None
                except json.decoder.JSONDecodeError:
                    return None
            self.server_handler_class = _make_new_hamilton_serv_handler(index_on_resp_id)
            self.httpd = None

        def run(self):
            self.exited = False
            self.httpd = server.HTTPServer(self.server_address, self.server_handler_class)
            while self.should_continue:
                self.httpd.handle_request()
            self.exited = True

        def disconnect(self):
            self.should_continue = False

        def has_exited(self):
            return self.exited

    def __init__(self, address=None, port=None, simulate=False):
        self.address = HamiltonInterface.default_address if address is None else address
        self.port = HamiltonInterface.default_port if port is None else port
        self.simulate = simulate
        self.server_thread = None
        self.oem_process = None
        self.active = False
        self.logger = None
        self.log_queue = []

    def start(self):
        """Starts the extra processes, threads, and servers for the Hamilton connection.

        Launches: 1) the pyhamilton interpreter using the Hamilton Run Control
        executable, either in the background for normal use, or in the foreground with a
        GUI for simulation; 2) a local HTTP server to ferry messages between the python
        module and the interpreter.

        When used with a `with:` block, called automatically upon entering the block.
        """

        if self.active:
            return
        self.log('starting a Hamilton interface')
        if self.simulate:
            sim_window_handle = None
            try:
                sim_window_handle = win32gui.FindWindow(None, 'Hamilton Run Control - ' + os.path.basename(OEM_HSL_PATH))
            except win32gui.error:
                pass
            if sim_window_handle:
                try:
                    win32gui.SendMessage(sim_window_handle, win32con.WM_CLOSE, 0, 0)
                    os.system('taskkill /f /im HxRun.exe')
                except win32gui.error:
                    self.stop()
                    self.log_and_raise(OSError('Simulator already open'))
            subprocess.Popen([OEM_RUN_EXE_PATH, OEM_HSL_PATH])
            self.log('started the oem application for simulation')
        else:
            self.oem_process = Process(target=run_hamilton_process, args=())
            self.oem_process.start()
            self.log('started the oem process')
        self.server_thread = HamiltonInterface.HamiltonServerThread(self.address, self.port)
        self.server_thread.start()
        self.log('started the server thread')
        self.active = True

    def stop(self):
        """Stop this HamiltonInterface and clean up associated async processes.

        Kills the pyhamilton interpreter subprocess and executable and stops the local
        web server thread.

        When used with a `with` block, called automatically on exiting the block.
        """

        if not self.active:
            return
        try:
            if self.simulate:
                self.log('sending end run command to simulator')
                try:
                    self.wait_on_response(self.send_command(command='end', id=hex(0)), timeout=1.5)
                except HamiltonTimeoutError:
                    pass
            else:
                for i in range(2):
                    try:
                        os.kill(self.oem_process.pid, signal.SIGTERM)
                        self.log('sent sigterm to oem process')
                        self.oem_process.join()
                        self.log('oem process exited')
                        break
                    except PermissionError:
                        self.log('permission denied, trying again...', 'warn')
                        time.sleep(2)
                else:
                    self.log('Could not kill oem process, moving on with shutdown', 'warn')
        finally:
            self.active = False
            self.server_thread.disconnect()
            self.log('disconnected from server')
            time.sleep(.1)
            if not self.server_thread.has_exited():
                self.log('server did not exit yet, sending dummy request to exit its loop')
                session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=20)
                session.mount('http://', adapter)
                session.get('http://' + HamiltonInterface.default_address + ':' + str(HamiltonInterface.default_port))
                self.log('dummy get request sent to server')
            self.server_thread.join()
            self.log('server thread exited')

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, tb):
        self.stop()

    def is_open(self):
        """Return `True` if the HamiltonInterface has been started and not stopped."""
        return self.active

    def send_command(self, template=None, block_until_sent=False, *args, **cmd_dict): # returns unique id of command
        """Add a command templated after HamiltonCmdTemplate to the server send queue.

        Args:
          template (HamiltonCmdTemplate): Optional; a template to provide default
            arguments not specified in `cmd_dict`.
          block_until_sent (bool): Optional; if `True`, wait for all queued messages,
            including this one, to get picked up by the local server and sent across
            the HTTP connection, before returning. Default is False.
          cmd_dict (dict): keyword arguments to be forwarded to `template` when building
            the command, overriding its defaults. If `template` not given, cmd_dict must
            either have a 'command' key with value matching one of the command names in
            `defaultcmds` and might be missing an 'id' key, or itself be a fully formed
            and correct pyhamilton command with its own 'id' key.

        Returns:
          unique id (str) of the command that can be used to index it later, either
            newly generated or same as originally present in cmd_dict.
        """
        if not self.is_open():
            self.log_and_raise(RuntimeError('Cannot send a command from a closed HamiltonInterface'))
        if template is None:
            if 'command' not in cmd_dict:
                self.log_and_raise(ValueError('Command dicts from HamiltonInterface must have a \'command\' key'))
            cmd_name = cmd_dict['command']
            if cmd_name in HamiltonInterface.known_templates:
                # raises if this is a known command but some fields in cmd_dict are invalid
                send_cmd_dict = HamiltonInterface.known_templates[cmd_name].assemble_cmd(**cmd_dict)
            else:
                send_cmd_dict = cmd_dict
        else:
            send_cmd_dict = template.assemble_cmd(**cmd_dict)
        if 'id' not in send_cmd_dict:
            self.log_and_raise(ValueError("Command dicts sent from HamiltonInterface must have a unique id with key 'id'"))
        self.server_thread.server_handler_class.send_str(json.dumps(send_cmd_dict))
        if block_until_sent:
            self._block_until_sq_clear()
        return send_cmd_dict['id']

    def wait_on_response(self, id, timeout=60, raise_first_exception=False, return_data=None):
        """Wait and do not return until the response for the specified id comes back.

        When the command corresponding to `id` regards multiple distinct pipette channels
        or devices, responses may contain encoded errors that might be different for
        different channels or devices. For this reason, the default behavior of
        `wait_on_response` is to not raise exceptions, but to delegate handling
        exceptions to the caller. For convenience, this method can optionally raise the
        first exception it encounters, often a useful behavior for succinct scripted
        commands that regard only one device, when raise_first_exception is `True`.

        Args:
          id (str): The unique id of a previously sent command
          timeout (float): Optional; maximum time in seconds to wait before raising
            `HamiltonTimeoutError`. Default is 60 seconds.
          raise_first_exception: Optional; if True, may raise if there is an error
            encoded in the response. Default is False.
          return_data(list | str): Optional
            field(s) value to extract (e.g: "step-result1")

        Returns:
          HamiltonResponse

        Raises:
          `HamiltonTimeoutError`: after `timeout` seconds elapse with no response, if
          `timeout` was specified.
        """

        delays = 1  # sec
        server_response = None
        for _ in wait(delays=delays, timeout=timeout):
            server_response = self.server_thread.server_handler_class.pop_response(id)
            if server_response is not None:
                break

        if server_response is None:
            self.log_and_raise(HamiltonTimeoutError('Timed out after ' + str(timeout) + ' sec while waiting for response id ' + str(id)))

        return self.parse_response(server_response, raise_first_exception, return_data)

    def parse_response(self, server_response:str, raise_first_exception:bool=False, return_data:"list|str"=None):
        """Parse the server response and return parsed response of type HamiltonResponse.

        Args:
          server_response (str): Venus server response
          raise_first_exception (bool): Optional; forwarded to `wait_on_response`.
            Default is `False`.
          return_data: field(s) value to extract (e.g: "step-result1")

        Returns:
          HamiltonResponse

        """

        hamiltonResponse = HamiltonResponse(raw=server_response)
        hamiltonResponse.digest(fields=return_data)
        if raise_first_exception:
            hamiltonResponse.raise_first_exception()

        return hamiltonResponse

    def _block_until_sq_clear(self):
        while HamiltonServerHandler.has_queued_cmds():
            pass

    def set_log_dir(self, log_dir):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        hdlr = logging.FileHandler(log_dir)
        formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s %(message)s')
        hdlr.setFormatter(formatter)
        self.logger.addHandler(hdlr)
        self._dump_log_queue()

    def log(self, msg, msg_type='info'):
        self.log_queue.append((msg, msg_type))
        self._dump_log_queue()

    def _dump_log_queue(self):
        if self.logger is None:
            return
        log_actions = {'error':self.logger.error,
                      'warn':self.logger.warn,
                      'debug':self.logger.debug,
                      'info':self.logger.info,
                      'critical':self.logger.critical}
        while self.log_queue:
            msg, msg_type = self.log_queue.pop(0)
            log_actions.get(msg_type.lower(), self.logger.info)(msg) # prints if no log path set

    def log_and_raise(self, err):
        self.log(repr(err), 'error')
        raise err
