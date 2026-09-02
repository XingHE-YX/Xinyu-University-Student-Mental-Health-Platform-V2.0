from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.api.dependencies import bearer_token, request_id, require_idempotency_key
from app.schemas.envelope import ApiEnvelope
from app.schemas.student_core import (
    AccountActionRequest,
    ConsentRequest,
    IdentityVerificationRequest,
    MoodRequest,
)

router = APIRouter(prefix="/api/v1", tags=["student-core"])


@router.get("/app/bootstrap")
async def bootstrap(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request), request.app.state.bootstrap_service.get(bearer_token(authorization))
    )


@router.post("/consents/base")
async def base_consent(
    request: Request, body: ConsentRequest, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    if body.action != "accepted":
        from app.schemas.errors import ApiException

        raise ApiException(422, "VALIDATION_FAILED")
    token = bearer_token(authorization)
    version = body.object_version or request.app.state.consent_service.repository.get_user(
        request.app.state.auth_service.authenticate(token).subject_id
    ).version
    data = request.app.state.consent_service.accept_base_consent(
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
    version = body.object_version or request.app.state.consent_service.repository.get_user(
        request.app.state.auth_service.authenticate(token).subject_id
    ).version
    if body.action == "accepted":
        data = request.app.state.consent_service.accept_community_consent(
            token,
            document_version=body.document_version,
            user_version=version,
            request_id=request_id(request),
            idempotency_key=key,
        )
    else:
        data = request.app.state.consent_service.withdraw_community_consent(
            token,
            document_version=body.document_version,
            user_version=version,
            request_id=request_id(request),
            idempotency_key=key,
        )
    return ApiEnvelope.success(request_id(request), data)


@router.post("/identity/verifications")
async def verify_identity(
    request: Request,
    body: IdentityVerificationRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    data = await request.app.state.identity_service.verify_student_identity(
        bearer_token(authorization),
        student_name=body.student_name,
        student_number=body.student_number,
        user_version=body.object_version
        or request.app.state.identity_service.repository.get_user(
            request.app.state.auth_service.authenticate(bearer_token(authorization)).subject_id
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
        request.app.state.identity_service.get_verification(
            bearer_token(authorization), verification_id
        ),
    )


@router.get("/me/anonymous-identity")
async def anonymous_identity(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        request.app.state.identity_service.get_anonymous_identity(bearer_token(authorization)),
    )


@router.get("/today")
async def today(
    request: Request,
    previous_quote_id: str | None = Query(default=None),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        request.app.state.today_service.get_today(
            bearer_token(authorization), previous_quote_id=previous_quote_id
        ),
    )


@router.put("/moods/today")
async def put_mood(
    request: Request, body: MoodRequest, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    data = request.app.state.mood_service.record_today_mood(
        bearer_token(authorization),
        mood_code=body.mood_code,
        record_date=body.record_date,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)


@router.get("/moods")
async def moods(
    request: Request,
    from_date: str | None = None,
    to_date: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    data = request.app.state.mood_service.list_history(
        bearer_token(authorization),
        from_date=from_date,
        to_date=to_date,
        cursor=cursor,
        limit=limit,
    )
    return ApiEnvelope.success(request_id(request), data)


@router.delete("/moods/{record_id}")
async def delete_mood(
    request: Request,
    record_id: str,
    object_version: int = Query(..., ge=1),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    data = request.app.state.mood_service.delete_mood(
        bearer_token(authorization),
        record_id=record_id,
        object_version=object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)


@router.get("/support-resources")
async def support_resources(
    request: Request,
    context: str = Query(default="normal"),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    bearer_token(authorization)
    return ApiEnvelope.success(
        request_id(request),
        request.app.state.support_resource_service.list_resources(context=context),
    )


@router.post("/account/stop")
async def stop_account(
    request: Request,
    body: AccountActionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    from app.schemas.errors import ApiException

    if body.confirmation_text != "停止使用":
        raise ApiException(422, "VALIDATION_FAILED")
    data = request.app.state.account_service.stop(
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
    from app.schemas.errors import ApiException

    if body.confirmation_text != "恢复使用":
        raise ApiException(422, "VALIDATION_FAILED")
    data = request.app.state.account_service.recover(
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
        request_id(request), request.app.state.account_service.status(bearer_token(authorization))
    )
