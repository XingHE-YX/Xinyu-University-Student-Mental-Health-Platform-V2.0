"""Fixed-account admin authentication and server-derived capability projection."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.infra.serializer.error.common import ApiException
from app.models.v2.requests.auth import AdminLoginRequest, RefreshRequest
from app.models.v2.responses.auth import AdminMeData, AdminSessionData
from app.routers.dependencies import admin_subject, bearer_token, get_container, request_id

router = APIRouter(prefix="/admin", tags=["admin-auth"])


@router.post("/auth/login")
async def login(request: Request, body: AdminLoginRequest) -> ApiEnvelope[AdminSessionData]:
    data = await get_container(request).auth_service.login_admin(body.login_name, body.password)
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/auth/refresh")
async def refresh(request: Request, body: RefreshRequest) -> ApiEnvelope[object]:
    data = await get_container(request).auth_service.refresh(
        body.refresh_token,
        expected_subject_type="admin",
    )
    if not isinstance(data, AdminSessionData):
        raise ApiException(401, "AUTH_REQUIRED")
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/auth/logout")
async def logout(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[dict[str, bool]]:
    token = bearer_token(authorization)
    (await get_container(request).auth_service.logout(token, expected_subject_type="admin"))
    return ApiEnvelope.success(request_id(request), data={"success": True})


@router.get("/me")
async def me(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[AdminMeData]:
    subject = await admin_subject(request, authorization)
    settings = get_container(request).settings
    data = AdminMeData(
        display_name="心理健康中心工作人员",
        capability_label="超级管理员",
        session_expires_at=subject.session_expires_at,
        environment_kind=settings.environment_kind.value,
    )
    return ApiEnvelope.success(request_id(request), data=data)
