"""Typed document models for the fixed backend collections."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NonEmptyString = Annotated[str, Field(min_length=1)]
VersionInt = Annotated[int, Field(ge=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
LocalDateString = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]


class DocumentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    document_id: NonEmptyString = Field(alias="_id")
    created_at: datetime
    updated_at: datetime
    version: VersionInt


class ConsentEventDocument(DocumentModel):
    user_id: NonEmptyString
    consent_kind: Literal["base_service", "community_content"]
    action: Literal["accepted", "withdrawn"]
    document_version: NonEmptyString
    source: Literal["mini_program", "admin_seed", "migration"]
    occurred_at: datetime
    request_id: NonEmptyString


class UserAccountDocument(DocumentModel):
    auth_subject_hash: NonEmptyString
    status: Literal["active", "recovery_pending", "stopped", "purged"]
    base_consent_status: Literal["accepted", "not_accepted"]
    base_consent_version: str | None = None
    base_consent_at: datetime | None = None
    community_consent_status: Literal["accepted", "withdrawn", "not_accepted"]
    community_consent_version: str | None = None
    community_consent_at: datetime | None = None
    identity_record_id: str | None = None
    anonymous_identity_id: str | None = None
    stop_requested_at: datetime | None = None
    recovery_deadline_at: datetime | None = None
    purged_at: datetime | None = None


class AuthSessionDocument(DocumentModel):
    subject_type: Literal["student", "admin"]
    subject_id: NonEmptyString
    access_token_hash: NonEmptyString
    refresh_token_hash: str | None = None
    status: Literal["active", "revoked", "expired"]
    access_expires_at: datetime
    refresh_expires_at: datetime | None = None
    last_seen_at: datetime
    device_hash: str | None = None


class IdentityRecordDocument(DocumentModel):
    user_id: NonEmptyString
    verification_status: Literal["not_started", "pending", "verified", "failed", "unavailable"]
    student_name_ciphertext: str | None = None
    student_number_ciphertext: str | None = None
    provider_reference_hash: str | None = None
    verified_at: datetime | None = None
    failed_reason_code: str | None = None
    access_version: VersionInt


class AnonymousIdentityDocument(DocumentModel):
    user_id: NonEmptyString
    display_name: NonEmptyString
    generation_version: NonEmptyString
    status: Literal["active", "retired"]


class DailyMoodRecordDocument(DocumentModel):
    user_id: NonEmptyString
    record_date: LocalDateString
    mood_code: NonEmptyString
    source: Literal["mini_program"]
    deleted_at: datetime | None = None


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


class SupportResourceDocument(DocumentModel):
    environment_scope: Literal["demo", "authorized"]
    category: Literal["trusted_person", "campus", "emergency"]
    title: NonEmptyString
    description: NonEmptyString
    action_type: Literal["call", "copy", "open_url", "text_only"]
    action_target: str | None = None
    availability_text: str | None = None
    source_text: NonEmptyString
    verified_at: datetime
    enabled: bool
    sort_order: NonNegativeInt


class QuoteEntryDocument(DocumentModel):
    quote_text: NonEmptyString
    author_text: NonEmptyString
    work_text: str | None = None
    source_kind: Literal["public_domain", "project_original", "copyright_pending"]
    rights_note: NonEmptyString
    enabled: bool
    display_from: LocalDateString | None = None
    display_until: LocalDateString | None = None
    sort_order: NonNegativeInt
    library_version: NonEmptyString

    @model_validator(mode="after")
    def validate_enabled_rights(self) -> QuoteEntryDocument:
        if self.enabled and self.source_kind == "copyright_pending":
            raise ValueError("copyright pending quotes cannot be enabled")
        return self


class TreeholePostDocument(DocumentModel):
    author_user_id: NonEmptyString
    anonymous_identity_id: NonEmptyString
    display_name_snapshot: NonEmptyString
    body_original_ciphertext: str | None = None
    body_sanitized: str | None = None
    body_hash: NonEmptyString
    visibility_state: Literal[
        "checking",
        "published",
        "protected",
        "pending_confirmation",
        "unpublished",
        "safety_priority",
        "deleted",
    ]
    review_state: Literal["not_started", "automated_checked", "human_required", "decided"]
    safety_state: Literal["not_triggered", "needs_support_review", "handled"]
    community_consent_version: NonEmptyString
    original_retention_deadline: datetime | None = None
    deleted_at: datetime | None = None


class TreeholeResponseDocument(DocumentModel):
    post_id: NonEmptyString
    author_user_id: NonEmptyString
    anonymous_identity_id: NonEmptyString
    display_name_snapshot: NonEmptyString
    body_original_ciphertext: str | None = None
    body_sanitized: str | None = None
    state: Literal["checking", "published", "unpublished", "deleted"]
    community_consent_version: NonEmptyString
    deleted_at: datetime | None = None


class WorkTaskDocument(DocumentModel):
    task_kind: Literal["content_review", "safety_support", "identity_access", "followup"]
    source_type: Literal[
        "post", "response", "assessment_result", "identity_request", "support_task"
    ]
    source_id: NonEmptyString
    available_capability: Literal["content_review", "safety_support", "identity_access", "followup"]
    state: Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]
    assigned_admin_id: str | None = None
    safe_summary: NonEmptyString
    object_version: VersionInt
    last_action: str | None = None


class ContentReviewTaskDocument(DocumentModel):
    task_kind: Literal["content_review"]
    post_id: NonEmptyString
    response_id: str | None = None
    state: Literal["needs_action", "claimed", "waiting_other", "completed", "cancelled"]
    assigned_admin_id: str | None = None
    object_version_snapshot: VersionInt
    decision: Literal["publish", "protect", "unpublish", "safety_review"] | None = None
    internal_reason: str | None = None
    automated_check_summary: dict[str, Any] | None = None
    completed_at: datetime | None = None


class SupportResourceSnapshotModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_id: NonEmptyString
    title: NonEmptyString
    category: Literal["trusted_person", "campus", "emergency"]
    action_type: Literal["call", "copy", "open_url", "text_only"]
    action_target: str | None = None


class SafetySupportTaskDocument(DocumentModel):
    task_kind: Literal["safety_support"]
    user_reference_id: NonEmptyString
    source_result_id: NonEmptyString
    safety_fact: Literal["uncertain", "cannot_be_safe"]
    support_resource_snapshot: list[SupportResourceSnapshotModel]
    state: Literal["needs_action", "claimed", "waiting_other", "completed"]
    assigned_admin_id: str | None = None
    followup_due_at: datetime | None = None
    fact_note: str | None = None
    completed_at: datetime | None = None


class IdentityAccessRequestDocument(DocumentModel):
    task_kind: Literal["identity_access"]
    user_reference_id: NonEmptyString
    requester_admin_id: NonEmptyString
    requested_fields: list[Literal["student_name", "student_number"]]
    reason_fact: NonEmptyString
    state: Literal["pending", "approved", "denied", "expired", "revoked"]
    decided_admin_id: str | None = None
    decision_reason: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class FollowupRecordDocument(DocumentModel):
    task_id: NonEmptyString
    actor_admin_id: NonEmptyString
    action_code: Literal[
        "resource_provided",
        "contact_made",
        "contact_failed",
        "next_contact_agreed",
    ]
    fact_note: NonEmptyString
    next_due_at: datetime | None = None


class AdminAccountDocument(DocumentModel):
    login_name: NonEmptyString
    display_name: NonEmptyString
    capability_label: NonEmptyString
    status: Literal["active", "disabled"]
    password_hash_reference: NonEmptyString
    last_login_at: datetime | None = None


class AuditEventDocument(DocumentModel):
    request_id: NonEmptyString
    environment_id: NonEmptyString
    actor_type: Literal["student", "admin", "system"]
    actor_id: str | None = None
    actor_capability: str | None = None
    action: NonEmptyString
    resource_type: Literal[
        "user", "mood", "assessment", "post", "task", "identity", "config", "demo"
    ]
    resource_id: NonEmptyString
    data_scope: list[NonEmptyString]
    outcome: Literal["success", "denied", "conflict", "failure"]
    reason_code: str | None = None
    occurred_at: datetime


class IdempotencyRecordDocument(DocumentModel):
    actor_type: Literal["student", "admin"]
    actor_id: NonEmptyString
    route_key: NonEmptyString
    idempotency_key: NonEmptyString
    request_hash: NonEmptyString
    outcome: Literal["processing", "success", "failure"]
    response_digest: str | None = None
    expires_at: datetime


class DemoResetRunDocument(DocumentModel):
    environment_id: NonEmptyString
    requested_by_admin_id: NonEmptyString
    state: Literal["started", "completed", "partial_failure", "failed", "rejected"]
    affected_collections: list[NonEmptyString]
    collection_results: dict[str, Any] | None = None
    request_id: NonEmptyString
    started_at: datetime
    completed_at: datetime | None = None


COLLECTION_MODELS: dict[str, type[DocumentModel]] = {
    "user_accounts": UserAccountDocument,
    "auth_sessions": AuthSessionDocument,
    "identity_records": IdentityRecordDocument,
    "consent_records": ConsentEventDocument,
    "anonymous_identities": AnonymousIdentityDocument,
    "daily_mood_records": DailyMoodRecordDocument,
    "assessment_modules": AssessmentModuleDocument,
    "assessment_questionnaires": AssessmentQuestionnaireDocument,
    "assessment_sessions": AssessmentSessionDocument,
    "assessment_results": AssessmentResultDocument,
    "ai_assist_snapshots": AIAssistSnapshotDocument,
    "support_resources": SupportResourceDocument,
    "quote_entries": QuoteEntryDocument,
    "treehole_posts": TreeholePostDocument,
    "treehole_responses": TreeholeResponseDocument,
    "work_tasks": WorkTaskDocument,
    "content_review_tasks": ContentReviewTaskDocument,
    "safety_support_tasks": SafetySupportTaskDocument,
    "identity_access_requests": IdentityAccessRequestDocument,
    "followup_records": FollowupRecordDocument,
    "admin_accounts": AdminAccountDocument,
    "audit_events": AuditEventDocument,
    "idempotency_records": IdempotencyRecordDocument,
    "demo_reset_runs": DemoResetRunDocument,
}
