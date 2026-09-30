from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.student_core import (
    MoodRequest,
    ObjectVersionRequest,
)
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
    require_idempotency_key,
)

router = APIRouter(tags=["mood"])


@router.put("/moods/today")
async def put_mood(
    request: Request, body: MoodRequest, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    data = await get_container(request).mood_service.record_today_mood(
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
    data = await get_container(request).mood_service.list_history(
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
    body: ObjectVersionRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    data = await get_container(request).mood_service.delete_mood(
        bearer_token(authorization),
        record_id=record_id,
        object_version=body.object_version,
        request_id=request_id(request),
        idempotency_key=require_idempotency_key(request),
    )
    return ApiEnvelope.success(request_id(request), data)
