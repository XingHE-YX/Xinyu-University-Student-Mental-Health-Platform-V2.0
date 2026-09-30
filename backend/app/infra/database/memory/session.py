"""Server-side session records; raw access and refresh tokens are never stored."""

from dataclasses import dataclass, replace
from datetime import datetime
from threading import RLock
from typing import Literal

SubjectType = Literal["student", "admin"]
SessionStatus = Literal["active", "revoked"]


@dataclass(frozen=True, slots=True)
class AuthSessionRecord:
    session_id: str
    subject_type: SubjectType
    subject_id: str
    capability: str | None
    access_token_hash: str
    refresh_token_hash: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    version: int = 1


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._records: dict[str, AuthSessionRecord] = {}
        self._access_index: dict[str, str] = {}
        self._refresh_index: dict[str, str] = {}
        self._lock = RLock()

    def save(self, record: AuthSessionRecord) -> None:
        with self._lock:
            self._records[record.session_id] = record
            self._access_index[record.access_token_hash] = record.session_id
            self._refresh_index[record.refresh_token_hash] = record.session_id

    def replace(self, record: AuthSessionRecord) -> None:
        with self._lock:
            old = self._records.get(record.session_id)
            if old is not None:
                self._access_index.pop(old.access_token_hash, None)
                self._refresh_index.pop(old.refresh_token_hash, None)
            self.save(record)

    def get_by_session_id(self, session_id: str) -> AuthSessionRecord | None:
        with self._lock:
            return self._records.get(session_id)

    def get_by_access_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        with self._lock:
            session_id = self._access_index.get(token_hash)
            return self._records.get(session_id) if session_id else None

    def get_by_refresh_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        with self._lock:
            session_id = self._refresh_index.get(token_hash)
            return self._records.get(session_id) if session_id else None

    def revoke(self, session_id: str, *, now: datetime) -> AuthSessionRecord | None:
        with self._lock:
            record = self._records.get(session_id)
            if record is None:
                return None
            if record.status == "revoked":
                return record
            revoked = replace(record, status="revoked", updated_at=now, version=record.version + 1)
            self._records[session_id] = revoked
            return revoked
