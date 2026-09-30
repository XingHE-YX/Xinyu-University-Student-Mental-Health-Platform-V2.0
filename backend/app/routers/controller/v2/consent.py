from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.student_core import (
    ConsentRequest,
)
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
    require_idempotency_key,
)

router = APIRouter(tags=["consent"])


@router.post("/consents/base")
async def base_consent(
    request: Request, body: ConsentRequest, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    if body.action != "accepted":
        from app.infra.serializer.error.common import ApiException

        raise ApiException(422, "VALIDATION_FAILED")
    token = bearer_token(authorization)
    version = (
        body.object_version
        or (
            await get_container(request).consent_service.repository.get_user(
                (await get_container(request).auth_service.authenticate(token)).subject_id
            )
        ).version
    )
    data = await get_container(request).consent_service.accept_base_consent(
        token,
        document_version=body.document_version,
        user_version=version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)


@router.post("/consents/community")
async def community_consent(
    request: Request, body: ConsentRequest, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    token = bearer_token(authorization)
    key = require_idempotency_key(request)
    version = (
        body.object_version
        or (
            await get_container(request).consent_service.repository.get_user(
                (await get_container(request).auth_service.authenticate(token)).subject_id
            )
        ).version
    )
    if body.action == "accepted":
        data = await get_container(request).consent_service.accept_community_consent(
            token,
            document_version=body.document_version,
            user_version=version,
            request_id=request_id(request),
            idempotency_key=key,
        )
    else:
        data = await get_container(request).consent_service.withdraw_community_consent(
            token,
            document_version=body.document_version,
            user_version=version,
            request_id=request_id(request),
            idempotency_key=key,
        )
    return ApiEnvelope.success(request_id(request), data)
