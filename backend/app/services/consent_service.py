"""Consent use cases for base service and community participation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Literal

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.models import ConsentEventDocument, UserAccountDocument
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
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
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

    def accept_base_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return self._apply_consent(
            access_token,
            consent_kind="base_service",
            action="accepted",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def accept_community_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return self._apply_consent(
            access_token,
            consent_kind="community_content",
            action="accepted",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def withdraw_community_consent(
        self,
        access_token: str,
        *,
        document_version: str,
        user_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> ConsentState:
        return self._apply_consent(
            access_token,
            consent_kind="community_content",
            action="withdrawn",
            document_version=document_version,
            user_version=user_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def ensure_community_write_allowed(self, access_token: str) -> None:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = self.repository.get_user(subject.subject_id)
        if user.status != "active":
            raise ApiException(403, "FORBIDDEN")
        if user.base_consent_status != "accepted" or user.community_consent_status != "accepted":
            raise ApiException(403, "CONSENT_REQUIRED")
        if not user.identity_record_id:
            raise ApiException(403, "IDENTITY_REQUIRED")
        try:
            identity = self.repository.get_identity_record(user.identity_record_id)
        except RepositoryNotFound:
            identity = None
        if identity is not None and identity.user_id != user.document_id:
            identity = None
        if identity is None or identity.verification_status != "verified":
            raise ApiException(403, "IDENTITY_REQUIRED")

    def _apply_consent(
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
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        reservation = self.idempotency.begin(
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
            with self.repository.transaction():
                user = self.repository.get_user(subject.subject_id)
                if user.status != "active":
                    raise ApiException(403, "FORBIDDEN")
                if consent_kind == "community_content" and user.base_consent_status != "accepted":
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
                saved_user = self.repository.save_user(
                    updated_user,
                    expected_version=user_version,
                )
                event = ConsentEventDocument(
                    _id=self.repository.next_consent_id(),
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
                self.repository.append_consent_event(event)
                state = ConsentState(
                    base_consent_status=saved_user.base_consent_status,
                    base_consent_version=saved_user.base_consent_version,
                    community_consent_status=saved_user.community_consent_status,
                    community_consent_version=saved_user.community_consent_version,
                )
            response_digest = _digest_state(state)
            self.idempotency.complete(
                reservation,
                status_code=200,
                response_digest=response_digest,
            )
            self.audit.write(
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
            return state
        except RepositoryVersionConflict as error:
            conflict = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, conflict)
            raise conflict from error
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


def _digest_state(state: ConsentState) -> str:
    return json.dumps(asdict(state), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
