import asyncio
import traceback

from websockets import ConnectionClosed

from device_python.mac_hub_ws_device import MacHubWSDevice
from device_python.ws_connection import WSConnection

# from device_python.esp32_ws_device import create_esp32_ws_devices

# async def create_singleton_devices(ws_connection: WSConnection):
#     devices = []
#     singleton_device_classes: list[type[Device]] = [DP100, Flameeye, ADB]
#     for SignletonDevice in singleton_device_classes:
#         device = await ws_connection.context.enter_async_context(
#             SignletonDevice(
#                 ws_connection=ws_connection,
#                 device_id=f"{SignletonDevice.__name__.lower()}-0",
#             )
#         )
#         devices.append(device)


async def connect_to_server():
    while True:
        ws_connection = WSConnection()
        try:
            await ws_connection.open()
            mac_hub = MacHubWSDevice(ws_connection=ws_connection)
            await mac_hub.open()
            await asyncio.gather(*ws_connection.tasks)

        except ConnectionClosed:
            pass
        except Exception:
            traceback.print_exc()
        finally:
            await ws_connection.close()
        await asyncio.sleep(1)
