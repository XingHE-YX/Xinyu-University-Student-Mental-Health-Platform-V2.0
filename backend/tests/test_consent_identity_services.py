from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

import httpx
import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import (
    AnonymousIdentityDocument,
    ConsentEventDocument,
    IdentityRecordDocument,
    UserAccountDocument,
)
from app.integrations.school_identity import (
    HttpSchoolIdentityProvider,
    SchoolIdentityVerificationResult,
)
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.protocols import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.consent_service import ConsentService
from app.services.idempotency_service import IdempotencyService
from app.services.identity_service import HmacIdentityCipher, IdentityService


class FakeSchoolIdentityProvider:
    def __init__(self, result: SchoolIdentityVerificationResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    async def verify_student(
        self,
        *,
        student_name: str,
        student_number: str,
    ) -> SchoolIdentityVerificationResult:
        self.calls.append((student_name, student_number))
        return self.result


class FakeIdentityCipher:
    def __init__(self) -> None:
        self.values: list[str] = []

    def encrypt(self, value: str) -> str:
        self.values.append(value)
        return f"cipher::{value[::-1]}"


class FailAfterUserSaveRepository(InMemoryDomainDataRepository):
    def __init__(self, *, users: list[UserAccountDocument]) -> None:
        super().__init__(users=users)
        self.fail_after_user_save = True

    def save_user(
        self,
        user: UserAccountDocument,
        *,
        expected_version: int,
    ) -> UserAccountDocument:
        saved = super().save_user(user, expected_version=expected_version)
        if self.fail_after_user_save:
            self.fail_after_user_save = False
            raise RepositoryVersionConflict(saved.version)
        return saved


class FailAfterConsentAppendRepository(InMemoryDomainDataRepository):
    def __init__(self, *, users: list[UserAccountDocument]) -> None:
        super().__init__(users=users)
        self.fail_after_append = True

    def append_consent_event(self, consent: ConsentEventDocument) -> ConsentEventDocument:
        saved = super().append_consent_event(consent)
        if self.fail_after_append:
            self.fail_after_append = False
            raise RepositoryUnavailable("consent event append failed")
        return saved


class FixedResponseTransport(httpx.AsyncBaseTransport):
    def __init__(self, *, body: bytes | None = None, error: Exception | None = None) -> None:
        self.body = body
        self.error = error

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.error is not None:
            raise self.error
        assert self.body is not None
        return httpx.Response(200, content=self.body, request=request)


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


def seed_user() -> UserAccountDocument:
    return UserAccountDocument(
        _id="user-1",
        auth_subject_hash="student-subject-hash",
        status="active",
        base_consent_status="not_accepted",
        community_consent_status="not_accepted",
        created_at=datetime(2026, 8, 30, tzinfo=UTC),
        updated_at=datetime(2026, 8, 30, tzinfo=UTC),
        version=1,
    )


def build_user(**overrides: object) -> UserAccountDocument:
    data = seed_user().model_dump()
    data.update(overrides)
    return UserAccountDocument(**data)


def build_identity_record(
    *,
    status: str = "verified",
    user_id: str = "user-1",
    record_id: str = "identity-1",
) -> IdentityRecordDocument:
    occurred_at = datetime(2026, 8, 30, 0, 3, tzinfo=UTC)
    return IdentityRecordDocument(
        _id=record_id,
        user_id=user_id,
        verification_status=cast(
            Literal["not_started", "pending", "verified", "failed", "unavailable"], status
        ),
        student_name_ciphertext="old-name-ciphertext" if status == "verified" else None,
        student_number_ciphertext="old-number-ciphertext" if status == "verified" else None,
        provider_reference_hash="old-provider-reference-hash" if status == "verified" else None,
        verified_at=occurred_at if status == "verified" else None,
        failed_reason_code="mismatch" if status == "failed" else None,
        access_version=1,
        created_at=occurred_at,
        updated_at=occurred_at,
        version=1,
    )


def build_anonymous_identity(
    *,
    user_id: str = "user-1",
    identity_id: str = "anonymous-1",
) -> AnonymousIdentityDocument:
    occurred_at = datetime(2026, 8, 30, 0, 4, tzinfo=UTC)
    return AnonymousIdentityDocument(
        _id=identity_id,
        user_id=user_id,
        display_name="树洞同学ABC123",
        generation_version="anon-v1",
        status="active",
        created_at=occurred_at,
        updated_at=occurred_at,
        version=1,
    )


def issue_student_access_token(
    sessions: InMemorySessionRepository,
    *,
    subject_id: str = "user-1",
) -> str:
    pair = TokenManager("student-session-secret").issue("student", subject_id, sessions)
    return pair.access_token


def issue_admin_access_token(sessions: InMemorySessionRepository) -> str:
    pair = TokenManager("student-session-secret").issue("admin", "admin-1", sessions)
    return pair.access_token


def test_accept_withdraw_and_reaccept_community_consent_are_versioned_and_append_only() -> None:
    repository = InMemoryDomainDataRepository(users=[seed_user()])
    sessions = InMemorySessionRepository()
    audit_repository = InMemoryAuditRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    base_result = service.accept_base_consent(
        access_token,
        document_version="base-v1",
        user_version=1,
        request_id="req_base_accept",
        idempotency_key="idem-base-1",
    )
    withdrawn = service.withdraw_community_consent(
        access_token,
        document_version="community-v1",
        user_version=2,
        request_id="req_comm_withdraw",
        idempotency_key="idem-community-withdraw",
    )
    reaccepted = service.accept_community_consent(
        access_token,
        document_version="community-v2",
        user_version=3,
        request_id="req_comm_reaccept",
        idempotency_key="idem-community-reaccept",
    )

    assert base_result.base_consent_status == "accepted"
    assert withdrawn.community_consent_status == "withdrawn"
    assert reaccepted.community_consent_status == "accepted"
    assert reaccepted.community_consent_version == "community-v2"
    assert [event.action for event in repository.list_consent_events("user-1")] == [
        "accepted",
        "withdrawn",
        "accepted",
    ]
    assert [event.document_version for event in repository.list_consent_events("user-1")] == [
        "base-v1",
        "community-v1",
        "community-v2",
    ]


def test_withdrawn_community_consent_blocks_posting_without_deleting_existing_content() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                community_consent_status="accepted",
                community_consent_version="community-v1",
                community_consent_at=datetime(2026, 8, 30, 0, 2, tzinfo=UTC),
                version=3,
            )
        ],
        extra_collections={
            "treehole_posts": [{"_id": "post-1", "user_id": "user-1", "body": "保留内容"}]
        },
    )
    sessions = InMemorySessionRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    service.withdraw_community_consent(
        access_token,
        document_version="community-v1",
        user_version=3,
        request_id="req_comm_withdraw",
        idempotency_key="idem-community-withdraw",
    )

    with pytest.raises(ApiException) as error:
        service.ensure_community_write_allowed(access_token)

    assert error.value.status_code == 403
    assert error.value.code == "CONSENT_REQUIRED"
    assert repository.extra_collection("treehole_posts")[0]["body"] == "保留内容"


