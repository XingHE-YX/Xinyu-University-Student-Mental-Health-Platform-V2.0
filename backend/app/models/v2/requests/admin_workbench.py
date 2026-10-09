from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskKind = Literal["content_review", "safety_support", "identity_access", "followup"]

TaskState = Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]

WorkbenchSection = Literal["needs_action", "waiting_other", "recent", "all"]


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


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_text: Literal["确认重置"]
    reset_scope: list[
        Literal["tasks", "posts", "responses", "assessments", "identities", "safety_tasks", "audit"]
    ] = Field(min_length=1)
