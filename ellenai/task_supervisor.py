from __future__ import annotations

import asyncio
from typing import Any, Awaitable


class TaskSupervisor:
    """Track background tasks so shutdown can wait for in-flight work."""

    def __init__(self) -> None:
        self._active_tasks: set[asyncio.Task[Any]] = set()

    def spawn(self, coro: Awaitable[Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)
        return task

    async def shutdown_wait(self) -> int:
        if not self._active_tasks:
            return 0
        pending = list(self._active_tasks)
        await asyncio.gather(*pending, return_exceptions=True)
        return len(pending)

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)