def test_community_consent_actions_require_base_consent() -> None:
    repository = InMemoryDomainDataRepository(users=[seed_user()])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    for action, method, key in [
        ("accepted", service.accept_community_consent, "idem-community-before-base-accept"),
        ("withdrawn", service.withdraw_community_consent, "idem-community-before-base-withdraw"),
    ]:
        with pytest.raises(ApiException) as error:
            method(
                access_token,
                document_version="community-v1",
                user_version=1,
                request_id=f"req-community-before-base-{action}",
                idempotency_key=key,
            )

        assert error.value.status_code == 403
        assert error.value.code == "CONSENT_REQUIRED"

    assert repository.get_user("user-1") == seed_user()
    assert repository.list_consent_events("user-1") == ()


def test_community_write_guard_rejects_an_unbound_verified_identity_record() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                community_consent_status="accepted",
                community_consent_version="community-v1",
            )
        ],
        identities=[build_identity_record()],
    )
    sessions = InMemorySessionRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        service.ensure_community_write_allowed(access_token)

    assert error.value.status_code == 403
    assert error.value.code == "IDENTITY_REQUIRED"


def test_identity_status_ignores_an_unbound_identity_record() -> None:
    repository = InMemoryDomainDataRepository(
        users=[build_user()],
        identities=[build_identity_record()],
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    assert service.get_identity_status(access_token) == {
        "verification_status": "not_started",
        "identity_status": "unverified",
    }


@pytest.mark.asyncio
async def test_identity_verification_success_encrypts_and_creates_anonymous_identity() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    audit_repository = InMemoryAuditRepository()
    cipher = FakeIdentityCipher()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
        identity_cipher=cipher,
    )
    access_token = issue_student_access_token(sessions)

    result = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_success",
        idempotency_key="idem-identity-success",
    )

    identity_record = repository.get_identity_record(result.identity_record_id)
    assert result.anonymous_identity_id is not None
    anonymous_identity = repository.get_anonymous_identity(result.anonymous_identity_id)
    user = repository.get_user("user-1")

    assert result.verification_status == "verified"
    assert identity_record.student_name_ciphertext == "cipher::雨小王"
    assert identity_record.student_number_ciphertext == "cipher::10006202"
    assert identity_record.provider_reference_hash != "school-ref-1"
    assert user.identity_record_id == identity_record.document_id
    assert user.anonymous_identity_id == anonymous_identity.document_id
    assert anonymous_identity.display_name
    assert "王小雨" not in str(user.model_dump())
    assert "20260001" not in str(user.model_dump())
    assert "王小雨" not in str(anonymous_identity.model_dump())
    assert "20260001" not in str(audit_repository.list())


