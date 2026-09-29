"""Assessment request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StartAssessmentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Literal["phq9", "gad7", "sleep_observation"]
    client_start_key: str


class AssessmentAnswerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_key: str
    option_key: str


class CompleteAssessmentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[AssessmentAnswerSubmission]
    object_version: int


class PublicQuestionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_key: str
    label: str


class PublicQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_key: str
    order: int
    text: str
    options: list[PublicQuestionOption]


class StartAssessmentSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    questionnaire_version: str
    questions: list[PublicQuestion]
    state: Literal["in_progress"]
    expires_at: datetime
    object_version: int


class AssessmentModuleProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Literal["phq9", "gad7", "sleep_observation"]
    title: str
    description: str
    expected_minutes: int
    current_questionnaire_version: str
    enabled: bool
    latest_completed_date: str | None = None
    latest_completed_text: str = "尚未记录"


class AssessmentModuleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modules: list[AssessmentModuleProjection]


class AssessmentSessionStateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    state: Literal["in_progress", "completed", "abandoned", "expired"]
    object_version: int
    abandoned_at: datetime | None = None


class AbandonAssessmentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int


class AssessmentResultDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int


class AssessmentResultProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    session_id: str
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    result_state: Literal["ordinary", "higher_score", "safety_support"]
    score: int | None = None
    fixed_summary: str
    reference_band: str | None = None
    boundary_notice: str
    dimension_summary: dict[str, object]
    safety_state: Literal["not_triggered", "can_be_safe", "uncertain"]
    visible_copy_version: str
    created_at: datetime
    updated_at: datetime
    object_version: int


class AssessmentResultListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AssessmentResultProjection]
    next_cursor: str | None = None


class AssessmentResultDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_id: str
    deleted_at: datetime
    object_version: int


class CompleteAssessmentSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completion_state: Literal[
        "result_ready", "safety_confirmation_required", "safety_support_blocked"
    ]
    session_id: str
    result_id: str | None
    safety_triggered: bool
    score: int | None = None
    result_state: Literal["ordinary", "higher_score", "safety_support"] | None = None


class SafetyConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["can_be_safe", "uncertain", "cannot_be_safe"]
    answers: list[AssessmentAnswerSubmission]
    object_version: int


class SafetyConfirmationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_step: Literal["continue_assessment", "show_support_resources", "support_only"]
    result_id: None = None
    support_required: bool
    task_created: bool
    visible_projection: dict[str, object]
    version: int


class SupportResourceAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_context: Literal["safety"]
    resource_version: str
    object_version: int


class SupportResourceAckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_version: str
    acknowledged_at: datetime
    version: int
