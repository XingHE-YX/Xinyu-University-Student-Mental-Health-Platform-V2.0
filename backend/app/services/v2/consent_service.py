"""Consent use cases for base service and community participation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from app.infra.config.settings import Settings
from app.infra.database.common import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.logger.common import get_logger, traced
from app.infra.security.tokens import TokenManager
from app.infra.serializer.error.common import ApiException
from app.models.v2.documents import ConsentEventDocument, UserAccountDocument
from app.services.v2.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)
from app.services.v2.repositories import DomainRepository, SessionRepository

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ConsentState:
    base_consent_status: str
    base_consent_version: str | None
    community_consent_status: str
    community_consent_version: str | None


class ConsentService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: DomainRepository,
        session_repository: SessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer
        share_memory_transaction(
            self.repository, self.idempotency.repository, self.audit.repository, self.sessions
        )

    @traced
    async def accept_base_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return await self._apply_consent(
            access_token,
            consent_kind="base_service",
            action="accepted",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    @traced
    async def accept_community_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return await self._apply_consent(
            access_token,
            consent_kind="community_content",
            action="accepted",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    @traced
    async def withdraw_community_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return await self._apply_consent(
            access_token,
            consent_kind="community_content",
            action="withdrawn",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    @traced
    async def ensure_community_write_allowed(self, access_token: str) -> None:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = await self.repository.get_user(subject.subject_id)
        if user.status != "active":
            raise ApiException(403, "FORBIDDEN")
        if user.base_consent_status != "accepted" or user.community_consent_status != "accepted":
            raise ApiException(403, "CONSENT_REQUIRED")
        if not user.identity_record_id:
            raise ApiException(403, "IDENTITY_REQUIRED")
        try:
            identity = await self.repository.get_identity_record(user.identity_record_id)
        except RepositoryNotFound:
            identity = None
        if identity is not None and identity.user_id != user.document_id:
            identity = None
        if identity is None or identity.verification_status != "verified":
            raise ApiException(403, "IDENTITY_REQUIRED")

    @traced
    async def _apply_consent(
        self,
        access_token: str,
        *,
        consent_kind: Literal["base_service", "community_content"],
        action: Literal["accepted", "withdrawn"],
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        reservation = await self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/consents/{consent_kind}",
            idempotency_key,
            {
                "action": action,
                "document_version": document_version,
                "user_version": user_version,
            },
        )
        if reservation.replayed:
            return _state_from_digest(reservation.record.response_digest)

        try:
            async with self.repository.transaction():
                async with self.repository.transaction():
                    user = await self.repository.get_user(subject.subject_id)
                    if user.status != "active":
                        raise ApiException(403, "FORBIDDEN")
                    if (
                        consent_kind == "community_content"
                        and user.base_consent_status != "accepted"
                    ):
                        raise ApiException(403, "CONSENT_REQUIRED")
                    if user.version != user_version:
                        raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
                    current = datetime.now(UTC)
                    updated_user = _updated_consent_user(
                        user,
                        consent_kind=consent_kind,
                        action=action,
                        document_version=document_version,
                        occurred_at=current,
                    )
                    saved_user = await self.repository.save_user(
                        updated_user,
                        expected_version=user_version,
                    )
                    event = ConsentEventDocument(
                        _id=(await self.repository.next_consent_id()),
                        user_id=user.document_id,
                        consent_kind=consent_kind,
                        action="accepted" if action == "accepted" else "withdrawn",
                        document_version=document_version,
                        source="mini_program",
                        occurred_at=current,
                        request_id=request_id,
                        created_at=current,
                        updated_at=current,
                        version=1,
                    )
                    (await self.repository.append_consent_event(event))
                    state = ConsentState(
                        base_consent_status=saved_user.base_consent_status,
                        base_consent_version=saved_user.base_consent_version,
                        community_consent_status=saved_user.community_consent_status,
                        community_consent_version=saved_user.community_consent_version,
                    )
                response_digest = _digest_state(state)
                (
                    await self.idempotency.complete(
                        reservation,
                        status_code=200,
                        response_digest=response_digest,
                    )
                )
                (
                    await self.audit.write(
                        request_id=request_id,
                        actor_type="student",
                        actor_id=user.document_id,
                        capability=None,
                        action="consent_update",
                        resource_type="user",
                        resource_id=user.document_id,
                        data_scope="necessary_facts",
                        outcome="success",
                        reason_code=action,
                        occurred_at=current,
                        facts={
                            "action_code": action,
                            "object_version": saved_user.version,
                            "resource_version": document_version,
                            "status": state.community_consent_status
                            if consent_kind == "community_content"
                            else state.base_consent_status,
                        },
                    )
                )
        except RepositoryVersionConflict as error:
            conflict = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            (await _complete_failure(self.idempotency, reservation, conflict))
            raise conflict from error
        except RepositoryError as error:
            failure = _repository_failure(error)
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
        except ApiException as error:
            (await _complete_failure(self.idempotency, reservation, error))
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error

        return state


@traced
def _updated_consent_user(
    user: UserAccountDocument,
    *,
    consent_kind: Literal["base_service", "community_content"],
    action: Literal["accepted", "withdrawn"],
    document_version: str,
    occurred_at: datetime,
) -> UserAccountDocument:
    if consent_kind == "base_service":
        return user.model_copy(
            update={
                "base_consent_status": "accepted",
                "base_consent_version": document_version,
                "base_consent_at": occurred_at,
            }
        )
    return user.model_copy(
        update={
            "community_consent_status": "accepted" if action == "accepted" else "withdrawn",
            "community_consent_version": document_version,
            "community_consent_at": occurred_at,
        }
    )


@traced
def _digest_state(state: ConsentState) -> str:
    return json.dumps(asdict(state), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@traced
def _state_from_digest(response_digest: str | None) -> ConsentState:
    if response_digest is None:
        raise ApiException(500, "INTERNAL_ERROR")
    try:
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        data = json.loads(response_digest)
        return ConsentState(**data)
    except ApiException:
        raise
    except (TypeError, ValueError, KeyError) as error:
        raise ApiException(500, "INTERNAL_ERROR") from error


@traced
async def _complete_failure(
    idempotency: IdempotencyService,
    reservation: IdempotencyReservation,
    error: ApiException,
) -> None:
    (
        await idempotency.complete(
            reservation,
            status_code=error.status_code,
            response_digest=serialize_api_error(error),
            outcome="failure",
        )
    )


@traced
def _repository_failure(error: RepositoryError) -> ApiException:
    if isinstance(error, RepositoryNotFound):
        return ApiException(404, "NOT_FOUND")
    return ApiException(503, "DEPENDENCY_UNAVAILABLE")
