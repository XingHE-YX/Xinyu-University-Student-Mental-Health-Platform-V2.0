from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    NonEmptyString,
)


class IdempotencyRecordDocument(DocumentModel):
    actor_type: Literal["student", "admin"]
    actor_id: NonEmptyString
    route_key: NonEmptyString
    idempotency_key: NonEmptyString
    request_hash: NonEmptyString
    outcome: Literal["processing", "success", "failure"]
    response_digest: str | None = None
    expires_at: datetime
