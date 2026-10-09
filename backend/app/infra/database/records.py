"""Persistence value types shared by asynchronous adapters."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

SubjectType = Literal["student", "admin"]

SessionStatus = Literal["active", "revoked"]


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    session_id: str
    subject_type: SubjectType
    subject_id: str
    capability: str | None
    access_token_hash: str
    refresh_token_hash: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1
    credential_version: str | None = None


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
