from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from .common import (
    DocumentModel,
    NonEmptyString,
)


class DemoResetRunDocument(DocumentModel):
    environment_id: NonEmptyString
    requested_by_admin_id: NonEmptyString
    state: Literal["started", "completed", "partial_failure", "failed", "rejected"]
    affected_collections: list[NonEmptyString]
    collection_results: dict[str, Any] | None = None
    request_id: NonEmptyString
    started_at: datetime
    completed_at: datetime | None = None
