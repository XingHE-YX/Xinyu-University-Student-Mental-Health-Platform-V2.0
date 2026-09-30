from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.responses.admin_workbench import (
    AuditPage,
)
from app.routers.dependencies import (
    get_container,
    request_id,
    super_admin_subject,
)

router = APIRouter(prefix="/admin", tags=["admin-audit"])
AuthorizationHeader = Annotated[str | None, Header()]


@router.get("/audit-events")
async def audit_events(
    request: Request,
    authorization: AuthorizationHeader = None,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    resource_type: str | None = None,
    action: str | None = None,
    outcome: Literal["success", "denied", "conflict", "failure"] | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[AuditPage]:
    (await super_admin_subject(request, authorization))
    items, next_cursor = await get_container(request).admin_workbench_service.list_audit_page(
        from_at=from_at,
        to_at=to_at,
        resource_type=resource_type,
        action=action,
        outcome=outcome,
        cursor=cursor,
        limit=limit,
    )
    return ApiEnvelope.success(request_id(request), AuditPage(items=items, next_cursor=next_cursor))
