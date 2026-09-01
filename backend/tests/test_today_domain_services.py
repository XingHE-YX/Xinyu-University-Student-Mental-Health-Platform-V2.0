from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, cast

import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import (
    AssessmentAnswerModel,
    AssessmentResultDocument,
    DailyMoodRecordDocument,
    IdentityRecordDocument,
    QuoteEntryDocument,
    SupportResourceDocument,
    UserAccountDocument,
)
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import IdempotencyService
from app.services.mood_service import MoodService
from app.services.quote_service import QuoteService
from app.services.support_resource_service import SupportResourceService
from app.services.today_service import TodayService

FIXED_NOW = datetime(2026, 9, 1, 1, 30, tzinfo=UTC)


def settings_for(kind: str = "demo") -> Settings:
    env = {
        "WECHAT_APPID": "wx-demo",
        "WECHAT_APPSECRET": "wechat-secret",
        "CLOUDBASE_ENV_ID": f"{kind}-env",
        "CLOUDBASE_API_KEY": "cloudbase-secret",
        "DEEPSEEK_API_KEY": "deepseek-secret",
        "ADMIN_PASSWORD_HASH": "password-hash",
        "ADMIN_SESSION_SECRET": "admin-session-secret",
        "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
        "SUPPORT_RESOURCE_VERSION": "support-v1",
        "DEMO_MODE": "true" if kind == "demo" else "false",
    }
    return Settings.from_environment(
        env,
        demo_env_ids={"demo-env"},
        authorized_env_ids={"authorized-env"},
    )


def build_user(**overrides: Any) -> UserAccountDocument:
    data: dict[str, Any] = {
        "_id": "user-1",
        "auth_subject_hash": "student-subject-hash",
        "status": "active",
        "base_consent_status": "accepted",
        "base_consent_version": "base-v1",
        "base_consent_at": datetime(2026, 8, 30, tzinfo=UTC),
        "community_consent_status": "not_accepted",
        "community_consent_version": None,
        "community_consent_at": None,
        "identity_record_id": "identity-1",
        "anonymous_identity_id": "anonymous-1",
        "created_at": datetime(2026, 8, 30, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 30, tzinfo=UTC),
        "version": 3,
    }
    data.update(overrides)
    return UserAccountDocument(**data)


def build_identity(
    *,
    status: str = "verified",
    user_id: str = "user-1",
    record_id: str = "identity-1",
) -> IdentityRecordDocument:
    return IdentityRecordDocument(
        _id=record_id,
        user_id=user_id,
        verification_status=cast(
            Literal["not_started", "pending", "verified", "failed", "unavailable"], status
        ),
        student_name_ciphertext="cipher-name" if status == "verified" else None,
        student_number_ciphertext="cipher-number" if status == "verified" else None,
        provider_reference_hash="provider-ref" if status == "verified" else None,
        verified_at=datetime(2026, 8, 30, tzinfo=UTC) if status == "verified" else None,
        failed_reason_code=None,
        access_version=1,
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, tzinfo=UTC),
        version=1,
    )


def quote_entry(
    item_id: str,
    *,
    enabled: bool = True,
    source_kind: str = "public_domain",
    display_from: str | None = None,
    display_until: str | None = None,
    sort_order: int = 1,
) -> QuoteEntryDocument:
    return QuoteEntryDocument(
        _id=item_id,
        quote_text=f"短句 {item_id}",
        author_text="作者",
        work_text="作品",
        source_kind=cast(
            Literal["public_domain", "project_original", "copyright_pending"], source_kind
        ),
        rights_note="已核验",
        enabled=enabled,
        display_from=display_from,
        display_until=display_until,
        sort_order=sort_order,
        library_version="quote-library-v1",
        created_at=datetime(2026, 8, 29, tzinfo=UTC),
        updated_at=datetime(2026, 8, 29, tzinfo=UTC),
        version=1,
    )


def support_resource(
    item_id: str,
    *,
    environment_scope: str = "demo",
    category: str,
    enabled: bool = True,
    sort_order: int,
    action_target: str | None,
) -> SupportResourceDocument:
    return SupportResourceDocument(
        _id=item_id,
        environment_scope=cast(Literal["demo", "authorized"], environment_scope),
        category=cast(Literal["trusted_person", "campus", "emergency"], category),
        title=f"{category} title",
        description=f"{category} description",
        action_type="copy" if action_target else "text_only",
        action_target=action_target,
        availability_text="可用时间",
        source_text="配置文档",
        verified_at=datetime(2026, 8, 30, tzinfo=UTC),
        enabled=enabled,
        sort_order=sort_order,
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, tzinfo=UTC),
        version=1,
    )


