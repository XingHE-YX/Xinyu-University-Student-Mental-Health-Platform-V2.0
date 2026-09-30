"""Safety confirmation and support-resource acknowledgement use cases."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import ValidationError

from app.infra.config.settings import Settings
from app.infra.config.validation import EnvironmentKind
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
from app.models.v2.documents import (
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    SafetySupportTaskDocument,
    SupportResourceSnapshotModel,
    WorkTaskDocument,
)
from app.models.v2.requests.assessment import (
    AssessmentAnswerSubmission,
    SafetyConfirmationRequest,
    SupportResourceAckRequest,
)
from app.models.v2.responses.assessment import (
    SafetyConfirmationResponse,
    SupportResourceAckResponse,
)
from app.services.v2.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)
from app.services.v2.repositories import DomainRepository, SessionRepository
from app.services.v2.rules.assessment import (
    PHQ9_Q9_KEY,
    AssessmentValidationError,
    questionnaire_questions,
)
from app.services.v2.rules.safety import (
    SafetyConfirmationState,
    decide_safety_branch,
    minimal_visible_projection,
)

logger = get_logger(__name__)


class SafetyService:
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
    async def confirm_safety(
        self,
        access_token: str,
        *,
        session_id: str,
        state: SafetyConfirmationState,
        object_version: int,
        answers: list[dict[str, object]],
        request_id: str,
        idempotency_key: str,
    ) -> SafetyConfirmationResponse:
        try:
            request = SafetyConfirmationRequest.model_validate(
                {"state": state, "answers": answers, "object_version": object_version}
            )
        except ValidationError as error:
            raise ApiException(422, "VALIDATION_FAILED") from error
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        (await self._ensure_assessment_access(subject.subject_id))
        reservation = await self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/assessment-sessions/{session_id}/safety-confirmation",
            idempotency_key,
            request.model_dump(mode="json"),
        )
        if reservation.replayed:
            return self._decode_confirmation_response(reservation.record.response_digest)

        try:
            async with self.repository.transaction():
                response = await self._confirm_safety(
                    subject_id=subject.subject_id,
                    session_id=session_id,
                    request=request,
                    request_id=request_id,
                )
                (
                    await self.idempotency.complete(
                        reservation,
                        status_code=200,
                        response_digest=response.model_dump_json(),
                    )
                )
                return response
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
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

    @traced
    async def acknowledge_support_resource(
        self,
        access_token: str,
        *,
        session_id: str,
        resource_context: str,
        resource_version: str,
        object_version: int,
        request_id: str,
        idempotency_key: str,
    ) -> SupportResourceAckResponse:
        try:
            request = SupportResourceAckRequest.model_validate(
                {
                    "resource_context": resource_context,
                    "resource_version": resource_version,
                    "object_version": object_version,
                }
            )
        except ValidationError as error:
            raise ApiException(422, "VALIDATION_FAILED") from error
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        (await self._ensure_assessment_access(subject.subject_id))
        reservation = await self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/assessment-sessions/{session_id}/support-resource-ack",
            idempotency_key,
            request.model_dump(mode="json"),
        )
        if reservation.replayed:
            return self._decode_ack_response(reservation.record.response_digest)

        try:
            async with self.repository.transaction():
                response = await self._acknowledge_support_resource(
                    subject_id=subject.subject_id,
                    session_id=session_id,
                    request=request,
                    request_id=request_id,
                )
                (
                    await self.idempotency.complete(
                        reservation,
                        status_code=200,
                        response_digest=response.model_dump_json(),
                    )
                )
                return response
        except RepositoryVersionConflict as error:
            failure = ApiException(409, "VERSION_CONFLICT", current_version=error.current_version)
            (await _complete_failure(self.idempotency, reservation, failure))
            raise failure from error
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

    @traced
    async def _confirm_safety(
        self,
        *,
        subject_id: str,
        session_id: str,
        request: SafetyConfirmationRequest,
        request_id: str,
    ) -> SafetyConfirmationResponse:
        current = datetime.now(UTC)
        decision = decide_safety_branch(request.state)
        async with self.repository.transaction():
            session = await self.repository.get_assessment_session(session_id)
            if session.user_id != subject_id:
                raise ApiException(404, "NOT_FOUND")
            if session.version != request.object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=session.version)
            if session.state != "in_progress":
                raise ApiException(404, "NOT_FOUND")
            if session.safety_confirmation_state == "uncertain" and request.state != "uncertain":
                raise ApiException(422, "SAFETY_SUPPORT_BLOCKED")
            if current > session.expires_at:
                expired = session.model_copy(update={"state": "expired", "updated_at": current})
                (
                    await self.repository.save_assessment_session(
                        expired, expected_version=session.version
                    )
                )
                raise ApiException(404, "NOT_FOUND")

            module = await self.repository.get_assessment_module(session.module_code)
            questionnaire = await self.repository.get_assessment_questionnaire(
                session.module_code,
                session.questionnaire_version,
            )
            self._validate_safety_answers(module, questionnaire, request.answers)

            resource_categories = await self._resource_categories()
            task_created = False
            task_state: str | None = None
            update: dict[str, object] = {
                "safety_triggered": True,
                "safety_confirmation_state": request.state,
                "updated_at": current,
            }
            if request.state == "cannot_be_safe":
                update.update({"state": "abandoned", "abandoned_at": current})
            saved_session = await self.repository.save_assessment_session(
                session.model_copy(update=update),
                expected_version=session.version,
            )
            if decision.creates_immediate_task:
                task_created, task_state = await self._create_safety_tasks(
                    user_id=subject_id,
                    source_session_id=saved_session.document_id,
                    safety_fact=request.state,
                    now=current,
                )
            projection = minimal_visible_projection(
                state=request.state,
                resource_categories_shown=resource_categories
                if request.state != "can_be_safe"
                else [],
                questionnaire_completed=False,
                task_state=task_state,
            )

        (
            await self._audit(
                request_id=request_id,
                actor_id=subject_id,
                action="assessment_safety_confirmation",
                resource_id=session_id,
                reason_code=request.state,
                facts={
                    "action_code": "safety_confirmation",
                    "object_version": saved_session.version,
                    "resource_version": self.settings.support_resource_version,
                    "status": request.state,
                    "task_kind": "safety_support" if task_created else None,
                },
            )
        )
        return SafetyConfirmationResponse(
            next_step=decision.next_step,
            result_id=None,
            support_required=decision.support_required,
            task_created=task_created,
            visible_projection=projection,
            version=saved_session.version,
        )

    @traced
    async def _acknowledge_support_resource(
        self,
        *,
        subject_id: str,
        session_id: str,
        request: SupportResourceAckRequest,
        request_id: str,
    ) -> SupportResourceAckResponse:
        if self.settings.support_resource_version is None:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE")
        if request.resource_version != self.settings.support_resource_version:
            raise ApiException(
                409,
                "VERSION_CONFLICT",
                current_version=self.settings.support_resource_version,
            )
        current = datetime.now(UTC)
        async with self.repository.transaction():
            session = await self.repository.get_assessment_session(session_id)
            if session.user_id != subject_id:
                raise ApiException(404, "NOT_FOUND")
            if session.version != request.object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=session.version)
            if session.state != "in_progress" or session.safety_confirmation_state != "uncertain":
                raise ApiException(422, "SAFETY_SUPPORT_BLOCKED")
            saved_session = await self.repository.save_assessment_session(
                session.model_copy(
                    update={
                        "safety_resource_version": request.resource_version,
                        "safety_resource_acknowledged_at": current,
                        "updated_at": current,
                    }
                ),
                expected_version=session.version,
            )
        (
            await self._audit(
                request_id=request_id,
                actor_id=subject_id,
                action="assessment_support_resource_ack",
                resource_id=session_id,
                reason_code="support_resource_acknowledged",
                facts={
                    "action_code": "support_resource_ack",
                    "object_version": saved_session.version,
                    "resource_version": request.resource_version,
                    "status": "acknowledged",
                },
            )
        )
        return SupportResourceAckResponse(
            resource_version=request.resource_version,
            acknowledged_at=current,
            version=saved_session.version,
        )

    @traced
    def _validate_safety_answers(
        self,
        module: AssessmentModuleDocument,
        questionnaire: AssessmentQuestionnaireDocument,
        answers: Sequence[AssessmentAnswerSubmission],
    ) -> None:
        if module.module_code != "phq9" or questionnaire.module_code != "phq9":
            raise ApiException(422, "VALIDATION_FAILED")
        if questionnaire.questionnaire_version != module.current_questionnaire_version:
            raise ApiException(409, "VERSION_CONFLICT", current_version=module.version)
        try:
            questions = questionnaire_questions(questionnaire)
        except AssessmentValidationError as error:
            raise ApiException(404, "NOT_FOUND") from error
        expected_keys = tuple(f"q{number}" for number in range(1, 10))
        submitted = [(answer.question_key, answer.option_key) for answer in answers]
        if tuple(question_key for question_key, _ in submitted) != expected_keys:
            raise ApiException(422, "VALIDATION_FAILED")
        option_scores = {
            question.question_key: {option.option_key: option.score for option in question.options}
            for question in questions
        }
        for question_key, option_key in submitted:
            if option_key not in option_scores.get(question_key, {}):
                raise ApiException(422, "VALIDATION_FAILED")
        if option_scores[PHQ9_Q9_KEY][submitted[-1][1]] == 0:
            raise ApiException(422, "VALIDATION_FAILED")

    @traced
    async def _resource_categories(self) -> list[str]:
        if self.settings.environment_kind not in {EnvironmentKind.DEMO, EnvironmentKind.AUTHORIZED}:
            return []
        resources = await self.repository.list_support_resources(
            self.settings.environment_kind.value,
            resource_set_version=self.settings.support_resource_version,
            now=datetime.now(UTC),
        )
        return sorted({resource.category for resource in resources})

    @traced
    async def _create_safety_tasks(
        self,
        *,
        user_id: str,
        source_session_id: str,
        safety_fact: str,
        now: datetime,
    ) -> tuple[bool, str | None]:
        if self.settings.environment_kind not in {EnvironmentKind.DEMO, EnvironmentKind.AUTHORIZED}:
            return False, None
        resources = await self.repository.list_support_resources(
            self.settings.environment_kind.value,
            resource_set_version=self.settings.support_resource_version,
            now=now,
        )
        snapshot = [
            SupportResourceSnapshotModel(
                resource_id=resource.document_id,
                title=resource.title,
                category=resource.category,
                action_type=resource.action_type,
                action_target=resource.action_target,
            )
            for resource in resources
        ]
        safety_task_id = await self.repository.next_safety_support_task_id()
        safety_task = SafetySupportTaskDocument(
            _id=safety_task_id,
            task_kind="safety_support",
            user_reference_id=user_id,
            source_result_id=None,
            source_session_id=source_session_id,
            safety_fact=safety_fact,  # type: ignore[arg-type]
            support_resource_snapshot=snapshot,
            state="needs_action",
            assigned_admin_id=None,
            followup_due_at=None,
            fact_note=None,
            completed_at=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        (await self.repository.create_safety_support_task(safety_task))
        work_task = WorkTaskDocument(
            _id=safety_task_id,
            task_kind="safety_support",
            source_type="support_task",
            source_id=safety_task.document_id,
            available_capability="safety_support",
            state="needs_action",
            assigned_admin_id=None,
            safe_summary="安全支持任务待处理",
            object_version=safety_task.version,
            last_action=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        (await self.repository.create_work_task(work_task))
        return True, safety_task.state

    @traced
    async def _ensure_assessment_access(self, user_id: str) -> None:
        user = await self.repository.get_user(user_id)
        if user.status != "active":
            raise ApiException(403, "FORBIDDEN")
        if user.base_consent_status != "accepted":
            raise ApiException(403, "CONSENT_REQUIRED")
        if not user.identity_record_id:
            raise ApiException(403, "IDENTITY_REQUIRED")
        try:
            identity = await self.repository.get_identity_record(user.identity_record_id)
        except RepositoryNotFound as error:
            raise ApiException(403, "IDENTITY_REQUIRED") from error
        if identity.user_id != user.document_id or identity.verification_status != "verified":
            raise ApiException(403, "IDENTITY_REQUIRED")

    @traced
    async def _audit(
        self,
        *,
        request_id: str,
        actor_id: str,
        action: str,
        resource_id: str,
        reason_code: str,
        facts: dict[str, object],
    ) -> None:
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="student",
                actor_id=actor_id,
                capability=None,
                action=action,
                resource_type="assessment",
                resource_id=resource_id,
                data_scope="necessary_facts",
                outcome="success",
                reason_code=reason_code,
                occurred_at=datetime.now(UTC),
                facts=facts,
            )
        )

    @traced
    def _decode_confirmation_response(
        self, response_digest: str | None
    ) -> SafetyConfirmationResponse:
        if response_digest is None:
            raise ApiException(500, "INTERNAL_ERROR")
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        return SafetyConfirmationResponse.model_validate_json(response_digest)

    @traced
    def _decode_ack_response(self, response_digest: str | None) -> SupportResourceAckResponse:
        if response_digest is None:
            raise ApiException(500, "INTERNAL_ERROR")
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        return SupportResourceAckResponse.model_validate_json(response_digest)


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
