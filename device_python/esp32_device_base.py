import asyncio
from datetime import datetime
import json
import time
import traceback
import uuid
import zlib

from device_python.openable import Openable


class ESP32DeviceBase(Openable):

    def __init__(self):
        super().__init__()
        self.timeout_s = 1
        self.heartbeat_interval_s = 0.2
        self.lock = asyncio.Lock()
        self.pending_commands: dict[str, asyncio.Future[dict]] = {}
        self.channel: None | str = None
        self.system_info = {}

    async def esp32_readline(self) -> bytes:
        raise NotImplementedError()

    async def esp32_write(self, data: bytes):
        raise NotImplementedError()

    async def on_open(self):

        self.add_task(asyncio.create_task(self.task_receive_line()))
        self.add_task(asyncio.create_task(self.task_heartbeat()))
        self.serial_number = (
            await self.send_command("state_get", {"key": "serial_number"})
        )["result"]["value"]
        self.system_info["serial_number"] = self.serial_number

        try:
            self.system_info["device_name"] = (
                await self.send_command("nvs_get", {"key": "device_name"})
            )["result"]["value"]
        except:
            traceback.print_exc()
        try:
            system_info = (await self.send_command("system_info_get"))["result"]
            self.system_info["project_name"] = system_info["project_name"]
            dt = datetime.strptime(system_info["compile_time"], "%b %d %Y %H:%M:%S")
            self.system_info["compile_time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            traceback.print_exc()
        if self.channel is not None:
            self.system_info["channel"] = self.channel

    async def on_close(self):
        while self.pending_commands:
            _, future = self.pending_commands.popitem()
            future.cancel()

    async def task_receive_line(self):
        while True:
            next_line = await self.esp32_readline()

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
                pending_command.set_result(json_dict)
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
            request_id = str(uuid.uuid4())
            command = {
                "name": name,
                "parameters": params if params else {},
                "request_id": request_id,
            }
            command_str = json.dumps(command, separators=(",", ":"))
            response_future = asyncio.Future[dict]()
            self.pending_commands[request_id] = response_future
            if print_log:
                print(f"esp32 > {command_str}")

            command_bytes = command_str.encode()
            command_bytes += (
                zlib.crc32(command_bytes)
                .to_bytes(length=4, byteorder="little", signed=False)
                .hex()
                .upper()
                .encode()
            )
            command_bytes += b"\n"
            start_time_ns = time.perf_counter_ns()
            await self.esp32_write(command_bytes)
            try:
                response = await asyncio.wait_for(response_future, self.timeout_s)
            except TimeoutError as e:
                raise TimeoutError("ESP32 command response timeout") from e
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
