"""Request and response models for the desktop admin workbench."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskKind = Literal["content_review", "safety_support", "identity_access", "followup"]
TaskState = Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]
WorkbenchSection = Literal["needs_action", "waiting_other", "recent", "all"]


class TaskFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    value: str


class TaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_kind: TaskKind
    state: TaskState
    created_at: datetime
    updated_at: datetime
    assigned_admin_display: str | None = None
    safe_summary: str
    object_version: int


class WorkbenchPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TaskSummary]
    next_cursor: str | None = None


class TaskDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_kind: TaskKind
    state: TaskState
    object_version: int
    facts: list[TaskFact]
    redacted_content: str | None = None
    allowed_actions: list[str]
    records: list[TaskFact] = Field(default_factory=list)
    environment_kind: Literal["demo", "authorized", "unconfigured"]


class TaskMutationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    new_state: TaskState
    new_object_version: int
    audit_request_id: str


class ObjectVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int = Field(ge=1)


class ContentDecisionRequest(ObjectVersionRequest):
    action: Literal["publish", "protect", "unpublish", "safety_review"]
    internal_reason: str = Field(default="", max_length=500)


class SafetyDecisionRequest(ObjectVersionRequest):
    action: Literal["record_support", "set_followup", "complete"]
    fact_note: str = Field(default="", max_length=500)
    followup_due_at: datetime | None = None


class IdentityDecisionRequest(ObjectVersionRequest):
    action: Literal["approve", "deny", "revoke"]


class FollowupDecisionRequest(ObjectVersionRequest):
    action: Literal["record_followup", "complete"]
    action_code: Literal[
        "resource_provided",
        "contact_made",
        "contact_failed",
        "next_contact_agreed",
    ] = "resource_provided"
    fact_note: str = Field(default="", max_length=500)
    next_due_at: datetime | None = None


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    actor: str
    capability: str
    resource: str
    action: str
    data_scope: list[str]
    outcome: Literal["success", "denied", "conflict", "failure"]
    reason_code: str | None = None
    occurred_at: datetime
    environment_kind: Literal["demo", "authorized", "unconfigured"]


class AuditPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AuditEvent]
    next_cursor: str | None = None


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_text: Literal["确认重置"]
    reset_scope: list[
        Literal["tasks", "posts", "responses", "assessments", "identities", "safety_tasks", "audit"]
    ] = Field(min_length=1)


class ResetCollectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: str
    state: Literal["completed", "failed", "skipped"]
    message: str | None = None


class ResetResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    request_id: str
    collections: list[ResetCollectionResult]
