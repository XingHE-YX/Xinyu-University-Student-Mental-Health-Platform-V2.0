from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.requests.admin_workbench import (
    ResetRequest,
)
from app.models.v2.responses.admin_workbench import (
    ResetCollectionResult,
    ResetResult,
)
from app.routers.dependencies import (
    get_container,
    request_id,
    require_idempotency_key,
    super_admin_subject,
)

router = APIRouter(prefix="/admin", tags=["admin-demo"])
AuthorizationHeader = Annotated[str | None, Header()]


@router.post("/demo/reset")
async def reset_demo(
    request: Request,
    body: ResetRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[ResetResult]:
    subject = await super_admin_subject(request, authorization)
    _ = require_idempotency_key(request)
    service = get_container(request).admin_workbench_service
    results = await service.reset_demo(
        request_id=request_id(request),
        admin_id=subject.subject_id,
        scopes=list(body.reset_scope),
    )
    collections = [
        ResetCollectionResult(
            collection=item["collection"],
            state=cast(Literal["completed", "failed", "skipped"], item["state"]),
            message=item.get("message"),
        )
        for item in results
    ]
    data = ResetResult(
        success=all(item.state == "completed" for item in collections),
        request_id=request_id(request),
        collections=collections,
    )
    return ApiEnvelope.success(request_id(request), data)
