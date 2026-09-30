from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    FixedVersionOne,
    NonEmptyString,
)


class AuditEventDocument(DocumentModel):
    version: FixedVersionOne = 1
    request_id: NonEmptyString
    environment_id: NonEmptyString
    actor_type: Literal["student", "admin", "system"]
    actor_id: str | None = None
    actor_capability: str | None = None
    action: NonEmptyString
    resource_type: Literal[
        "user", "mood", "assessment", "post", "task", "identity", "config", "demo"
    ]
    resource_id: NonEmptyString
    data_scope: list[NonEmptyString]
    outcome: Literal["success", "denied", "conflict", "failure"]
    reason_code: str | None = None
    occurred_at: datetime
