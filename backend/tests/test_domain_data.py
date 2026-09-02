from __future__ import annotations

import importlib
import importlib.util
import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.config.environments import EnvironmentKind

EXPECTED_COLLECTIONS = {
    "user_accounts",
    "auth_sessions",
    "identity_records",
    "consent_records",
    "anonymous_identities",
    "daily_mood_records",
    "assessment_modules",
    "assessment_questionnaires",
    "assessment_sessions",
    "assessment_results",
    "ai_assist_snapshots",
    "support_resources",
    "quote_entries",
    "treehole_posts",
    "treehole_responses",
    "work_tasks",
    "content_review_tasks",
    "safety_support_tasks",
    "identity_access_requests",
    "followup_records",
    "admin_accounts",
    "audit_events",
    "idempotency_records",
    "demo_reset_runs",
}


def load_module(module_name: str) -> Any:
    spec = importlib.util.find_spec(module_name)
    assert spec is not None, f"{module_name} module is missing"
    return importlib.import_module(module_name)


def sample_metadata() -> dict[str, object]:
    return {
        "_id": "doc-1",
        "created_at": datetime(2026, 8, 29, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 29, 1, tzinfo=UTC),
        "version": 1,
    }


def test_collection_registry_covers_all_fixed_collections_and_serializes_indexes() -> None:
    registry = load_module("app.repositories.collection_registry")
    models = load_module("app.domain.models")

    collection_names = set(registry.COLLECTIONS)
    assert collection_names == EXPECTED_COLLECTIONS
    assert all(name == name.lower() for name in collection_names)

    schema_projection = registry.build_collection_projection()
    json.dumps(schema_projection, ensure_ascii=False)

    quote_fields = schema_projection["quote_entries"]["fields"]
    assert quote_fields["source_kind"]["storage_type"] == "string"
    assert quote_fields["library_version"]["required"] is True
    assert quote_fields["source_url"]["required"] is True
    assert quote_fields["language_version"]["required"] is True
    assert quote_fields["review_status"]["required"] is True

    support_fields = schema_projection["support_resources"]["fields"]
    assert support_fields["resource_set_version"]["required"] is True
    assert support_fields["expires_at"]["required"] is False

    indexes = schema_projection["assessment_results"]["indexes"]
    assert indexes == [
        {
            "name": "assessment_results__user_id_module_code_created_at",
            "fields": ["user_id", "module_code", "created_at"],
            "unique": False,
        },
        {
            "name": "assessment_results__session_id__unique",
            "fields": ["session_id"],
            "unique": True,
        },
    ]

    auth_session_indexes = schema_projection["auth_sessions"]["indexes"]
    assert auth_session_indexes == [
        {
            "name": "auth_sessions__access_token_hash__unique",
            "fields": ["access_token_hash"],
            "unique": True,
        },
        {
            "name": "auth_sessions__subject_id_status",
            "fields": ["subject_id", "status"],
            "unique": False,
        },
        {
            "name": "auth_sessions__access_expires_at",
            "fields": ["access_expires_at"],
            "unique": False,
        },
    ]

    for collection_name, collection_spec in registry.REGISTRY.items():
        schema_fields = set(schema_projection[collection_name]["fields"])
        model_fields = set(models.COLLECTION_MODELS[collection_name].model_fields)
        model_fields.add("_id")

        for index in collection_spec.indexes:
            assert set(index.fields) <= schema_fields
            assert set(index.fields) <= model_fields


def test_consent_and_audit_records_require_fixed_version_one() -> None:
    models = load_module("app.domain.models")

    consent = models.ConsentEventDocument(
        **sample_metadata(),
        user_id="user-1",
        consent_kind="base_service",
        action="accepted",
        document_version="base-v1",
        source="admin_seed",
        occurred_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
        request_id="req-1",
    )
    audit = models.AuditEventDocument(
        **sample_metadata(),
        request_id="req-2",
        environment_id="demo-env",
        actor_type="system",
        actor_id=None,
        actor_capability=None,
        action="seed_reset",
        resource_type="demo",
        resource_id="demo-run-1",
        data_scope=["state"],
        outcome="success",
        reason_code=None,
        occurred_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
    )

    assert consent.version == 1
    assert audit.version == 1

    with pytest.raises(ValidationError):
        models.ConsentEventDocument(
            **sample_metadata() | {"version": 2},
            user_id="user-1",
            consent_kind="base_service",
            action="accepted",
            document_version="base-v1",
            source="admin_seed",
            occurred_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            request_id="req-1",
        )

    with pytest.raises(ValidationError):
        models.AuditEventDocument(
            **sample_metadata() | {"version": 2},
            request_id="req-2",
            environment_id="demo-env",
            actor_type="system",
            actor_id=None,
            actor_capability=None,
            action="seed_reset",
            resource_type="demo",
            resource_id="demo-run-1",
            data_scope=["state"],
            outcome="success",
            reason_code=None,
            occurred_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
        )


