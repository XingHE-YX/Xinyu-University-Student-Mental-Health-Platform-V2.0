"""Daily mood recording and history use cases."""

from __future__ import annotations

import base64
import binascii
import json
import logging
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from app.audit.writer import AuditWriter
from app.domain.models import DailyMoodRecordDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)

logger = logging.getLogger(__name__)

SHANGHAI = ZoneInfo("Asia/Shanghai")
MoodCode = Literal["pleasant", "calm", "tired", "anxious", "low", "irritable"]


class MoodFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    record_date: str
    mood_code: MoodCode
    saved_at: datetime
    version: int


class DeletedMoodFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    deleted_at: datetime
    version: int


class MoodHistoryPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MoodFact]
    next_cursor: str | None


class MoodService:
    MOOD_LABELS: dict[str, str] = {
        "pleasant": "愉快",
        "calm": "平静",
        "tired": "疲惫",
        "anxious": "焦虑",
        "low": "低落",
        "irritable": "烦躁",
    }

    def __init__(
        self,
        *,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
        now_provider: object | None = None,
    ) -> None:
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer
        self._now_provider = now_provider

    def record_today_mood(
        self,
        access_token: str,
        *,
        mood_code: str,
        record_date: str,
        request_id: str,
        idempotency_key: str,
    ) -> MoodFact:
        if mood_code not in self.MOOD_LABELS:
            raise ApiException(422, "VALIDATION_FAILED")
        if record_date != self._today():
            raise ApiException(422, "VALIDATION_FAILED")
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            "/daily-moods",
            idempotency_key,
            {"mood_code": mood_code, "record_date": record_date},
        )
        if reservation.replayed:
            return _mood_fact_from_digest(reservation.record.response_digest)

        try:
            self._ensure_private_access(subject.subject_id)
            current = self._now()
            with self.repository.transaction():
                existing = self.repository.get_daily_mood_by_user_date(
                    subject.subject_id,
                    record_date,
                )
                if existing is None:
                    record = DailyMoodRecordDocument(
                        _id=self.repository.next_daily_mood_id(),
                        user_id=subject.subject_id,
                        record_date=record_date,
                        mood_code=mood_code,  # type: ignore[arg-type]
                        source="mini_program",
                        deleted_at=None,
                        created_at=current,
                        updated_at=current,
                        version=1,
                    )
                    saved = self.repository.create_daily_mood_record(record)
                    reason_code = "saved"
                else:
                    saved = existing
                    reason_code = "existing"
                response = _mood_fact(saved)
            self.idempotency.complete(
                reservation,
                status_code=200,
                response_digest=response.model_dump_json(),
            )
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryError as error:
            failure = _repository_failure(error)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

        self._audit(
            request_id=request_id,
            actor_id=subject.subject_id,
            action="mood_record",
            resource_id=response.record_id,
            reason_code=reason_code,
            facts={
                "action_code": "record",
                "object_version": response.version,
                "status": reason_code,
            },
        )
        return response

    def list_history(
        self,
        access_token: str,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> MoodHistoryPage:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        self._ensure_private_access(subject.subject_id)
        if limit < 1:
            raise ApiException(422, "VALIDATION_FAILED")
        offset = _decode_cursor(cursor)
        page_size = min(limit, 100)
        records = [
            record
            for record in self.repository.list_daily_mood_records(subject.subject_id)
            if (from_date is None or record.record_date >= from_date)
            and (to_date is None or record.record_date <= to_date)
        ]
        page = records[offset : offset + page_size]
        next_offset = offset + page_size
        next_cursor = _encode_cursor(next_offset) if next_offset < len(records) else None
        return MoodHistoryPage(
            items=[_mood_fact(record) for record in page],
            next_cursor=next_cursor,
        )

    def delete_mood(
        self,
        access_token: str,
        *,
        record_id: str,
        object_version: int,
        request_id: str,
    ) -> DeletedMoodFact:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        self._ensure_private_access(subject.subject_id)
        try:
            with self.repository.transaction():
                record = self.repository.get_daily_mood(record_id)
                if record.user_id != subject.subject_id:
                    raise ApiException(404, "NOT_FOUND")
                if record.version != object_version:
                    raise ApiException(
                        409,
                        "VERSION_CONFLICT",
                        current_version=record.version,
                    )
                current = self._now()
                saved = self.repository.save_daily_mood_record(
                    record.model_copy(update={"deleted_at": current, "updated_at": current}),
                    expected_version=record.version,
                )
        except RepositoryVersionConflict as error:
            raise ApiException(
                409,
                "VERSION_CONFLICT",
                current_version=error.current_version,
            ) from error
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error

        self._audit(
            request_id=request_id,
            actor_id=subject.subject_id,
            action="mood_delete",
            resource_id=saved.document_id,
            reason_code="deleted",
            facts={
                "action_code": "delete",
                "object_version": saved.version,
                "status": "deleted",
            },
        )
        return DeletedMoodFact(
            record_id=saved.document_id,
            deleted_at=saved.deleted_at or self._now(),
            version=saved.version,
        )

    def _ensure_private_access(self, user_id: str) -> None:
        user = self.repository.get_user(user_id)
        if user.status != "active":
            raise ApiException(403, "FORBIDDEN")
        if user.base_consent_status != "accepted":
            raise ApiException(403, "CONSENT_REQUIRED")
        if not user.identity_record_id:
            raise ApiException(403, "IDENTITY_REQUIRED")
        try:
            identity = self.repository.get_identity_record(user.identity_record_id)
        except RepositoryNotFound as error:
            raise ApiException(403, "IDENTITY_REQUIRED") from error
        if identity.user_id != user.document_id or identity.verification_status != "verified":
            raise ApiException(403, "IDENTITY_REQUIRED")

    def _audit(
        self,
        *,
        request_id: str,
        actor_id: str,
        action: str,
        resource_id: str,
        reason_code: str,
        facts: dict[str, object],
    ) -> None:
        try:
            self.audit.write(
                request_id=request_id,
                actor_type="student",
                actor_id=actor_id,
                capability=None,
                action=action,
                resource_type="mood",
                resource_id=resource_id,
                data_scope="necessary_facts",
                outcome="success",
                reason_code=reason_code,
                occurred_at=self._now(),
                facts=facts,
            )
        except Exception:
            logger.warning("audit_write_failed")

    def _now(self) -> datetime:
        if callable(self._now_provider):
            value = self._now_provider()
            if isinstance(value, datetime):
                return value
        return datetime.now(UTC)

    def _today(self) -> str:
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(SHANGHAI).date().isoformat()


def _mood_fact(record: DailyMoodRecordDocument) -> MoodFact:
    return MoodFact(
        record_id=record.document_id,
        record_date=record.record_date,
        mood_code=record.mood_code,
        saved_at=record.created_at,
        version=record.version,
    )


def _mood_fact_from_digest(response_digest: str | None) -> MoodFact:
    if response_digest is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(response_digest)
    if error is not None:
        raise error
    return MoodFact.model_validate_json(response_digest)


def _complete_failure(
    idempotency: IdempotencyService,
    reservation: IdempotencyReservation,
    error: ApiException,
) -> None:
    idempotency.complete(
        reservation,
        status_code=error.status_code,
        response_digest=serialize_api_error(error),
        outcome="failure",
    )


def _repository_failure(error: RepositoryError) -> ApiException:
    if isinstance(error, RepositoryNotFound):
        return ApiException(404, "NOT_FOUND")
    return ApiException(503, "DEPENDENCY_UNAVAILABLE")


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(json.dumps(offset).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        offset = int(json.loads(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")))
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error) as error:
        raise ApiException(422, "VALIDATION_FAILED") from error
    if offset < 0:
        raise ApiException(422, "VALIDATION_FAILED")
    return offset
