from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_version: str = Field(min_length=1, max_length=64)
    action: Literal["accepted", "withdrawn"] = "accepted"
    object_version: int | None = Field(default=None, ge=1)


class IdentityVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_name: str = Field(min_length=1, max_length=128)
    student_number: str = Field(min_length=1, max_length=128)
    client_request_key: str = Field(min_length=1, max_length=128)
    object_version: int | None = Field(default=None, ge=1)


class IdentityVerificationProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    status: Literal["not_started", "pending", "verified", "failed", "unavailable"]
    next_poll_after_seconds: int | None = None


class AnonymousIdentityProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anonymous_identity_id: str
    display_name: str
    display_scope: Literal["treehole_only"]
    generation_version: str
    status: Literal["active", "retired"]


class ConsentProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["required", "accepted", "withdrawn"]
    version: str | None = None


class BootstrapProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_status: Literal["active", "recovery_pending", "stopped", "purged"]
    object_version: int
    base_consent: ConsentProjection
    community_consent: ConsentProjection
    identity_status: Literal["unverified", "pending", "verified"]
    anonymous_identity_summary: AnonymousIdentityProjection | None
    today_summary: object | None
    module_summaries: list[dict[str, object]]
    feature_flags: dict[str, bool]


class MoodRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    mood_code: Literal["pleasant", "calm", "tired", "anxious", "low", "irritable"]
    object_version: int = Field(ge=1)


class ObjectVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int = Field(ge=1)


class AccountActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation_text: str | None = Field(default=None, min_length=1, max_length=64)
    object_version: int = Field(ge=1)


class AccountState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "recovery_pending", "stopped", "purged"]
    recovery_deadline_at: datetime | None
    can_recover: bool
    object_version: int
    available_features: list[str]
