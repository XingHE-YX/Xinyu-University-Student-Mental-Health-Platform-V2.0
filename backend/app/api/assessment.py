"""Assessment safety branch routes."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.dependencies import bearer_token, request_id, require_idempotency_key
from app.schemas.assessment import (
    SafetyConfirmationRequest,
    SafetyConfirmationResponse,
    SupportResourceAckRequest,
    SupportResourceAckResponse,
)
from app.schemas.envelope import ApiEnvelope

router = APIRouter(prefix="/api/v1/assessment-sessions", tags=["assessment"])


@router.post("/{session_id}/safety-confirmation")
async def safety_confirmation(
    request: Request,
    session_id: str,
    body: SafetyConfirmationRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[SafetyConfirmationResponse]:
    access_token = bearer_token(authorization)
    idempotency_key = require_idempotency_key(request)
    data = request.app.state.safety_service.confirm_safety(
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
    data = request.app.state.safety_service.acknowledge_support_resource(
        access_token,
        session_id=session_id,
        resource_context=body.resource_context,
        resource_version=body.resource_version,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=idempotency_key,
    )
    return ApiEnvelope.success(request_id(request), data=data)
