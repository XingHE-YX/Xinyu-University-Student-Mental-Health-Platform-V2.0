from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import IdentityRecordDocument, UserAccountDocument
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import IdempotencyService


def configured_settings() -> Settings:
    return Settings.from_environment(
        {
            "WECHAT_APPID": "wx-demo",
            "WECHAT_APPSECRET": "wechat-secret",
            "CLOUDBASE_ENV_ID": "demo-env",
            "CLOUDBASE_API_KEY": "cloudbase-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
            "ADMIN_PASSWORD_HASH": "password-hash",
            "ADMIN_SESSION_SECRET": "admin-session-secret",
            "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
            "SUPPORT_RESOURCE_VERSION": "support-v1",
            "DEMO_MODE": "true",
        },
        demo_env_ids={"demo-env"},
    )


def build_user(**overrides: Any) -> UserAccountDocument:
    data: dict[str, Any] = {
        "_id": "user-1",
        "auth_subject_hash": "student-subject-hash",
        "status": "active",
        "base_consent_status": "accepted",
        "base_consent_version": "base-v1",
        "base_consent_at": datetime(2026, 8, 30, tzinfo=UTC),
        "community_consent_status": "accepted",
        "community_consent_version": "community-v1",
        "community_consent_at": datetime(2026, 8, 30, tzinfo=UTC),
        "identity_record_id": "identity-1",
        "anonymous_identity_id": "anonymous-1",
        "created_at": datetime(2026, 8, 30, tzinfo=UTC),
        "updated_at": datetime(2026, 8, 30, tzinfo=UTC),
        "version": 3,
    }
    data.update(overrides)
    return UserAccountDocument(**data)


def issue_student_access_token(
    sessions: InMemorySessionRepository,
    *,
    subject_id: str = "user-1",
) -> str:
    pair = TokenManager("student-session-secret").issue("student", subject_id, sessions)
    return pair.access_token


def seed_rules_repository() -> InMemoryDomainDataRepository:
    rules = pytest.importorskip("app.domain.assessment_rules")
    seed_documents = rules.build_seed_documents()
    return InMemoryDomainDataRepository(
        users=[build_user()],
        identities=[
            IdentityRecordDocument(
                _id="identity-1",
                user_id="user-1",
                verification_status="verified",
                student_name_ciphertext="cipher-name",
                student_number_ciphertext="cipher-number",
                provider_reference_hash="provider-ref",
                verified_at=datetime(2026, 8, 30, tzinfo=UTC),
                failed_reason_code=None,
                access_version=1,
                created_at=datetime(2026, 8, 30, tzinfo=UTC),
                updated_at=datetime(2026, 8, 30, tzinfo=UTC),
                version=1,
            )
        ],
        assessment_modules=seed_documents["assessment_modules"],
        assessment_questionnaires=seed_documents["assessment_questionnaires"],
    )


def build_service(repository: InMemoryDomainDataRepository) -> object:
    service_module = pytest.importorskip("app.services.assessment_service")
    return service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=InMemorySessionRepository(),
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )


def test_start_session_freezes_enabled_questionnaire_version_without_score_rules() -> None:
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    started = service.start_session(
        access_token,
        module_code="phq9",
        request_id="req-start-1",
        idempotency_key="start-1",
    )

    assert started.questionnaire_version == "phq9-cn-v1"
    assert started.state == "in_progress"
    assert len(started.questions) == 10
    assert all(not hasattr(question, "score_rule") for question in started.questions)

    session = repository.get_assessment_session(started.session_id)
    assert session.questionnaire_version == "phq9-cn-v1"
    assert session.answers is None
    assert session.answered_count is None


def test_completion_persists_result_atomically_and_replays_duplicate_submit() -> None:
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)
    started = service.start_session(
        access_token,
        module_code="gad7",
        request_id="req-start-1",
        idempotency_key="start-1",
    )

    result = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=started.object_version,
        answers=[
            {"question_key": "q1", "option_key": "2"},
            {"question_key": "q2", "option_key": "2"},
            {"question_key": "q3", "option_key": "2"},
            {"question_key": "q4", "option_key": "2"},
            {"question_key": "q5", "option_key": "2"},
            {"question_key": "q6", "option_key": "0"},
            {"question_key": "q7", "option_key": "0"},
        ],
        request_id="req-complete-1",
        idempotency_key="complete-1",
    )

    replay = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=started.object_version,
        answers=[
            {"question_key": "q1", "option_key": "2"},
            {"question_key": "q2", "option_key": "2"},
            {"question_key": "q3", "option_key": "2"},
            {"question_key": "q4", "option_key": "2"},
            {"question_key": "q5", "option_key": "2"},
            {"question_key": "q6", "option_key": "0"},
            {"question_key": "q7", "option_key": "0"},
        ],
        request_id="req-complete-1b",
        idempotency_key="complete-1",
    )

    assert result.completion_state == "result_ready"
    assert result.result_id is not None
    assert result.score == 10
    assert result.result_state == "higher_score"
    assert replay.result_id == result.result_id

    session = repository.get_assessment_session(started.session_id)
    stored_result = repository.get_assessment_result(result.result_id)
    assert session.state == "completed"
    assert session.answered_count == 7
    assert stored_result.session_id == started.session_id
    assert stored_result.score == 10
    assert len(repository.list_assessment_results_by_session(started.session_id)) == 1


