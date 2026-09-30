from __future__ import annotations

from typing import Any, Literal

from .common import (
    DocumentModel,
    NonEmptyString,
)


class AIAssistSnapshotDocument(DocumentModel):
    task_type: Literal["assessment_explanation", "treehole_review_assist"]
    resource_type: Literal["assessment_result", "treehole_post", "treehole_response"]
    resource_id: NonEmptyString
    owner_user_id: str | None = None
    input_digest: NonEmptyString
    request_model: Literal["deepseek-v4-flash"]
    resolved_model_version: NonEmptyString
    prompt_version: NonEmptyString
    output_status: Literal["adopted", "fallback", "rejected"]
    output_projection: dict[str, Any] | None = None
    adopted_copy: str | None = None