@pytest.mark.asyncio
async def test_identity_binding_rolls_back_when_final_user_save_conflicts() -> None:
    original_user = build_user(
        base_consent_status="accepted",
        base_consent_version="base-v1",
        base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
        version=2,
    )
    repository = FailAfterUserSaveRepository(users=[original_user])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="王小雨",
            student_number="20260001",
            user_version=2,
            request_id="req_identity_atomic_rollback",
            idempotency_key="idem-identity-atomic-rollback",
        )

    with pytest.raises(ApiException) as replay_error:
        await service.verify_student_identity(
            access_token,
            student_name="王小雨",
            student_number="20260001",
            user_version=2,
            request_id="req_identity_atomic_rollback_replay",
            idempotency_key="idem-identity-atomic-rollback",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/identity/verify",
        "idem-identity-atomic-rollback",
        now=datetime.now(UTC),
    )
    assert error.value.code == "VERSION_CONFLICT"
    assert replay_error.value.code == error.value.code
    assert replay_error.value.status_code == error.value.status_code
    assert replay_error.value.retryable == error.value.retryable
    assert replay_error.value.current_version == error.value.current_version
    assert replay_error.value.message == error.value.message
    assert repository.get_user("user-1") == original_user
    with pytest.raises(RepositoryNotFound):
        repository.get_identity_record("identity_0001")
    assert repository.list_anonymous_identities("user-1") == ()
    assert repository.next_identity_record_id() == "identity_0001"
    assert repository.next_anonymous_identity_id() == "anonymous_0001"
    assert record is not None
    assert record.outcome == "failure"


def test_community_consent_append_failure_rolls_back_user_and_event() -> None:
    original_user = seed_user()
    repository = FailAfterConsentAppendRepository(users=[original_user])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as first_error:
        service.accept_base_consent(
            access_token,
            document_version="base-v1",
            user_version=1,
            request_id="req_consent_append_failure",
            idempotency_key="idem-consent-append-failure",
        )

    with pytest.raises(ApiException) as replay_error:
        service.accept_base_consent(
            access_token,
            document_version="base-v1",
            user_version=1,
            request_id="req_consent_append_failure_replay",
            idempotency_key="idem-consent-append-failure",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/consents/base_service",
        "idem-consent-append-failure",
        now=datetime.now(UTC),
    )
    assert first_error.value.code == "DEPENDENCY_UNAVAILABLE"
    assert first_error.value.status_code == 503
    assert first_error.value.retryable is True
    assert replay_error.value.code == first_error.value.code
    assert replay_error.value.status_code == first_error.value.status_code
    assert replay_error.value.retryable == first_error.value.retryable
    assert replay_error.value.message == first_error.value.message
    assert repository.get_user("user-1") == original_user
    assert repository.list_consent_events("user-1") == ()
    assert record is not None
    assert record.outcome == "failure"


