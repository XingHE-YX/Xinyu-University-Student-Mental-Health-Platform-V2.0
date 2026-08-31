from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import (
    AssessmentQuestionnaireDocument,
    IdentityRecordDocument,
    UserAccountDocument,
)
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.protocols import RepositoryNotFound
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


def seed_rules_repository(
    *,
    module_updates: dict[str, dict[str, Any]] | None = None,
    questionnaire_updates: dict[tuple[str, str], dict[str, Any]] | None = None,
    extra_questionnaires: list[AssessmentQuestionnaireDocument] | None = None,
) -> InMemoryDomainDataRepository:
    rules = pytest.importorskip("app.domain.assessment_rules")
    seed_documents = rules.build_seed_documents()
    modules = [
        module.model_copy(update=(module_updates or {}).get(module.module_code, {}))
        for module in seed_documents["assessment_modules"]
    ]
    questionnaires = [
        questionnaire.model_copy(
            update=(questionnaire_updates or {}).get(
                (questionnaire.module_code, questionnaire.questionnaire_version), {}
            )
        )
        for questionnaire in seed_documents["assessment_questionnaires"]
    ]
    questionnaires.extend(extra_questionnaires or [])
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
        assessment_modules=modules,
        assessment_questionnaires=questionnaires,
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


def test_start_session_rejects_disabled_module_from_repository() -> None:
    repository = seed_rules_repository(module_updates={"phq9": {"enabled": False}})
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

    with pytest.raises(ApiException) as error:
        service.start_session(
            issue_student_access_token(sessions),
            module_code="phq9",
            request_id="req-start-disabled-module",
            idempotency_key="start-disabled-module",
        )

    assert error.value.code == "NOT_FOUND"
    with pytest.raises(RepositoryNotFound):
        repository.get_assessment_session("assessment_session_0001")


def test_start_session_rejects_disabled_questionnaire_from_repository() -> None:
    repository = seed_rules_repository(
        questionnaire_updates={("phq9", "phq9-cn-v1"): {"enabled": False}}
    )
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

    with pytest.raises(ApiException) as error:
        service.start_session(
            issue_student_access_token(sessions),
            module_code="phq9",
            request_id="req-start-disabled-questionnaire",
            idempotency_key="start-disabled-questionnaire",
        )

    assert error.value.code == "NOT_FOUND"


def test_start_session_uses_repository_current_version_and_question_projection() -> None:
    rules = pytest.importorskip("app.domain.assessment_rules")
    seed_documents = rules.build_seed_documents()
    phq9_v1 = next(
        questionnaire
        for questionnaire in seed_documents["assessment_questionnaires"]
        if questionnaire.module_code == "phq9"
    )
    phq9_v2 = phq9_v1.model_copy(
        update={
            "_id": "assessment-questionnaire-phq9-v2",
            "questionnaire_version": "phq9-cn-v2",
            "questions": [
                question.model_copy(update={"text": "仓储发布的 v2 题干。"})
                if question.question_key == "q1"
                else question
                for question in phq9_v1.questions
            ],
        }
    )
    repository = seed_rules_repository(
        module_updates={"phq9": {"current_questionnaire_version": "phq9-cn-v2"}},
        extra_questionnaires=[phq9_v2],
    )
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

    started = service.start_session(
        issue_student_access_token(sessions),
        module_code="phq9",
        request_id="req-start-v2",
        idempotency_key="start-v2",
    )

    assert started.questionnaire_version == "phq9-cn-v2"
    assert started.questions[0].text == "仓储发布的 v2 题干。"
    assert all(not hasattr(question, "score_rule") for question in started.questions)


def test_start_session_rejects_missing_current_questionnaire() -> None:
    repository = seed_rules_repository(
        module_updates={"phq9": {"current_questionnaire_version": "phq9-cn-v2"}}
    )
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

    with pytest.raises(ApiException) as error:
        service.start_session(
            issue_student_access_token(sessions),
            module_code="phq9",
            request_id="req-start-missing-questionnaire",
            idempotency_key="start-missing-questionnaire",
        )

    assert error.value.code == "NOT_FOUND"


