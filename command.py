import asyncio
from typing import Dict

from serial import Serial
import serial.tools.list_ports


devices = [
    {
        "id": "desktop-control",
        "serial_number": "10:20:BA:C3:A6:3C",
    },
    {
        "id": "spectrum-test",
        "serial_number": "10:20:BA:C3:B1:A0",
    },
]

ports: Dict[str, Serial] = {}

for p in serial.tools.list_ports.comports():
    for dev in devices:
        if p.serial_number == dev["serial_number"]:
            ports[dev["id"]] = Serial(p.device)
            print(
                f"已连接到设备 {dev['id']}, serial_number: {dev['serial_number']}, 串口号: {p.device}"
            )
            break


def sync_send_command(id: str, command: str) -> str:
    port = ports.get(id)
    assert port is not None, f"未找到设备 {id} 的串口连接"
    port.write(command.encode("utf-8") + b"\n")
    while True:
        line = port.readline().decode().strip()
        if not line.startswith("rsp| "):
            continue
        rsp = line[5:]
        # print(f"result {rsp}")
        return rsp


command_queues = {}
for dev in devices:
    command_queues[dev["id"]] = asyncio.Queue()


task_send_command_running = False


async def task_send_command(esp32c3_id: str):
    while True:
        cmd = await command_queues[esp32c3_id].get()
        # print(f"from queue {cmd}")
        result = await asyncio.to_thread(sync_send_command, esp32c3_id, cmd["command"])
        cmd["future"].set_result(result)


async def send_command(esp32c3_id: str, command: str) -> str:
    # print("send_command", command)
    global task_send_command_running
    if not task_send_command_running:
        for dev in devices:
            asyncio.create_task(task_send_command(dev["id"]))
        task_send_command_running = True
    future = asyncio.Future[str]()
    await command_queues[esp32c3_id].put({"command": command, "future": future})
    return await future


async def assert_connection(id: str):
    assert (await send_command(id, "test_connection")).startswith("OK: Connected")
