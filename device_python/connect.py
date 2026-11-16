import asyncio
import logging


from websockets import ConnectionClosed

from device_python.mac_hub_ws_device import MacHubWSDevice
from device_python.servo_gimbal import ServoGimBalWSDevice
from device_python.ws_connection import WSConnection

from device_python import log

logger = log.get_logger("connect")


async def connect_to_server():
    while True:
        ws_connection = WSConnection()
        try:
            await ws_connection.open()
            mac_hub = MacHubWSDevice(ws_connection=ws_connection)
            await mac_hub.open()
            servo_gimbal = ServoGimBalWSDevice(ws_connection=ws_connection)
            await servo_gimbal.open()
            await asyncio.gather(*ws_connection.tasks)

        except ConnectionClosed as e:
            logger.debug("ws_closed", code=e.code, reason=e.reason)
        except Exception:
            logger.exception("connection_error")
        finally:
            try:
                await ws_connection.close()
            except Exception:
                logger.exception("close_failed")
        await asyncio.sleep(1)