def test_start_session_rejects_questionnaire_with_mismatched_module() -> None:
    rules = pytest.importorskip("app.domain.assessment_rules")
    repository = seed_rules_repository()
    gad7 = next(
        questionnaire
        for questionnaire in rules.build_seed_documents()["assessment_questionnaires"]
        if questionnaire.module_code == "gad7"
    )
    mismatch: AssessmentQuestionnaireDocument = gad7.model_copy(
        update={"questionnaire_version": "phq9-cn-v1", "_id": "mismatched-questionnaire"}
    )
    original_get = repository.get_assessment_questionnaire

    def get_mismatched_questionnaire(
        module_code: str, questionnaire_version: str
    ) -> AssessmentQuestionnaireDocument:
        assert module_code == "phq9"
        assert questionnaire_version == "phq9-cn-v1"
        return mismatch

    repository.get_assessment_questionnaire = get_mismatched_questionnaire  # type: ignore[method-assign]
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

    with pytest.raises(ApiException) as error:
        service.start_session(
            issue_student_access_token(sessions),
            module_code="phq9",
            request_id="req-start-mismatched-questionnaire",
            idempotency_key="start-mismatched-questionnaire",
        )

    assert error.value.code == "NOT_FOUND"
    repository.get_assessment_questionnaire = original_get  # type: ignore[method-assign]


def test_completion_scores_from_the_session_questionnaire_document() -> None:
    rules = pytest.importorskip("app.domain.assessment_rules")
    seed_documents = rules.build_seed_documents()
    gad7_v1 = next(
        questionnaire
        for questionnaire in seed_documents["assessment_questionnaires"]
        if questionnaire.module_code == "gad7"
    )
    gad7_v2 = gad7_v1.model_copy(
        update={
            "_id": "assessment-questionnaire-gad7-v2",
            "questionnaire_version": "gad7-cn-v2",
            "questions": [
                question.model_copy(
                    update={
                        "options": [
                            option.model_copy(update={"score": 1})
                            if option.option_key == "0"
                            else option
                            for option in question.options
                        ]
                    }
                )
                if question.question_key == "q1"
                else question
                for question in gad7_v1.questions
            ],
        }
    )
    repository = seed_rules_repository(
        module_updates={"gad7": {"current_questionnaire_version": "gad7-cn-v2"}},
        extra_questionnaires=[gad7_v2],
    )
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
        request_id="req-start-gad-v2",
        idempotency_key="start-gad-v2",
    )

    result = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=started.object_version,
        answers=[
            {"question_key": f"q{question_number}", "option_key": "0"}
            for question_number in range(1, 8)
        ],
        request_id="req-complete-gad-v2",
        idempotency_key="complete-gad-v2",
    )

    assert result.score == 1
    stored_result = repository.get_assessment_result(result.result_id or "")
    assert stored_result.answers_snapshot is not None
    assert stored_result.answers_snapshot[0].score_snapshot == 1


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


def test_cannot_be_safe_blocks_completion_without_persisting_answers_or_result() -> None:
    repository = seed_rules_repository()
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    audit_repository = InMemoryAuditRepository()
    service_module = pytest.importorskip("app.services.assessment_service")
    service = service_module.AssessmentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)
    started = service.start_session(
        access_token,
        module_code="phq9",
        request_id="req-start-cannot-be-safe",
        idempotency_key="start-cannot-be-safe",
    )
    blocked_session = repository.get_assessment_session(started.session_id).model_copy(
        update={
            "safety_triggered": True,
            "safety_confirmation_state": "cannot_be_safe",
        }
    )
    repository.save_assessment_session(blocked_session, expected_version=started.object_version)
    answers = [
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
    ]

    result = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=blocked_session.version + 1,
        answers=answers,
        request_id="req-complete-cannot-be-safe",
        idempotency_key="complete-cannot-be-safe",
    )
    replay = service.complete_session(
        access_token,
        session_id=started.session_id,
        object_version=blocked_session.version + 1,
        answers=answers,
        request_id="req-complete-cannot-be-safe-replay",
        idempotency_key="complete-cannot-be-safe",
    )

    assert result.completion_state == "safety_support_blocked"
    assert result.result_id is None
    assert result.score is None
    assert result.result_state is None
    assert replay == result
    session = repository.get_assessment_session(started.session_id)
    assert session.state == "in_progress"
    assert session.answers is None
    assert session.answered_count is None
    assert repository.list_assessment_results_by_session(started.session_id) == ()
    idempotency_record = idempotency_repository.get(
        "student",
        "user-1",
        f"/assessment-sessions/{started.session_id}/complete",
        "complete-cannot-be-safe",
        now=datetime.now(UTC),
    )
    assert idempotency_record is not None
    assert idempotency_record.outcome == "success"
    assert idempotency_record.response_status == 200
    blocked_events = [
        event
        for event in audit_repository.list()
        if event.action == "assessment_complete" and event.reason_code == "safety_support_blocked"
    ]
    assert len(blocked_events) == 1
    assert "question_key" not in str(blocked_events[0])
    assert "option_key" not in str(blocked_events[0])


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
