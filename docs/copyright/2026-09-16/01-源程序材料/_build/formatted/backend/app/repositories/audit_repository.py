"""Read-only audit event persistence contract and local implementation."""

from dataclasses import dataclass
from datetime import datetime
from threading import RLock
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    event_id: str
    request_id: str
    environment_id: str
    actor_type: str
    actor_id: str
    capability: str | None
    action: str
    resource_type: str
    resource_id: str
    data_scope: str
    outcome: str
    reason_code: str | None
    occurred_at: datetime
    details: dict[str, Any]
    version: int = 1


class AuditRepository(Protocol):
    def append(self, event: AuditEventRecord) -> AuditEventRecord: ...

    def list(self) -> tuple[AuditEventRecord, ...]: ...


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._events: list[AuditEventRecord] = []
        self._lock = RLock()

    def append(self, event: AuditEventRecord) -> AuditEventRecord:
        with self._lock:
            self._events.append(event)
        return event

    def list(self) -> tuple[AuditEventRecord, ...]:
        with self._lock:
            return tuple(self._events)
