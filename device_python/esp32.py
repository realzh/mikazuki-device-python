import json
from typing import Awaitable, Callable


import asyncio


from serial import Serial
import serial.tools.list_ports


from .device import AsyncSend, Device, string_to_type

AsyncSendCommand = Callable[[str], Awaitable[str]]

esp32_devices = []


async def task_receive(device: dict):
    while True:
        next_line = await asyncio.to_thread(device["serial"].readline)
        next_line = next_line.decode().strip()
        if next_line.startswith("rsp| "):
            rsp = next_line[5:]
            print(f"esp32 | {rsp}")
            await device["command_receive_queue"].put(rsp)
        elif next_line.startswith("evt| "):
            evt = next_line[5:]
            print(f"esp32 * {evt}")
        else:
            print(next_line)


async def task_send_command(
    device: dict,
):
    ser: Serial = device["serial"]
    command_send_queue: asyncio.Queue = device["command_send_queue"]
    command_receive_queue: asyncio.Queue = device["command_receive_queue"]

    while True:
        next_command = await command_send_queue.get()
        while not command_receive_queue.empty():
            try:
                command_receive_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        command = next_command["command"]
        print(f"esp32 > {command}")
        await asyncio.to_thread(ser.write, command.encode("utf-8") + b"\n")
        result = await command_receive_queue.get()
        next_command["future"].set_result(result)


async def send_command(device: dict, command: str, assert_success=True) -> str:
    future = asyncio.Future[str]()
    await device["command_send_queue"].put({"command": command, "future": future})
    result = await future
    success = result.startswith("OK")
    if assert_success:
        if not success:
            raise Exception(
                f"Command {command} to {device.get('serial_number') or 'no-serial-number'} failed | {result}"
            )
        if result.startswith("OK:"):
            result = result[3:].strip()
    return result


enumerated = False


async def enumerate_devices():

    global enumerated
    assert not enumerated
    enumerated = True

    for p in serial.tools.list_ports.comports():
        if p.product == "mikatsuki":
            device = {
                "serial": Serial(p.device),
                "command_send_queue": asyncio.Queue(),
                "command_receive_queue": asyncio.Queue(),
            }
            esp32_devices.append(device)
            device["task_receive"] = asyncio.create_task(task_receive(device))
            device["task_send_command"] = asyncio.create_task(task_send_command(device))

            async def device_send_command(command: str):
                return await send_command(device, command)

            device["send_command"] = device_send_command

    for dev in esp32_devices:
        serial_number = await send_command(dev, "get_state serial_number")
        dev["serial_number"] = serial_number
        features = await send_command(dev, "get_state features")
        features = features.split(",")
        if len(features) == 1 and features[0] == "":
            features = []
        dev["features"] = features


class ESP32(Device):

    def __init__(self, *, esp32_device: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.esp32_device = esp32_device

    async def on_connected(self):
        await super().on_connected()
        commands = json.loads(await self.esp32_device["send_command"]("get_commands"))
        for command in commands:
            arg_strs = [
                x for x in command["arguments_description"].split(" ") if x != ""
            ]
            parameters = []
            for arg_str in arg_strs:
                if ":" not in arg_str:
                    continue
                name, type_str = arg_str.split(":")
                type_class = string_to_type(type_str)
                if not type_class:
                    continue
                parameters.append(
                    {
                        "name": name,
                        "type": type_class,
                        "type_str": type_str,
                        "optional": False,
                    }
                )

            def handler_wrapper():
                this_command = command
                this_parameters = parameters

                async def handler(**kwargs):
                    s = f"{this_command['command']}"
                    for param in this_parameters:
                        param_name = param["name"]
                        type_class = param["type"]
                        s += f" {type_class(kwargs[param_name])}"
                    resposne = await self.esp32_device["send_command"](s)
                    try:
                        resposne = json.loads(resposne)
                    except Exception:
                        pass
                    return {"esp32_response": resposne}

                return handler

            action = {
                "action": f"esp_{command['command']}",
                "method": "post",
                "handler": handler_wrapper(),
                "parameters": parameters,
            }
            self.actions.append(action)
        await self.send_action_definitions()
        features = await self.esp32_device["send_command"]("get_state features")
        await self.set_state("features", features)


if __name__ == "__main__":
    asyncio.run(enumerate_devices())
