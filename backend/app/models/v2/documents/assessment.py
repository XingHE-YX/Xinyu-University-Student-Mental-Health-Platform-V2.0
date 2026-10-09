from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import (
    DocumentModel,
    NonEmptyString,
)


class AssessmentModuleDocument(DocumentModel):
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    title: NonEmptyString
    description: NonEmptyString
    expected_minutes: Annotated[int, Field(ge=1)]
    current_questionnaire_version: NonEmptyString
    enabled: bool


class QuestionOptionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_key: NonEmptyString
    label: NonEmptyString
    score: int


class QuestionnaireQuestionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_key: NonEmptyString
    order: Annotated[int, Field(ge=1)]
    text: NonEmptyString
    options: list[QuestionOptionModel]
    observation_code: str | None = None


class AssessmentQuestionnaireDocument(DocumentModel):
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    questionnaire_version: NonEmptyString
    questions: list[QuestionnaireQuestionModel]
    score_rule: dict[str, Any]
    non_diagnostic_copy_version: NonEmptyString
    enabled: bool
    published_at: datetime | None = None


class AssessmentAnswerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_key: NonEmptyString
    option_key: NonEmptyString
    score_snapshot: int


class AssessmentSessionDocument(DocumentModel):
    user_id: NonEmptyString
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    questionnaire_version: NonEmptyString
    state: Literal["in_progress", "completed", "abandoned", "expired"]
    answers: list[AssessmentAnswerModel] | None = None
    answered_count: int | None = None
    safety_triggered: bool
    safety_confirmation_state: Literal["can_be_safe", "uncertain", "cannot_be_safe"] | None = None
    safety_resource_version: str | None = None
    safety_resource_acknowledged_at: datetime | None = None
    client_idempotency_key: NonEmptyString
    started_at: datetime
    completed_at: datetime | None = None
    abandoned_at: datetime | None = None
    expires_at: datetime

    @model_validator(mode="after")
    def validate_state_payload(self) -> AssessmentSessionDocument:
        if self.state == "completed":
            if self.safety_triggered and self.safety_confirmation_state == "uncertain":
                if self.answers is not None or self.answered_count is None:
                    raise ValueError(
                        "uncertain safety support sessions persist answered_count but not answers"
                    )
            else:
                if self.answers is None or self.answered_count is None:
                    raise ValueError(
                        "completed sessions must include final answers and answered_count"
                    )
                if self.answered_count != len(self.answers):
                    raise ValueError("answered_count must match the number of final answers")
            if self.completed_at is None:
                raise ValueError("completed sessions must include completed_at")
            if self.abandoned_at is not None:
                raise ValueError("completed sessions cannot include abandoned_at")
            return self

        if self.state == "in_progress":
            if self.completed_at is not None or self.abandoned_at is not None:
                raise ValueError("in_progress sessions cannot include completed_at or abandoned_at")
        elif self.state == "abandoned":
            if self.abandoned_at is None:
                raise ValueError("abandoned sessions must include abandoned_at")
            if self.completed_at is not None:
                raise ValueError("abandoned sessions cannot include completed_at")
        elif self.state == "expired":
            if self.completed_at is not None or self.abandoned_at is not None:
                raise ValueError("expired sessions cannot include completed_at or abandoned_at")

        if self.answers is not None or self.answered_count is not None:
            raise ValueError("only completed sessions may persist answers and answered_count")
        return self


class AssessmentResultDocument(DocumentModel):
    session_id: NonEmptyString
    user_id: NonEmptyString
    module_code: Literal["phq9", "gad7", "sleep_observation"]
    scoring_rule_version: NonEmptyString
    answers_snapshot: list[AssessmentAnswerModel] | None = None
    fixed_summary: NonEmptyString
    reference_band: str | None = None
    boundary_notice: NonEmptyString
    ai_assist_snapshot_id: str | None = None
    result_state: Literal["ordinary", "higher_score", "safety_support"]
    score: int | None = None
    dimension_summary: dict[str, Any]
    safety_state: Literal["not_triggered", "can_be_safe", "uncertain", "cannot_be_safe"]
    visible_copy_version: NonEmptyString
    deleted_at: datetime | None = None

    @model_validator(mode="after")
    def validate_result_projection(self) -> AssessmentResultDocument:
        if self.safety_state == "cannot_be_safe":
            raise ValueError("cannot_be_safe assessments must not persist any result")

        if self.result_state == "safety_support":
            if self.answers_snapshot is not None:
                raise ValueError("safety_support results cannot persist answers_snapshot")
            if self.score is not None:
                raise ValueError("safety_support results cannot persist score")
            if self.ai_assist_snapshot_id is not None:
                raise ValueError("safety_support results cannot reference ai_assist_snapshot_id")
            if self.reference_band is not None:
                raise ValueError("safety_support results cannot persist reference_band")
            if self.safety_state != "uncertain":
                raise ValueError("safety_support results must use safety_state uncertain")
            return self

        if self.safety_state not in {"not_triggered", "can_be_safe"}:
            raise ValueError(
                "ordinary and higher_score results must use safety_state "
                "not_triggered or can_be_safe"
            )

        if self.answers_snapshot is None:
            raise ValueError("ordinary and higher_score results must include answers_snapshot")

        if self.module_code in {"phq9", "gad7"}:
            if self.score is None:
                raise ValueError("phq9 and gad7 results must include score")
            if self.reference_band is None:
                raise ValueError("phq9 and gad7 results must include reference_band")
        else:
            if self.score is not None:
                raise ValueError("sleep_observation results cannot persist score")
            if self.reference_band is not None:
                raise ValueError("sleep_observation results cannot persist reference_band")
        return self
