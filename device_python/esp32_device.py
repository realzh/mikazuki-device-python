import asyncio
import json
import time
import traceback
import zlib
from uuid import uuid4

import serial.tools.list_ports

from device_python.openable import Openable


class Command:
    def __init__(self, command: dict) -> None:
        self.command = command
        self.response = asyncio.Future[dict]()


class ESP32Device(Openable):

    @classmethod
    async def enumerate_device_ports(cls):
        ports: list[str] = []
        for p in serial.tools.list_ports.comports():
            if p.product == "mikatsuki":
                ports.append(p.device)
        return ports

    def __init__(self, port: str):
        super().__init__()
        self.port = port
        self.timeout_s = 1
        self.heartbeat_interval_s = 0.2

    async def on_open(self):
        self.serial = serial.Serial(self.port)
        self.lock = asyncio.Lock()
        self.pending_commands: dict[str, Command] = {}
        self.add_task(asyncio.create_task(self.task_receive_line()))
        self.add_task(asyncio.create_task(self.task_heartbeat()))
        self.serial_number = (
            await self.send_command("state_get", {"key": "serial_number"})
        )["result"]["value"]

    async def on_close(self):
        self.serial.close()

    async def task_receive_line(self):
        while True:
            next_line = await asyncio.to_thread(self.serial.readline)

            try:
                next_line = next_line.decode().strip()
                assert len(next_line) > 8
                json_str = next_line[:-8]
                crc_received = int.from_bytes(
                    bytes.fromhex(next_line[-8:]), byteorder="little", signed=False
                )
                crc_calculated = zlib.crc32(json_str.encode())
                assert crc_received == crc_calculated
                json_dict = json.loads(json_str)
                assert isinstance(json_dict, dict)
            except Exception:
                traceback.print_exc()
                continue
            type = json_dict.get("type")
            if type == "response":
                request_id = json_dict.get("request_id")
                if not isinstance(request_id, str):
                    print("request_id not found in response")
                    continue
                if request_id not in self.pending_commands:
                    print(f"response {request_id} not pending")
                    continue
                pending_command = self.pending_commands.pop(request_id)
                pending_command.response.set_result(json_dict)
            else:
                print(f"unknown type {type}")

    async def task_heartbeat(self):
        while True:
            try:
                await self.send_command("echo", {"value": "hearbeat"}, print_log=False)
                await asyncio.sleep(self.heartbeat_interval_s)
            except:
                await self.close()
                break

    async def send_command(
        self, name: str, params: dict | None = None, assert_success=True, print_log=True
    ):
        assert self.has_opened and not self.has_closed
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
            if print_log:
                print(f"esp32 > {command_str}")

            serial_line = command_str.encode()
            serial_line += (
                zlib.crc32(serial_line)
                .to_bytes(length=4, byteorder="little", signed=False)
                .hex()
                .upper()
                .encode()
            )
            serial_line += b"\n"
            start_time_ns = time.perf_counter_ns()
            await asyncio.to_thread(self.serial.write, serial_line)
            response = await asyncio.wait_for(pending_command.response, self.timeout_s)
            stop_time_ns = time.perf_counter_ns()
            if print_log:
                print(f"esp32 | {response}")
            response["response_time"] = (stop_time_ns - start_time_ns) / 1e9
            success = response.get("success")
            if assert_success and not success:
                raise Exception(
                    f"Command {command} to {self.serial_number} failed, {response}"
                )

            return response
