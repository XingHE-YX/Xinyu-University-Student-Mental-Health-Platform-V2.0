from __future__ import annotations

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


class AbandonAssessmentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int


class AssessmentResultDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_version: int


class SafetyConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["can_be_safe", "uncertain", "cannot_be_safe"]
    answers: list[AssessmentAnswerSubmission]
    object_version: int


class SupportResourceAckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_context: Literal["safety"]
    resource_version: str
    object_version: int
