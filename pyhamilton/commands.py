"""Wrappers with documentation to make pyhamilton easier to use

"""
from pyhamilton import (
    HamiltonInterface,
    INITIALIZE,
    MOVE_AUTO_LOAD,
    HHS_SET_SIMULATION,
    HHS_CREATE_STAR_DEVICE,
    HHS_CREATE_USB_DEVICE,
    HHS_BEGIN_MONITORING,
    HHS_END_MONITORING,
    HHS_SET_PLATE_LOCK,
    HHS_SET_SHAKER_PARAM,
    HHS_START_SHAKER,
    HHS_START_SHAKER_TIMED,
    HHS_WAIT_FOR_SHAKER,
    HHS_TERMINATE,
    HHS_STOP_SHAKER,
    HHS_GET_SHAKER_SPEED,
    HHS_GET_SHAKER_PARAM,
    HHS_GET_SERIAL_NUM,
    HHS_GET_FIRMWARE_VERSION,
    HHS_GET_TEMP,
    HHS_GET_TEMP_PARAM,
    HHS_GET_TEMP_STATE,
    HHS_SET_TEMP_PARAM,
    HHS_START_TEMP_CTRL,
    HHS_STOP_TEMP_CTRL,
    HHS_WAIT_FOR_TEMP_CTRL,
    PICKUP,
    EJECT,
    ASPIRATE,
    DISPENSE,
    PICKUP96,
    EJECT96,
    ASPIRATE96,
    DISPENSE96,
)
from resources import Plate


class Instrument:
    """Utility functions for the Hamilton"""

    def __init__(self, hammy: HamiltonInterface) -> None:
        self.hammy = hammy

    def initialize(self, asynch: bool = False) -> None:
        """Initializes Hamilton instrument.

        Args:
            hammy (HamiltonInterface): instrument to initialize
            asynch (bool): perform asynchronously
        """
        cmd = self.hammy.send_command(INITIALIZE)
        if not asynch:
            self.hammy.wait_on_response(cmd, raise_first_exception=True, timeout=300)

    def move_auto_load(self, track: int) -> None:
        """Moves auto loader.

        Args:
            hammy (HamiltonInterface): instrument
            track (int): track to move to
        """
        cmd = self.hammy.send_command(MOVE_AUTO_LOAD, track=track)
        self.hammy.wait_on_response(cmd, raise_first_exception=True, timeout=120)


