from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.audit.writer import AuditWriter
from app.domain.models import IdentityAccessRequestDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import RepositoryError, RepositoryNotFound
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.schemas.identity_access import (
    IdentityAccessIdentityProjection,
    IdentityAccessRequestCreate,
    IdentityAccessRequestProjection,
)
from app.security.tokens import AuthenticatedSubject, TokenManager
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)
from app.services.identity_service import IdentityService


class IdentityAccessService:
    DEFAULT_VALIDITY = timedelta(hours=24)

    def __init__(
        self,
        *,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
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

    def create_request(
        self,
        access_token: str,
        *,
        payload: IdentityAccessRequestCreate,
        request_id: str,
        idempotency_key: str,
    ) -> IdentityAccessRequestProjection:
        subject = self._admin(access_token)
        reservation = self.idempotency.begin(
            "admin",
            subject.subject_id,
            "/admin/identity-access-requests",
            idempotency_key,
            payload.model_dump(mode="json"),
        )
        if reservation.replayed:
            return _decode_request(reservation.record.response_digest)
        try:
            user = self.repository.get_user(payload.user_reference_id)
            if user.status == "purged":
                raise ApiException(404, "NOT_FOUND")
            now = datetime.now(UTC)
            request = IdentityAccessRequestDocument(
                _id=self.repository.next_identity_access_request_id(),
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
            self.repository.create_identity_access_request(request)
            response = _request_projection(request)
            self.idempotency.complete(
                reservation, status_code=200, response_digest=response.model_dump_json()
            )
            self._audit(
                request_id,
                subject.subject_id,
                "identity_access_request_create",
                request.document_id,
                "pending",
            )
            return response
        except RepositoryNotFound as error:
            failure = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except RepositoryError as error:
            failure = ApiException(503, "DEPENDENCY_UNAVAILABLE")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        except Exception as error:
            failure = ApiException(500, "INTERNAL_ERROR")
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error

    def get_request(self, access_token: str, *, request_id: str) -> IdentityAccessRequestProjection:
        subject = self._admin(access_token)
        try:
            request = self.repository.get_identity_access_request(request_id)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error
        if request.state == "approved" and request.valid_until is not None:
            if datetime.now(UTC) > request.valid_until:
                request = self.repository.save_identity_access_request(
                    request.model_copy(update={"state": "expired"}),
                    expected_version=request.version,
                )
        if request.requester_admin_id != subject.subject_id and subject.capability != "super_admin":
            raise ApiException(403, "FORBIDDEN")
        return _request_projection(request)

    def read_identity(
        self,
        access_token: str,
        *,
        request_id: str,
        audit_request_id: str,
    ) -> IdentityAccessIdentityProjection:
        subject = self._admin(access_token)
        try:
            request = self.repository.get_identity_access_request(request_id)
        except RepositoryNotFound as error:
            self._audit(
                audit_request_id, subject.subject_id, "identity_read", request_id, "not_found"
            )
            raise ApiException(404, "NOT_FOUND") from error
        now = datetime.now(UTC)
        if request.state != "approved" or request.valid_from is None or request.valid_until is None:
            self._audit(audit_request_id, subject.subject_id, "identity_read", request_id, "denied")
            raise ApiException(403, "FORBIDDEN")
        if now < request.valid_from or now > request.valid_until:
            self._audit(
                audit_request_id, subject.subject_id, "identity_read", request_id, "expired"
            )
            raise ApiException(403, "FORBIDDEN")
        try:
            user = self.repository.get_user(request.user_reference_id)
            identity_record = self.repository.get_identity_record_by_user(user.document_id)
        except RepositoryNotFound as error:
            self._audit(audit_request_id, subject.subject_id, "identity_read", request_id, "denied")
            raise ApiException(404, "NOT_FOUND") from error
        if identity_record is None or identity_record.verification_status != "verified":
            self._audit(audit_request_id, subject.subject_id, "identity_read", request_id, "denied")
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
            self._audit(
                audit_request_id, subject.subject_id, "identity_read", request_id, "failure"
            )
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE") from error
        self._audit(audit_request_id, subject.subject_id, "identity_read", request_id, "success")
        return IdentityAccessIdentityProjection(
            request_id=request.document_id,
            fields=fields,  # type: ignore[arg-type]
            object_version=request.version,
        )

    def decide_request(
        self,
        access_token: str,
        *,
        request_id: str,
        state: str,
        object_version: int,
        decision_reason: str | None = None,
        valid_until: datetime | None = None,
    ) -> IdentityAccessRequestProjection:
        subject = self._admin(access_token)
        try:
            request = self.repository.get_identity_access_request(request_id)
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
            saved = self.repository.save_identity_access_request(
                updated, expected_version=request.version
            )
            self._audit(
                request_id, subject.subject_id, "identity_access_decision", request_id, state
            )
            return _request_projection(saved)
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error

    def _admin(self, access_token: str) -> AuthenticatedSubject:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "admin" or subject.capability != "super_admin":
            raise ApiException(403, "FORBIDDEN")
        return subject

    def _audit(
        self, request_id: str, actor_id: str, action: str, resource_id: str, outcome: str
    ) -> None:
        try:
            self.audit.write(
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
        except Exception:
            pass


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
