from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    DocumentModel,
    NonEmptyString,
    VersionInt,
)


class WorkTaskDocument(DocumentModel):
    task_kind: Literal["content_review", "safety_support", "identity_access", "followup"]
    source_type: Literal[
        "post", "response", "assessment_result", "identity_request", "support_task"
    ]
    source_id: NonEmptyString
    available_capability: Literal["content_review", "safety_support", "identity_access", "followup"]
    state: Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]
    assigned_admin_id: str | None = None
    safe_summary: NonEmptyString
    object_version: VersionInt
    last_action: str | None = None
    facts: list[dict[str, str]] = Field(default_factory=list)
    records: list[dict[str, str]] = Field(default_factory=list)
    redacted_content: str | None = None
    is_deleted: bool = False


class ContentReviewTaskDocument(DocumentModel):
    task_kind: Literal["content_review"]
    post_id: NonEmptyString
    response_id: str | None = None
    state: Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]
    assigned_admin_id: str | None = None
    object_version_snapshot: VersionInt
    decision: Literal["publish", "protect", "unpublish", "safety_review"] | None = None
    internal_reason: str | None = None
    automated_check_summary: dict[str, Any] | None = None
    completed_at: datetime | None = None


class SupportResourceSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: NonEmptyString
    title: NonEmptyString
    category: Literal["trusted_person", "campus", "emergency"]
    action_type: Literal["call", "copy", "open_url", "text_only"]
    action_target: str | None = None


class SafetySupportTaskDocument(DocumentModel):
    task_kind: Literal["safety_support"]
    user_reference_id: NonEmptyString
    source_result_id: NonEmptyString | None = None
    source_session_id: NonEmptyString | None = None
    safety_fact: Literal["uncertain", "cannot_be_safe"]
    support_resource_snapshot: list[SupportResourceSnapshotModel]
    state: Literal["needs_action", "claimed", "waiting_other", "completed"]
    assigned_admin_id: str | None = None
    followup_due_at: datetime | None = None
    fact_note: str | None = None
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_source_reference(self) -> SafetySupportTaskDocument:
        has_result = self.source_result_id is not None
        has_session = self.source_session_id is not None
        if has_result == has_session:
            raise ValueError("safety support tasks must reference exactly one source")
        if self.safety_fact == "uncertain" and not has_result:
            raise ValueError("uncertain safety tasks must reference source_result_id")
        if self.safety_fact == "cannot_be_safe" and not has_session:
            raise ValueError("cannot_be_safe safety tasks must reference source_session_id")
        return self


class FollowupRecordDocument(DocumentModel):
    task_id: NonEmptyString
    actor_admin_id: NonEmptyString
    action_code: Literal[
        "resource_provided",
        "contact_made",
        "contact_failed",
        "next_contact_agreed",
    ]
    fact_note: NonEmptyString
    next_due_at: datetime | None = None