def mood_record(
    record_id: str,
    *,
    user_id: str = "user-1",
    record_date: str = "2026-09-01",
    mood_code: str = "calm",
    deleted_at: datetime | None = None,
    created_at: datetime = datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
    version: int = 1,
) -> DailyMoodRecordDocument:
    return DailyMoodRecordDocument(
        _id=record_id,
        user_id=user_id,
        record_date=record_date,
        mood_code=cast(
            Literal["pleasant", "calm", "tired", "anxious", "low", "irritable"],
            mood_code,
        ),
        source="mini_program",
        deleted_at=deleted_at,
        created_at=created_at,
        updated_at=created_at,
        version=version,
    )


def assessment_result(
    result_id: str,
    *,
    user_id: str = "user-1",
    module_code: str = "phq9",
    state: str = "ordinary",
    created_at: datetime,
) -> AssessmentResultDocument:
    return AssessmentResultDocument(
        _id=result_id,
        session_id=f"session-{result_id}",
        user_id=user_id,
        module_code=cast(Literal["phq9", "gad7", "sleep_observation"], module_code),
        scoring_rule_version="assessment-rules-v1",
        answers_snapshot=[
            AssessmentAnswerModel(question_key="q1", option_key="0", score_snapshot=0)
        ]
        if state != "safety_support"
        else None,
        fixed_summary="summary",
        reference_band="minimal"
        if module_code in {"phq9", "gad7"} and state != "safety_support"
        else None,
        boundary_notice="notice",
        ai_assist_snapshot_id=None,
        result_state=cast(Literal["ordinary", "higher_score", "safety_support"], state),
        score=0 if module_code in {"phq9", "gad7"} and state != "safety_support" else None,
        dimension_summary={"support_required": state == "safety_support"},
        safety_state="uncertain" if state == "safety_support" else "not_triggered",
        visible_copy_version="copy-v1",
        deleted_at=None,
        created_at=created_at,
        updated_at=created_at,
        version=1,
    )


def build_repository(**overrides: Any) -> InMemoryDomainDataRepository:
    return InMemoryDomainDataRepository(
        users=overrides.get("users", [build_user()]),
        identities=overrides.get("identities", [build_identity()]),
        daily_mood_records=overrides.get("daily_mood_records"),
        quote_entries=overrides.get("quote_entries"),
        support_resources=overrides.get("support_resources"),
        assessment_results=overrides.get("assessment_results"),
    )


def issue_student_token(sessions: InMemorySessionRepository, *, subject_id: str = "user-1") -> str:
    return TokenManager("student-session-secret").issue(
        "student",
        subject_id,
        sessions,
    ).access_token


def issue_admin_token(sessions: InMemorySessionRepository) -> str:
    return TokenManager("student-session-secret").issue("admin", "admin-1", sessions).access_token


def build_services(
    repository: InMemoryDomainDataRepository,
    *,
    settings: Settings | None = None,
) -> tuple[
    MoodService,
    QuoteService,
    SupportResourceService,
    TodayService,
    InMemorySessionRepository,
    InMemoryAuditRepository,
]:
    resolved_settings = settings or settings_for()
    sessions = InMemorySessionRepository()
    token_manager = TokenManager("student-session-secret")
    idempotency = IdempotencyService(InMemoryIdempotencyRepository())
    audit_repository = InMemoryAuditRepository()
    audit = AuditWriter(audit_repository, environment_id="demo-env")
    quote = QuoteService(repository=repository)
    resources = SupportResourceService(settings=resolved_settings, repository=repository)
    mood = MoodService(
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        idempotency_service=idempotency,
        audit_writer=audit,
        now_provider=lambda: FIXED_NOW,
    )
    today = TodayService(
        settings=resolved_settings,
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        quote_service=quote,
        support_resource_service=resources,
        now_provider=lambda: FIXED_NOW,
    )
    return mood, quote, resources, today, sessions, audit_repository


