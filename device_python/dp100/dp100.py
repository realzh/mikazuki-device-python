import os

import pathlib

from device_python.device import Device, action

os.environ["PYTHONNET_RUNTIME"] = "coreclr"

dll_path = str(pathlib.Path(__file__).parent.joinpath("lib/ATKDP100DLL.dll").absolute())

import pythonnet, clr

from contextlib import contextmanager

clr.AddReference(dll_path)  # type: ignore

import ATKDP100DLL  # type: ignore


class DP100(Device):

    async def on_connected(self):
        await super().on_connected()

    async def on_disconnected(self):
        await super().on_disconnected()

    async def connect_to_dp100(self):
        dp100 = ATKDP100DLL.ATKDP100API()
        connected = dp100.DevOpenOrClose()
        if not connected:
            dp100.DevOpenOrClose()

        connected = dp100.GetBasicInfo()
        if not connected:
            raise Exception("DP100 not connected to USB")
        return dp100

    @action(method="get")
    async def get_state(self):

        print("dp100 | get_state")

        dp100 = await self.connect_to_dp100()

        device_type = ""
        hardware_version = ""
        app_version = ""
        device_serial_number = ""
        device_state = ""
        preset_group_index = 0
        output_state = 0
        voltage_set = 0
        current_set = 0
        over_voltage_protection = 0
        over_current_protection = 0
        voltage_output = 0
        current_output = 0
        workSt = ATKDP100DLL.WorkSt.Normal
        outMode = ATKDP100DLL.OutMode.OFF
        back_light_level = 0
        volume_level = 0
        enable_reverse_protection = 0
        enable_auto_output = 0
        over_power_protection = 0
        over_temperature_protection = 0

        (
            success,
            device_type,
            hardware_version,
            app_version,
            device_serial_number,
            device_state,
        ) = dp100.GetDevInfo(
            device_type,
            hardware_version,
            app_version,
            device_serial_number,
            device_state,
        )
        if not success:
            raise Exception(f"ATKDP100API GetDevInfo failed")

        (
            success,
            preset_group_index,
            output_state,
            voltage_set,
            current_set,
            over_voltage_protection,
            over_current_protection,
        ) = dp100.GetCurrentBasic(
            preset_group_index,
            output_state,
            voltage_set,
            current_set,
            over_voltage_protection,
            over_current_protection,
        )
        if not success:
            raise Exception("ATKDP100API GetCurrentBasic failed")

        success, voltage_output, current_output, workSt, outMode = dp100.GetBasicInfo(
            voltage_output, current_output, workSt, outMode
        )
        if not success:
            raise Exception("ATKDP100API GetBasicInfo failed")

        (
            success,
            back_light_level,
            volume_level,
            over_power_protection,
            over_temperature_protection,
            enable_reverse_protection,
            enable_auto_output,
        ) = dp100.GetSysPar(
            back_light_level,
            volume_level,
            over_power_protection,
            over_temperature_protection,
            enable_reverse_protection,
            enable_auto_output,
        )
        if not success:
            raise Exception("ATKDP100API GetSysPar failed")
        device_type: str

        state = {
            "device_type": device_type.split("\u0000")[0],
            "hardware_version": hardware_version,
            "app_version": app_version,
            "device_serial_number": device_serial_number,
            "device_state": device_state,
            "preset_group_index": preset_group_index,
            "output_state": output_state,
            "voltage_set": voltage_set,
            "current_set": current_set,
            "over_voltage_protection": over_voltage_protection,
            "over_current_protection": over_current_protection,
            "voltage_output": voltage_output,
            "current_output": current_output,
            "workSt": workSt.ToString(),
            "outMode": outMode.ToString(),
            "back_light_level": back_light_level,
            "volume_level": volume_level,
            "enable_reverse_protection": enable_reverse_protection,
            "enable_auto_output": enable_auto_output,
            "over_power_protection": over_power_protection,
            "over_temperature_protection": over_temperature_protection,
        }

        await self.set_state("Output", "ON" if state["output_state"] > 0 else "OFF")
        await self.set_state("V", f'{state["voltage_output"]/1000:.3f} mV')
        await self.set_state("I", f'{state["current_output"]/1000:.3f} mA')
        await self.set_state("Vset", f'{state["voltage_set"]/1000:.3f} mV')
        await self.set_state("Iset", f'{state["current_set"]/1000:.3f} mA')

        return state

    @action("post")
    async def output_on(self, voltage: float, current: float):
        dp100 = await self.connect_to_dp100()
        assert dp100.OpenOut(0, int(current * 1000), int(voltage * 1000))

    @action("post")
    async def output_off(self):
        dp100 = await self.connect_to_dp100()
        assert dp100.CloseOut(0, 0, 0)
