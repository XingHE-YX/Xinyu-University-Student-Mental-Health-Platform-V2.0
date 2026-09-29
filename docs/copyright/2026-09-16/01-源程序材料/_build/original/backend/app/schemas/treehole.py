from __future__ import annotations

from datetime import datetime
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


class TreeholeResponseProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_id: str
    post_id: str
    display_name_snapshot: str | None
    body_sanitized: str | None
    state: Literal["checking", "published", "unpublished", "deleted"]
    created_at: datetime
    updated_at: datetime
    object_version: int


class TreeholePostProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str
    display_name_snapshot: str | None
    body_sanitized: str | None
    visibility_state: PostVisibility
    review_state: Literal["not_started", "automated_checked", "human_required", "decided"]
    safety_state: Literal["not_triggered", "needs_support_review", "handled"] | None
    created_at: datetime
    updated_at: datetime
    response_count: int
    object_version: int
    mine: bool = False
    responses: list[TreeholeResponseProjection] = Field(default_factory=list)


class TreeholePostListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TreeholePostProjection]
    next_cursor: str | None = None


class TreeholeMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    post_id: str
    visibility_state: PostVisibility
    review_state: Literal["not_started", "automated_checked", "human_required", "decided"]
    display_projection: TreeholePostProjection
    object_version: int


class TreeholeDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: str
    deleted_at: datetime
    object_version: int
