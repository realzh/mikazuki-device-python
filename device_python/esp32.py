import asyncio
import json
import traceback
from uuid import uuid4

import serial.tools.list_ports

from device_python import device

from .connection import Connection
from .device import Device, action
from .ws2812 import WS2812


class Command:
    def __init__(self, command: dict) -> None:
        self.command = command
        self.response = asyncio.Future[dict]()


class ESP32Device:

    def __init__(self, port: str, timeout: int | None = None):
        self.port = port
        self.timeout = timeout
        self.has_opened = False

    async def open(self):
        print(f"esp32 device at {self.port} open")
        assert not self.has_opened
        self.has_opened = True
        self.serial = serial.Serial(self.port)
        self.lock = asyncio.Lock()
        self.pending_commands: dict[str, Command] = {}
        self.tasks = [asyncio.create_task(self.task_receive_line())]
        self.serial_number = (
            await self.send_command("get_state", {"key": "serial_number"})
        )["result"]["value"]

    async def close(self):
        self.serial.close()
        for task in self.tasks:
            task.cancel()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    async def task_receive_line(self):
        while True:
            next_line = await asyncio.to_thread(self.serial.readline)

            try:
                next_line = next_line.decode().strip()
                print(f"esp32 | {next_line}")
                next_line_dict = json.loads(next_line)
                assert isinstance(next_line_dict, dict)
            except Exception:
                traceback.print_exc()
                continue
            type = next_line_dict.get("type")
            if type == "response":
                request_id = next_line_dict.get("request_id")
                if not isinstance(request_id, str):
                    print("request_id not found in response")
                    continue
                if request_id not in self.pending_commands:
                    print(f"response {request_id} not pending")
                    continue
                pending_command = self.pending_commands.pop(request_id)
                pending_command.response.set_result(next_line_dict)
            else:
                print(f"unknown type {type}")

    async def send_command(
        self, name: str, params: dict | None = None, assert_success=True
    ):
        async with self.lock:
            request_id = str(uuid4())
            command = {
                "name": name,
                "parameters": params if params else {},
                "request_id": request_id,
            }
            command_str = json.dumps(command, separators=(",", ":"))
            pending_command = Command(command)
            self.pending_commands[request_id] = pending_command
            print(f"esp32 > {command_str}")
            await asyncio.to_thread(self.serial.write, command_str.encode() + b"\n")
            if self.timeout is not None:
                response = await asyncio.wait_for(
                    pending_command.response, self.timeout
                )
            else:
                response = await pending_command.response
            success = response.get("success")
            if assert_success and not success:
                raise Exception(
                    f"Command {command} to {self.serial_number} failed, {response}"
                )

            return response


async def enumerate_device_ports():
    ports: list[str] = []
    for p in serial.tools.list_ports.comports():
        if p.product == "mikatsuki":
            ports.append(p.device)
    return ports


class ESP32WSDevice(Device):

    def __init__(self, *, ws_connection: Connection, esp32_device_port: str) -> None:
        super().__init__(
            ws_connection=ws_connection,
            device_id=None,
        )
        self.esp32_device_port = esp32_device_port
        self.sub_devices = set[Device]()
        self.feature_configs = {
            "ws2812": {
                "gpio_num": 38,
            }
        }

    async def open(self):
        self.esp32_device = ESP32Device(self.esp32_device_port)
        await self.esp32_device.open()
        self.device_id = f"esp32-{self.esp32_device.serial_number}"
        await super().open()
        actions_from_commands = await self.generate_actions_from_commands()
        self.actions.extend(actions_from_commands)
        await self.send_action_definitions()
        # await self.create_devices_from_features()

    async def close(self):
        await super().close()
        await self.esp32_device.close()
        while self.sub_devices:
            sub_device = self.sub_devices.pop()
            await sub_device.close()

    async def generate_action_handler_from_command(self, command: dict):

        async def handler(**kwargs):

            response = await self.esp32_device.send_command(command["name"], kwargs)
            return response

        return handler

    async def generate_actions_from_commands(self):
        commands = (await self.esp32_device.send_command("get_command_defs"))["result"][
            "command_defs"
        ]

        actions: list[device.Action] = []
        for command in commands:
            esp32_param_defs = command["parameters"]
            action_param_defs: list[device.Parameter] = []
            for param_def in esp32_param_defs:
                action_param_defs.append(
                    device.Parameter(
                        param_def["name"], param_def["type"], param_def["optional"]
                    )
                )
            action = device.Action(
                f"_{command['name']}",
                action_param_defs,
                None,
                await self.generate_action_handler_from_command(command),
            )

            actions.append(action)
        return actions

    # @action
    # async def create_devices_from_features(self):
    #     while self.sub_devices:
    #         sub_device = self.sub_devices.pop()
    #         await sub_device.close()
    #     features = await self.esp32_device.send_command("get_state features")
    #     features = [x.strip() for x in features.split(",")]
    #     await self.set_state("features", features)
    #     for feature in features:
    #         if feature == "ws2812":
    #             sub_device = WS2812(
    #                 ws_connection=self.ws_connection,
    #                 device_id=f"ws2812-{self.esp32_device.serial_number}",
    #                 esp32_send_command=self.esp32_device.send_command,
    #                 gpio_num=self.feature_configs["ws2812"]["gpio_num"],
    #             )
    #             await sub_device.open()
    #             self.sub_devices.add(sub_device)

    @action
    async def get_feature_configs(self):
        return self.feature_configs

    @action
    async def set_feature_configs(self, config: str):
        self.feature_configs = json.loads(config)


async def create_esp32_ws_devices(ws_connection: Connection):
    ports = await enumerate_device_ports()

    for port in ports:

        await ws_connection.context.enter_async_context(
            ESP32WSDevice(
                ws_connection=ws_connection,
                esp32_device_port=port,
            )
        )


async def main():
    for port in await enumerate_device_ports():
        async with ESP32Device(port) as device:
            await device.send_command("get_command_defs")


if __name__ == "__main__":
    asyncio.run(main())