def test_quote_entry_model_blocks_enabled_copyright_pending_records() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.QuoteEntryDocument(
            **sample_metadata(),
            quote_text="直到最后都不能放弃希望。",
            author_text="安西教练",
            work_text="灌篮高手",
            source_kind="copyright_pending",
            source_url="https://example.test/candidate",
            language_version="zh-Hans",
            review_status="待核验",
            rights_note="待版权与正式译文核验",
            enabled=True,
            display_from=None,
            display_until=None,
            sort_order=1,
            library_version="quote-library-v1",
        )


def test_daily_mood_model_requires_a_calendar_date_string() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.DailyMoodRecordDocument(
            **sample_metadata(),
            user_id="user-1",
            record_date="2026/08/29",
            mood_code="calm",
            source="mini_program",
            deleted_at=None,
        )


def test_assessment_session_requires_answers_only_for_completed_state() -> None:
    models = load_module("app.domain.models")

    completed = models.AssessmentSessionDocument(
        **sample_metadata(),
        user_id="user-1",
        module_code="phq9",
        questionnaire_version="phq9-v1",
        state="completed",
        answers=[
            {
                "question_key": "q1",
                "option_key": "o1",
                "score_snapshot": 1,
            }
        ],
        answered_count=1,
        safety_triggered=False,
        safety_confirmation_state=None,
        safety_resource_version=None,
        safety_resource_acknowledged_at=None,
        client_idempotency_key="idem-1",
        started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
        completed_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
        abandoned_at=None,
        expires_at=datetime(2026, 8, 30, tzinfo=UTC),
    )
    assert completed.answered_count == 1

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="in_progress",
            answers=[
                {
                    "question_key": "q1",
                    "option_key": "o1",
                    "score_snapshot": 1,
                }
            ],
            answered_count=1,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=None,
            abandoned_at=None,
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )


def test_assessment_session_enforces_state_timestamp_combinations() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="completed",
            answers=[{"question_key": "q1", "option_key": "o1", "score_snapshot": 1}],
            answered_count=1,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=None,
            abandoned_at=None,
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="completed",
            answers=[{"question_key": "q1", "option_key": "o1", "score_snapshot": 1}],
            answered_count=1,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            abandoned_at=datetime(2026, 8, 29, 3, tzinfo=UTC),
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="in_progress",
            answers=None,
            answered_count=None,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            abandoned_at=None,
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="abandoned",
            answers=None,
            answered_count=None,
            safety_triggered=True,
            safety_confirmation_state="cannot_be_safe",
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            abandoned_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="abandoned",
            answers=None,
            answered_count=None,
            safety_triggered=True,
            safety_confirmation_state="cannot_be_safe",
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=None,
            abandoned_at=None,
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="expired",
            answers=None,
            answered_count=None,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=None,
            abandoned_at=datetime(2026, 8, 29, 3, tzinfo=UTC),
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )

    with pytest.raises(ValidationError):
        models.AssessmentSessionDocument(
            **sample_metadata(),
            user_id="user-1",
            module_code="phq9",
            questionnaire_version="phq9-v1",
            state="completed",
            answers=None,
            answered_count=None,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key="idem-1",
            started_at=datetime(2026, 8, 29, 1, tzinfo=UTC),
            completed_at=datetime(2026, 8, 29, 2, tzinfo=UTC),
            abandoned_at=None,
            expires_at=datetime(2026, 8, 30, tzinfo=UTC),
        )


def test_safety_support_result_rejects_full_answers_score_and_ai_snapshot() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.AssessmentResultDocument(
            **sample_metadata(),
            session_id="session-1",
            user_id="user-1",
            module_code="phq9",
            scoring_rule_version="rule-v1",
            answers_snapshot=[
                {
                    "question_key": "q1",
                    "option_key": "o1",
                    "score_snapshot": 1,
                }
            ],
            fixed_summary="summary",
            reference_band="10-14",
            boundary_notice="notice",
            ai_assist_snapshot_id="ai-1",
            result_state="safety_support",
            score=12,
            dimension_summary={"support_required": True},
            safety_state="uncertain",
            visible_copy_version="copy-v1",
            deleted_at=None,
        )

    ordinary = models.AssessmentResultDocument(
        **sample_metadata(),
        session_id="session-2",
        user_id="user-1",
        module_code="phq9",
        scoring_rule_version="rule-v1",
        answers_snapshot=[
            {
                "question_key": "q1",
                "option_key": "o1",
                "score_snapshot": 1,
            }
        ],
        fixed_summary="summary",
        reference_band="10-14",
        boundary_notice="notice",
        ai_assist_snapshot_id="ai-1",
        result_state="ordinary",
        score=12,
        dimension_summary={"band": "10-14"},
        safety_state="not_triggered",
        visible_copy_version="copy-v1",
        deleted_at=None,
    )
    assert ordinary.score == 12


