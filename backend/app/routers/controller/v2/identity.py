from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.student_core import (
    IdentityVerificationRequest,
)
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
    require_idempotency_key,
)

router = APIRouter(tags=["identity"])


@router.post("/identity/verifications")
async def verify_identity(
    request: Request,
    body: IdentityVerificationRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    data = await get_container(request).identity_service.verify_student_identity(
        bearer_token(authorization),
        student_name=body.student_name,
        student_number=body.student_number,
        user_version=body.object_version
        or (
            await get_container(request).identity_service.repository.get_user(
                (
                    await get_container(request).auth_service.authenticate(
                        bearer_token(authorization)
                    )
                ).subject_id
            )
        ).version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(
        request_id(request),
        {
            "verification_id": data.identity_record_id,
            "status": data.verification_status,
            "next_poll_after_seconds": 5 if data.verification_status == "pending" else None,
        },
    )


@router.get("/identity/verifications/{verification_id}")
async def verification_status(
    request: Request, verification_id: str, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        (
            await get_container(request).identity_service.get_verification(
                bearer_token(authorization), verification_id
            )
        ),
    )


@router.get("/me/anonymous-identity")
async def anonymous_identity(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        (
            await get_container(request).identity_service.get_anonymous_identity(
                bearer_token(authorization)
            )
        ),
    )
