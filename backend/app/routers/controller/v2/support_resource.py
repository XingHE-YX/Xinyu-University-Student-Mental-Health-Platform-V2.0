from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, Query, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.routers.dependencies import (
    get_container,
    request_id,
    student_subject,
)

router = APIRouter(tags=["support_resource"])


@router.get("/support-resources")
async def support_resources(
    request: Request,
    context: str = Query(default="normal"),
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[object]:
    (await student_subject(request, authorization))
    return ApiEnvelope.success(
        request_id(request),
        (await get_container(request).support_resource_service.list_resources(context=context)),
    )
