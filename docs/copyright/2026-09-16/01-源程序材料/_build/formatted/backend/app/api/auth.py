"""Student session and self-subject routes."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, Request

from app.api.dependencies import bearer_token, request_id, student_subject
from app.schemas.auth import (
    RefreshRequest,
    StudentMeData,
    StudentSessionData,
    WechatSessionRequest,
)
from app.schemas.envelope import ApiEnvelope

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
me_router = APIRouter(prefix="/api/v1", tags=["student"])


@router.post("/wechat/session")
async def wechat_session(
    request: Request,
    body: WechatSessionRequest,
) -> ApiEnvelope[StudentSessionData]:
    data = await request.app.state.auth_service.login_student(
        body.code,
        client_version=body.client_version,
    )
    return ApiEnvelope.success(request_id(request), data=data)


@router.post("/refresh")
async def refresh(request: Request, body: RefreshRequest) -> ApiEnvelope[object]:
    data = request.app.state.auth_service.refresh(
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
    request.app.state.auth_service.logout(token, expected_subject_type="student")
    return ApiEnvelope.success(request_id(request), data={"success": True})


@me_router.get("/me")
async def me(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[StudentMeData]:
    subject = student_subject(request, authorization)
    account_status: Literal["active", "recovery_pending", "stopped", "purged"] = "active"
    account_service = getattr(request.app.state, "account_service", None)
    if account_service is not None:
        account_status = cast(
            Literal["active", "recovery_pending", "stopped", "purged"],
            account_service.status(bearer_token(authorization)).status,
        )
    data = StudentMeData(
        subject_type="student",
        subject_id=subject.subject_id,
        account_status=account_status,
    )
    return ApiEnvelope.success(request_id(request), data=data)