def test_assessment_result_rejects_cannot_be_safe_and_invalid_state_combinations() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.AssessmentResultDocument(
            **sample_metadata(),
            session_id="session-3",
            user_id="user-1",
            module_code="phq9",
            scoring_rule_version="rule-v1",
            answers_snapshot=[{"question_key": "q1", "option_key": "o1", "score_snapshot": 1}],
            fixed_summary="summary",
            reference_band="10-14",
            boundary_notice="notice",
            ai_assist_snapshot_id="ai-1",
            result_state="ordinary",
            score=12,
            dimension_summary={"band": "10-14"},
            safety_state="cannot_be_safe",
            visible_copy_version="copy-v1",
            deleted_at=None,
        )

    with pytest.raises(ValidationError):
        models.AssessmentResultDocument(
            **sample_metadata(),
            session_id="session-4",
            user_id="user-1",
            module_code="phq9",
            scoring_rule_version="rule-v1",
            answers_snapshot=[{"question_key": "q1", "option_key": "o1", "score_snapshot": 1}],
            fixed_summary="summary",
            reference_band="10-14",
            boundary_notice="notice",
            ai_assist_snapshot_id="ai-1",
            result_state="ordinary",
            score=12,
            dimension_summary={"band": "10-14"},
            safety_state="uncertain",
            visible_copy_version="copy-v1",
            deleted_at=None,
        )

    with pytest.raises(ValidationError):
        models.AssessmentResultDocument(
            **sample_metadata(),
            session_id="session-5",
            user_id="user-1",
            module_code="phq9",
            scoring_rule_version="rule-v1",
            answers_snapshot=None,
            fixed_summary="summary",
            reference_band=None,
            boundary_notice="notice",
            ai_assist_snapshot_id=None,
            result_state="safety_support",
            score=None,
            dimension_summary={"support_required": True},
            safety_state="can_be_safe",
            visible_copy_version="copy-v1",
            deleted_at=None,
        )

    safety_support = models.AssessmentResultDocument(
        **sample_metadata(),
        session_id="session-6",
        user_id="user-1",
        module_code="phq9",
        scoring_rule_version="rule-v1",
        answers_snapshot=None,
        fixed_summary="summary",
        reference_band=None,
        boundary_notice="notice",
        ai_assist_snapshot_id=None,
        result_state="safety_support",
        score=None,
        dimension_summary={"support_required": True},
        safety_state="uncertain",
        visible_copy_version="copy-v1",
        deleted_at=None,
    )
    assert safety_support.safety_state == "uncertain"


def test_safety_support_task_source_reference_matches_safety_fact() -> None:
    models = load_module("app.domain.models")
    snapshot = [
        {
            "resource_id": "resource-campus",
            "title": "校内支持",
            "category": "campus",
            "action_type": "text_only",
            "action_target": None,
        }
    ]

    uncertain = models.SafetySupportTaskDocument(
        **sample_metadata(),
        task_kind="safety_support",
        user_reference_id="user-1",
        source_result_id="assessment_result_0001",
        source_session_id=None,
        safety_fact="uncertain",
        support_resource_snapshot=snapshot,
        state="needs_action",
        assigned_admin_id=None,
        followup_due_at=None,
        fact_note=None,
        completed_at=None,
    )
    assert uncertain.source_result_id == "assessment_result_0001"

    cannot = models.SafetySupportTaskDocument(
        **sample_metadata(),
        task_kind="safety_support",
        user_reference_id="user-1",
        source_result_id=None,
        source_session_id="assessment_session_0001",
        safety_fact="cannot_be_safe",
        support_resource_snapshot=snapshot,
        state="needs_action",
        assigned_admin_id=None,
        followup_due_at=None,
        fact_note=None,
        completed_at=None,
    )
    assert cannot.source_session_id == "assessment_session_0001"

    for invalid_payload in [
        {
            "source_result_id": "assessment_result_0001",
            "source_session_id": "assessment_session_0001",
            "safety_fact": "uncertain",
        },
        {
            "source_result_id": None,
            "source_session_id": "assessment_session_0001",
            "safety_fact": "uncertain",
        },
        {
            "source_result_id": "assessment_result_0001",
            "source_session_id": None,
            "safety_fact": "cannot_be_safe",
        },
    ]:
        with pytest.raises(ValidationError):
            models.SafetySupportTaskDocument(
                **sample_metadata(),
                task_kind="safety_support",
                user_reference_id="user-1",
                support_resource_snapshot=snapshot,
                state="needs_action",
                assigned_admin_id=None,
                followup_due_at=None,
                fact_note=None,
                completed_at=None,
                **invalid_payload,
            )


