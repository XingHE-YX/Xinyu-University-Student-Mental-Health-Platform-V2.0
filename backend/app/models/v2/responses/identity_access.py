from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

IdentityField = Literal["student_name", "student_number"]

IdentityAccessState = Literal["pending", "approved", "denied", "expired", "revoked"]


class IdentityAccessRequestProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    user_reference_id: str
    requested_fields: list[IdentityField]
    reason_fact: str
    state: IdentityAccessState
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    object_version: int


class IdentityAccessIdentityProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    fields: dict[IdentityField, str]
    object_version: int
