"""Assessment session orchestration and result persistence."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.domain.assessment_rules import questionnaire_catalog, score_questionnaire
from app.domain.models import (
    AssessmentAnswerModel,
    AssessmentResultDocument,
    AssessmentSessionDocument,
)
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.assessment import (
    CompleteAssessmentSessionRequest,
    CompleteAssessmentSessionResponse,
    PublicQuestion,
    PublicQuestionOption,
    StartAssessmentSessionResponse,
)
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.idempotency_service import (
    IdempotencyReservation,
    IdempotencyService,
    deserialize_api_error,
    serialize_api_error,
)

logger = logging.getLogger(__name__)


class AssessmentService:
    SESSION_TTL = timedelta(hours=1)

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

    def start_session(
        self,
        access_token: str,
        *,
        module_code: str,
        request_id: str,
        idempotency_key: str,
    ) -> StartAssessmentSessionResponse:
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        self._ensure_assessment_access(subject.subject_id)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            "/assessment-sessions",
            idempotency_key,
            {"module_code": module_code},
        )
        if reservation.replayed:
            return self._decode_start_response(reservation.record.response_digest)

        catalog = questionnaire_catalog(module_code)  # type: ignore[arg-type]
        if not catalog.module.enabled or not catalog.questionnaire.enabled:
            error = ApiException(404, "NOT_FOUND")
            _complete_failure(self.idempotency, reservation, error)
            raise error

        current = datetime.now(UTC)
        session = AssessmentSessionDocument(
            _id=self.repository.next_assessment_session_id(),
            user_id=subject.subject_id,
            module_code=catalog.module.module_code,
            questionnaire_version=catalog.questionnaire.questionnaire_version,
            state="in_progress",
            answers=None,
            answered_count=None,
            safety_triggered=False,
            safety_confirmation_state=None,
            safety_resource_version=None,
            safety_resource_acknowledged_at=None,
            client_idempotency_key=idempotency_key,
            started_at=current,
            completed_at=None,
            abandoned_at=None,
            expires_at=current + self.SESSION_TTL,
            created_at=current,
            updated_at=current,
            version=1,
        )
        self.repository.create_assessment_session(session)
        response = StartAssessmentSessionResponse(
            session_id=session.document_id,
            module_code=session.module_code,
            questionnaire_version=session.questionnaire_version,
            questions=[
                PublicQuestion(
                    question_key=question.question_key,
                    order=question.order,
                    text=question.text,
                    options=[
                        PublicQuestionOption(option_key=option.option_key, label=option.label)
                        for option in question.options
                    ],
                )
                for question in catalog.questions
            ],
            state="in_progress",
            expires_at=session.expires_at,
            object_version=session.version,
        )
        self.idempotency.complete(
            reservation,
            status_code=200,
            response_digest=response.model_dump_json(),
        )
        self._audit(
            request_id=request_id,
            actor_id=subject.subject_id,
            action="assessment_session",
            resource_id=session.document_id,
            reason_code="started",
            facts={
                "action_code": "start",
                "object_version": session.version,
                "resource_version": session.questionnaire_version,
                "status": session.state,
            },
        )
        return response

    def complete_session(
        self,
        access_token: str,
        *,
        session_id: str,
        object_version: int,
        answers: list[dict[str, object]],
        request_id: str,
        idempotency_key: str,
    ) -> CompleteAssessmentSessionResponse:
        request = CompleteAssessmentSessionRequest.model_validate(
            {"answers": answers, "object_version": object_version}
        )
        subject = self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        self._ensure_assessment_access(subject.subject_id)
        reservation = self.idempotency.begin(
            "student",
            subject.subject_id,
            f"/assessment-sessions/{session_id}/complete",
            idempotency_key,
            request.model_dump(mode="json"),
        )
        if reservation.replayed:
            return self._decode_complete_response(reservation.record.response_digest)

        try:
            session = self.repository.get_assessment_session(session_id)
            if session.user_id != subject.subject_id:
                raise ApiException(404, "NOT_FOUND")
            if session.version != request.object_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=session.version)
            existing_result = self.repository.get_assessment_result_by_session(session_id)
            if existing_result is not None:
                response = CompleteAssessmentSessionResponse(
                    completion_state="result_ready",
                    session_id=session.document_id,
                    result_id=existing_result.document_id,
                    safety_triggered=session.safety_triggered,
                    score=existing_result.score,
                    result_state=existing_result.result_state,
                )
                self.idempotency.complete(
                    reservation,
                    status_code=200,
                    response_digest=response.model_dump_json(),
                )
                return response
            if session.state == "abandoned":
                raise ApiException(404, "NOT_FOUND")
            if session.state == "completed":
                raise ApiException(409, "VERSION_CONFLICT", current_version=session.version)
            if datetime.now(UTC) > session.expires_at:
                expired = session.model_copy(
                    update={
                        "state": "expired",
                        "updated_at": datetime.now(UTC),
                    }
                )
                self.repository.save_assessment_session(expired, expected_version=session.version)
                raise ApiException(404, "NOT_FOUND")

            module = self.repository.get_assessment_module(session.module_code)
            if module.current_questionnaire_version != session.questionnaire_version:
                raise ApiException(409, "VERSION_CONFLICT", current_version=module.version)

            questionnaire = self.repository.get_assessment_questionnaire(
                session.module_code,
                session.questionnaire_version,
            )
            _ = questionnaire
            scored = score_questionnaire(
                session.module_code,
                [(answer.question_key, answer.option_key) for answer in request.answers],
            )
            if session.module_code == "phq9" and scored.safety_triggered:
                if session.safety_confirmation_state == "cannot_be_safe":
                    response = CompleteAssessmentSessionResponse(
                        completion_state="safety_support_blocked",
                        session_id=session.document_id,
                        result_id=None,
                        safety_triggered=True,
                    )
                elif session.safety_confirmation_state != "can_be_safe":
                    updated_session = session.model_copy(update={"safety_triggered": True})
                    self.repository.save_assessment_session(
                        updated_session,
                        expected_version=session.version,
                    )
                    response = CompleteAssessmentSessionResponse(
                        completion_state="safety_confirmation_required",
                        session_id=session.document_id,
                        result_id=None,
                        safety_triggered=True,
                    )
                    self.idempotency.complete(
                        reservation,
                        status_code=200,
                        response_digest=response.model_dump_json(),
                    )
                    self._audit(
                        request_id=request_id,
                        actor_id=subject.subject_id,
                        action="assessment_complete",
                        resource_id=session.document_id,
                        reason_code="safety_confirmation_required",
                        facts={
                            "action_code": "complete",
                            "object_version": session.version + 1,
                            "resource_version": session.questionnaire_version,
                            "status": "in_progress",
                        },
                    )
                    return response
                else:
                    response = CompleteAssessmentSessionResponse(
                        completion_state="result_ready",
                        session_id=session.document_id,
                        result_id=None,
                        safety_triggered=True,
                    )
            answer_snapshot = [
                AssessmentAnswerModel.model_validate(item) for item in scored.answers_snapshot
            ]
            current = datetime.now(UTC)
            with self.repository.transaction():
                latest_session = self.repository.get_assessment_session(session_id)
                if latest_session.version != request.object_version:
                    raise ApiException(
                        409, "VERSION_CONFLICT", current_version=latest_session.version
                    )
                completed_session = latest_session.model_copy(
                    update={
                        "state": "completed",
                        "answers": answer_snapshot,
                        "answered_count": len(answer_snapshot),
                        "safety_triggered": scored.safety_triggered,
                        "completed_at": current,
                        "updated_at": current,
                    }
                )
                saved_session = self.repository.save_assessment_session(
                    completed_session,
                    expected_version=latest_session.version,
                )
                result = AssessmentResultDocument(
                    _id=self.repository.next_assessment_result_id(),
                    session_id=saved_session.document_id,
                    user_id=saved_session.user_id,
                    module_code=saved_session.module_code,
                    scoring_rule_version=scored.scoring_rule_version,
                    answers_snapshot=answer_snapshot,
                    fixed_summary=scored.fixed_summary,
                    reference_band=scored.reference_band,
                    boundary_notice=scored.boundary_notice,
                    ai_assist_snapshot_id=None,
                    result_state=scored.result_state,
                    score=scored.score,
                    dimension_summary=scored.dimension_summary,
                    safety_state="can_be_safe"
                    if scored.safety_triggered
                    and saved_session.safety_confirmation_state == "can_be_safe"
                    else "not_triggered",
                    visible_copy_version=scored.visible_copy_version,
                    deleted_at=None,
                    created_at=current,
                    updated_at=current,
                    version=1,
                )
                saved_result = self.repository.create_assessment_result(result)

            response = CompleteAssessmentSessionResponse(
                completion_state="result_ready",
                session_id=saved_session.document_id,
                result_id=saved_result.document_id,
                safety_triggered=scored.safety_triggered,
                score=saved_result.score,
                result_state=saved_result.result_state,
            )
            self.idempotency.complete(
                reservation,
                status_code=200,
                response_digest=response.model_dump_json(),
            )
            self._audit(
                request_id=request_id,
                actor_id=subject.subject_id,
                action="assessment_complete",
                resource_id=saved_session.document_id,
                reason_code="completed",
                facts={
                    "action_code": "complete",
                    "object_version": saved_session.version,
                    "resource_version": saved_session.questionnaire_version,
                    "status": saved_result.result_state,
                },
            )
            return response
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

    def _ensure_assessment_access(self, user_id: str) -> None:
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
                resource_type="assessment_session",
                resource_id=resource_id,
                data_scope="necessary_facts",
                outcome="success",
                reason_code=reason_code,
                occurred_at=datetime.now(UTC),
                facts=facts,
            )
        except Exception:
            logger.warning("audit_write_failed")

    def _decode_start_response(self, response_digest: str | None) -> StartAssessmentSessionResponse:
        if response_digest is None:
            raise ApiException(500, "INTERNAL_ERROR")
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        return StartAssessmentSessionResponse.model_validate_json(response_digest)

    def _decode_complete_response(
        self, response_digest: str | None
    ) -> CompleteAssessmentSessionResponse:
        if response_digest is None:
            raise ApiException(500, "INTERNAL_ERROR")
        error = deserialize_api_error(response_digest)
        if error is not None:
            raise error
        return CompleteAssessmentSessionResponse.model_validate_json(response_digest)


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
