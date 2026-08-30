from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import UserAccountDocument
from app.integrations.school_identity import SchoolIdentityVerificationResult
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.consent_service import ConsentService
from app.services.idempotency_service import IdempotencyService
from app.services.identity_service import IdentityService


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


def issue_student_access_token(
    sessions: InMemorySessionRepository,
    *,
    subject_id: str = "user-1",
) -> str:
    pair = TokenManager("student-session-secret").issue("student", subject_id, sessions)
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

    assert identity_status == {"verification_status": "verified"}
    assert set(anonymous_identity) == {"anonymous_identity_id", "display_name"}


def test_session_expiration_and_version_conflict_block_private_mutations() -> None:
    repository = InMemoryDomainDataRepository(users=[seed_user()])
    sessions = InMemorySessionRepository()
    access_token = issue_student_access_token(sessions)
    token_manager = TokenManager("student-session-secret")
    token_manager.logout(access_token, sessions)
    service = ConsentService(
        settings=configured_settings(),
        repository=repository,
        session_repository=sessions,
        token_manager=token_manager,
        idempotency_service=IdempotencyService(InMemoryIdempotencyRepository()),
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
