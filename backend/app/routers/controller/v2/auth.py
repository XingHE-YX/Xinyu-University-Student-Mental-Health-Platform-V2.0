"""Student session and self-subject routes."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.auth import RefreshRequest, WechatSessionRequest
from app.models.v2.responses.auth import StudentSessionData
from app.routers.dependencies import bearer_token, get_container, request_id

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/wechat/session")
async def wechat_session(
    request: Request,
    body: WechatSessionRequest,
) -> ApiEnvelope[StudentSessionData]:
    data = await get_container(request).auth_service.login_student(
        body.code,
        client_version=body.client_version,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/refresh")
async def refresh(request: Request, body: RefreshRequest) -> ApiEnvelope[object]:
    data = await get_container(request).auth_service.refresh(
        body.refresh_token,
        expected_subject_type="student",
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/logout")
async def logout(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[dict[str, bool]]:
    token = bearer_token(authorization)
    (await get_container(request).auth_service.logout(token, expected_subject_type="student"))
    return ApiEnvelope.success(request_id(request), data={"success": True})