@pytest.mark.asyncio
async def test_identity_verification_failed_records_failed_status_without_storing_plaintext() -> (
    None
):
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="failed", failed_reason_code="mismatch")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    result = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_failed",
        idempotency_key="idem-identity-failed",
    )

    identity_record = repository.get_identity_record(result.identity_record_id)

    assert result.verification_status == "failed"
    assert identity_record.student_name_ciphertext is None
    assert identity_record.student_number_ciphertext is None
    assert repository.list_anonymous_identities("user-1") == ()


@pytest.mark.asyncio
async def test_failed_identity_reason_is_safe_when_provider_returns_identity_input() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=FakeSchoolIdentityProvider(
            SchoolIdentityVerificationResult(
                status="failed",
                failed_reason_code="name=王小雨;student_number=20260001",
            )
        ),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    result = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_failed_reason",
        idempotency_key="idem-identity-failed-reason",
    )
    identity_record = repository.get_identity_record(result.identity_record_id)

    assert identity_record.failed_reason_code == "provider_rejected"
    assert "王小雨" not in str(identity_record)
    assert "20260001" not in str(identity_record)


@pytest.mark.asyncio
async def test_identity_verification_unavailable_never_falls_back_to_verified() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=FakeSchoolIdentityProvider(
            SchoolIdentityVerificationResult(status="unavailable")
        ),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    result = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_unavailable",
        idempotency_key="idem-identity-unavailable",
    )

    assert result.verification_status == "unavailable"
    assert repository.get_user("user-1").anonymous_identity_id is None


@pytest.mark.asyncio
async def test_identity_status_projection_is_separate_from_anonymous_identity_projection() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=FakeSchoolIdentityProvider(
            SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
        ),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)
    await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_projection",
        idempotency_key="idem-identity-projection",
    )

    identity_status = service.get_identity_status(access_token)
    anonymous_identity = service.get_anonymous_identity(access_token)

    assert identity_status == {
        "verification_status": "verified",
        "identity_status": "verified",
    }
    assert set(anonymous_identity) == {
        "anonymous_identity_id",
        "display_name",
        "display_scope",
        "generation_version",
        "status",
    }
    assert (
        anonymous_identity["anonymous_identity_id"]
        == repository.get_user("user-1").anonymous_identity_id
    )
    assert anonymous_identity["display_scope"] == "treehole_only"
    assert anonymous_identity["generation_version"] == "anon-v1"
    assert anonymous_identity["status"] == "active"


@pytest.mark.asyncio
async def test_identity_idempotency_digest_is_stable_private_and_distinguishes_inputs() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    first = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_idem_1",
        idempotency_key="idem-identity-stable",
    )
    replay = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_idem_2",
        idempotency_key="idem-identity-stable",
    )

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="李小雨",
            student_number="20260001",
            user_version=2,
            request_id="req_identity_idem_3",
            idempotency_key="idem-identity-stable",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/identity/verify",
        "idem-identity-stable",
        now=datetime.now(UTC),
    )
    assert first == replay
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    assert provider.calls == [("王小雨", "20260001")]
    assert record is not None
    assert record.outcome == "success"
    assert "王小雨" not in str(record)
    assert "20260001" not in str(record)
    assert record.request_hash


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("student_name", "student_number"),
    [("", "20260001"), ("   ", "20260001"), ("王小雨", ""), ("王小雨", "   ")],
)
async def test_identity_verification_rejects_blank_identity_input_before_provider(
    student_name: str,
    student_number: str,
) -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name=student_name,
            student_number=student_number,
            user_version=2,
            request_id="req_identity_blank",
            idempotency_key=f"idem-identity-blank-{student_name}-{student_number}",
        )

    assert error.value.status_code == 422
    assert error.value.code == "VALIDATION_FAILED"
    assert provider.calls == []
    assert repository.get_user("user-1").identity_record_id is None
    assert repository.list_anonymous_identities("user-1") == ()
    assert (
        idempotency_repository.get(
            "student",
            "user-1",
            "/identity/verify",
            f"idem-identity-blank-{student_name}-{student_number}",
            now=datetime.now(UTC),
        )
        is None
    )


