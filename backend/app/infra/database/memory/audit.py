"""Read-only audit event persistence contract and local implementation."""

from typing import Protocol

from app.infra.database.memory.transaction import MemoryUnitOfWork
from app.infra.database.records import AuditEventRecord as AuditEventRecord
from app.infra.logger.common import traced


class AuditRepository(Protocol):
    @traced
    async def append(self, event: AuditEventRecord) -> AuditEventRecord: ...

    @traced
    async def list(self) -> tuple[AuditEventRecord, ...]: ...


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._events: list[AuditEventRecord] = []
        self._lock = MemoryUnitOfWork()
        self._lock.register(self)

    @traced
    async def append(self, event: AuditEventRecord) -> AuditEventRecord:
        async with self._lock:
            self._events.append(event)
        return event

    @traced
    async def list(self) -> tuple[AuditEventRecord, ...]:
        async with self._lock:
            return tuple(self._events)
