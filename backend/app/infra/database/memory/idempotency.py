"""Atomic in-memory idempotency records matching the CloudBase collection shape."""

from dataclasses import replace
from datetime import datetime
from typing import Protocol

from app.infra.database.memory.transaction import MemoryUnitOfWork
from app.infra.database.records import IdempotencyOutcome as IdempotencyOutcome
from app.infra.database.records import IdempotencyRecord as IdempotencyRecord
from app.infra.logger.common import traced


class IdempotencyRepository(Protocol):
    @traced
    async def get(
        self,
        actor_type: str,
        actor_id: str,
        route_key: str,
        idempotency_key: str,
        *,
        now: datetime,
    ) -> IdempotencyRecord | None: ...

    @traced
    async def reserve(
        self, record: IdempotencyRecord, *, now: datetime
    ) -> IdempotencyRecord | None: ...

    @traced
    async def complete(
        self,
        record_id: str,
        *,
        outcome: IdempotencyOutcome,
        response_status: int,
        response_digest: str,
        now: datetime,
    ) -> IdempotencyRecord: ...


class InMemoryIdempotencyRepository:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], IdempotencyRecord] = {}
        self._lock = MemoryUnitOfWork()
        self._lock.register(self)

    @staticmethod
    @traced
    def _key(record: IdempotencyRecord) -> tuple[str, str, str, str]:
        return record.actor_type, record.actor_id, record.route_key, record.idempotency_key

    @traced
    async def get(
        self,
        actor_type: str,
        actor_id: str,
        route_key: str,
        idempotency_key: str,
        *,
        now: datetime,
    ) -> IdempotencyRecord | None:
        async with self._lock:
            record = self._records.get((actor_type, actor_id, route_key, idempotency_key))
            if record is not None and record.expires_at <= now:
                self._records.pop((actor_type, actor_id, route_key, idempotency_key), None)
                return None
            return record

    @traced
    async def reserve(
        self, record: IdempotencyRecord, *, now: datetime
    ) -> IdempotencyRecord | None:
        async with self._lock:
            key = self._key(record)
            existing = self._records.get(key)
            if existing is not None and existing.expires_at > now:
                return existing
            self._records[key] = record
            return None

    @traced
    async def complete(
        self,
        record_id: str,
        *,
        outcome: IdempotencyOutcome,
        response_status: int,
        response_digest: str,
        now: datetime,
    ) -> IdempotencyRecord:
        async with self._lock:
            for key, record in self._records.items():
                if record.record_id == record_id:
                    if record.outcome != "processing":
                        return record
                    completed = replace(
                        record,
                        outcome=outcome,
                        response_status=response_status,
                        response_digest=response_digest,
                        updated_at=now,
                        version=record.version + 1,
                    )
                    self._records[key] = completed
                    return completed
        raise KeyError(record_id)
