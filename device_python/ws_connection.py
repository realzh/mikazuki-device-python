import asyncio
import json
import traceback

import websockets

from device_python.openable import Openable

from .types import Async


class WSConnection(Openable):

    async def open(self):
        await super().open()

        self.url = "ws://localhost:8000/api/ws"
        self.ws = await websockets.connect(self.url)

        print(f"WSConnection to {self.url} open")
        self.message_listeners = set[Async[dict, None]]()

        self.add_task(asyncio.create_task(self.task_receive()))

    async def close(self):
        print(f"WSConnection to {self.url} close")
        await super().close()

    async def send(self, message: dict):
        message_json = json.dumps(message, ensure_ascii=False)
        print(f"ws > {message_json}")
        await self.ws.send(message_json)

    async def task_receive(self):
        while True:
            message_json = await self.ws.recv()
            print(f"ws | {message_json}")
            try:
                message = json.loads(message_json)
                assert isinstance(message, dict)
            except:
                traceback.print_exc()
                continue

            for listener in list(self.message_listeners):
                try:
                    await listener(message)
                except websockets.ConnectionClosed:
                    raise
                except Exception:
                    traceback.print_exc()
