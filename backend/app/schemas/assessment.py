"""Assessment request and response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StartAssessmentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_code: Literal["phq9", "gad7", "sleep_observation"]


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
