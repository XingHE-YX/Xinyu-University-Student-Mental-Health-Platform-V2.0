from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
)

router = APIRouter(tags=["today"])


@router.get("/today")
async def today(
    request: Request,
    previous_quote_id: str | None = Query(default=None),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        (
            await get_container(request).today_service.get_today(
                bearer_token(authorization), previous_quote_id=previous_quote_id
            )
        ),
    )
