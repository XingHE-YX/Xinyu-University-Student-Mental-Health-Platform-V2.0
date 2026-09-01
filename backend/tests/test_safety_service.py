from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import (
    IdentityRecordDocument,
    SupportResourceDocument,
    UserAccountDocument,
)
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.assessment_service import AssessmentService
from app.services.idempotency_service import IdempotencyService
from app.services.safety_service import SafetyService


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


def build_repository(*, kind: str = "demo") -> InMemoryDomainDataRepository:
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
        assessment_modules=list(seed_documents["assessment_modules"]),
        assessment_questionnaires=list(seed_documents["assessment_questionnaires"]),
        support_resources=[
            SupportResourceDocument(
                _id="resource-campus",
                environment_scope="demo" if kind == "demo" else "authorized",
                category="campus",
                title="校内支持",
                description="可以联系学校支持资源。",
                action_type="text_only",
                action_target=None,
                availability_text="工作日",
                source_text="演示资源库",
                verified_at=datetime(2026, 8, 30, tzinfo=UTC),
                enabled=True,
                sort_order=1,
                created_at=datetime(2026, 8, 30, tzinfo=UTC),
                updated_at=datetime(2026, 8, 30, tzinfo=UTC),
                version=1,
            )
        ],
    )


def build_services(
    *,
    kind: str = "demo",
) -> tuple[
    AssessmentService,
    SafetyService,
    InMemoryDomainDataRepository,
    InMemorySessionRepository,
    InMemoryIdempotencyRepository,
    InMemoryAuditRepository,
]:
    settings = settings_for(kind)
    repository = build_repository(kind=kind if kind != "unconfigured" else "demo")
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    audit_repository = InMemoryAuditRepository()
    token_manager = TokenManager("student-session-secret")
    idempotency = IdempotencyService(idempotency_repository)
    audit = AuditWriter(audit_repository, environment_id=f"{kind}-env")
    assessment = AssessmentService(
        settings=settings,
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        idempotency_service=idempotency,
        audit_writer=audit,
    )
    safety = SafetyService(
        settings=settings,
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        idempotency_service=idempotency,
        audit_writer=audit,
    )
    return assessment, safety, repository, sessions, idempotency_repository, audit_repository


def issue_access_token(sessions: InMemorySessionRepository) -> str:
    return TokenManager("student-session-secret").issue("student", "user-1", sessions).access_token


def phq9_safety_answers(option_key: str = "1") -> list[dict[str, object]]:
    return [
        {"question_key": "q1", "option_key": "0"},
        {"question_key": "q2", "option_key": "0"},
        {"question_key": "q3", "option_key": "0"},
        {"question_key": "q4", "option_key": "0"},
        {"question_key": "q5", "option_key": "0"},
        {"question_key": "q6", "option_key": "0"},
        {"question_key": "q7", "option_key": "0"},
        {"question_key": "q8", "option_key": "0"},
        {"question_key": "q9", "option_key": option_key},
    ]


def phq9_complete_answers(option_key: str = "1") -> list[dict[str, object]]:
    return [*phq9_safety_answers(option_key), {"question_key": "impact", "option_key": "some"}]


def start_phq9(
    assessment: AssessmentService,
    sessions: InMemorySessionRepository,
) -> tuple[str, str, int]:
    access_token = issue_access_token(sessions)
    started = assessment.start_session(
        access_token,
        module_code="phq9",
        request_id="req-start-safety",
        idempotency_key="start-safety",
    )
    return access_token, started.session_id, started.object_version


