from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.infra.database.common import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.logger.common import traced
from app.infra.security.tokens import TokenManager
from app.infra.serializer.error.common import ApiException
from app.models.v2.documents import UserAccountDocument
from app.models.v2.responses.student_core import AccountState
from app.services.v2.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)
from app.services.v2.repositories import DomainRepository, SessionRepository


class AccountService:
    def __init__(
        self,
        *,
        repository: DomainRepository,
        session_repository: SessionRepository,
        token_manager: TokenManager,
        idempotency_service: IdempotencyService,
        audit_writer: AuditWriter,
    ) -> None:
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.idempotency = idempotency_service
        self.audit = audit_writer
        share_memory_transaction(
            self.repository, self.idempotency.repository, self.audit.repository, self.sessions
        )

    @traced
    async def stop(
        self, access_token: str, *, object_version: int, request_id: str, idempotency_key: str
    ) -> AccountState:
        return await self._transition(
            access_token,
            target="recovery_pending",
            object_version=object_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    @traced
    async def recover(
        self, access_token: str, *, object_version: int, request_id: str, idempotency_key: str
    ) -> AccountState:
        return await self._transition(
            access_token,
            target="active",
            object_version=object_version,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

    @traced
    async def status(self, access_token: str) -> AccountState:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        return self._state(await self.repository.get_user(subject.subject_id))

    @traced
    async def _transition(
        self,
        access_token: str,
        *,
        target: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> AccountState:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        reservation = await self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/account/{target}",
            idempotency_key,
            {"object_version": object_version},
        )
        if reservation.replayed:
            return _state_from_digest(reservation.record.response_digest)
        try:
            async with self.repository.transaction():
                async with self.repository.transaction():
                    user = await self.repository.get_user(subject.subject_id)
                    if user.version != object_version:
                        raise ApiException(409, "VERSION_CONFLICT", current_version=user.version)
                    now = datetime.now(UTC)
                    if target == "recovery_pending":
                        if user.status != "active":
                            raise ApiException(
                                409, "VERSION_CONFLICT", current_version=user.version
                            )
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
                        if (
                            user.recovery_deadline_at is not None
                            and now > user.recovery_deadline_at
                        ):
                            raise ApiException(403, "FORBIDDEN")
                        updated = user.model_copy(
                            update={
                                "status": "active",
                                "stop_requested_at": None,
                                "recovery_deadline_at": None,
                            }
                        )
                    saved = await self.repository.save_user(updated, expected_version=user.version)
                    state = self._state(saved)
                (
                    await self.idempotency.complete(
                        reservation, status_code=200, response_digest=state.model_dump_json()
                    )
                )
                (
                    await self.audit.write(
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
                )
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
        except (RepositoryError, RepositoryNotFound) as error:
            failure = ApiException(
                404 if isinstance(error, RepositoryNotFound) else 503,
                "NOT_FOUND" if isinstance(error, RepositoryNotFound) else "DEPENDENCY_UNAVAILABLE",
            )
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

    @staticmethod
    @traced
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


@traced
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


@traced
async def _complete_failure(
    idempotency: IdempotencyService, reservation: IdempotencyReservation, error: ApiException
) -> None:
    (
        await idempotency.complete(
            reservation,
            status_code=error.status_code,
            response_digest=serialize_api_error(error),
            outcome="failure",
        )
    )