@pytest.mark.asyncio
async def test_identity_verification_rejects_non_student_subject_before_provider() -> None:
    repository = InMemoryDomainDataRepository()
    sessions = InMemorySessionRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_admin_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="王小雨",
            student_number="20260001",
            user_version=1,
            request_id="req_identity_admin_subject",
            idempotency_key="idem-identity-admin-subject",
        )

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"
    assert provider.calls == []


def test_community_write_guard_rejects_non_student_subject() -> None:
    sessions = InMemorySessionRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=InMemoryDomainDataRepository(),
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_admin_access_token(sessions)

    with pytest.raises(ApiException) as error:
        service.ensure_community_write_allowed(access_token)

    assert error.value.status_code == 403
    assert error.value.code == "FORBIDDEN"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user_overrides", "expected_code"),
    [
        ({"status": "stopped", "base_consent_status": "accepted"}, "FORBIDDEN"),
        ({"status": "active", "base_consent_status": "not_accepted"}, "CONSENT_REQUIRED"),
    ],
)
async def test_identity_verification_checks_account_and_base_consent_before_provider(
    user_overrides: dict[str, str],
    expected_code: str,
) -> None:
    repository = InMemoryDomainDataRepository(users=[build_user(**user_overrides)])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="王小雨",
            student_number="20260001",
            user_version=1,
            request_id="req_identity_precondition",
            idempotency_key="idem-identity-precondition",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/identity/verify",
        "idem-identity-precondition",
        now=datetime.now(UTC),
    )
    assert error.value.status_code == 403
    assert error.value.code == expected_code
    assert provider.calls == []
    assert repository.get_user("user-1").version == 1
    assert record is None or record.outcome != "processing"


@pytest.mark.parametrize(
    ("status", "base_status", "community_status", "expected_code"),
    [
        ("verified", "accepted", "accepted", "FORBIDDEN"),
        ("verified", "not_accepted", "accepted", "CONSENT_REQUIRED"),
        ("verified", "accepted", "withdrawn", "CONSENT_REQUIRED"),
        ("failed", "accepted", "accepted", "IDENTITY_REQUIRED"),
        (None, "accepted", "accepted", "IDENTITY_REQUIRED"),
    ],
)
def test_community_write_guard_requires_active_consented_verified_account(
    status: str | None,
    base_status: str,
    community_status: str,
    expected_code: str,
) -> None:
    identity = build_identity_record(status=status) if status is not None else None
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                status="stopped" if expected_code == "FORBIDDEN" else "active",
                base_consent_status=base_status,
                base_consent_version="base-v1" if base_status == "accepted" else None,
                community_consent_status=community_status,
                community_consent_version=(
                    "community-v1" if community_status != "not_accepted" else None
                ),
                identity_record_id=identity.document_id if identity is not None else None,
            )
        ],
        identities=[identity] if identity is not None else [],
    )
    sessions = InMemorySessionRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        service.ensure_community_write_allowed(access_token)

    assert error.value.status_code == 403
    assert error.value.code == expected_code


@pytest.mark.asyncio
async def test_verified_identity_reverification_preserves_state_without_provider_call() -> None:
    identity = build_identity_record()
    anonymous = build_anonymous_identity()
    user = build_user(
        base_consent_status="accepted",
        base_consent_version="base-v1",
        base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
        identity_record_id=identity.document_id,
        anonymous_identity_id=anonymous.document_id,
        version=3,
    )
    repository = InMemoryDomainDataRepository(
        users=[user], identities=[identity], anonymous_identities=[anonymous]
    )
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="failed", failed_reason_code="mismatch")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="李小雨",
            student_number="20260002",
            user_version=3,
            request_id="req_identity_reverify",
            idempotency_key="idem-identity-reverify",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/identity/verify",
        "idem-identity-reverify",
        now=datetime.now(UTC),
    )
    assert error.value.status_code == 409
    assert error.value.code == "VERSION_CONFLICT"
    assert provider.calls == []
    assert repository.get_user("user-1") == user
    assert repository.get_identity_record(identity.document_id) == identity
    assert repository.get_anonymous_identity(anonymous.document_id) == anonymous
    assert record is None or record.outcome != "processing"