def test_can_be_safe_records_minimal_confirmation_and_never_creates_task() -> None:
    assessment, safety, repository, sessions, _, audit_repository = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)

    response = safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="can_be_safe",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id="req-safe",
        idempotency_key="safe-1",
    )

    assert response.next_step == "continue_assessment"
    assert response.result_id is None
    assert response.support_required is False
    assert response.task_created is False
    assert response.visible_projection == {
        "confirmation_source": "phq9_current_safety_confirmation",
        "current_selection": "can_be_safe",
        "resource_categories_shown": [],
        "questionnaire_completed": False,
        "task_state": None,
    }
    session = repository.get_assessment_session(session_id)
    assert session.safety_triggered is True
    assert session.safety_confirmation_state == "can_be_safe"
    assert session.answers is None
    assert repository.list_safety_support_tasks() == ()
    assert repository.extra_collection("work_tasks") == []
    assert "question_key" not in str(audit_repository.list())

    completed = assessment.complete_session(
        access_token,
        session_id=session_id,
        object_version=session.version,
        answers=phq9_complete_answers("1"),
        request_id="req-safe-complete",
        idempotency_key="safe-complete",
    )
    assert completed.completion_state == "result_ready"
    assert completed.result_state in {"ordinary", "higher_score"}
    stored_result = repository.get_assessment_result(completed.result_id or "")
    assert stored_result.safety_state == "can_be_safe"
    assert stored_result.answers_snapshot is not None
    assert repository.list_safety_support_tasks() == ()
    assert repository.extra_collection("work_tasks") == []


def test_q9_zero_rejects_safety_confirmation_without_persisting_partial_answers() -> None:
    assessment, safety, repository, sessions, _, _ = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)

    with pytest.raises(ApiException) as error:
        safety.confirm_safety(
            access_token,
            session_id=session_id,
            state="can_be_safe",
            object_version=version,
            answers=phq9_safety_answers("0"),
            request_id="req-zero",
            idempotency_key="zero-1",
        )

    assert error.value.code == "VALIDATION_FAILED"
    session = repository.get_assessment_session(session_id)
    assert session.safety_confirmation_state is None
    assert session.answers is None


def test_uncertain_requires_matching_resource_ack_before_final_restricted_result_and_task() -> None:
    assessment, safety, repository, sessions, _, _ = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)

    confirmation = safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="uncertain",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id="req-uncertain",
        idempotency_key="uncertain-1",
    )
    assert confirmation.next_step == "show_support_resources"
    assert confirmation.support_required is True
    assert confirmation.task_created is False

    with pytest.raises(ApiException) as blocked:
        assessment.complete_session(
            access_token,
            session_id=session_id,
            object_version=version + 1,
            answers=phq9_complete_answers("1"),
            request_id="req-complete-before-ack",
            idempotency_key="complete-before-ack",
        )
    assert blocked.value.code == "SAFETY_CONFIRMATION_REQUIRED"

    ack = safety.acknowledge_support_resource(
        access_token,
        session_id=session_id,
        resource_context="safety",
        resource_version="support-v1",
        object_version=version + 1,
        request_id="req-ack",
        idempotency_key="ack-1",
    )
    assert ack.resource_version == "support-v1"
    assert ack.version == version + 2

    result = assessment.complete_session(
        access_token,
        session_id=session_id,
        object_version=version + 2,
        answers=phq9_complete_answers("1"),
        request_id="req-complete-after-ack",
        idempotency_key="complete-after-ack",
    )

    assert result.completion_state == "result_ready"
    assert result.result_state == "safety_support"
    assert result.score is None
    stored_result = repository.get_assessment_result(result.result_id or "")
    assert stored_result.answers_snapshot is None
    assert stored_result.score is None
    assert stored_result.reference_band is None
    assert stored_result.ai_assist_snapshot_id is None
    assert stored_result.safety_state == "uncertain"
    session = repository.get_assessment_session(session_id)
    assert session.state == "completed"
    assert session.answers is None
    assert session.answered_count == 10
    tasks = repository.list_safety_support_tasks()
    assert len(tasks) == 1
    assert tasks[0].task_kind == "safety_support"
    assert tasks[0].safety_fact == "uncertain"
    assert tasks[0].source_result_id == stored_result.document_id
    assert tasks[0].state == "needs_action"
    assert repository.extra_collection("work_tasks")[0]["available_capability"] == "safety_support"


