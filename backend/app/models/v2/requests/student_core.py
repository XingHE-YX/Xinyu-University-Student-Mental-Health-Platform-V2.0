from __future__ import annotations

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