class HHS:
    """Functions for the hamilton heater shaker module."""

    def __init__(
        self,
        hammy: HamiltonInterface,
        used_node: int,
        star_device: str = None,
        simulation: bool = False,
    ) -> None:
        """Initializes the HHS module so it is ready to have commands sent to it.

        Args:
            hammy (HamiltonInterface): instrument context
            used_node (int): controller node the particular HHS of interest is connected to
            star_device (str, optional): determines whether HHS is created as a STAR device
                or USB device. Defaults to None, meaning as a USB device.
                    star_device = "ML_STAR"
            simulation (bool, optional): whether the HHS should be simulated. Defaults to False.
        """
        self.hammy = hammy
        self.set_simulation(hammy, simulation)
        if star_device is None:
            self.num = self.create_usb_dev(hammy, used_node)
        else:
            self.num = self.create_star_dev(hammy, used_node, star_device)

        # initializes heater and shakers functions
        self.shaker = HHS.Shaker(hammy, self.num)
        self.heater = HHS.Heater(hammy, self.num)

    @staticmethod
    def set_simulation(hammy: HamiltonInterface, simulation: bool = True) -> str:
        """Set simulation status of the HHS.

        Args:
            hammy (HamiltonInterface): instrument
            simulation (bool, optional): whether HHS is simulated. Defaults to True.

        Returns:
            str: command unique ID. Can be sent to instrument to ask for response.
        """
        cmd = hammy.send_command(HHS_SET_SIMULATION, simulate=int(simulation))
        return cmd

    @staticmethod
    def create_star_dev(
        hammy: HamiltonInterface, used_node: int, star_device: str = "ML_STAR"
    ) -> int:
        """Creates HHS as a STAR device

        Args:
            hammy (HamiltonInterface): instrument
            used_node (int): controller node the particular HHS of interest is connected to
            star_device (str, optional): instrument context as string for Venus. Defaults to "ML_STAR".

        Returns:
            int: unique ID for HHS
        """
        cmd = hammy.send_command(
            HHS_CREATE_STAR_DEVICE, starDevice=star_device, usedNode=used_node
        )
        response = hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    @staticmethod
    def create_usb_dev(hammy: HamiltonInterface, used_node: int) -> int:
        """Creates HHS as a USB device.

        Args:
            hammy (HamiltonInterface): instrument
            used_node (int): controller node the particular HHS of interest is connected to

        Returns:
            int: unique ID for HHS
        """
        cmd = hammy.send_command(HHS_CREATE_USB_DEVICE, usedNode=used_node)
        response = hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    def terminate(self) -> None:
        """Terminates communication with all HHS modules. Does not stop heating or shaking."""
        cmd = self.hammy.send_command(HHS_TERMINATE)
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def begin_monitoring(
        self,
        rpm_tolerance: int = 10,
        interval: int = 5,
        action: bool = False,
    ):
        """Begin monitoring of HHS shaking to ensure values stay within expected tolerance.

        Args:
            rpm_tolerance (int, optional): difference to programmed RPM allowed. Defaults to 10.
            interval (int, optional): how frequently values are polled (s). Defaults to 5.
            action (bool, optional): whether the instrument takes action when reported RPM
                is outside allowed tolerance. Defaults to False.
        """
        cmd = self.hammy.send_command(
            HHS_BEGIN_MONITORING,
            deviceNumber=self.num,
            shakingToleranceRange=rpm_tolerance,
            sampleInterval=interval,
            action=int(action),
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)
        # TODO: return path to trace file for real time monitoring

    def end_monitoring(self):
        """Ends monitoring of HHS shaking and returns

        Returns:
            _type_: _description_
        """
        cmd = self.hammy.send_command(HHS_END_MONITORING, deviceNumber=self.num)
        response = self.hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        # TODO: learn what type of data is return
        return response.return_data[0]

    def lock_plate(self, plate_lock: bool = True) -> None:
        """(Dis)engages plate lock of HHS.

        Args:
            plate_lock (bool, optional): determines whether plate lock is engaged or not. Defaults to True.
        """
        cmd = self.hammy.send_command(
            HHS_SET_PLATE_LOCK, deviceNumber=self.num, plateLock=plate_lock
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def serial_number(self) -> str:
        """Gets HHS serial number

        Returns:
            str: serial number
        """
        cmd = self.hammy.send_command(HHS_GET_SERIAL_NUM, deviceNumber=self.num)
        response = self.hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    def firmware_version(self):
        """Gets firmware version loaded on HHS

        Returns:
            str: firmware version
        """
        cmd = self.hammy.send_command(HHS_GET_FIRMWARE_VERSION, deviceNumber=self.num)
        response = self.hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    class Shaker:
        """Shaker relevant functions and information."""

        def __init__(self, hammy: HamiltonInterface, device_number: int):
            self.hammy = hammy
            self.num = device_number

        def start(self, shaking_speed: int) -> None:
            """Starts shaking at given rpm

            Args:
                shaking_speed (int): desired rpm to shake at.
            """
            cmd = self.hammy.send_command(
                HHS_START_SHAKER,
                deviceNumber=self.num,
                shakingSpeed=shaking_speed,
            )
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def start_timed(
            self,
            shaking_speed: int,
            shaking_time: int,
        ) -> None:
            """Starts shaking for a given time.

            Args:
                shaking_speed (int): desired RPM.
                shaking_time (int): time (s) to shake for.
            """
            cmd = self.hammy.send_command(
                HHS_START_SHAKER_TIMED,
                deviceNumber=self.num,
                shakingSpeed=shaking_speed,
                shakingTime=shaking_time,
            )
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def wait(self) -> None:
            """Halts method until shaker (started from 'start_timed') has finished."""
            cmd = self.hammy.send_command(HHS_WAIT_FOR_SHAKER, deviceNumber=self.num)
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def stop(self) -> None:
            """Stops shaking."""
            cmd = self.hammy.send_command(HHS_STOP_SHAKER, deviceNumber=self.num)
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def set_parameters(
            self,
            shaking_direction: int,
            shaking_acc_ramp: int,
        ) -> None:
            """Set the parameters for the shaker module.

            Args:
                hammy (HamiltonInterface): instrument
                device_number (int): ID for target HHS module
                shaking_direction (int): 0 for clockwise, 1 for counter-clockwise rotation
                shaking_acc_ramp (int): acceleration in rpm/s [630, 125000]

            Raises:
                ValueError: Shaking direction must be either 0 or 1
                ValueError: Acceleration ramp must be between 630 and 125000
            """
            if shaking_direction != 0 or shaking_direction != 1:
                raise ValueError("Shaking direction must be either 0 or 1")
            if shaking_acc_ramp not in range(630, 125001):
                raise ValueError("Acceleration ramp must be between 630 and 125000")

            cmd = self.hammy.send_command(
                HHS_SET_SHAKER_PARAM,
                deviceNumber=self.num,
                shakingDirection=shaking_direction,
                shakingAccRamp=shaking_acc_ramp,
            )
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def get_parameters(self) -> list:
            """Gets shaking parameters specified on the HHS.

            Returns:
                list: [shaking direction, acceleration ramp]
            """
            cmd = self.hammy.send_command(HHS_GET_SHAKER_PARAM, deviceNumber=self.num)
            response = self.hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
                return_data=["step-return2", "step-return3"],
            )
            return response.return_data

        def get_rpm(self) -> int:
            """Gets current shaker RPM.

            Returns:
                int: RPM.
            """
            cmd = self.hammy.send_command(HHS_GET_SHAKER_SPEED, deviceNumber=self.num)
            response = self.hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
                return_data=["step-return2"],
            )
            return response.return_data[0]

    class Heater:
        """Heater relevant functions and information."""

        def __init__(self, hammy: HamiltonInterface, device_number: int):
            self.hammy = hammy
            self.num = device_number

        def start(self, temperature: float, wait: bool = False) -> None:
            """Starts temperature control of module.

            Args:
                temperature (float): desired temperature.
                wait (bool, optional): halt function until module reaches desired temperate.
                    Defaults to False.
            """
            cmd = self.hammy.send_command(
                HHS_START_TEMP_CTRL,
                deviceNumber=self.num,
                temperature=temperature,
                waitForTempReached=wait,
            )
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def stop(self) -> None:
            """Stops temperature control of HHS."""
            cmd = self.hammy.send_command(HHS_STOP_TEMP_CTRL, deviceNumber=self.num)
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def temperature(self) -> float:
            """Gets current temperature of HHS.

            Returns:
                float: current temperature.
            """
            cmd = self.hammy.send_command(HHS_GET_TEMP, deviceNumber=self.num)
            response = self.hammy.wait_on_response(
                cmd, raise_first_exception=True, return_data=["step-return2"]
            )
            temp = response.return_data[0]
            return temp

        def state(self):
            """_summary_

            Returns:
                _type_: _description_
            """
            cmd = self.hammy.send_command(HHS_GET_TEMP_STATE, deviceNumber=self.num)
            response = self.hammy.wait_on_response(
                cmd, raise_first_exception=True, return_data=["step-return2"]
            )

            # TODO: learn what temp state is
            return response.return_data[0]

        def wait(self) -> None:
            """Waits for HHS to reach desired temperature."""
            cmd = self.hammy.send_command(HHS_WAIT_FOR_TEMP_CTRL, deviceNumber=self.num)
            self.hammy.wait_on_response(cmd, raise_first_exception=True)

        def set_parameters(
            self,
            start_timeout: int = 1800,
            tolerance_range: float = 2.0,
            security_range: float = 6.0,
        ) -> None:
            """Set default temperature parameters for the temperature control function.

            Args:
                start_timeout (int, optional): timeout if module doesn't reach desired temperature.
                    Defaults to 1800.
                tolerance_range (float, optional): allowed difference between actual and desired temperature.
                    Defaults to 2.0.
                security_range (float, optional): limit where the module will shutdown if difference is
                    greater than value specified. Defaults to 6.0.
            """
            cmd = self.hammy.send_command(
                HHS_SET_TEMP_PARAM,
                deviceNumber=self.num,
                startTimeout=start_timeout,
                toleranceRange=tolerance_range,
                securityRange=security_range,
            )
            self.hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
            )

        def get_parameters(self) -> list:
            """Returns current parameters of temperature control function.

            Returns:
                list: [timeout, tolerance, security]
            """
            cmd = self.hammy.send_command(HHS_GET_TEMP_PARAM, deviceNumber=self.num)
            response = self.hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
                return_data=["step-return2", "step-return3", "step-return4"],
            )
            return response.return_data