def test_today_requires_active_consented_verified_student_and_returns_minimal_projection() -> None:
    repository = build_repository(
        daily_mood_records=[mood_record("mood-1", mood_code="pleasant")],
        quote_entries=[quote_entry("Q-0001", sort_order=1)],
        support_resources=[
            support_resource(
                "support-trusted",
                category="trusted_person",
                sort_order=1,
                action_target="configured-target",
            )
        ],
        assessment_results=[
            assessment_result(
                "result-phq9",
                module_code="phq9",
                created_at=datetime(2026, 8, 31, 10, tzinfo=UTC),
            ),
            assessment_result(
                "result-gad7",
                module_code="gad7",
                created_at=datetime(2026, 8, 30, 10, tzinfo=UTC),
            ),
            assessment_result(
                "result-sleep",
                module_code="sleep_observation",
                created_at=datetime(2026, 8, 29, 10, tzinfo=UTC),
            ),
            assessment_result(
                "result-safety",
                module_code="phq9",
                state="safety_support",
                created_at=datetime(2026, 9, 1, 0, tzinfo=UTC),
            ),
        ],
    )
    _, _, _, today, sessions, _ = build_services(repository)
    access_token = issue_student_token(sessions)

    projection = today.get_today(access_token)
    payload = projection.model_dump()

    assert set(payload) == {"quote", "mood_today", "assessment_shortcuts", "support_entry"}
    assert payload["quote"] == {
        "quote_text": "短句 Q-0001",
        "author_text": "作者",
        "work_text": "作品",
        "library_version": "quote-library-v1",
    }
    assert payload["mood_today"] == {
        "record_id": "mood-1",
        "record_date": "2026-09-01",
        "mood_code": "pleasant",
        "saved_at": datetime(2026, 9, 1, 1, 0, tzinfo=UTC),
        "version": 1,
    }
    assert [item["module_code"] for item in payload["assessment_shortcuts"]] == [
        "phq9",
        "gad7",
        "sleep_observation",
    ]
    assert payload["assessment_shortcuts"][0]["latest_completed_date"] == "2026-08-31"
    assert payload["assessment_shortcuts"][0]["safety_entry_required"] is True
    assert "score" not in str(payload)
    assert "student" not in str(payload)
    assert "anonymous" not in str(payload)

    for user in [
        build_user(status="stopped"),
        build_user(base_consent_status="not_accepted", base_consent_version=None),
        build_user(identity_record_id=None),
    ]:
        blocked_repository = build_repository(users=[user])
        _, _, _, blocked_today, blocked_sessions, _ = build_services(blocked_repository)
        with pytest.raises(ApiException):
            blocked_today.get_today(issue_student_token(blocked_sessions))

    _, _, _, admin_today, admin_sessions, _ = build_services(repository)
    with pytest.raises(ApiException) as admin_error:
        admin_today.get_today(issue_admin_token(admin_sessions))
    assert admin_error.value.code == "FORBIDDEN"


def test_mood_records_only_six_codes_for_current_shanghai_day_with_idempotent_first_fact() -> None:
    repository = build_repository()
    mood, _, _, _, sessions, audit_repository = build_services(repository)
    access_token = issue_student_token(sessions)

    saved = mood.record_today_mood(
        access_token,
        mood_code="calm",
        record_date="2026-09-01",
        request_id="req-mood-1",
        idempotency_key="mood-key-1",
    )

    assert saved.record_date == "2026-09-01"
    assert saved.mood_code == "calm"
    assert saved.version == 1
    assert repository.extra_collection("work_tasks") == []
    assert repository.extra_collection("safety_support_tasks") == []
    assert "calm" not in str(audit_repository.list())

    replay = mood.record_today_mood(
        access_token,
        mood_code="calm",
        record_date="2026-09-01",
        request_id="req-mood-1-replay",
        idempotency_key="mood-key-1",
    )
    assert replay == saved

    not_overwritten = mood.record_today_mood(
        access_token,
        mood_code="low",
        record_date="2026-09-01",
        request_id="req-mood-2",
        idempotency_key="mood-key-2",
    )
    assert not_overwritten == saved
    stored_mood = repository.get_daily_mood_by_user_date("user-1", "2026-09-01")
    assert stored_mood is not None
    assert stored_mood.mood_code == "calm"

    with pytest.raises(ApiException) as conflict:
        mood.record_today_mood(
            access_token,
            mood_code="pleasant",
            record_date="2026-09-01",
            request_id="req-mood-conflict",
            idempotency_key="mood-key-1",
        )
    assert conflict.value.code == "IDEMPOTENCY_CONFLICT"

    for code in ["pleasant", "tired", "anxious", "irritable"]:
        assert code in MoodService.MOOD_LABELS

    with pytest.raises(ApiException) as invalid_code:
        mood.record_today_mood(
            access_token,
            mood_code="excited",
            record_date="2026-09-01",
            request_id="req-invalid-code",
            idempotency_key="invalid-code",
        )
    assert invalid_code.value.code == "VALIDATION_FAILED"

    with pytest.raises(ApiException) as wrong_date:
        mood.record_today_mood(
            access_token,
            mood_code="calm",
            record_date="2026-08-31",
            request_id="req-wrong-date",
            idempotency_key="wrong-date",
        )
    assert wrong_date.value.code == "VALIDATION_FAILED"


