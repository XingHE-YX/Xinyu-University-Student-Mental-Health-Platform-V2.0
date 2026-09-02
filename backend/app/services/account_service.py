from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.audit.writer import AuditWriter
from app.domain.models import UserAccountDocument
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.errors import ApiException
from app.schemas.student_core import AccountState
from app.security.tokens import TokenManager
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)


class AccountService:
    def __init__(
        self,
        *,
        repository: InMemoryDomainDataRepository,
        session_repository: InMemorySessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
    ) -> None:
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer

    def stop(
        self, access_token: str, *, object_version: int, request_id: str, idempotency_key: str
    ) -> AccountState:
        return self._transition(
            access_token,
            target="recovery_pending",
            object_version=object_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def recover(
        self, access_token: str, *, object_version: int, request_id: str, idempotency_key: str
    ) -> AccountState:
        return self._transition(
            access_token,
            target="active",
            object_version=object_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    def status(self, access_token: str) -> AccountState:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        return self._state(self.repository.get_user(subject.subject_id))

    def _transition(
        self,
        access_token: str,
        *,
        target: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> AccountState:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/account/{target}",
            idempotency_key,
            {"object_version": object_version},
        )
        if reservation.replayed:
            return _state_from_digest(reservation.record.response_digest)
        try:
            with self.repository.transaction():
                user = self.repository.get_user(subject.subject_id)
                if user.version != object_version:
                    raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
                now = datetime.now(UTC)
                if target == "recovery_pending":
                    if user.status != "active":
                        raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
                    updated = user.model_copy(
                        update={
                            "status": "recovery_pending",
                            "stop_requested_at": now,
                            "recovery_deadline_at": now + timedelta(days=30),
                        }
                    )
                else:
                    if user.status != "recovery_pending":
                        raise ApiException(403, "FORBIDDEN")
                    if user.recovery_deadline_at is not None and now > user.recovery_deadline_at:
                        raise ApiException(403, "FORBIDDEN")
                    updated = user.model_copy(
                        update={
                            "status": "active",
                            "stop_requested_at": None,
                            "recovery_deadline_at": None,
                        }
                    )
                saved = self.repository.save_user(updated, expected_version=user.version)
                state = self._state(saved)
            self.idempotency.complete(
                reservation, status_code=200, response_digest=state.model_dump_json()
            )
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except (RepositoryError, RepositoryNotFound) as error:
            failure = ApiException(
                404 if isinstance(error, RepositoryNotFound) else 503,
                "NOT_FOUND" if isinstance(error, RepositoryNotFound) else "DEPENDENCY_UNAVAILABLE",
            )
            _complete_failure(self.idempotency, reservation, failure)
            raise failure from error
        except ApiException as error:
            _complete_failure(self.idempotency, reservation, error)
            raise
        try:
            self.audit.write(
                request_id=request_id,
                actor_type="student",
                actor_id=subject.subject_id,
                capability=None,
                action=f"account_{target}",
                resource_type="user",
                resource_id=subject.subject_id,
                data_scope="necessary_facts",
                outcome="success",
                reason_code=target,
                occurred_at=datetime.now(UTC),
                facts={"action_code": target, "object_version": state.object_version},
            )
        except Exception:
            pass
        return state

    @staticmethod
    def _state(user: UserAccountDocument) -> AccountState:
        return AccountState(
            status=user.status,
            recovery_deadline_at=user.recovery_deadline_at,
            can_recover=user.status == "recovery_pending"
            and (
                user.recovery_deadline_at is None or datetime.now(UTC) <= user.recovery_deadline_at
            ),
            object_version=user.version,
            available_features=[] if user.status != "active" else ["today", "assessment", "mood"],
        )


def _state_from_digest(value: str | None) -> AccountState:
    if value is None:
        raise ApiException(500, "INTERNAL_ERROR")
    error = deserialize_api_error(value)
    if error is not None:
        raise error
    try:
        return AccountState.model_validate_json(value)
    except Exception as exc:
        raise ApiException(500, "INTERNAL_ERROR") from exc


def _complete_failure(
    idempotency: IdempotencyService, reservation: IdempotencyReservation, error: ApiException
) -> None:
    idempotency.complete(
        reservation,
        status_code=error.status_code,
        response_digest=serialize_api_error(error),
        outcome="failure",
    )
