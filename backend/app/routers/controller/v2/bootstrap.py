from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.routers.dependencies import (
    bearer_token,
    get_container,
    request_id,
)

router = APIRouter(tags=["bootstrap"])


@router.get("/app/bootstrap")
async def bootstrap(
    request: Request, authorization: Annotated[str | None, Header()] = None
) -> ApiEnvelope[object]:
    return ApiEnvelope.success(
        request_id(request),
        (await get_container(request).bootstrap_service.get(bearer_token(authorization))),
    )
