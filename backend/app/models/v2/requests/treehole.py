from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PostVisibility = Literal[
    "checking",
    "published",
    "protected",
    "pending_confirmation",
    "unpublished",
    "safety_priority",
    "deleted",
]


class TreeholePostRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=1000)
    client_idempotency_key: str = Field(min_length=1, max_length=128)


class TreeholeResponseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=1000)
    object_version: int = Field(ge=1)
    client_idempotency_key: str = Field(min_length=1, max_length=128)


class TreeholeObjectVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int = Field(ge=1)
