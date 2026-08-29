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

    collection_names = set(registry.COLLECTIONS)
    assert collection_names == EXPECTED_COLLECTIONS
    assert all(name == name.lower() for name in collection_names)

    schema_projection = registry.build_collection_projection()
    json.dumps(schema_projection, ensure_ascii=False)

    quote_fields = schema_projection["quote_entries"]["fields"]
    assert quote_fields["source_kind"]["storage_type"] == "string"
    assert quote_fields["library_version"]["required"] is True

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


def test_quote_entry_model_blocks_enabled_copyright_pending_records() -> None:
    models = load_module("app.domain.models")

    with pytest.raises(ValidationError):
        models.QuoteEntryDocument(
            **sample_metadata(),
            quote_text="直到最后都不能放弃希望。",
            author_text="安西教练",
            work_text="灌篮高手",
            source_kind="copyright_pending",
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


def test_seed_demo_is_deterministic_and_restricted_to_demo_environments() -> None:
    seed_demo = load_module("scripts.seed_demo")

    with pytest.raises(ValueError):
        seed_demo.build_demo_seed_bundle(EnvironmentKind.AUTHORIZED)

    first_bundle = seed_demo.build_demo_seed_bundle(EnvironmentKind.DEMO)
    second_bundle = seed_demo.build_demo_seed_bundle(EnvironmentKind.DEMO)

    assert first_bundle == second_bundle
    assert set(first_bundle["collections"]) == EXPECTED_COLLECTIONS

    quote_entries = first_bundle["collections"]["quote_entries"]
    enabled_quotes = [entry for entry in quote_entries if entry["enabled"]]
    disabled_candidates = [entry for entry in quote_entries if not entry["enabled"]]

    assert len(enabled_quotes) == 40
    assert {entry["_id"] for entry in disabled_candidates} == {"Q-C001", "Q-C002", "Q-C003"}
    assert all(entry["source_kind"] != "copyright_pending" for entry in enabled_quotes)

    support_resources = first_bundle["collections"]["support_resources"]
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
