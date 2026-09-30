from __future__ import annotations

from datetime import datetime
from typing import Literal

from .common import (
    DocumentModel,
    NonEmptyString,
)


class TreeholePostDocument(DocumentModel):
    author_user_id: NonEmptyString
    anonymous_identity_id: NonEmptyString
    display_name_snapshot: NonEmptyString
    body_original_ciphertext: str | None = None
    body_sanitized: str | None = None
    body_hash: NonEmptyString
    visibility_state: Literal[
        "checking",
        "published",
        "protected",
        "pending_confirmation",
        "unpublished",
        "safety_priority",
        "deleted",
    ]
    review_state: Literal["not_started", "automated_checked", "human_required", "decided"]
    safety_state: Literal["not_triggered", "needs_support_review", "handled"]
    ai_assist_snapshot_id: str | None = None
    community_consent_version: NonEmptyString
    original_retention_deadline: datetime | None = None
    deleted_at: datetime | None = None


class TreeholeResponseDocument(DocumentModel):
    post_id: NonEmptyString
    author_user_id: NonEmptyString
    anonymous_identity_id: NonEmptyString
    display_name_snapshot: NonEmptyString
    body_original_ciphertext: str | None = None
    body_sanitized: str | None = None
    state: Literal["checking", "published", "unpublished", "deleted"]
    ai_assist_snapshot_id: str | None = None
    community_consent_version: NonEmptyString
    deleted_at: datetime | None = None
