"""HTTP adapter for the read/write admin workbench projection."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ValidationError

from app.infra.security.tokens import AuthenticatedSubject
from app.infra.serializer.envelope import ApiEnvelope
from app.infra.serializer.error.common import ApiException
from app.models.v2.requests.admin_workbench import (
    ContentDecisionRequest,
    FollowupDecisionRequest,
    IdentityDecisionRequest,
    ObjectVersionRequest,
    SafetyDecisionRequest,
)
from app.models.v2.responses.admin_workbench import (
    TaskDetail,
    TaskMutationResult,
    WorkbenchPage,
    WorkbenchSection,
)
from app.routers.dependencies import (
    admin_subject,
    get_container,
    request_id,
    require_idempotency_key,
)
from app.services.v2.admin_workbench_service import AdminWorkbenchService

router = APIRouter(prefix="/admin", tags=["admin-workbench"])
AuthorizationHeader = Annotated[str | None, Header()]


def _service(request: Request) -> AdminWorkbenchService:
    return get_container(request).admin_workbench_service


async def _admin(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = await admin_subject(request, authorization)
    if subject.capability != "super_admin":
        raise ApiException(403, "FORBIDDEN")
    return subject


async def _record_mutation_error(
    request: Request,
    task_id: str,
    admin_id: str,
    action: str,
    error: ApiException,
) -> None:
    outcome: Literal["denied", "conflict", "failure"] = (
        "denied"
        if error.status_code == 403
        else "conflict"
        if error.status_code == 409
        else "failure"
    )
    (
        await _service(request).record_task_outcome(
            task_id,
            admin_id=admin_id,
            request_id=request_id(request),
            action=action,
            outcome=outcome,
            reason_code=error.code,
        )
    )


@router.get("/workbench")
async def workbench(
    request: Request,
    authorization: AuthorizationHeader = None,
    section: WorkbenchSection = "all",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[WorkbenchPage]:
    subject = await _admin(request, authorization)
    data = await _service(request).list_tasks(
        section,
        admin_id=subject.subject_id,
        cursor=cursor,
        limit=limit,
    )
    return ApiEnvelope.success(request_id(request), data)


@router.get("/tasks/{task_id}")
async def task_detail(
    request: Request,
    task_id: str,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskDetail]:
    subject = await _admin(request, authorization)
    service = _service(request)
    data = await service.get_task(task_id, admin_id=subject.subject_id)
    (
        await service.record_view(
            task_id, admin_id=subject.subject_id, request_id=request_id(request)
        )
    )
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/claim")
async def claim_task(
    request: Request,
    task_id: str,
    body: ObjectVersionRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = await _admin(request, authorization)
    try:
        data = await _service(request).claim(
            task_id,
            object_version=body.object_version,
            admin_id=subject.subject_id,
            request_id=request_id(request),
            idempotency_key=require_idempotency_key(request),
        )
    except ApiException as error:
        (await _record_mutation_error(request, task_id, subject.subject_id, "task_claim", error))
        raise
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/release")
async def release_task(
    request: Request,
    task_id: str,
    body: ObjectVersionRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = await _admin(request, authorization)
    try:
        data = await _service(request).release(
            task_id,
            object_version=body.object_version,
            admin_id=subject.subject_id,
            request_id=request_id(request),
            idempotency_key=require_idempotency_key(request),
        )
    except ApiException as error:
        (await _record_mutation_error(request, task_id, subject.subject_id, "task_release", error))
        raise
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/decision")
async def decide_task(
    request: Request,
    task_id: str,
    body: dict[str, Any],
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = await _admin(request, authorization)
    service = _service(request)
    task = await service.get_task(task_id, admin_id=subject.subject_id)
    model = _decision_model(task.task_kind, body)
    action_code = getattr(model, "action_code", None)
    if (
        task.task_kind == "followup"
        and action_code == "contact_made"
        and service.settings.environment_kind.value == "demo"
    ):
        raise ApiException(422, "VALIDATION_FAILED", "演示环境不能记录真实联系结果")
    try:
        data = await service.decide(
            task_id,
            object_version=model.object_version,
            admin_id=subject.subject_id,
            request_id=request_id(request),
            idempotency_key=require_idempotency_key(request),
            action=model.action,
            action_code=action_code,
            fact_note=getattr(model, "fact_note", None),
            due_at=getattr(model, "followup_due_at", None) or getattr(model, "next_due_at", None),
            internal_reason=getattr(model, "internal_reason", None),
        )
    except ApiException as error:
        (await _record_mutation_error(request, task_id, subject.subject_id, model.action, error))
        raise
    return ApiEnvelope.success(request_id(request), data)


def _decision_model(task_kind: str, body: dict[str, Any]) -> Any:
    models: dict[str, type[BaseModel]] = {
        "content_review": ContentDecisionRequest,
        "safety_support": SafetyDecisionRequest,
        "identity_access": IdentityDecisionRequest,
        "followup": FollowupDecisionRequest,
    }
    model_type = models.get(task_kind)
    if model_type is None:
        raise ApiException(422, "VALIDATION_FAILED")
    try:
        return model_type.model_validate(body)
    except ValidationError as error:
        del error
        raise ApiException(422, "VALIDATION_FAILED") from None
