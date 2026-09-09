import asyncio
import json
import traceback
from contextlib import AsyncExitStack

import websockets

from .types import Async


class Connection:

    def __init__(self):
        self.has_opened = False

    async def open(self):
        if self.has_opened:
            raise Exception(f"Connection can't be opened twice")
        self.has_opened = True
        self.url = "ws://localhost:8000/api/ws"
        self.context = AsyncExitStack()
        self.ws = await self.context.enter_async_context(websockets.connect(self.url))
        print(f"Connection to {self.url} open")
        self.message_listeners = set[Async[dict, None]]()

        self.tasks = set[asyncio.Task]()
        self.tasks.add(asyncio.create_task(self.task_receive()))

    async def close(self):
        print(f"Connection to {self.url} closed")
        for task in self.tasks:
            task.cancel()
        await self.context.aclose()

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

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
