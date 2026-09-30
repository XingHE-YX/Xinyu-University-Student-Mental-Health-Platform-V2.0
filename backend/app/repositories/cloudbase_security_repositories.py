"""Persistent session, idempotency and audit records for the Python backend."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, fields, replace
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.repositories.audit_repository import AuditEventRecord
from app.repositories.cloudbase_store import CloudBaseStore
from app.repositories.idempotency_repository import (
    IdempotencyOutcome,
    IdempotencyRecord,
    InMemoryIdempotencyRepository,
)
from app.repositories.protocols import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import AuthSessionRecord, InMemorySessionRepository
from app.schemas.errors import ApiException


def parse_record[R: (AuthSessionRecord, IdempotencyRecord, AuditEventRecord)](
    model: type[R], data: dict[str, Any]
) -> R:
    try:
        return TypeAdapter(model).validate_python({f.name: data[f.name] for f in fields(model)})
    except KeyError, ValidationError:
        raise RepositoryUnavailable("stored security record is invalid") from None


class CloudBaseSessionRepository(InMemorySessionRepository):
    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    def save(self, record: AuthSessionRecord) -> None:
        document = asdict(record)
        document.pop("session_id")
        self.store.insert("auth_sessions", {"_id": record.session_id, **document})

    def replace(self, record: AuthSessionRecord) -> None:
        try:
            document = asdict(record)
            document.pop("session_id")
            self.store.replace(
                "auth_sessions", {"_id": record.session_id, **document}, record.version - 1
            )
        except RepositoryVersionConflict:
            # A concurrent refresh/logout consumes or revokes the old token only once.
            raise ApiException(401, "SESSION_EXPIRED") from None

    def _find(self, where: dict[str, Any]) -> AuthSessionRecord | None:
        rows = self.store.query("auth_sessions", where, limit=1)
        return (
            parse_record(AuthSessionRecord, {"session_id": rows[0]["_id"], **rows[0]})
            if rows
            else None
        )

    def get_by_session_id(self, session_id: str) -> AuthSessionRecord | None:
        return self._find({"_id": session_id})

    def get_by_access_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        return self._find({"access_token_hash": token_hash})

    def get_by_refresh_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        return self._find({"refresh_token_hash": token_hash})

    def revoke(self, session_id: str, *, now: datetime) -> AuthSessionRecord | None:
        with self.store.transaction():
            record = self.get_by_session_id(session_id)
            if record is None or record.status == "revoked":
                return record
            revoked = replace(record, status="revoked", updated_at=now, version=record.version + 1)
            self.replace(revoked)
            return revoked


class CloudBaseIdempotencyRepository(InMemoryIdempotencyRepository):
    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    @staticmethod
    def _document_id(actor_type: str, actor_id: str, route_key: str, idempotency_key: str) -> str:
        value = json.dumps([actor_type, actor_id, route_key, idempotency_key])
        return "idem_" + hashlib.sha256(value.encode()).hexdigest()

    def get(
        self, actor_type: str, actor_id: str, route_key: str, idempotency_key: str, *, now: datetime
    ) -> IdempotencyRecord | None:
        document_id = self._document_id(actor_type, actor_id, route_key, idempotency_key)
        try:
            record = parse_record(
                IdempotencyRecord, self.store.get("idempotency_records", document_id)
            )
        except RepositoryNotFound:
            return None
        return record if record.expires_at > now else None

    def reserve(self, record: IdempotencyRecord, *, now: datetime) -> IdempotencyRecord | None:
        document_id = self._document_id(*self._key(record))
        try:
            with self.store.transaction():
                rows = self.store.query("idempotency_records", {"_id": document_id}, limit=1)
                if rows:
                    current = parse_record(IdempotencyRecord, rows[0])
                    if current.expires_at > now:
                        return current
                    updated = replace(record, version=current.version + 1)
                    self.store.replace(
                        "idempotency_records",
                        {"_id": document_id, **asdict(updated)},
                        current.version,
                    )
                else:
                    self.store.insert("idempotency_records", {"_id": document_id, **asdict(record)})
        except RepositoryVersionConflict:
            existing = self.get(*self._key(record), now=now)
            if existing is not None:
                return existing
            raise
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
        with self.store.transaction():
            rows = self.store.query("idempotency_records", {"record_id": record_id}, limit=1)
            if not rows:
                raise RepositoryNotFound("idempotency reservation not found")
            record = parse_record(IdempotencyRecord, rows[0])
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
            self.store.replace(
                "idempotency_records", {"_id": rows[0]["_id"], **asdict(completed)}, record.version
            )
            return completed


class CloudBaseAuditRepository:
    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    def append(self, event: AuditEventRecord) -> AuditEventRecord:
        self.store.insert(
            "audit_events",
            {
                "_id": event.event_id,
                "request_id": event.request_id,
                "environment_id": event.environment_id,
                "actor_type": event.actor_type,
                "actor_id": event.actor_id,
                "actor_capability": event.capability,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "data_scope": [part for part in event.data_scope.split(",") if part],
                "outcome": event.outcome,
                "reason_code": event.reason_code,
                "occurred_at": event.occurred_at,
                "details": event.details,
                "created_at": event.occurred_at,
                "updated_at": event.occurred_at,
                "version": event.version,
            },
        )
        return event

    def list(self) -> tuple[AuditEventRecord, ...]:
        events = [
            AuditEventRecord(
                event_id=str(row["_id"]),
                request_id=str(row["request_id"]),
                environment_id=str(row["environment_id"]),
                actor_type=str(row["actor_type"]),
                actor_id=str(row["actor_id"] or ""),
                capability=(str(row["actor_capability"]) if row.get("actor_capability") else None),
                action=str(row["action"]),
                resource_type=str(row["resource_type"]),
                resource_id=str(row["resource_id"]),
                data_scope=",".join(str(item) for item in row.get("data_scope", [])),
                outcome=str(row["outcome"]),
                reason_code=str(row["reason_code"]) if row.get("reason_code") else None,
                occurred_at=TypeAdapter(datetime).validate_python(row["occurred_at"]),
                details=dict(row.get("details", {})),
                version=int(row.get("version", 1)),
            )
            for row in self.store.all("audit_events")
        ]
        return tuple(sorted(events, key=lambda event: (event.occurred_at, event.event_id)))
