import asyncio
import traceback
from typing import Self

from device_python.types import Async


class Openable:

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.has_opened = False
        self.has_closed = False
        self.on_close_callbacks: set[Async[Self, None]] = set()
        self.tasks = set[asyncio.Task]()

    async def open(self):
        assert not self.has_opened
        self.has_opened = True
        await self.on_open()

    async def on_open(self):
        pass

    async def close(self):
        assert self.has_opened
        if self.has_closed:
            return
        self.has_closed = True

        while self.tasks:
            task = self.tasks.pop()
            task.cancel()

        while self.on_close_callbacks:
            callback = self.on_close_callbacks.pop()
            try:
                await callback(self)
            except Exception:
                traceback.print_exc()
        await self.on_close()

    async def on_close(self):
        pass

    def add_task(self, task: asyncio.Task):
        self.tasks.add(task)
