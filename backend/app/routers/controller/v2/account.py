from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.student_core import (
    AccountActionRequest,
)
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
    require_idempotency_key,
)

router = APIRouter(tags=["account"])


@router.post("/account/stop")
async def stop_account(
    request: Request,
    body: AccountActionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    from app.infra.serializer.error.common import ApiException

    if body.confirmation_text != "停止使用":
        raise ApiException(422, "VALIDATION_FAILED")
    data = await get_container(request).account_service.stop(
        bearer_token(authorization),
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)


@router.post("/account/recover")
async def recover_account(
    request: Request,
    body: AccountActionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    from app.infra.serializer.error.common import ApiException

    if body.confirmation_text not in {None, "恢复使用"}:
        raise ApiException(422, "VALIDATION_FAILED")
    data = await get_container(request).account_service.recover(
        bearer_token(authorization),
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)


@router.get("/account/status")
async def account_status(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        (await get_container(request).account_service.status(bearer_token(authorization))),
    )
