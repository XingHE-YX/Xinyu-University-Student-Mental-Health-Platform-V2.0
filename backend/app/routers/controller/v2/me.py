from typing import Annotated, Literal, cast

from fastapi import APIRouter, Header, Request

from app.infra.serializer.envelope import ApiEnvelope
from app.models.v2.responses.auth import StudentMeData
from app.routers.dependencies import bearer_token, request_id, student_subject

router = APIRouter(tags=["me"])


@router.get("/me")
async def me(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> ApiEnvelope[StudentMeData]:
    subject = await student_subject(request, authorization)
    account_status: Literal["active", "recovery_pending", "stopped", "purged"] = "active"
    account_service = getattr(request.app.state, "account_service", None)
    if account_service is not None:
        account_status = cast(
            Literal["active", "recovery_pending", "stopped", "purged"],
            (await account_service.status(bearer_token(authorization))).status,
        )
    data = StudentMeData(
        subject_type="student",
        subject_id=subject.subject_id,
        account_status=account_status,
    )
    return ApiEnvelope.success(request_id(request), data=data)
