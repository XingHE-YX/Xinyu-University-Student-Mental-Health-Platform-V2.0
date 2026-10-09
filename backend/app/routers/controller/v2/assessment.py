"""Assessment safety branch routes."""

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.assessment import (
    AbandonAssessmentSessionRequest,
    AssessmentResultDeleteRequest,
    CompleteAssessmentSessionRequest,
    SafetyConfirmationRequest,
    StartAssessmentSessionRequest,
    SupportResourceAckRequest,
)
from app.models.v2.responses.assessment import (
    AssessmentModuleListResponse,
    AssessmentResultDeleteResponse,
    AssessmentResultListResponse,
    AssessmentResultProjection,
    AssessmentSessionStateResponse,
    SafetyConfirmationResponse,
    StartAssessmentSessionResponse,
    SupportResourceAckResponse,
)
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
    require_idempotency_key,
)

router = APIRouter(prefix="/assessment-sessions", tags=["assessment"])
contract_router = APIRouter(prefix="", tags=["assessment"])


@contract_router.get("/assessment-modules")
async def assessment_modules(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[AssessmentModuleListResponse]:
    data = await get_container(request).assessment_service.list_modules(bearer_token(authorization))
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("", response_model=ApiEnvelope[StartAssessmentSessionResponse])
async def start_assessment_session(
    request: Request,
    body: StartAssessmentSessionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[StartAssessmentSessionResponse]:
    data = await get_container(request).assessment_service.start_session(
        bearer_token(authorization),
        module_code=body.module_code,
        request_id=request_id(request),
        idempotency_key=body.client_start_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/{session_id}/complete")
async def complete_assessment_session(
    request: Request,
    session_id: str,
    body: CompleteAssessmentSessionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    access_token = bearer_token(authorization)
    data = await get_container(request).assessment_service.complete_session(
        access_token,
        session_id=session_id,
        object_version=body.object_version,
        answers=[answer.model_dump(mode="json") for answer in body.answers],
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    if data.completion_state == "result_ready" and data.result_id:
        await get_container(request).assessment_service.attach_ai_assist(
            access_token,
            result_id=data.result_id,
        )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/{session_id}/abandon")
async def abandon_assessment_session(
    request: Request,
    session_id: str,
    body: AbandonAssessmentSessionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[AssessmentSessionStateResponse]:
    data = await get_container(request).assessment_service.abandon_session(
        bearer_token(authorization),
        session_id=session_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)


@contract_router.get("/assessment-results/{result_id}")
async def assessment_result(
    request: Request,
    result_id: str,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[AssessmentResultProjection]:
    data = await get_container(request).assessment_service.get_result(
        bearer_token(authorization), result_id=result_id
    )
    return ApiEnvelope.success(request_id(request), data=data)


@contract_router.get("/assessment-results")
async def assessment_results(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    module_code: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> ApiEnvelope[AssessmentResultListResponse]:
    data = await get_container(request).assessment_service.list_results(
        bearer_token(authorization),
        module_code=module_code,
        from_date=from_date,
        to_date=to_date,
        cursor=cursor,
        limit=limit,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@contract_router.delete("/assessment-results/{result_id}")
async def delete_assessment_result(
    request: Request,
    result_id: str,
    body: AssessmentResultDeleteRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[AssessmentResultDeleteResponse]:
    data = await get_container(request).assessment_service.delete_result(
        bearer_token(authorization),
        result_id=result_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/{session_id}/safety-confirmation")
async def safety_confirmation(
    request: Request,
    session_id: str,
    body: SafetyConfirmationRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[SafetyConfirmationResponse]:
    access_token = bearer_token(authorization)
    idempotency_key = require_idempotency_key(request)
    data = await get_container(request).safety_service.confirm_safety(
        access_token,
        session_id=session_id,
        state=body.state,
        object_version=body.object_version,
        answers=[answer.model_dump(mode="json") for answer in body.answers],
        request_id=request_id(request),
        idempotency_key=idempotency_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/{session_id}/support-resource-ack")
async def support_resource_ack(
    request: Request,
    session_id: str,
    body: SupportResourceAckRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[SupportResourceAckResponse]:
    access_token = bearer_token(authorization)
    idempotency_key = require_idempotency_key(request)
    data = await get_container(request).safety_service.acknowledge_support_resource(
        access_token,
        session_id=session_id,
        resource_context=body.resource_context,
        resource_version=body.resource_version,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=idempotency_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)
