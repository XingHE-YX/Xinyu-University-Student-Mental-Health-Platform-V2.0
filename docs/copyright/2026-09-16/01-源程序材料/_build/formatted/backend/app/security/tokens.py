"""Opaque access and rotating refresh tokens backed by hashed session records."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from app.repositories.session_repository import (
    AuthSessionRecord,
    InMemorySessionRepository,
)
from app.schemas.errors import ApiException

TokenSubjectType = Literal["student", "admin"]


@dataclass(frozen=True)
class TokenPair:
    session_id: str
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


@dataclass(frozen=True)
class AuthenticatedSubject:
    session_id: str
    subject_type: TokenSubjectType
    subject_id: str
    capability: str | None
    session_expires_at: datetime


class TokenManager:
    STUDENT_ACCESS_TTL = timedelta(minutes=15)
    STUDENT_REFRESH_TTL = timedelta(days=30)
    ADMIN_ACCESS_TTL = timedelta(minutes=15)
    ADMIN_REFRESH_TTL = timedelta(hours=8)

    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("token secret cannot be empty")
        self._secret = secret.encode("utf-8")

    def issue(
        self,
        subject_type: TokenSubjectType,
        subject_id: str,
        repository: InMemorySessionRepository,
        *,
        capability: str | None = None,
        now: datetime | None = None,
    ) -> TokenPair:
        issued_at = _utc(now or datetime.now(UTC))
        access_ttl, refresh_ttl = self._ttls(subject_type)
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        pair = TokenPair(
            session_id=f"sess_{uuid4().hex}",
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=issued_at + access_ttl,
            refresh_expires_at=issued_at + refresh_ttl,
        )
        repository.save(
            AuthSessionRecord(
                session_id=pair.session_id,
                subject_type=subject_type,
                subject_id=subject_id,
                capability=capability,
                access_token_hash=self.hash_token(access_token),
                refresh_token_hash=self.hash_token(refresh_token),
                access_expires_at=pair.access_expires_at,
                refresh_expires_at=pair.refresh_expires_at,
                status="active",
                created_at=issued_at,
                updated_at=issued_at,
            )
        )
        return pair

    def authenticate_access(
        self,
        access_token: str,
        repository: InMemorySessionRepository,
        *,
        now: datetime | None = None,
    ) -> AuthenticatedSubject:
        record = repository.get_by_access_token_hash(self.hash_token(access_token))
        current = _utc(now or datetime.now(UTC))
        if record is None:
            raise ApiException(401, "AUTH_REQUIRED")
        if record.status != "active" or record.access_expires_at <= current:
            raise ApiException(401, "SESSION_EXPIRED")
        return AuthenticatedSubject(
            session_id=record.session_id,
            subject_type=record.subject_type,
            subject_id=record.subject_id,
            capability=record.capability,
            session_expires_at=record.access_expires_at,
        )

    def refresh(
        self,
        refresh_token: str,
        repository: InMemorySessionRepository,
        *,
        expected_subject_type: TokenSubjectType | None = None,
        now: datetime | None = None,
    ) -> TokenPair:
        current = _utc(now or datetime.now(UTC))
        record = repository.get_by_refresh_token_hash(self.hash_token(refresh_token))
        if record is None or record.status != "active" or record.refresh_expires_at <= current:
            raise ApiException(401, "SESSION_EXPIRED")
        if expected_subject_type is not None and record.subject_type != expected_subject_type:
            raise ApiException(401, "AUTH_REQUIRED")

        access_token = secrets.token_urlsafe(32)
        new_refresh_token = secrets.token_urlsafe(32)
        access_ttl, refresh_ttl = self._ttls(record.subject_type)
        pair = TokenPair(
            session_id=record.session_id,
            access_token=access_token,
            refresh_token=new_refresh_token,
            access_expires_at=current + access_ttl,
            refresh_expires_at=current + refresh_ttl,
        )
        repository.replace(
            AuthSessionRecord(
                session_id=record.session_id,
                subject_type=record.subject_type,
                subject_id=record.subject_id,
                capability=record.capability,
                access_token_hash=self.hash_token(access_token),
                refresh_token_hash=self.hash_token(new_refresh_token),
                access_expires_at=pair.access_expires_at,
                refresh_expires_at=pair.refresh_expires_at,
                status="active",
                created_at=record.created_at,
                updated_at=current,
                version=record.version + 1,
            )
        )
        return pair

    def logout(
        self,
        access_token: str,
        repository: InMemorySessionRepository,
        *,
        expected_subject_type: TokenSubjectType | None = None,
        now: datetime | None = None,
    ) -> None:
        record = repository.get_by_access_token_hash(self.hash_token(access_token))
        if record is None:
            raise ApiException(401, "AUTH_REQUIRED")
        if expected_subject_type is not None and record.subject_type != expected_subject_type:
            raise ApiException(403, "FORBIDDEN")
        repository.revoke(record.session_id, now=_utc(now or datetime.now(UTC)))

    def hash_token(self, token: str) -> str:
        return hmac.new(self._secret, token.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def _ttls(cls, subject_type: TokenSubjectType) -> tuple[timedelta, timedelta]:
        if subject_type == "student":
            return cls.STUDENT_ACCESS_TTL, cls.STUDENT_REFRESH_TTL
        return cls.ADMIN_ACCESS_TTL, cls.ADMIN_REFRESH_TTL


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
