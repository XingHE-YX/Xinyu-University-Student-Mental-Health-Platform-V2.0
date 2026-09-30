"""Task-owned async lock and rollback across all participating memory stores."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from copy import deepcopy
from typing import Any


class MemoryUnitOfWork:
    def __init__(self) -> None:
        self._mutex = asyncio.Lock()
        self._owner: asyncio.Task[Any] | None = None
        self._depth = 0
        self._transaction_depth = 0
        self._participants: list[object] = []

    def register(self, participant: object) -> None:
        if not any(item is participant for item in self._participants):
            self._participants.append(participant)

    async def __aenter__(self) -> None:
        task = asyncio.current_task()
        if task is not self._owner:
            await self._mutex.acquire()
            self._owner = task
        self._depth += 1

    async def __aexit__(self, *args: object) -> None:
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._mutex.release()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        async with self:
            if self._transaction_depth:
                yield
                return
            snapshots = [
                (
                    participant,
                    deepcopy(
                        {key: value for key, value in vars(participant).items() if key != "_lock"}
                    ),
                )
                for participant in self._participants
            ]
            self._transaction_depth += 1
            try:
                yield
            except BaseException:
                for participant, snapshot in snapshots:
                    state = vars(participant)
                    for key in tuple(state):
                        if key != "_lock":
                            del state[key]
                    state.update(snapshot)
                raise
            finally:
                self._transaction_depth -= 1


def share_memory_transaction(primary: object, *participants: object) -> None:
    """Join locally injected stores; CloudBase stores already share native transactions."""
    lock = getattr(primary, "_lock", None)
    if not isinstance(lock, MemoryUnitOfWork):
        return
    for participant in participants:
        if isinstance(getattr(participant, "_lock", None), MemoryUnitOfWork):
            participant._lock = lock  # type: ignore[attr-defined]
            lock.register(participant)
