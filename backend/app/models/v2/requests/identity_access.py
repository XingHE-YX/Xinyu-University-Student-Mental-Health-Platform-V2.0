from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IdentityField = Literal["student_name", "student_number"]

IdentityAccessState = Literal["pending", "approved", "denied", "expired", "revoked"]


class IdentityAccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_reference_id: str = Field(min_length=1, max_length=128)
    requested_fields: list[IdentityField] = Field(min_length=1, max_length=2)
    reason_fact: str = Field(min_length=1, max_length=500)
