"""Central registry for collection contracts and index definitions."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import COLLECTION_MODELS


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    storage_type: str
    required: bool

    def as_dict(self) -> dict[str, object]:
        return {"storage_type": self.storage_type, "required": self.required}


@dataclass(frozen=True, slots=True)
class IndexSpec:
    fields: tuple[str, ...]
    unique: bool = False

    def as_dict(self, collection: str) -> dict[str, object]:
        suffix = "__unique" if self.unique else ""
        return {
            "name": f"{collection}__{'_'.join(self.fields)}{suffix}",
            "fields": list(self.fields),
            "unique": self.unique,
        }


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    name: str
    fields: tuple[FieldSpec, ...]
    indexes: tuple[IndexSpec, ...]


def field(name: str, storage_type: str, *, required: bool) -> FieldSpec:
    return FieldSpec(name=name, storage_type=storage_type, required=required)


COMMON_FIELDS = (
    field("_id", "string", required=True),
    field("created_at", "datetime", required=True),
    field("updated_at", "datetime", required=True),
    field("version", "integer", required=True),
)


REGISTRY: dict[str, CollectionSpec] = {
    "user_accounts": CollectionSpec(
        name="user_accounts",
        fields=COMMON_FIELDS
        + (
            field("auth_subject_hash", "hash_string", required=True),
            field("status", "string", required=True),
            field("base_consent_status", "string", required=True),
            field("base_consent_version", "string", required=False),
            field("base_consent_at", "datetime", required=False),
            field("community_consent_status", "string", required=True),
            field("community_consent_version", "string", required=False),
            field("community_consent_at", "datetime", required=False),
            field("identity_record_id", "string", required=False),
            field("anonymous_identity_id", "string", required=False),
            field("stop_requested_at", "datetime", required=False),
            field("recovery_deadline_at", "datetime", required=False),
            field("purged_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("auth_subject_hash",), unique=True),
            IndexSpec(("status", "updated_at")),
        ),
    ),
    "auth_sessions": CollectionSpec(
        name="auth_sessions",
        fields=COMMON_FIELDS
        + (
            field("subject_type", "string", required=True),
            field("subject_id", "string", required=True),
            field("access_token_hash", "hash_string", required=True),
            field("refresh_token_hash", "hash_string", required=False),
            field("status", "string", required=True),
            field("access_expires_at", "datetime", required=True),
            field("refresh_expires_at", "datetime", required=False),
            field("last_seen_at", "datetime", required=True),
            field("device_hash", "hash_string", required=False),
        ),
        indexes=(
            IndexSpec(("access_token_hash",), unique=True),
            IndexSpec(("subject_id", "status")),
            IndexSpec(("access_expires_at",)),
        ),
    ),
    "identity_records": CollectionSpec(
        name="identity_records",
        fields=COMMON_FIELDS
        + (
            field("user_id", "string", required=True),
            field("verification_status", "string", required=True),
            field("student_name_ciphertext", "encrypted_string", required=False),
            field("student_number_ciphertext", "encrypted_string", required=False),
            field("provider_reference_hash", "hash_string", required=False),
            field("verified_at", "datetime", required=False),
            field("failed_reason_code", "string", required=False),
            field("access_version", "integer", required=True),
        ),
        indexes=(),
    ),
    "consent_records": CollectionSpec(
        name="consent_records",
        fields=COMMON_FIELDS
        + (
            field("user_id", "string", required=True),
            field("consent_kind", "string", required=True),
            field("action", "string", required=True),
            field("document_version", "string", required=True),
            field("source", "string", required=True),
            field("occurred_at", "datetime", required=True),
            field("request_id", "string", required=True),
        ),
        indexes=(IndexSpec(("user_id", "consent_kind", "occurred_at")),),
    ),
    "anonymous_identities": CollectionSpec(
        name="anonymous_identities",
        fields=COMMON_FIELDS
        + (
            field("user_id", "string", required=True),
            field("display_name", "string", required=True),
            field("generation_version", "string", required=True),
            field("status", "string", required=True),
        ),
        indexes=(),
    ),
    "daily_mood_records": CollectionSpec(
        name="daily_mood_records",
        fields=COMMON_FIELDS
        + (
            field("user_id", "string", required=True),
            field("record_date", "string", required=True),
            field("mood_code", "string", required=True),
            field("source", "string", required=True),
            field("deleted_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("user_id", "record_date"), unique=True),
            IndexSpec(("user_id", "record_date", "deleted_at")),
        ),
    ),
    "assessment_modules": CollectionSpec(
        name="assessment_modules",
        fields=COMMON_FIELDS
        + (
            field("module_code", "string", required=True),
            field("title", "string", required=True),
            field("description", "string", required=True),
            field("expected_minutes", "integer", required=True),
            field("current_questionnaire_version", "string", required=True),
            field("enabled", "boolean", required=True),
        ),
        indexes=(),
    ),
    "assessment_questionnaires": CollectionSpec(
        name="assessment_questionnaires",
        fields=COMMON_FIELDS
        + (
            field("module_code", "string", required=True),
            field("questionnaire_version", "string", required=True),
            field("questions", "array[object]", required=True),
            field("score_rule", "object", required=True),
            field("non_diagnostic_copy_version", "string", required=True),
            field("enabled", "boolean", required=True),
            field("published_at", "datetime", required=False),
        ),
        indexes=(),
    ),
    "assessment_sessions": CollectionSpec(
        name="assessment_sessions",
        fields=COMMON_FIELDS
        + (
            field("user_id", "string", required=True),
            field("module_code", "string", required=True),
            field("questionnaire_version", "string", required=True),
            field("state", "string", required=True),
            field("answers", "array[object]", required=False),
            field("answered_count", "integer", required=False),
            field("safety_triggered", "boolean", required=True),
            field("safety_confirmation_state", "string", required=False),
            field("safety_resource_version", "string", required=False),
            field("safety_resource_acknowledged_at", "datetime", required=False),
            field("client_idempotency_key", "string", required=True),
            field("started_at", "datetime", required=True),
            field("completed_at", "datetime", required=False),
            field("abandoned_at", "datetime", required=False),
            field("expires_at", "datetime", required=True),
        ),
        indexes=(IndexSpec(("user_id", "created_at")), IndexSpec(("user_id", "state"))),
    ),
    "assessment_results": CollectionSpec(
        name="assessment_results",
        fields=COMMON_FIELDS
        + (
            field("session_id", "string", required=True),
            field("user_id", "string", required=True),
            field("module_code", "string", required=True),
            field("scoring_rule_version", "string", required=True),
            field("answers_snapshot", "array[object]", required=False),
            field("fixed_summary", "string", required=True),
            field("reference_band", "string", required=False),
            field("boundary_notice", "string", required=True),
            field("ai_assist_snapshot_id", "string", required=False),
            field("result_state", "string", required=True),
            field("score", "integer", required=False),
            field("dimension_summary", "object", required=True),
            field("safety_state", "string", required=True),
            field("visible_copy_version", "string", required=True),
            field("deleted_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("user_id", "module_code", "created_at")),
            IndexSpec(("session_id",), unique=True),
        ),
    ),
    "ai_assist_snapshots": CollectionSpec(
        name="ai_assist_snapshots",
        fields=COMMON_FIELDS
        + (
            field("task_type", "string", required=True),
            field("resource_type", "string", required=True),
            field("resource_id", "string", required=True),
            field("owner_user_id", "string", required=False),
            field("input_digest", "hash_string", required=True),
            field("request_model", "string", required=True),
            field("resolved_model_version", "string", required=True),
            field("prompt_version", "string", required=True),
            field("output_status", "string", required=True),
            field("output_projection", "object", required=False),
            field("adopted_copy", "string", required=False),
        ),
        indexes=(
            IndexSpec(("resource_type", "resource_id", "created_at")),
            IndexSpec(("owner_user_id", "created_at")),
        ),
    ),
    "support_resources": CollectionSpec(
        name="support_resources",
        fields=COMMON_FIELDS
        + (
            field("environment_scope", "string", required=True),
            field("category", "string", required=True),
            field("title", "string", required=True),
            field("description", "string", required=True),
            field("action_type", "string", required=True),
            field("action_target", "string", required=False),
            field("availability_text", "string", required=False),
            field("source_text", "string", required=True),
            field("verified_at", "datetime", required=True),
            field("enabled", "boolean", required=True),
            field("sort_order", "integer", required=True),
        ),
        indexes=(),
    ),
    "quote_entries": CollectionSpec(
        name="quote_entries",
        fields=COMMON_FIELDS
        + (
            field("quote_text", "string", required=True),
            field("author_text", "string", required=True),
            field("work_text", "string", required=False),
            field("source_kind", "string", required=True),
            field("rights_note", "string", required=True),
            field("enabled", "boolean", required=True),
            field("display_from", "string", required=False),
            field("display_until", "string", required=False),
            field("sort_order", "integer", required=True),
            field("library_version", "string", required=True),
        ),
        indexes=(),
    ),
    "treehole_posts": CollectionSpec(
        name="treehole_posts",
        fields=COMMON_FIELDS
        + (
            field("author_user_id", "string", required=True),
            field("anonymous_identity_id", "string", required=True),
            field("display_name_snapshot", "string", required=True),
            field("body_original_ciphertext", "encrypted_string", required=False),
            field("body_sanitized", "string", required=False),
            field("body_hash", "hash_string", required=True),
            field("visibility_state", "string", required=True),
            field("review_state", "string", required=True),
            field("safety_state", "string", required=True),
            field("community_consent_version", "string", required=True),
            field("original_retention_deadline", "datetime", required=False),
            field("deleted_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("visibility_state", "created_at")),
            IndexSpec(("author_user_id", "created_at")),
        ),
    ),
    "treehole_responses": CollectionSpec(
        name="treehole_responses",
        fields=COMMON_FIELDS
        + (
            field("post_id", "string", required=True),
            field("author_user_id", "string", required=True),
            field("anonymous_identity_id", "string", required=True),
            field("display_name_snapshot", "string", required=True),
            field("body_original_ciphertext", "encrypted_string", required=False),
            field("body_sanitized", "string", required=False),
            field("state", "string", required=True),
            field("community_consent_version", "string", required=True),
            field("deleted_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("post_id", "state", "created_at")),
            IndexSpec(("author_user_id", "created_at")),
        ),
    ),
    "work_tasks": CollectionSpec(
        name="work_tasks",
        fields=COMMON_FIELDS
        + (
            field("task_kind", "string", required=True),
            field("source_type", "string", required=True),
            field("source_id", "string", required=True),
            field("available_capability", "string", required=True),
            field("state", "string", required=True),
            field("assigned_admin_id", "string", required=False),
            field("safe_summary", "string", required=True),
            field("object_version", "integer", required=True),
            field("last_action", "string", required=False),
        ),
        indexes=(
            IndexSpec(("state", "updated_at")),
            IndexSpec(("available_capability", "state")),
            IndexSpec(("assigned_admin_id", "state")),
        ),
    ),
    "content_review_tasks": CollectionSpec(
        name="content_review_tasks",
        fields=COMMON_FIELDS
        + (
            field("task_kind", "string", required=True),
            field("post_id", "string", required=True),
            field("response_id", "string", required=False),
            field("state", "string", required=True),
            field("assigned_admin_id", "string", required=False),
            field("object_version_snapshot", "integer", required=True),
            field("decision", "string", required=False),
            field("internal_reason", "string", required=False),
            field("automated_check_summary", "object", required=False),
            field("completed_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("state", "created_at")),
            IndexSpec(("assigned_admin_id", "state")),
        ),
    ),
    "safety_support_tasks": CollectionSpec(
        name="safety_support_tasks",
        fields=COMMON_FIELDS
        + (
            field("task_kind", "string", required=True),
            field("user_reference_id", "string", required=True),
            field("source_result_id", "string", required=True),
            field("safety_fact", "string", required=True),
            field("support_resource_snapshot", "array[object]", required=True),
            field("state", "string", required=True),
            field("assigned_admin_id", "string", required=False),
            field("followup_due_at", "datetime", required=False),
            field("fact_note", "string", required=False),
            field("completed_at", "datetime", required=False),
        ),
        indexes=(
            IndexSpec(("state", "created_at")),
            IndexSpec(("assigned_admin_id", "state")),
        ),
    ),
    "identity_access_requests": CollectionSpec(
        name="identity_access_requests",
        fields=COMMON_FIELDS
        + (
            field("task_kind", "string", required=True),
            field("user_reference_id", "string", required=True),
            field("requester_admin_id", "string", required=True),
            field("requested_fields", "array[string]", required=True),
            field("reason_fact", "string", required=True),
            field("state", "string", required=True),
            field("decided_admin_id", "string", required=False),
            field("decision_reason", "string", required=False),
            field("valid_from", "datetime", required=False),
            field("valid_until", "datetime", required=False),
        ),
        indexes=(IndexSpec(("user_reference_id", "state")), IndexSpec(("valid_until",))),
    ),
    "followup_records": CollectionSpec(
        name="followup_records",
        fields=COMMON_FIELDS
        + (
            field("task_id", "string", required=True),
            field("actor_admin_id", "string", required=True),
            field("action_code", "string", required=True),
            field("fact_note", "string", required=True),
            field("next_due_at", "datetime", required=False),
        ),
        indexes=(),
    ),
    "admin_accounts": CollectionSpec(
        name="admin_accounts",
        fields=COMMON_FIELDS
        + (
            field("login_name", "string", required=True),
            field("display_name", "string", required=True),
            field("capability_label", "string", required=True),
            field("status", "string", required=True),
            field("password_hash_reference", "string", required=True),
            field("last_login_at", "datetime", required=False),
        ),
        indexes=(),
    ),
    "audit_events": CollectionSpec(
        name="audit_events",
        fields=COMMON_FIELDS
        + (
            field("request_id", "string", required=True),
            field("environment_id", "string", required=True),
            field("actor_type", "string", required=True),
            field("actor_id", "string", required=False),
            field("actor_capability", "string", required=False),
            field("action", "string", required=True),
            field("resource_type", "string", required=True),
            field("resource_id", "string", required=True),
            field("data_scope", "array[string]", required=True),
            field("outcome", "string", required=True),
            field("reason_code", "string", required=False),
            field("occurred_at", "datetime", required=True),
        ),
        indexes=(
            IndexSpec(("occurred_at",)),
            IndexSpec(("resource_type", "resource_id", "occurred_at")),
            IndexSpec(("actor_id", "occurred_at")),
        ),
    ),
    "idempotency_records": CollectionSpec(
        name="idempotency_records",
        fields=COMMON_FIELDS
        + (
            field("actor_type", "string", required=True),
            field("actor_id", "string", required=True),
            field("route_key", "string", required=True),
            field("idempotency_key", "string", required=True),
            field("request_hash", "hash_string", required=True),
            field("outcome", "string", required=True),
            field("response_digest", "hash_string", required=False),
            field("expires_at", "datetime", required=True),
        ),
        indexes=(IndexSpec(("actor_id", "route_key", "idempotency_key"), unique=True),),
    ),
    "demo_reset_runs": CollectionSpec(
        name="demo_reset_runs",
        fields=COMMON_FIELDS
        + (
            field("environment_id", "string", required=True),
            field("requested_by_admin_id", "string", required=True),
            field("state", "string", required=True),
            field("affected_collections", "array[string]", required=True),
            field("collection_results", "object", required=False),
            field("request_id", "string", required=True),
            field("started_at", "datetime", required=True),
            field("completed_at", "datetime", required=False),
        ),
        indexes=(),
    ),
}


COLLECTIONS = tuple(REGISTRY)

if set(COLLECTION_MODELS) != set(REGISTRY):
    missing_models = sorted(set(REGISTRY) - set(COLLECTION_MODELS))
    missing_registry = sorted(set(COLLECTION_MODELS) - set(REGISTRY))
    raise RuntimeError(
        "collection registry and models are out of sync: "
        f"missing_models={missing_models}, missing_registry={missing_registry}"
    )


def build_collection_projection() -> dict[str, dict[str, object]]:
    return {
        name: {
            "fields": {item.name: item.as_dict() for item in spec.fields},
            "indexes": [index.as_dict(name) for index in spec.indexes],
        }
        for name, spec in REGISTRY.items()
    }


def build_index_projection() -> dict[str, list[dict[str, object]]]:
    return {
        name: [index.as_dict(name) for index in spec.indexes] for name, spec in REGISTRY.items()
    }