def test_mood_history_filters_owner_dates_cursor_limit_and_delete_keeps_same_day_slot() -> None:
    repository = build_repository(
        daily_mood_records=[
            mood_record(
                "mood-old",
                record_date="2026-08-30",
                mood_code="tired",
                created_at=datetime(2026, 8, 30, 2, tzinfo=UTC),
            ),
            mood_record(
                "mood-yesterday",
                record_date="2026-08-31",
                mood_code="low",
                created_at=datetime(2026, 8, 31, 2, tzinfo=UTC),
            ),
            mood_record(
                "mood-today",
                record_date="2026-09-01",
                mood_code="calm",
                created_at=datetime(2026, 9, 1, 2, tzinfo=UTC),
            ),
            mood_record("mood-other", user_id="user-2", record_date="2026-09-01"),
            mood_record(
                "mood-deleted",
                record_date="2026-08-29",
                deleted_at=datetime(2026, 8, 30, tzinfo=UTC),
            ),
        ]
    )
    mood, _, _, _, sessions, _ = build_services(repository)
    access_token = issue_student_token(sessions)

    page = mood.list_history(access_token, from_date="2026-08-30", to_date="2026-09-01", limit=2)

    assert [item.record_id for item in page.items] == ["mood-today", "mood-yesterday"]
    assert page.next_cursor is not None
    second_page = mood.list_history(access_token, cursor=page.next_cursor, limit=2)
    assert [item.record_id for item in second_page.items] == ["mood-old"]

    with pytest.raises(ApiException) as stale:
        mood.delete_mood(
            access_token,
            record_id="mood-today",
            object_version=999,
            request_id="req-stale",
        )
    assert stale.value.code == "VERSION_CONFLICT"
    assert stale.value.current_version == 1

    deleted = mood.delete_mood(
        access_token,
        record_id="mood-today",
        object_version=1,
        request_id="req-delete",
    )
    assert deleted.version == 2
    assert deleted.deleted_at is not None
    assert "mood-today" not in [
        item.record_id for item in mood.list_history(access_token, limit=10).items
    ]

    replacement = mood.record_today_mood(
        access_token,
        mood_code="pleasant",
        record_date="2026-09-01",
        request_id="req-after-delete",
        idempotency_key="after-delete",
    )
    assert replacement.record_id == "mood-today"
    assert replacement.mood_code == "calm"
    assert repository.extra_collection("work_tasks") == []
    assert repository.extra_collection("safety_support_tasks") == []

    with pytest.raises(ApiException) as other_owner:
        mood.delete_mood(
            access_token,
            record_id="mood-other",
            object_version=1,
            request_id="req-other",
        )
    assert other_owner.value.code == "NOT_FOUND"


def test_mood_delete_rejects_already_deleted_record_without_mutation_or_second_audit() -> None:
    repository = build_repository(daily_mood_records=[mood_record("mood-terminal")])
    mood, _, _, _, sessions, audit_repository = build_services(repository)
    access_token = issue_student_token(sessions)

    deleted = mood.delete_mood(
        access_token,
        record_id="mood-terminal",
        object_version=1,
        request_id="req-delete-first",
    )
    persisted_after_first_delete = repository.get_daily_mood("mood-terminal")
    audits_after_first_delete = audit_repository.list()

    with pytest.raises(ApiException) as second_delete:
        mood.delete_mood(
            access_token,
            record_id="mood-terminal",
            object_version=deleted.version,
            request_id="req-delete-second",
        )

    persisted_after_second_delete = repository.get_daily_mood("mood-terminal")
    assert second_delete.value.code == "NOT_FOUND"
    assert second_delete.value.status_code == 404
    assert persisted_after_second_delete.version == persisted_after_first_delete.version == 2
    assert persisted_after_second_delete.deleted_at == persisted_after_first_delete.deleted_at
    assert audit_repository.list() == audits_after_first_delete
    assert len([event for event in audits_after_first_delete if event.action == "mood_delete"]) == 1


def test_mood_account_gate_failures_do_not_write_success_facts() -> None:
    repository = build_repository(
        users=[build_user(base_consent_status="not_accepted", base_consent_version=None)]
    )
    mood, _, _, _, sessions, _ = build_services(repository)
    access_token = issue_student_token(sessions)

    with pytest.raises(ApiException) as blocked:
        mood.record_today_mood(
            access_token,
            mood_code="calm",
            record_date="2026-09-01",
            request_id="req-blocked",
            idempotency_key="blocked",
        )

    assert blocked.value.code == "CONSENT_REQUIRED"
    assert repository.list_daily_mood_records("user-1") == ()


