"""HTTP adapter for the read/write admin workbench projection."""

from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel, ValidationError

from app.api.dependencies import admin_subject, request_id, require_idempotency_key
from app.schemas.admin_workbench import (
    AuditPage,
    ContentDecisionRequest,
    FollowupDecisionRequest,
    IdentityDecisionRequest,
    ObjectVersionRequest,
    ResetCollectionResult,
    ResetRequest,
    ResetResult,
    SafetyDecisionRequest,
    TaskDetail,
    TaskMutationResult,
    WorkbenchPage,
    WorkbenchSection,
)
from app.schemas.envelope import ApiEnvelope
from app.schemas.errors import ApiException
from app.security.tokens import AuthenticatedSubject
from app.services.admin_workbench_service import AdminWorkbenchService

router = APIRouter(prefix="/api/v1/admin", tags=["admin-workbench"])
AuthorizationHeader = Annotated[str | None, Header()]


def _service(request: Request) -> AdminWorkbenchService:
    return cast(AdminWorkbenchService, request.app.state.admin_workbench_service)


def _admin(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = admin_subject(request, authorization)
    if subject.capability != "super_admin":
        raise ApiException(403, "FORBIDDEN")
    return subject


def _record_mutation_error(
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
    _service(request).record_task_outcome(
        task_id,
        admin_id=admin_id,
        request_id=request_id(request),
        action=action,
        outcome=outcome,
        reason_code=error.code,
    )


@router.get("/workbench")
async def workbench(
    request: Request,
    authorization: AuthorizationHeader = None,
    section: WorkbenchSection = "all",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ApiEnvelope[WorkbenchPage]:
    subject = _admin(request, authorization)
    data = _service(request).list_tasks(
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
    subject = _admin(request, authorization)
    service = _service(request)
    data = service.get_task(task_id, admin_id=subject.subject_id)
    service.record_view(task_id, admin_id=subject.subject_id, request_id=request_id(request))
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/claim")
async def claim_task(
    request: Request,
    task_id: str,
    body: ObjectVersionRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = _admin(request, authorization)
    try:
        data = _service(request).claim(
            task_id,
            object_version=body.object_version,
            admin_id=subject.subject_id,
            request_id=request_id(request),
            idempotency_key=require_idempotency_key(request),
        )
    except ApiException as error:
        _record_mutation_error(request, task_id, subject.subject_id, "task_claim", error)
        raise
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/release")
async def release_task(
    request: Request,
    task_id: str,
    body: ObjectVersionRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = _admin(request, authorization)
    try:
        data = _service(request).release(
            task_id,
            object_version=body.object_version,
            admin_id=subject.subject_id,
            request_id=request_id(request),
            idempotency_key=require_idempotency_key(request),
        )
    except ApiException as error:
        _record_mutation_error(request, task_id, subject.subject_id, "task_release", error)
        raise
    return ApiEnvelope.success(request_id(request), data)


@router.post("/tasks/{task_id}/decision")
async def decide_task(
    request: Request,
    task_id: str,
    body: dict[str, Any],
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[TaskMutationResult]:
    subject = _admin(request, authorization)
    service = _service(request)
    task = service.tasks.get(task_id)
    if task is None or task.get("is_deleted", False):
        raise ApiException(404, "NOT_FOUND")
    model = _decision_model(task["task_kind"], body)
    action_code = getattr(model, "action_code", None)
    if (
        task["task_kind"] == "followup"
        and action_code == "contact_made"
        and service.settings.environment_kind.value == "demo"
    ):
        raise ApiException(422, "VALIDATION_FAILED", "演示环境不能记录真实联系结果")
    try:
        data = service.decide(
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
        _record_mutation_error(request, task_id, subject.subject_id, model.action, error)
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
    _admin(request, authorization)
    items, next_cursor = _service(request).list_audit_page(
        from_at=from_at,
        to_at=to_at,
        resource_type=resource_type,
        action=action,
        outcome=outcome,
        cursor=cursor,
        limit=limit,
    )
    return ApiEnvelope.success(request_id(request), AuditPage(items=items, next_cursor=next_cursor))


@router.post("/demo/reset")
async def reset_demo(
    request: Request,
    body: ResetRequest,
    authorization: AuthorizationHeader = None,
) -> ApiEnvelope[ResetResult]:
    subject = _admin(request, authorization)
    _ = require_idempotency_key(request)
    service = _service(request)
    results = service.reset_demo(
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
