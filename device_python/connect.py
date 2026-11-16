import asyncio
import traceback

from websockets import ConnectionClosed

from device_python.mac_hub_ws_device import MacHubWSDevice
from device_python.ws_connection import WSConnection


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