def test_quote_service_uses_enabled_seed_pool_window_and_never_exposes_candidates() -> None:
    import scripts.seed_demo as seed_demo

    seed_quotes = [
        QuoteEntryDocument(**entry)
        for entry in seed_demo.build_demo_seed_bundle(
            __import__("app.config.environments", fromlist=["EnvironmentKind"]).EnvironmentKind.DEMO
        )["collections"]["quote_entries"]
    ]
    repository = build_repository(quote_entries=seed_quotes)
    _, quote, _, _, _, _ = build_services(repository)

    pool = repository.list_available_quote_entries(record_date="2026-09-01")
    assert len(pool) == 40
    assert {entry.document_id for entry in pool} == {f"Q-{number:04d}" for number in range(1, 41)}
    assert {entry.source_kind for entry in pool} == {"public_domain", "project_original"}

    selection = quote.get_daily_quote(now=FIXED_NOW)
    assert selection.status == "available"
    assert selection.quote is not None
    assert set(selection.quote.model_dump()) == {
        "quote_text",
        "author_text",
        "work_text",
        "library_version",
    }

    windowed_repository = build_repository(
        quote_entries=[
            quote_entry("Q-disabled", enabled=False, sort_order=1),
            quote_entry("Q-future", display_from="2026-09-02", sort_order=2),
            quote_entry("Q-expired", display_until="2026-08-31", sort_order=3),
            quote_entry(
                "Q-available",
                display_from="2026-09-01",
                display_until="2026-09-01",
                sort_order=4,
            ),
        ]
    )
    _, windowed_quote, _, _, _, _ = build_services(windowed_repository)
    windowed_selection = windowed_quote.get_daily_quote(now=FIXED_NOW)
    assert windowed_selection.quote is not None
    assert windowed_selection.quote.quote_text == "短句 Q-available"

    empty_repository = build_repository(quote_entries=[])
    _, empty_quote, _, _, _, _ = build_services(empty_repository)
    empty = empty_quote.get_daily_quote(now=FIXED_NOW)
    assert empty.status == "unconfigured"
    assert empty.quote is None


def test_support_resources_are_environment_scoped_ordered_and_explicit_when_missing() -> None:
    repository = build_repository(
        support_resources=[
            support_resource(
                "demo-campus",
                category="campus",
                sort_order=1,
                action_target="DEMO-CAMPUS",
            ),
            support_resource(
                "demo-emergency",
                category="emergency",
                sort_order=2,
                action_target=None,
            ),
            support_resource(
                "demo-trusted",
                category="trusted_person",
                sort_order=3,
                action_target="DEMO-TRUSTED",
            ),
            support_resource(
                "auth-emergency",
                environment_scope="authorized",
                category="emergency",
                sort_order=1,
                action_target="REAL-CONFIGURED-VALUE",
            ),
            support_resource(
                "demo-disabled",
                category="trusted_person",
                enabled=False,
                sort_order=4,
                action_target="DISABLED",
            ),
        ]
    )
    _, _, resources, _, _, _ = build_services(repository)

    normal = resources.list_resources(context="normal")
    safety = resources.list_resources(context="safety")

    assert normal.status == "available"
    assert [item.category for item in normal.resources] == ["trusted_person", "campus", "emergency"]
    assert [item.category for item in safety.resources] == ["emergency", "trusted_person", "campus"]
    assert [item.resource_id for item in normal.resources] == [
        "demo-trusted",
        "demo-campus",
        "demo-emergency",
    ]
    assert normal.resources[0].action_target == "DEMO-TRUSTED"
    assert set(normal.resources[0].model_dump()) == {
        "resource_id",
        "title",
        "description",
        "category",
        "action_type",
        "action_target",
        "availability_text",
        "source_text",
        "verified_at",
        "version",
    }
    assert "REAL-CONFIGURED-VALUE" not in str(normal.model_dump())
    assert "DISABLED" not in str(normal.model_dump())

    unconfigured = SupportResourceService(
        settings=settings_for("unknown"),
        repository=repository,
    ).list_resources(context="normal")
    assert unconfigured.status == "unconfigured"
    assert unconfigured.resources == []

    empty = SupportResourceService(
        settings=settings_for(),
        repository=build_repository(support_resources=[]),
    ).list_resources(context="normal")
    assert empty.status == "empty"
    assert empty.resources == []

    with pytest.raises(ApiException) as bad_context:
        resources.list_resources(context="community")
    assert bad_context.value.code == "VALIDATION_FAILED"
