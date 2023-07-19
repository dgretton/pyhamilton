"""Wrappers with documentation to make pyhamilton easier to use

"""
import logging

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
    HHS_STOP_ALL_SHAKER,
    HHS_STOP_SHAKER,
    HHS_GET_SHAKER_SPEED,
    HHS_GET_SHAKER_PARAM,
)


class Instrument:
    """Utility functions for the Hamilton"""

    def __init__(self, hammy: HamiltonInterface) -> None:
        self.hammy = hammy

    def initialize(self, asynch: bool = False):
        """Initializes Hamilton instrument.

        Args:
            hammy (HamiltonInterface): instrument to initialize
            asynch (bool): perform asynchronously
        """
        logging.info(
            "Initializing: %s",
            ("a" if asynch else "") + "synchronously initialize the robot",
        )
        cmd = self.hammy.send_command(INITIALIZE)
        if not asynch:
            self.hammy.wait_on_response(cmd, raise_first_exception=True, timeout=300)

    def move_auto_load(self, track: int):
        """Moves auto loader.

        Args:
            hammy (HamiltonInterface): instrument
            track (int): track to move to
        """
        logging.info("Moving auto load to track: %i", track)
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
        self.hammy = hammy
        self.hammy.send_command(HHS_SET_SIMULATION, simulate=simulation)
        if star_device is None:
            cmd = self.hammy.send_command(HHS_CREATE_USB_DEVICE, usedNode=used_node)
            response = self.hammy.wait_on_response(
                cmd, raise_first_exception=True, return_data=["step-return2"]
            )
            self.num = response.return_data[0]
        else:
            cmd = self.hammy.send_command(
                HHS_CREATE_STAR_DEVICE, starDevice=star_device, usedNode=used_node
            )
            response = self.hammy.wait_on_response(
                cmd, raise_first_exception=True, return_data=["step-return2"]
            )
            self.num = response.return_data[0]

    @staticmethod
    def set_simulation(hammy: HamiltonInterface, simulation: bool = True) -> str:
        cmd = hammy.send_command(HHS_SET_SIMULATION, simulate=simulation)
        return cmd

    @staticmethod
    def create_star_dev(
        hammy: HamiltonInterface, used_node: int, star_device: str = "ML_STAR"
    ) -> int:
        cmd = hammy.send_command(
            HHS_CREATE_STAR_DEVICE, starDevice=star_device, usedNode=used_node
        )
        response = hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    @staticmethod
    def create_usb_dev(hammy: HamiltonInterface, used_node: int) -> int:
        cmd = hammy.send_command(HHS_CREATE_USB_DEVICE, usedNode=used_node)
        response = hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        return response.return_data[0]

    def terminate(self):
        cmd = self.hammy.send_command(HHS_TERMINATE)
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    def hhs_begin_monitoring(
        self,
        rpm_tolerance: int = 10,
        interval: int = 5,
        action: int = 0,
    ):
        cmd = self.hammy.send_command(
            HHS_BEGIN_MONITORING,
            deviceNumber=self.num,
            shakingToleranceRange=rpm_tolerance,
            sampleInterval=interval,
            action=action,
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

        # return path to trace file for real time monitoring

    def end_monitoring(self):
        cmd = self.hammy.send_command(HHS_END_MONITORING, deviceNumber=self.num)
        response = self.hammy.wait_on_response(
            cmd, raise_first_exception=True, return_data=["step-return2"]
        )
        monitor_result = response.return_data[0]
        return monitor_result

    def lock_plate(self, plate_lock: bool = True):
        cmd = self.hammy.send_command(
            HHS_SET_PLATE_LOCK, deviceNumber=self.num, plateLock=plate_lock
        )
        self.hammy.wait_on_response(cmd, raise_first_exception=True)

    class Shaker:
        @staticmethod
        def parameters(
            hammy: HamiltonInterface,
            device_number: int,
            shaking_direction: int,
            shaking_acc_ramp: int,
        ):
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

            cmd = hammy.send_command(
                HHS_SET_SHAKER_PARAM,
                deviceNumber=device_number,
                shakingDirection=shaking_direction,
                shakingAccRamp=shaking_acc_ramp,
            )
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def start(hammy: HamiltonInterface, device_number: int, shaking_speed: int):
            cmd = hammy.send_command(
                HHS_START_SHAKER,
                deviceNumber=device_number,
                shakingSpeed=shaking_speed,
            )
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def start_timed(
            hammy: HamiltonInterface,
            device_number: int,
            shaking_speed: int,
            shaking_time: int,
        ):
            cmd = hammy.send_command(
                HHS_START_SHAKER_TIMED,
                deviceNumber=device_number,
                shakingSpeed=shaking_speed,
                shakingTime=shaking_time,
            )
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def wait(hammy: HamiltonInterface, device_number: int):
            cmd = hammy.send_command(HHS_WAIT_FOR_SHAKER, deviceNumber=device_number)
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def stop(hammy: HamiltonInterface, device_number: int):
            cmd = hammy.send_command(HHS_STOP_SHAKER, deviceNumber=device_number)
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def stop_all(hammy: HamiltonInterface):
            cmd = hammy.send_command(HHS_STOP_ALL_SHAKER)
            hammy.wait_on_response(cmd, raise_first_exception=True)

        @staticmethod
        def get_parameters(hammy: HamiltonInterface, device_number: int):
            cmd = hammy.send_command(HHS_GET_SHAKER_PARAM, deviceNumber=device_number)
            response = hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
                return_data=["step-return2", "step-return3"],
            )
            return response.return_data[0:1]

        @staticmethod
        def get_rpm(hammy: HamiltonInterface, device_number: int):
            cmd = hammy.send_command(HHS_GET_SHAKER_SPEED, deviceNumber=device_number)
            response = hammy.wait_on_response(
                cmd,
                raise_first_exception=True,
                return_data=["step-return2"],
            )
            return response.return_data[0]