def test_support_resource_ack_rejects_resource_version_conflict() -> None:
    assessment, safety, repository, sessions, _, _ = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)
    safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="uncertain",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id="req-uncertain-version",
        idempotency_key="uncertain-version",
    )

    with pytest.raises(ApiException) as error:
        safety.acknowledge_support_resource(
            access_token,
            session_id=session_id,
            resource_context="safety",
            resource_version="old-support-v0",
            object_version=version + 1,
            request_id="req-ack-conflict",
            idempotency_key="ack-conflict",
        )

    assert error.value.code == "VERSION_CONFLICT"
    assert error.value.current_version == "support-v1"
    session = repository.get_assessment_session(session_id)
    assert session.safety_resource_version is None


def test_cannot_be_safe_abandons_session_creates_minimal_task_but_no_result() -> None:
    assessment, safety, repository, sessions, _, _ = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)

    response = safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="cannot_be_safe",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id="req-cannot",
        idempotency_key="cannot-1",
    )
    replay = safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="cannot_be_safe",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id="req-cannot-replay",
        idempotency_key="cannot-1",
    )

    assert response.next_step == "support_only"
    assert response.support_required is True
    assert response.task_created is True
    assert replay == response
    session = repository.get_assessment_session(session_id)
    assert session.state == "abandoned"
    assert session.answers is None
    assert repository.list_assessment_results_by_session(session_id) == ()
    tasks = repository.list_safety_support_tasks()
    assert len(tasks) == 1
    assert tasks[0].safety_fact == "cannot_be_safe"
    assert tasks[0].user_reference_id == "user-1"
    assert tasks[0].assigned_admin_id is None
    assert repository.extra_collection("work_tasks")[0]["source_id"] == tasks[0].document_id


@pytest.mark.parametrize("kind", ["authorized", "unconfigured"])
def test_task_creation_depends_on_allowed_environment(kind: str) -> None:
    assessment, safety, repository, sessions, _, _ = build_services(kind=kind)
    access_token, session_id, version = start_phq9(assessment, sessions)

    response = safety.confirm_safety(
        access_token,
        session_id=session_id,
        state="cannot_be_safe",
        object_version=version,
        answers=phq9_safety_answers("1"),
        request_id=f"req-cannot-{kind}",
        idempotency_key=f"cannot-{kind}",
    )

    assert response.task_created is (kind == "authorized")
    assert len(repository.list_safety_support_tasks()) == (1 if kind == "authorized" else 0)
    assert len(repository.extra_collection("work_tasks")) == (1 if kind == "authorized" else 0)


def test_safety_confirmation_rejects_object_version_conflict_and_tampered_fields() -> None:
    assessment, safety, repository, sessions, _, _ = build_services()
    access_token, session_id, version = start_phq9(assessment, sessions)
    saved = repository.get_assessment_session(session_id).model_copy(
        update={"safety_triggered": True}
    )
    repository.save_assessment_session(saved, expected_version=version)

    with pytest.raises(ApiException) as conflict:
        safety.confirm_safety(
            access_token,
            session_id=session_id,
            state="can_be_safe",
            object_version=version,
            answers=phq9_safety_answers("1"),
            request_id="req-conflict",
            idempotency_key="conflict-1",
        )

    assert conflict.value.code == "VERSION_CONFLICT"
    assert conflict.value.current_version == version + 1

    with pytest.raises(ApiException) as tampered:
        safety.confirm_safety(
            access_token,
            session_id=session_id,
            state="can_be_safe",
            object_version=version + 1,
            answers=[
                *phq9_safety_answers("1"),
                {"question_key": "score", "option_key": "27"},
            ],
            request_id="req-tampered",
            idempotency_key="tampered-1",
        )

    assert tampered.value.code == "VALIDATION_FAILED"