class Channels:
    """Functions to control the individual 1000uL channels."""

    def __init__(
        self, hammy: HamiltonInterface, num_channels: int = 8, size_ul: int = 1000
    ) -> None:
        self.hammy = hammy
        self.num = num_channels
        self.size = size_ul

    def pickup(
        self,
        seq: str = "",
        positions: str = "",
        channels: str = None,
        count: bool = True,
        channel_use: int = 1,
    ):
        if channels is None:
            channels = "1" * self.num
        cmd = self.hammy.send_command(
            PICKUP,
            tipSequence=seq,
            labwarePositions=positions,
            channelVariable=channels,
            sequenceCounting=int(count),
            channelUse=channel_use,
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def eject(
        self,
        seq: str = "",
        positions: str = "",
        channels: str = None,
        count: bool = False,
        channel_use: int = 1,
        default_waste: bool = True,
    ):
        if channels is None:
            channels = "1" * self.num
        cmd = self.hammy.send_command(
            EJECT,
            wasteSequence=seq,
            labwarePositions=positions,
            channelVariable=channels,
            sequenceCounting=int(count),
            channelUse=channel_use,
            useDefaultWaste=int(default_waste),
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def aspirate(
        self,
        vol: list,
        liquid_class: str = None,
        seq: str = "",
        positions: str = "",
        **kwargs
    ):
        """Aspirates from the given location.

        Args:
            vol (list): _description_
            liquid_class (str, optional): _description_. Defaults to None.
            seq (str, optional): _description_. Defaults to "".
            positions (str, optional): _description_. Defaults to "".

        Keyword Args:
            channelVariable
            aspirateMode:0, (integer) 0=Normal Aspiration, 1=Consecutive (don't aspirate blowout), 2=Aspirate all
            capacitiveLLD:0, (integer) 0=Off, 1=Max, 2=High, 3=Mid, 4=Low, 5=From labware definition
            pressureLLD:0, (integer) 0=Off, 1=Max, 2=High, 3=Mid, 4=Low, 5=From liquid class definition
            liquidFollowing:0, (integer) 0=Off , 1=On
            submergeDepth:2.0, (float) mm of immersion below liquid's surface to start aspiration when using LLD
            liquidHeight:1.0, (float) mm above container's bottom to start aspiration when not using LLD
            maxLLdDifference:0.0, (float) max mm height different between cLLD and pLLD detected liquid levels
            mixCycles:0, (integer) number of mixing cycles (1 cycle = 1 asp + 1 disp)
            mixPosition:0.0, (float) additional immersion mm below aspiration position to start mixing
            mixVolume:0.0, (float) mix volume
            xDisplacement:0.0,
            yDisplacement:0.0,
            zDisplacement:0.0,
            airTransportRetractDist:10.0, (float) mm to move up in Z after finishing the aspiration at a fixed height before aspirating 'transport air'
            touchOff:0, (integer) 0=Off , 1=On
            aspPosAboveTouch:0.0, (float)  mm to move up in Z after touch off detects the bottom before aspirating liquid
        """
        cmd = self.hammy.send_command(
            ASPIRATE,
            aspirateSequence=seq,
            labwarePositions=positions,
            volumes=vol,
            liquidClass=liquid_class,
            **kwargs,
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def dispense(
        self,
        vol: list,
        liquid_class: str = None,
        seq: str = "",
        positions: str = "",
        **kwargs
    ):
        """_summary_

        Args:
            vol (list): _description_
            liquid_class (str, optional): _description_. Defaults to None.
            seq (str, optional): _description_. Defaults to "".
            positions (str, optional): _description_. Defaults to "".

        Keyward Args:
            channelVariable
            sequenceCounting:0, (integer) 0=don't autoincrement,  1=Autoincrement
            channelUse:1, (integer) 1=use all sequence positions (no empty wells), 2=keep channel pattern
            dispenseMode:8, (integer) 0=Jet Part, 1=Jet Empty, 2=Surface Part, 3=Surface Empty, 4=Jet Drain tip, 8=From liquid class, 9=Blowout tip
            capacitiveLLD:0, (integer) 0=Off, 1=Max, 2=High, 3=Mid, 4=Low, 5=From labware definition
            liquidFollowing:0, (integer) 0=Off , 1=On
            submergeDepth:2.0, (float) mm of immersion below liquid's surface to start dispense when using LLD
            liquidHeight:1.0, (float) mm above container's bottom to start dispense when not using LLD
            mixCycles:0, (integer) number of mixing cycles (1 cycle = 1 asp + 1 disp)
            mixPosition:0.0, (float) additional immersion mm below dispense position to start mixing
            mixVolume:0.0, (float) mix volume
            xDisplacement:0.0,
            yDisplacement:0.0,
            zDisplacement:0.0,
            airTransportRetractDist:10.0, (float) mm to move up in Z after finishing the dispense at a fixed height before aspirating 'transport air'
            touchOff:0, (integer) 0=Off , 1=On
            dispPositionAboveTouch:0.0, (float) mm to move up in Z after touch off detects the bottom, before dispense
            zMoveAfterStep:0, (integer) 0=normal, 1=Minimized (Attention!!! this depends on labware clearance height, can crash).
            sideTouch:0 (integer) 0=Off , 1=On
        """

        cmd = self.hammy.send_command(
            DISPENSE,
            dispenseSequence=seq,
            labwarePositions=positions,
            volumes=vol,
            liquidClass=liquid_class,
            **kwargs,
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def create_channel_str(self, pos: list) -> str:
        out = "1" * len(pos)
        for i in range(self.num - len(out)):
            out = out + "0"
        return out


class MPH96:
    def init(self, hammy: HamiltonInterface):
        self.hammy = hammy

    def pickup(self, seq: str = "", **kwargs):
        cmd = self.hammy.send_command(PICKUP96, tipSequence=seq, **kwargs)
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def eject(self, **kwargs):
        cmd = self.hammy.send_command(EJECT96, **kwargs)
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def aspirate(
        self,
        vol: float,
        liquid_class: str,
        seq: str = "",
        positions: str = "",
        **kwargs
    ):
        cmd = self.hammy.send_command(
            ASPIRATE96,
            aspirateSequence=seq,
            labwarePositions=positions,
            aspirateVolume=vol,
            liquidClass=liquid_class,
            **kwargs,
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def dispense(
        self,
        vol: float,
        liquid_class: str,
        seq: str = "",
        positions: str = "",
        **kwargs
    ):
        cmd = self.hammy.send_command(
            DISPENSE96,
            dispenseSequence=seq,
            labwarePositions=positions,
            dispenseVolume=vol,
            liquidClass=liquid_class,
            **kwargs,
        )

        self.hammy.wait_on_response(cmd, raise_first_exception=True)
