"""Minimal-fact, append-only audit event writer."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.repositories.audit_repository import (
    AuditEventRecord,
    AuditRepository,
    InMemoryAuditRepository,
)

# Only these facts are safe to keep in the first audit projection. Full answers,
# post bodies and identity values are intentionally absent from the allowlist.
SAFE_DETAIL_KEYS = frozenset(
    {
        "action_code",
        "content_hash",
        "error_category",
        "model_version",
        "next_due_at",
        "object_version",
        "outcome_category",
        "prompt_version",
        "requested_fields",
        "resource_version",
        "status",
        "task_kind",
        "task_type",
        "output_status",
        "fallback_reason",
    }
)


class AuditWriter:
    def __init__(
        self,
        repository: AuditRepository | None = None,
        *,
        environment_id: str = "unconfigured",
    ) -> None:
        self.repository = repository or InMemoryAuditRepository()
        self.environment_id = environment_id

    def write(
        self,
        *,
        request_id: str,
        actor_type: str,
        actor_id: str,
        capability: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        data_scope: str,
        outcome: str,
        reason_code: str | None,
        occurred_at: datetime,
        facts: Mapping[str, Any] | None = None,
    ) -> AuditEventRecord:
        event = AuditEventRecord(
            event_id=f"audit_{uuid4().hex}",
            request_id=request_id,
            environment_id=self.environment_id,
            actor_type=actor_type,
            actor_id=actor_id,
            capability=capability,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            data_scope=data_scope,
            outcome=outcome,
            reason_code=reason_code,
            occurred_at=occurred_at,
            details=_safe_details(facts or {}),
        )
        return self.repository.append(event)


def _safe_details(facts: Mapping[str, Any]) -> dict[str, Any]:
    return {key: _safe_value(value) for key, value in facts.items() if key in SAFE_DETAIL_KEYS}


def _safe_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _safe_value(item) for key, item in value.items() if key in SAFE_DETAIL_KEYS}
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
