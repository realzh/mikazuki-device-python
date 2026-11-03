from asyncio import Task
from collections.abc import Callable
from typing import Coroutine

type Async[P, T] = Callable[[P], Coroutine[T, None, None]]