@pytest.mark.asyncio
async def test_pending_identity_cannot_be_submitted_again_before_provider_call() -> None:
    identity = build_identity_record(status="pending")
    user = build_user(
        base_consent_status="accepted",
        base_consent_version="base-v1",
        base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
        identity_record_id=identity.document_id,
        version=3,
    )
    repository = InMemoryDomainDataRepository(users=[user], identities=[identity])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    provider = FakeSchoolIdentityProvider(
        SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-2")
    )
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    with pytest.raises(ApiException) as error:
        await service.verify_student_identity(
            access_token,
            student_name="李小雨",
            student_number="20260002",
            user_version=3,
            request_id="req_identity_pending",
            idempotency_key="idem-identity-pending",
        )

    record = idempotency_repository.get(
        "student",
        "user-1",
        "/identity/verify",
        "idem-identity-pending",
        now=datetime.now(UTC),
    )
    assert error.value.code == "VERSION_CONFLICT"
    assert provider.calls == []
    assert repository.get_user("user-1") == user
    assert repository.get_identity_record(identity.document_id) == identity
    assert record is None or record.outcome != "processing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_result",
    [
        SchoolIdentityVerificationResult(status="failed", failed_reason_code="mismatch"),
        SchoolIdentityVerificationResult(status="unavailable"),
    ],
)
async def test_failed_or_unavailable_identity_can_be_retried(
    first_result: SchoolIdentityVerificationResult,
) -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    provider = FakeSchoolIdentityProvider(first_result)
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=provider,
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
        identity_cipher=FakeIdentityCipher(),
    )
    access_token = issue_student_access_token(sessions)

    first = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_retry_1",
        idempotency_key="idem-identity-retry-1",
    )
    provider.result = SchoolIdentityVerificationResult(
        status="verified", provider_reference="school-ref-2"
    )
    second = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=3,
        request_id="req_identity_retry_2",
        idempotency_key="idem-identity-retry-2",
    )

    assert first.verification_status == first_result.status
    assert second.verification_status == "verified"
    assert len(provider.calls) == 2


@pytest.mark.parametrize(
    ("record_status", "session_status"),
    [
        ("not_started", "unverified"),
        ("pending", "pending"),
        ("verified", "verified"),
        ("failed", "unverified"),
        ("unavailable", "unverified"),
    ],
)
def test_identity_status_projection_has_domain_status_and_student_session_mapping(
    record_status: str,
    session_status: str,
) -> None:
    identity = (
        None if record_status == "not_started" else build_identity_record(status=record_status)
    )
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(identity_record_id=identity.document_id if identity is not None else None)
        ],
        identities=[identity] if identity is not None else [],
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    assert service.get_identity_status(access_token) == {
        "verification_status": record_status,
        "identity_status": session_status,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [b"not-json", b"null", b'["verified"]'])
async def test_school_identity_adapter_normalizes_malformed_json_to_unavailable(
    body: bytes,
) -> None:
    provider = HttpSchoolIdentityProvider(
        provider_url="https://identity.example.test",
        transport=FixedResponseTransport(body=body),
    )

    result = await provider.verify_student(student_name="王小雨", student_number="20260001")

    assert result == SchoolIdentityVerificationResult(status="unavailable")


@pytest.mark.asyncio
async def test_school_identity_adapter_normalizes_response_exception_to_unavailable() -> None:
    provider = HttpSchoolIdentityProvider(
        provider_url="https://identity.example.test",
        transport=FixedResponseTransport(error=RuntimeError("provider response failed")),
    )

    result = await provider.verify_student(student_name="王小雨", student_number="20260001")

    assert result == SchoolIdentityVerificationResult(status="unavailable")