def test_seed_demo_is_deterministic_and_restricted_to_demo_environments() -> None:
    seed_demo = load_module("scripts.seed_demo")
    models = load_module("app.domain.models")

    with pytest.raises(ValueError):
        seed_demo.build_demo_seed_bundle(EnvironmentKind.AUTHORIZED)

    first_bundle = seed_demo.build_demo_seed_bundle(EnvironmentKind.DEMO)
    second_bundle = seed_demo.build_demo_seed_bundle(EnvironmentKind.DEMO)

    assert first_bundle == second_bundle
    assert set(first_bundle["collections"]) == EXPECTED_COLLECTIONS

    quote_entries = first_bundle["collections"]["quote_entries"]
    enabled_quotes = [entry for entry in quote_entries if entry["enabled"]]
    disabled_candidates = [entry for entry in quote_entries if not entry["enabled"]]

    assert len(quote_entries) == 43
    assert len(enabled_quotes) == 40
    assert {entry["_id"] for entry in disabled_candidates} == {"Q-C001", "Q-C002", "Q-C003"}
    assert all(entry["source_kind"] != "copyright_pending" for entry in enabled_quotes)

    validated_quotes = [models.QuoteEntryDocument(**entry) for entry in quote_entries]
    assert len(validated_quotes) == 43
    assert all(item.version == 1 for item in validated_quotes)
    assert sum(1 for item in validated_quotes if item.enabled) == 40
    assert sum(1 for item in validated_quotes if not item.enabled) == 3
    by_id = {entry["_id"]: entry for entry in quote_entries}
    assert by_id["Q-0001"] == {
        "_id": "Q-0001",
        "created_at": "2026-08-29T00:00:00+00:00",
        "updated_at": "2026-08-29T00:00:00+00:00",
        "version": 1,
        "quote_text": "天行健，君子以自强不息。",
        "author_text": "《周易·乾》",
        "work_text": None,
        "source_kind": "public_domain",
        "source_url": "https://ctext.org/book-of-changes/qian/zh",
        "language_version": "zh-Hans",
        "review_status": "已启用",
        "rights_note": "公版古典文本，已核验",
        "enabled": True,
        "display_from": None,
        "display_until": None,
        "sort_order": 1,
        "library_version": "quote-library-v1",
    }
    assert by_id["Q-0040"]["quote_text"] == "把很大的事情，先缩成眼前的一小步。"
    assert by_id["Q-0040"]["author_text"] == "心语短句库"
    assert by_id["Q-0040"]["source_kind"] == "project_original"
    assert by_id["Q-0040"]["rights_note"] == "项目原创温和短句，已启用"
    assert by_id["Q-C001"]["enabled"] is False
    assert by_id["Q-C001"]["source_kind"] == "copyright_pending"
    assert by_id["Q-C001"]["review_status"] == "已停用"
    assert by_id["Q-C001"]["rights_note"] == "待版权与正式译文核验"
    assert by_id["Q-C002"]["quote_text"] == "教练，我想打篮球。"
    assert by_id["Q-C003"]["work_text"] == "小魔女学园"

    support_resources = first_bundle["collections"]["support_resources"]
    validated_resources = [models.SupportResourceDocument(**entry) for entry in support_resources]
    assert all(resource.resource_set_version == "support-v1" for resource in validated_resources)
    assert all(resource.expires_at is None for resource in validated_resources)
    assert all(
        target is None or ".invalid" in target or target.startswith("DEMO-")
        for target in (entry["action_target"] for entry in support_resources)
    )


def test_create_indexes_script_serializes_registry_indexes() -> None:
    registry = load_module("app.repositories.collection_registry")
    create_indexes = load_module("scripts.create_indexes")

    expected = registry.build_index_projection()
    actual = create_indexes.serialize_index_plan()

    assert actual == expected
    json.dumps(actual, ensure_ascii=False)
