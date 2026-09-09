import asyncio
import traceback
from contextlib import AsyncExitStack, asynccontextmanager

from websockets import ConnectionClosed

from device_python.connection import Connection
from device_python.device import Device
from device_python.esp32 import create_esp32_ws_devices

from .device import Device
from .dp100.dp100 import DP100
from .flameeye import ADB, Flameeye


async def create_singleton_devices(ws_connection: Connection):
    devices = []
    singleton_device_classes: list[type[Device]] = [DP100, Flameeye, ADB]
    for SignletonDevice in singleton_device_classes:
        device = await ws_connection.context.enter_async_context(
            SignletonDevice(
                ws_connection=ws_connection,
                device_id=f"{SignletonDevice.__name__.lower()}-0",
            )
        )
        devices.append(device)


async def connect_to_server():
    while True:
        try:
            async with AsyncExitStack() as stack:
                connection = await stack.enter_async_context(Connection())
                await create_esp32_ws_devices(connection)
                await create_singleton_devices(connection)
                await asyncio.gather(*connection.tasks)

        except ConnectionClosed:
            pass
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(1)
