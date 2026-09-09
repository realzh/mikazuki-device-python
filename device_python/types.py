from collections.abc import Awaitable, Callable

type Async[P, T] = Callable[[P], Awaitable[T]]
