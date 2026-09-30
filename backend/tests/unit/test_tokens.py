from datetime import UTC, datetime, timedelta

import pytest

from app.infra.config.types import SessionConfig
from app.infra.database.memory.session import InMemorySessionRepository
from app.infra.security.tokens import TokenManager
from app.infra.serializer.error.common import ApiException


async def test_tokens_are_opaque_and_only_hashes_are_stored() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)

    pair = await manager.issue("student", "student-1", repository, now=now)

    record = await repository.get_by_session_id(pair.session_id)
    assert record is not None
    assert pair.access_token not in record.access_token_hash
    assert pair.refresh_token not in record.refresh_token_hash
    assert pair.access_expires_at == now + timedelta(minutes=15)
    assert pair.refresh_expires_at == now + timedelta(days=30)


async def test_refresh_rotates_the_refresh_token_and_recovers_server_subject() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    old_pair = await manager.issue(
        "admin", "admin-1", repository, capability="super_admin", now=now
    )

    subject = await manager.authenticate_access(old_pair.access_token, repository, now=now)
    assert subject.subject_type == "admin"
    assert subject.subject_id == "admin-1"
    assert subject.capability == "super_admin"

    new_pair = await manager.refresh(old_pair.refresh_token, repository, now=now)

    assert new_pair.refresh_token != old_pair.refresh_token
    with pytest.raises(ApiException) as error:
        (await manager.refresh(old_pair.refresh_token, repository, now=now))
    assert error.value.code == "SESSION_EXPIRED"


async def test_expired_and_revoked_access_tokens_are_rejected() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    pair = await manager.issue("student", "student-1", repository, now=now)

    (await manager.logout(pair.access_token, repository, now=now))
    with pytest.raises(ApiException) as revoked_error:
        (await manager.authenticate_access(pair.access_token, repository, now=now))
    assert revoked_error.value.code == "SESSION_EXPIRED"

    expired_pair = await manager.issue("student", "student-2", repository, now=now)
    with pytest.raises(ApiException) as expired_error:
        (
            await manager.authenticate_access(
                expired_pair.access_token,
                repository,
                now=now + timedelta(minutes=16),
            )
        )
    assert expired_error.value.code == "SESSION_EXPIRED"


@pytest.mark.parametrize("subject_type,refresh_seconds", [("student", 7200), ("admin", 1800)])
async def test_validated_session_settings_control_issue_and_refresh(
    subject_type: str, refresh_seconds: int
) -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager(
        "test-session-secret",
        config=SessionConfig(
            access_ttl_seconds=120,
            student_refresh_ttl_seconds=7200,
            admin_refresh_ttl_seconds=1800,
        ),
    )
    now = datetime(2026, 9, 30, tzinfo=UTC)
    pair = await manager.issue(subject_type, "subject", repository, now=now)  # type: ignore[arg-type]
    assert pair.access_expires_at == now + timedelta(seconds=120)
    assert pair.refresh_expires_at == now + timedelta(seconds=refresh_seconds)
    refreshed_at = now + timedelta(seconds=60)
    rotated = await manager.refresh(pair.refresh_token, repository, now=refreshed_at)
    assert rotated.access_expires_at == refreshed_at + timedelta(seconds=120)
    assert rotated.refresh_expires_at == refreshed_at + timedelta(seconds=refresh_seconds)
