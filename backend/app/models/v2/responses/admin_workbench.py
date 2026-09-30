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
