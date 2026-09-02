from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.api.dependencies import bearer_token, request_id, require_idempotency_key
from app.schemas.envelope import ApiEnvelope
from app.schemas.identity_access import (
    IdentityAccessIdentityProjection,
    IdentityAccessRequestCreate,
    IdentityAccessRequestProjection,
)

router = APIRouter(prefix="/api/v1/admin/identity-access-requests", tags=["admin-identity"])
AuthHeader = Annotated[str | None, Header()]


@router.post("")
async def create_identity_access_request(
    request: Request,
    body: IdentityAccessRequestCreate,
    authorization: AuthHeader = None,
) -> ApiEnvelope[IdentityAccessRequestProjection]:
    data = request.app.state.identity_access_service.create_request(
        bearer_token(authorization),
        payload=body,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.get("/{identity_request_id}")
async def get_identity_access_request(
    request: Request,
    identity_request_id: str,
    authorization: AuthHeader = None,
) -> ApiEnvelope[IdentityAccessRequestProjection]:
    data = request.app.state.identity_access_service.get_request(
        bearer_token(authorization), request_id=identity_request_id
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.get("/{identity_request_id}/identity")
async def read_identity(
    request: Request,
    identity_request_id: str,
    authorization: AuthHeader = None,
) -> ApiEnvelope[IdentityAccessIdentityProjection]:
    data = request.app.state.identity_access_service.read_identity(
        bearer_token(authorization),
        request_id=identity_request_id,
        audit_request_id=request_id(request),
    )
    return ApiEnvelope.success(request_id(request), data=data)
