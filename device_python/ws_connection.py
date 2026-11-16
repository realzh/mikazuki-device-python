import asyncio
import json
import websockets

from device_python.openable import Openable
from device_python import log

from .types import Async

logger = log.get_logger("ws_connection")


class WSConnection(Openable):

    async def open(self):
        await super().open()

        self.url = "ws://localhost:8000/api/ws"
        self.ws = await websockets.connect(self.url)

        logger.info(f"WSConnection open", url=self.url)
        self.message_listeners = set[Async[dict, None]]()

        self.add_task(asyncio.create_task(self.task_receive()))

    async def close(self):
        logger.info(f"WSConnection close", url=self.url)
        await super().close()

    async def send(self, message: dict):
        logger.debug("send_message", message=message)
        message_json = json.dumps(message, ensure_ascii=False)
        await self.ws.send(message_json)

    async def task_receive(self):
        while True:
            message_json = await self.ws.recv()
            try:
                message = json.loads(message_json)
                assert isinstance(message, dict)
                logger.debug("receive_message", message=message)
            except:
                logger.exception("Invalid message")
                continue

            listener_tasks = [
                asyncio.create_task(x(message)) for x in self.message_listeners
            ]
            await asyncio.gather(*listener_tasks)
