from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from app.infra.database.common import RepositoryError, RepositoryNotFound
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.logger.common import traced
from app.infra.security.tokens import AuthenticatedSubject, TokenManager
from app.infra.serializer.error.common import ApiException
from app.infra.serializer.error.database import RepositoryCommitUncertain
from app.models.v2.documents import IdentityAccessRequestDocument
from app.models.v2.requests.identity_access import IdentityAccessRequestCreate
from app.models.v2.responses.identity_access import (
    IdentityAccessIdentityProjection,
    IdentityAccessRequestProjection,
)
from app.services.v2.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)
from app.services.v2.identity_service import IdentityService
from app.services.v2.repositories import DomainRepository, SessionRepository


class IdentityAccessService:
    DEFAULT_VALIDITY = timedelta(hours=24)

    def __init__(
        self,
        *,
        repository: DomainRepository,
        session_repository: SessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
        identity_service: IdentityService,
    ) -> None:
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer
        self.identity = identity_service
        share_memory_transaction(
            self.repository, self.idempotency.repository, self.audit.repository, self.sessions
        )

    @traced
    async def create_request(
        self,
        access_token: str,
        *,
        payload: IdentityAccessRequestCreate,
        request_id: str,
        idempotency_key: str,
    ) -> IdentityAccessRequestProjection:
        subject = await self._admin(access_token)
        reservation = await self.idempotency.begin(
            "admin",
            subject.subject_id,
            "/admin/identity-access-requests",
            idempotency_key,
            payload.model_dump(mode="json"),
        )
        if reservation.replayed:
            return _decode_request(reservation.record.response_digest)
        try:
            async with self.repository.transaction():
                user = await self.repository.get_user(payload.user_reference_id)
                if user.status == "purged":
                    raise ApiException(404, "NOT_FOUND")
                now = datetime.now(UTC)
                request = IdentityAccessRequestDocument(
                    _id=(await self.repository.next_identity_access_request_id()),
                    task_kind="identity_access",
                    user_reference_id=user.document_id,
                    requester_admin_id=subject.subject_id,
                    requested_fields=list(dict.fromkeys(payload.requested_fields)),
                    reason_fact=payload.reason_fact,
                    state="pending",
                    decided_admin_id=None,
                    decision_reason=None,
                    valid_from=None,
                    valid_until=None,
                    created_at=now,
                    updated_at=now,
                    version=1,
                )
                (await self.repository.create_identity_access_request(request))
                response = _request_projection(request)
                (
                    await self.idempotency.complete(
                        reservation, status_code=200, response_digest=response.model_dump_json()
                    )
                )
                (
                    await self._audit(
                        request_id,
                        subject.subject_id,
                        "identity_access_request_create",
                        request.document_id,
                        "pending",
                    )
                )
                return response
        except asyncio.CancelledError as error:
            await self.idempotency.cancel(reservation, error)
            raise
        except RepositoryCommitUncertain:
            raise
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
        except RepositoryError as error:
            failure = ApiException(503, "DEPENDENCY_UNAVAILABLE")
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
        except ApiException as error:
            (await _complete_failure(self.idempotency, reservation, error))
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error

    @traced
    async def get_request(
        self, access_token: str, *, request_id: str
    ) -> IdentityAccessRequestProjection:
        subject = await self._admin(access_token)
        try:
            request = await self.repository.get_identity_access_request(request_id)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error
        if request.state == "approved" and request.valid_until is not None:
            if datetime.now(UTC) > request.valid_until:
                request = await self.repository.save_identity_access_request(
                    request.model_copy(update={"state": "expired"}),
                    expected_version=request.version,
                )
        if request.requester_admin_id != subject.subject_id and subject.capability != "super_admin":
            raise ApiException(403, "FORBIDDEN")
        return _request_projection(request)

    @traced
    async def read_identity(
        self,
        access_token: str,
        *,
        request_id: str,
        audit_request_id: str,
    ) -> IdentityAccessIdentityProjection:
        subject = await self._admin(access_token)
        try:
            request = await self.repository.get_identity_access_request(request_id)
        except RepositoryNotFound as error:
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "not_found"
                )
            )
            raise ApiException(404, "NOT_FOUND") from error
        now = datetime.now(UTC)
        if request.state != "approved" or request.valid_from is None or request.valid_until is None:
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "denied"
                )
            )
            raise ApiException(403, "FORBIDDEN")
        if now < request.valid_from or now > request.valid_until:
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "expired"
                )
            )
            raise ApiException(403, "FORBIDDEN")
        try:
            user = await self.repository.get_user(request.user_reference_id)
            identity_record = await self.repository.get_identity_record_by_user(user.document_id)
        except RepositoryNotFound as error:
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "denied"
                )
            )
            raise ApiException(404, "NOT_FOUND") from error
        if identity_record is None or identity_record.verification_status != "verified":
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "denied"
                )
            )
            raise ApiException(404, "NOT_FOUND")
        fields: dict[str, str] = {}
        try:
            decrypt = getattr(self.identity.identity_cipher, "decrypt")
            for field in request.requested_fields:
                ciphertext = (
                    identity_record.student_name_ciphertext
                    if field == "student_name"
                    else identity_record.student_number_ciphertext
                )
                if not ciphertext:
                    raise ValueError("missing identity ciphertext")
                fields[field] = decrypt(ciphertext)
        except Exception as error:
            (
                await self._audit(
                    audit_request_id, subject.subject_id, "identity_read", request_id, "failure"
                )
            )
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE") from error
        (
            await self._audit(
                audit_request_id, subject.subject_id, "identity_read", request_id, "success"
            )
        )
        return IdentityAccessIdentityProjection(
            request_id=request.document_id,
            fields=fields,  # type: ignore[arg-type]
            object_version=request.version,
        )

    @traced
    async def decide_request(
        self,
        access_token: str,
        *,
        request_id: str,
        state: str,
        object_version: int,
        decision_reason: str | None = None,
        valid_until: datetime | None = None,
    ) -> IdentityAccessRequestProjection:
        subject = await self._admin(access_token)
        try:
            request = await self.repository.get_identity_access_request(request_id)
            if request.version != object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=request.version)
            if state not in {"approved", "denied", "revoked"}:
                raise ApiException(422, "VALIDATION_FAILED")
            now = datetime.now(UTC)
            updated = request.model_copy(
                update={
                    "state": state,
                    "decided_admin_id": subject.subject_id,
                    "decision_reason": decision_reason,
                    "valid_from": now if state == "approved" else None,
                    "valid_until": (valid_until or now + self.DEFAULT_VALIDITY)
                    if state == "approved"
                    else None,
                }
            )
            saved = await self.repository.save_identity_access_request(
                updated, expected_version=request.version
            )
            (
                await self._audit(
                    request_id, subject.subject_id, "identity_access_decision", request_id, state
                )
            )
            return _request_projection(saved)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error

    @traced
    async def _admin(self, access_token: str) -> AuthenticatedSubject:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "admin" or subject.capability != "super_admin":
            raise ApiException(403, "FORBIDDEN")
        return subject

    @traced
    async def _audit(
        self, request_id: str, actor_id: str, action: str, resource_id: str, outcome: str
    ) -> None:
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="admin",
                actor_id=actor_id,
                capability="super_admin",
                action=action,
                resource_type="identity",
                resource_id=resource_id,
                data_scope="necessary_facts",
                outcome="success" if outcome in {"success", "pending", "approved"} else "denied",
                reason_code=outcome,
                occurred_at=datetime.now(UTC),
                facts={"action_code": action, "status": outcome},
            )
        )


@traced
def _request_projection(request: IdentityAccessRequestDocument) -> IdentityAccessRequestProjection:
    return IdentityAccessRequestProjection(
        request_id=request.document_id,
        user_reference_id=request.user_reference_id,
        requested_fields=request.requested_fields,
        reason_fact=request.reason_fact,
        state=request.state,
        valid_from=request.valid_from,
        valid_until=request.valid_until,
        object_version=request.version,
    )


@traced
def _decode_request(value: str | None) -> IdentityAccessRequestProjection:
    if value is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(value)
    if error is not None:
        raise error
    try:
        return IdentityAccessRequestProjection.model_validate_json(value)
    except Exception as exc:
        raise ApiException(500, "INTERNAL_ERROR") from exc


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
