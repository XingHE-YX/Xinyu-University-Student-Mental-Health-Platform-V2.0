"""Server-side session records; raw access and refresh tokens are never stored."""

from dataclasses import replace
from datetime import datetime

from app.infra.database.memory.transaction import MemoryUnitOfWork
from app.infra.database.records import AuthSessionRecord as AuthSessionRecord
from app.infra.database.records import SessionStatus as SessionStatus
from app.infra.database.records import SubjectType as SubjectType
from app.infra.logger.common import traced
from app.infra.serializer.error.common import ApiException


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._records: dict[str, AuthSessionRecord] = {}
        self._access_index: dict[str, str] = {}
        self._refresh_index: dict[str, str] = {}
        self._lock = MemoryUnitOfWork()
        self._lock.register(self)

    @traced
    async def save(self, record: AuthSessionRecord) -> None:
        async with self._lock:
            self._records[record.session_id] = record
            self._access_index[record.access_token_hash] = record.session_id
            self._refresh_index[record.refresh_token_hash] = record.session_id

    @traced
    async def replace(self, record: AuthSessionRecord) -> None:
        async with self._lock:
            old = self._records.get(record.session_id)
            if old is None or old.version != record.version - 1 or old.status != "active":
                raise ApiException(401, "SESSION_EXPIRED")
            if old is not None:
                self._access_index.pop(old.access_token_hash, None)
                self._refresh_index.pop(old.refresh_token_hash, None)
            (await self.save(record))

    @traced
    async def get_by_session_id(self, session_id: str) -> AuthSessionRecord | None:
        async with self._lock:
            return self._records.get(session_id)

    @traced
    async def get_by_access_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        async with self._lock:
            session_id = self._access_index.get(token_hash)
            return self._records.get(session_id) if session_id else None

    @traced
    async def get_by_refresh_token_hash(self, token_hash: str) -> AuthSessionRecord | None:
        async with self._lock:
            session_id = self._refresh_index.get(token_hash)
            return self._records.get(session_id) if session_id else None

    @traced
    async def revoke(self, session_id: str, *, now: datetime) -> AuthSessionRecord | None:
        async with self._lock:
            record = self._records.get(session_id)
            if record is None:
                return None
            if record.status == "revoked":
                return record
            revoked = replace(record, status="revoked", updated_at=now, version=record.version + 1)
            self._records[session_id] = revoked
            return revoked
