from typing import Awaitable, Callable

AsyncSendCommand = Callable[[str], Awaitable[str]]

import asyncio
import uuid


from serial import Serial
import serial.tools.list_ports

esp32_devices = []


async def task_receive(device: dict):
    while True:
        next_line = await asyncio.to_thread(device["serial"].readline)
        next_line = next_line.decode().strip()
        if next_line.startswith("rsp| "):
            rsp = next_line[5:]
            print(f"esp32 | {rsp}")
            await device["command_receive_queue"].put(rsp)
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
            raise Exception(f"command {command} to {device["esp32_id"]} failed")
        if result.startswith("OK:"):
            result = result[3:].strip()
    return result


async def enumerate_devices():

    for p in serial.tools.list_ports.comports():
        if p.product == "mikatsuki":
            esp32_id = str(uuid.uuid4())
            device = {
                "serial": Serial(p.device),
                "esp32_id": esp32_id,
                "command_send_queue": asyncio.Queue(),
                "command_receive_queue": asyncio.Queue(),
            }
            esp32_devices.append(device)
            device["task_receive"] = asyncio.create_task(task_receive(device))
            device["task_send_command"] = asyncio.create_task(task_send_command(device))

    for dev in esp32_devices:
        serial_number = await send_command(dev, "get_state serial_number")
        dev["serial_number"] = serial_number
        features = await send_command(dev, "get_state features")
        features = features.split(",")
        if len(features) == 1 and features[0] == "":
            features = []
        dev["features"] = features

    print(esp32_devices)


if __name__ == "__main__":
    asyncio.run(enumerate_devices())