@pytest.mark.asyncio
async def test_default_identity_cipher_does_not_store_plaintext() -> None:
    repository = InMemoryDomainDataRepository(
        users=[
            build_user(
                base_consent_status="accepted",
                base_consent_version="base-v1",
                base_consent_at=datetime(2026, 8, 30, 0, 1, tzinfo=UTC),
                version=2,
            )
        ]
    )
    sessions = InMemorySessionRepository()
    service = IdentityService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        school_identity_provider=FakeSchoolIdentityProvider(
            SchoolIdentityVerificationResult(status="verified", provider_reference="school-ref-1")
        ),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    result = await service.verify_student_identity(
        access_token,
        student_name="王小雨",
        student_number="20260001",
        user_version=2,
        request_id="req_identity_default_cipher",
        idempotency_key="idem-identity-default-cipher",
    )
    identity_record = repository.get_identity_record(result.identity_record_id)

    assert identity_record.student_name_ciphertext is not None
    assert identity_record.student_number_ciphertext is not None
    assert identity_record.student_name_ciphertext.startswith("enc:v1:")
    assert identity_record.student_number_ciphertext.startswith("enc:v1:")
    assert "王小雨" not in identity_record.student_name_ciphertext
    assert "20260001" not in identity_record.student_number_ciphertext


def test_identity_cipher_uses_a_fresh_nonce_for_repeated_plaintext() -> None:
    cipher = HmacIdentityCipher("identity-secret")

    first = cipher.encrypt("王小雨")
    second = cipher.encrypt("王小雨")

    assert first.startswith("enc:v1:")
    assert second.startswith("enc:v1:")
    assert first != second
    assert "王小雨" not in first
    assert "王小雨" not in second


def test_session_expiration_and_version_conflict_block_private_mutations() -> None:
    repository = InMemoryDomainDataRepository(users=[seed_user()])
    sessions = InMemorySessionRepository()
    idempotency_repository = InMemoryIdempotencyRepository()
    access_token = issue_student_access_token(sessions)
    token_manager = TokenManager("student-session-secret")
    token_manager.logout(access_token, sessions)
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        idempotency_service=IdempotencyService(idempotency_repository),
        audit_writer=AuditWriter(InMemoryAuditRepository(), environment_id="demo-env"),
    )

    with pytest.raises(ApiException) as session_error:
        service.accept_base_consent(
            access_token,
            document_version="base-v1",
            user_version=1,
            request_id="req_expired",
            idempotency_key="idem-expired",
        )
    with pytest.raises(ApiException) as version_error:
        fresh_token = issue_student_access_token(sessions)
        service.accept_base_consent(
            fresh_token,
            document_version="base-v1",
            user_version=9,
            request_id="req_version_conflict",
            idempotency_key="idem-version-conflict",
        )

    assert session_error.value.code == "SESSION_EXPIRED"
    assert version_error.value.code == "VERSION_CONFLICT"
    assert version_error.value.status_code == 409
    assert version_error.value.retryable is False
    assert version_error.value.current_version == 1
    with pytest.raises(ApiException) as failed_replay_error:
        service.accept_base_consent(
            fresh_token,
            document_version="base-v1",
            user_version=9,
            request_id="req_version_conflict_replay",
            idempotency_key="idem-version-conflict",
        )
    version_record = idempotency_repository.get(
        "student",
        "user-1",
        "/consents/base_service",
        "idem-version-conflict",
        now=datetime.now(UTC),
    )
    assert failed_replay_error.value.code == "VERSION_CONFLICT"
    assert failed_replay_error.value.status_code == version_error.value.status_code
    assert failed_replay_error.value.retryable == version_error.value.retryable
    assert failed_replay_error.value.current_version == version_error.value.current_version
    assert failed_replay_error.value.message == version_error.value.message
    assert version_record is None or version_record.outcome != "processing"


def test_idempotent_replay_does_not_duplicate_consent_events_or_audit_entries() -> None:
    repository = InMemoryDomainDataRepository(users=[seed_user()])
    sessions = InMemorySessionRepository()
    audit_repository = InMemoryAuditRepository()
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=TokenManager("student-session-secret"),
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
        audit_writer=AuditWriter(audit_repository, environment_id="demo-env"),
    )
    access_token = issue_student_access_token(sessions)

    first = service.accept_base_consent(
        access_token,
        document_version="base-v1",
        user_version=1,
        request_id="req_same_1",
        idempotency_key="idem-same-request",
    )
    replay = service.accept_base_consent(
        access_token,
        document_version="base-v1",
        user_version=1,
        request_id="req_same_2",
        idempotency_key="idem-same-request",
    )

    assert first == replay
    assert len(repository.list_consent_events("user-1")) == 1
    assert len(audit_repository.list()) == 1
