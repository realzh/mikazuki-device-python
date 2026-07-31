import asyncio

import serial


port = serial.Serial("/dev/cu.usbmodem1401")


def sync_send_command(command: str) -> str:
    # print(f"sync_send_command {command}")
    port.write(command.encode("utf-8") + b"\n")
    while True:
        line = port.readline().decode().strip()
        if not line.startswith("rsp| "):
            continue
        rsp = line[5:]
        # print(f"result {rsp}")
        return rsp


command_queue = asyncio.Queue[dict]()

task_send_command_running = False


async def task_send_command():
    while True:
        cmd = await command_queue.get()
        # print(f"from queue {cmd}")
        result = await asyncio.to_thread(sync_send_command, cmd["command"])
        cmd["future"].set_result(result)


async def send_command(command: str) -> str:
    # print("send_command", command)
    global task_send_command_running
    if not task_send_command_running:
        asyncio.create_task(task_send_command())
        task_send_command_running = True
    future = asyncio.Future[str]()
    await command_queue.put({"command": command, "future": future})
    return await future


async def assert_connection():
    assert (await send_command("test_connection")).startswith("OK: Connected")
