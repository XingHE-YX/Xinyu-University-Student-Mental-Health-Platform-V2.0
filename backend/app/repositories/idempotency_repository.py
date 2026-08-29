"""Atomic in-memory idempotency records matching the CloudBase collection shape."""

from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock
from typing import Literal, Protocol

IdempotencyOutcome = Literal["processing", "success", "failure"]


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    record_id: str
    actor_type: str
    actor_id: str
    route_key: str
    idempotency_key: str
    request_hash: str
    outcome: IdempotencyOutcome
    response_status: int | None
    response_digest: str | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    version: int = 1


class IdempotencyRepository(Protocol):
    def get(
        self,
        actor_type: str,
        actor_id: str,
        route_key: str,
        idempotency_key: str,
        *,
        now: datetime,
    ) -> IdempotencyRecord | None: ...

    def reserve(self, record: IdempotencyRecord, *, now: datetime) -> IdempotencyRecord | None: ...

    def complete(
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
        self._lock = RLock()

    @staticmethod
    def _key(record: IdempotencyRecord) -> tuple[str, str, str, str]:
        return record.actor_type, record.actor_id, record.route_key, record.idempotency_key

    def get(
        self,
        actor_type: str,
        actor_id: str,
        route_key: str,
        idempotency_key: str,
        *,
        now: datetime,
    ) -> IdempotencyRecord | None:
        with self._lock:
            record = self._records.get((actor_type, actor_id, route_key, idempotency_key))
            if record is not None and record.expires_at <= now:
                self._records.pop((actor_type, actor_id, route_key, idempotency_key), None)
                return None
            return record

    def reserve(self, record: IdempotencyRecord, *, now: datetime) -> IdempotencyRecord | None:
        with self._lock:
            key = self._key(record)
            existing = self._records.get(key)
            if existing is not None and existing.expires_at > now:
                return existing
            self._records[key] = record
            return None

    def complete(
        self,
        record_id: str,
        *,
        outcome: IdempotencyOutcome,
        response_status: int,
        response_digest: str,
        now: datetime,
    ) -> IdempotencyRecord:
        with self._lock:
            for key, record in self._records.items():
                if record.record_id == record_id:
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
