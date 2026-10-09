from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


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


class AccountState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "recovery_pending", "stopped", "purged"]
    recovery_deadline_at: datetime | None
    can_recover: bool
    object_version: int
    available_features: list[str]
