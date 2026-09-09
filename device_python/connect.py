import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
import json
import traceback
import typing

import websockets

from .flameeye import Flameeye, ADB
from .device import AsyncSend, Device
from .dp100.dp100 import DP100
from . import esp32
from .ws2812 import WS2812


@asynccontextmanager
async def create_singleton_devices(socket_send: AsyncSend):
    async with AsyncExitStack() as stack:
        devices = []
        singleton_device_classes: list[typing.Type[Device]] = [DP100, Flameeye, ADB]
        for SignletonDevice in singleton_device_classes:
            device = await stack.enter_async_context(
                SignletonDevice(
                    socket_send=socket_send,
                    device_id=f"{SignletonDevice.__name__.lower()}-0",
                )
            )
            devices.append(device)
        yield devices


async def ws_session():
    async with AsyncExitStack() as stack:

        ws = await stack.enter_async_context(
            websockets.connect("ws://localhost:8000/api/ws")
        )

        print(f"ws : Connected {ws}")

        async def socket_send(message: dict):
            message_json = json.dumps(message, ensure_ascii=False)
            print(f"ws > {message_json}")
            await ws.send(message_json)

        devices: list[Device] = []

        devices.extend(
            await stack.enter_async_context(esp32.create_esp32_ws_devices(socket_send))
        )
        devices.extend(
            await stack.enter_async_context(create_singleton_devices(socket_send))
        )

        while True:
            message_json = await ws.recv()
            print(f"ws | {message_json}")
            try:
                message = json.loads(message_json)
                assert isinstance(message, dict)
                for device in devices:
                    try:
                        await device.on_message(message)
                    except Exception:
                        traceback.print_exc()
            except Exception:
                traceback.print_exc()


async def connect_to_server():
    while True:
        try:
            await ws_session()
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(1)