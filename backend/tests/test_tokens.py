from datetime import UTC, datetime, timedelta

import pytest

from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager


def test_tokens_are_opaque_and_only_hashes_are_stored() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)

    pair = manager.issue("student", "student-1", repository, now=now)

    record = repository.get_by_session_id(pair.session_id)
    assert record is not None
    assert pair.access_token not in record.access_token_hash
    assert pair.refresh_token not in record.refresh_token_hash
    assert pair.access_expires_at == now + timedelta(minutes=15)
    assert pair.refresh_expires_at == now + timedelta(days=30)


def test_refresh_rotates_the_refresh_token_and_recovers_server_subject() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    old_pair = manager.issue("admin", "admin-1", repository, capability="super_admin", now=now)

    subject = manager.authenticate_access(old_pair.access_token, repository, now=now)
    assert subject.subject_type == "admin"
    assert subject.subject_id == "admin-1"
    assert subject.capability == "super_admin"

    new_pair = manager.refresh(old_pair.refresh_token, repository, now=now)

    assert new_pair.refresh_token != old_pair.refresh_token
    with pytest.raises(ApiException) as error:
        manager.refresh(old_pair.refresh_token, repository, now=now)
    assert error.value.code == "SESSION_EXPIRED"


def test_expired_and_revoked_access_tokens_are_rejected() -> None:
    repository = InMemorySessionRepository()
    manager = TokenManager("test-session-secret")
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    pair = manager.issue("student", "student-1", repository, now=now)

    manager.logout(pair.access_token, repository, now=now)
    with pytest.raises(ApiException) as revoked_error:
        manager.authenticate_access(pair.access_token, repository, now=now)
    assert revoked_error.value.code == "SESSION_EXPIRED"

    expired_pair = manager.issue("student", "student-2", repository, now=now)
    with pytest.raises(ApiException) as expired_error:
        manager.authenticate_access(
            expired_pair.access_token,
            repository,
            now=now + timedelta(minutes=16),
        )
    assert expired_error.value.code == "SESSION_EXPIRED"
