import asyncio
import json

import serial.tools.list_ports

from device_python import device

from .connection import Connection
from .device import Device, action
from .ws2812 import WS2812


class Command:
    def __init__(self, command: str) -> None:
        self.command = command
        self.result = asyncio.Future[str]()


class ESP32Device:

    def __init__(self, port: str, timeout: int | None = None):
        self.port = port
        self.timeout = timeout

    async def open(self):
        self.serial = serial.Serial(self.port)
        self.serial_number: str | None = None
        self.lock = asyncio.Lock()
        self.pending_command: Command | None = None
        self.tasks = [asyncio.create_task(self.task_receive_line())]
        self.serial_number = await self.send_command("get_state serial_number")
        assert len(self.serial_number) > 0

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
            except UnicodeDecodeError as e:
                print(e)
                continue

            if next_line.startswith("rsp| "):
                rsp = next_line[5:]
                print(f"esp32 | {rsp}")
                if self.pending_command is not None:
                    try:
                        self.pending_command.result.set_result(rsp)
                    except asyncio.InvalidStateError as e:
                        print(e)
                    self.pending_command = None

            elif next_line.startswith("evt| "):
                evt = next_line[5:]
                print(f"esp32 * {evt}")
            else:
                print(next_line)

    async def send_command(self, command: str, assert_success=True):
        async with self.lock:
            command_bytes = command.encode("utf-8", "ignore")
            pending_command = Command(command)
            self.pending_command = pending_command
            print(f"esp32 > {command}")
            await asyncio.to_thread(self.serial.write, command_bytes + b"\n")
            if self.timeout is not None:
                result = await asyncio.wait_for(pending_command.result, self.timeout)
            else:
                result = await pending_command.result
            success = result.startswith("OK")
            if assert_success and not success:
                raise Exception(f"Command {command} to {self.serial_number} failed")
            if result.startswith("OK:"):
                result = result[3:].strip()

            return result


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

    async def open(self):
        self.esp32_device = ESP32Device(self.esp32_device_port)
        await self.esp32_device.open()
        self.device_id = f"esp32-{self.esp32_device.serial_number}"
        await super().open()
        actions_from_commands = await self.generate_actions_from_commands()
        self.actions.extend(actions_from_commands)
        await self.send_action_definitions()
        await self.create_devices_from_features()

    async def close(self):
        await super().close()
        await self.esp32_device.close()
        while self.sub_devices:
            sub_device = self.sub_devices.pop()
            await sub_device.close()

    async def generate_action_handler_from_command(self, command: dict):

        async def handler(**kwargs):
            esp32_command = f"{command['name']}"
            for arg_def in command["args"]:
                arg_name = arg_def["name"]
                arg_value = kwargs[arg_name]
                esp32_command += f" {arg_value}"
            response = await self.esp32_device.send_command(esp32_command)
            try:
                response = json.loads(response)
            except Exception:
                pass
            return response

        return handler

    async def generate_actions_from_commands(self):
        commands = json.loads(await self.esp32_device.send_command("get_commands"))
        actions: list[device.Action] = []
        for command in commands:
            args = command["args"]
            parameters: list[device.Parameter] = []
            for arg in args:
                parameters.append(device.Parameter(arg["name"], arg["type"], False))
            action = device.Action(
                f"cmd_{command['name']}",
                parameters,
                None,
                await self.generate_action_handler_from_command(command),
            )

            actions.append(action)
        return actions

    @action
    async def create_devices_from_features(self):
        while self.sub_devices:
            sub_device = self.sub_devices.pop()
            await sub_device.close()
        features = await self.esp32_device.send_command("get_state features")
        features = [x.strip() for x in features.split(",")]
        await self.set_state("features", features)
        for feature in features:
            if feature == "ws2812":
                sub_device = WS2812(
                    ws_connection=self.ws_connection,
                    device_id=f"ws2812-{self.esp32_device.serial_number}",
                    esp32_send_command=self.esp32_device.send_command,
                    gpio_num=38,
                )
                await sub_device.open()
                self.sub_devices.add(sub_device)


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
            pass


if __name__ == "__main__":
    asyncio.run(main())
