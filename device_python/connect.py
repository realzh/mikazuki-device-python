import json
import traceback

import websockets

from .flameeye import Flameeye, ADB
from .device import Device
from .dp100.dp100 import DP100
from . import esp32
from .ws2812 import WS2812


async def ws_session():
    async with websockets.connect("ws://localhost:8000/api/ws") as ws:
        print(f"ws : Connected to server")

        async def socket_send(message: dict):
            message_json = json.dumps(message, ensure_ascii=False)
            print(f"ws > {message_json}")
            await ws.send(message_json)

        devices: list[Device] = []

        try:

            await esp32.enumerate_devices()
            for esp32_device in esp32.esp32_devices:
                device_esp32 = esp32.ESP32(
                    socket_send=socket_send,
                    device_id=f"esp32-{esp32_device['serial_number']}",
                    esp32_device=esp32_device,
                )
                devices.append(device_esp32)
                await device_esp32.on_connected()
                for feature in esp32_device["features"]:
                    if feature == "ws2812":
                        device_ws2812 = WS2812(
                            socket_send=socket_send,
                            device_id=f"ws2812-{esp32_device['serial_number']}",
                            esp32_send_command=esp32_device["send_command"],
                            gpio_num=38,
                        )
                        devices.append(device_ws2812)
                        await device_ws2812.on_connected()

            singleton_devices = [DP100, Flameeye, ADB]
            for dev_class in singleton_devices:
                dev = dev_class(
                    socket_send=socket_send,
                    device_id=f'{dev_class.__name__.lower()}-0'
                )
                devices.append(dev)
                await dev.on_connected()


            while True:
                message_json = await ws.recv()
                print(f"ws | {message_json}")
                message = json.loads(message_json)
                for device in devices:
                    await device.on_message(message)
        except Exception as e:
            for device in devices:
                try:
                    await device.on_disconnected()
                except:
                    pass
            raise e


async def connect_to_server():

    try:
        await ws_session()
    except Exception as e:
        stack_trace = traceback.format_exc()

        print(f"WS session error: {e}")
        print(stack_trace)