def test_phq9_question_9_non_zero_requires_safety_confirmation_and_does_not_persist_answers() -> (
    None
):
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    audit_repository = InMemoryAuditRepository()
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)
    started = service.start_session(
        access_token,
        module_code="phq9",
        request_id="req-start-1",
        idempotency_key="start-1",
    )

    result = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=started.object_version,
        answers=[
            {"question_key": "q1", "option_key": "0"},
            {"question_key": "q2", "option_key": "0"},
            {"question_key": "q3", "option_key": "0"},
            {"question_key": "q4", "option_key": "0"},
            {"question_key": "q5", "option_key": "0"},
            {"question_key": "q6", "option_key": "0"},
            {"question_key": "q7", "option_key": "0"},
            {"question_key": "q8", "option_key": "0"},
            {"question_key": "q9", "option_key": "1"},
            {"question_key": "impact", "option_key": "some"},
        ],
        request_id="req-complete-1",
        idempotency_key="complete-1",
    )

    assert result.completion_state == "safety_confirmation_required"
    assert result.result_id is None
    assert result.safety_triggered is True

    session = repository.get_assessment_session(started.session_id)
    assert session.state == "in_progress"
    assert session.answers is None
    assert session.answered_count is None
    assert session.safety_triggered is True
    assert repository.list_assessment_results_by_session(started.session_id) == ()
    first_event = audit_repository.list()[0]
    assert "question_key" not in str(first_event)
    assert "option_key" not in str(first_event)


def test_completion_rejects_missing_duplicate_invalid_or_extra_answers() -> None:
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)
    started = service.start_session(
        access_token,
        module_code="sleep_observation",
        request_id="req-start-1",
        idempotency_key="start-1",
    )

    with pytest.raises(ApiException) as missing:
        service.complete_session(
            access_token,
            session_id=started.session_id,
            object_version=started.object_version,
            answers=[
                {"question_key": "q1", "option_key": "stable"},
                {"question_key": "q2", "option_key": "7_to_9"},
            ],
            request_id="req-missing",
            idempotency_key="complete-missing",
        )
    assert missing.value.code == "VALIDATION_FAILED"

    with pytest.raises(ApiException) as duplicate:
        service.complete_session(
            access_token,
            session_id=started.session_id,
            object_version=started.object_version,
            answers=[
                {"question_key": "q1", "option_key": "stable"},
                {"question_key": "q1", "option_key": "occasional_variation"},
                {"question_key": "q2", "option_key": "7_to_9"},
                {"question_key": "q3", "option_key": "within_15"},
                {"question_key": "q4", "option_key": "easy_to_resume"},
                {"question_key": "q5", "option_key": "good"},
                {"question_key": "q6", "option_key": "none"},
                {"question_key": "q7", "option_key": "never"},
            ],
            request_id="req-duplicate",
            idempotency_key="complete-duplicate",
        )
    assert duplicate.value.code == "VALIDATION_FAILED"

    with pytest.raises(ApiException) as invalid:
        service.complete_session(
            access_token,
            session_id=started.session_id,
            object_version=started.object_version,
            answers=[
                {"question_key": "q1", "option_key": "stable"},
                {"question_key": "q2", "option_key": "not-an-option"},
                {"question_key": "q3", "option_key": "within_15"},
                {"question_key": "q4", "option_key": "easy_to_resume"},
                {"question_key": "q5", "option_key": "good"},
                {"question_key": "q6", "option_key": "none"},
                {"question_key": "q7", "option_key": "never"},
            ],
            request_id="req-invalid",
            idempotency_key="complete-invalid",
        )
    assert invalid.value.code == "VALIDATION_FAILED"


def test_completion_rejects_version_conflict_expired_and_abandoned_sessions() -> None:
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)
    started = service.start_session(
        access_token,
        module_code="gad7",
        request_id="req-start-1",
        idempotency_key="start-1",
    )

    repository.replace_assessment_module(
        repository.get_assessment_module("gad7").model_copy(
            update={"current_questionnaire_version": "gad7-cn-v2"}
        ),
        expected_version=1,
    )
    with pytest.raises(ApiException) as version_error:
        service.complete_session(
            access_token,
            session_id=started.session_id,
            object_version=started.object_version,
            answers=[
                {"question_key": "q1", "option_key": "0"},
                {"question_key": "q2", "option_key": "0"},
                {"question_key": "q3", "option_key": "0"},
                {"question_key": "q4", "option_key": "0"},
                {"question_key": "q5", "option_key": "0"},
                {"question_key": "q6", "option_key": "0"},
                {"question_key": "q7", "option_key": "0"},
            ],
            request_id="req-version-conflict",
            idempotency_key="complete-version-conflict",
        )
    assert version_error.value.code == "VERSION_CONFLICT"

    expired_session = repository.get_assessment_session(started.session_id).model_copy(
        update={"expires_at": datetime.now(UTC) - timedelta(minutes=1)}
    )
    repository.save_assessment_session(expired_session, expected_version=1)
    with pytest.raises(ApiException) as expired:
        service.complete_session(
            access_token,
            session_id=started.session_id,
            object_version=2,
            answers=[
                {"question_key": "q1", "option_key": "0"},
                {"question_key": "q2", "option_key": "0"},
                {"question_key": "q3", "option_key": "0"},
                {"question_key": "q4", "option_key": "0"},
                {"question_key": "q5", "option_key": "0"},
                {"question_key": "q6", "option_key": "0"},
                {"question_key": "q7", "option_key": "0"},
            ],
            request_id="req-expired",
            idempotency_key="complete-expired",
        )
    assert expired.value.code == "NOT_FOUND"
