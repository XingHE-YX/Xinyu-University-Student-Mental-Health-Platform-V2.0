"""Server-side projections and state transitions for the admin workbench."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, Literal, cast

from app.infra.config.settings import Settings
from app.infra.database.common import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.infra.database.memory.audit import AuditRepository, InMemoryAuditRepository
from app.infra.database.memory.domain import InMemoryDomainDataRepository
from app.infra.database.memory.tasks import MemoryAdminTaskRepository
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.logger.common import traced
from app.infra.serializer.error.common import ApiException
from app.infra.serializer.error.database import RepositoryCommitUncertain
from app.models.v2.documents import WorkTaskDocument
from app.models.v2.responses.admin_workbench import (
    AuditEvent,
    TaskDetail,
    TaskFact,
    TaskKind,
    TaskMutationResult,
    TaskSummary,
    WorkbenchPage,
    WorkbenchSection,
)
from app.services.v2.idempotency_service import IdempotencyService, serialize_api_error
from app.services.v2.repositories import AdminTaskRepository, DomainRepository


def task_mutation(
    function: Callable[..., Awaitable[TaskMutationResult]],
) -> Callable[..., Awaitable[TaskMutationResult]]:
    @wraps(function)
    async def mutate(
        self: AdminWorkbenchService, task_id: str, **kwargs: Any
    ) -> TaskMutationResult:
        await self.initialize()
        reservation = await self.idempotency.begin(
            "admin",
            kwargs["admin_id"],
            f"/admin/tasks/{task_id}/{function.__name__}",
            kwargs["idempotency_key"],
            {
                key: value
                for key, value in kwargs.items()
                if key not in {"request_id", "idempotency_key"}
            },
        )
        if reservation.replayed:
            from app.services.v2.idempotency_service import deserialize_api_error

            error = deserialize_api_error(reservation.record.response_digest)
            if error is not None:
                raise error
            return TaskMutationResult.model_validate_json(reservation.record.response_digest or "")
        try:
            async with self.task_repository.transaction():
                result = await function(self, task_id, **kwargs)
                await self.idempotency.complete(
                    reservation, status_code=200, response_digest=result.model_dump_json()
                )
                return result
        except asyncio.CancelledError as error:
            await self.idempotency.cancel(reservation, error)
            raise
        except RepositoryCommitUncertain:
            raise
        except Exception as error:
            failure = (
                error
                if isinstance(error, ApiException)
                else ApiException(503, "DEPENDENCY_UNAVAILABLE")
                if isinstance(error, RepositoryError)
                else ApiException(500, "INTERNAL_ERROR")
            )
            await self.idempotency.complete(
                reservation,
                status_code=failure.status_code,
                response_digest=serialize_api_error(failure),
                outcome="failure",
            )
            if failure is error:
                raise
            raise failure from error

    return mutate


class AdminWorkbenchService:
    """Owns the minimal demo task index used by the HTTP adapter.

    The service deliberately stores only projected facts. A production deployment
    can replace this store with a repository without changing the API projection.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        audit_repository: AuditRepository | None = None,
        task_repository: AdminTaskRepository | None = None,
        content_repository: DomainRepository | None = None,
        idempotency_service: IdempotencyService | None = None,
    ) -> None:
        self.settings = settings
        self.content_repository = content_repository or InMemoryDomainDataRepository()
        self.task_repository = task_repository or MemoryAdminTaskRepository(self.content_repository)
        self.tasks: dict[str, dict[str, Any]] = {}
        self.audit = AuditWriter(
            audit_repository or InMemoryAuditRepository(),
            environment_id=settings.cloudbase_env_id or settings.environment_kind.value,
        )
        self.idempotency = idempotency_service or IdempotencyService()
        share_memory_transaction(
            self.content_repository, self.idempotency.repository, self.audit.repository
        )
        self._initialize_lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._initialize_lock:
            if self._initialized:
                return
            await self._reload_tasks()
            if not self.tasks:
                await self._seed_demo_tasks()
            self._initialized = True

    @traced
    async def list_tasks(
        self,
        section: WorkbenchSection,
        *,
        admin_id: str,
        cursor: str | None,
        limit: int,
    ) -> WorkbenchPage:
        await self.initialize()
        (await self._reload_tasks())
        tasks = [
            task
            for task in self.tasks.values()
            if not task.get("is_deleted", False) and self._in_section(task, section, admin_id)
        ]
        tasks.sort(key=lambda item: str(item["updated_at"]), reverse=True)
        offset = self._decode_cursor(cursor)
        page_items = tasks[offset : offset + max(1, min(limit, 100))]
        next_cursor = (
            str(offset + len(page_items)) if offset + len(page_items) < len(tasks) else None
        )
        return WorkbenchPage(
            items=[self._summary(task, admin_id=admin_id) for task in page_items],
            next_cursor=next_cursor,
        )

    @traced
    async def get_task(self, task_id: str, *, admin_id: str) -> TaskDetail:
        await self.initialize()
        (await self._reload_tasks())
        task = self.tasks.get(task_id)
        if task is None or task.get("is_deleted", False):
            raise ApiException(404, "NOT_FOUND")
        return self._detail(task)

    @traced
    async def record_view(self, task_id: str, *, admin_id: str, request_id: str) -> None:
        """Record a minimal detail-view audit event after the projection is authorized."""

        await self.initialize()
        (await self._reload_tasks())
        task = self.tasks.get(task_id)
        if task is None or task.get("is_deleted", False):
            return
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="admin",
                actor_id=admin_id,
                capability="super_admin",
                action="task_view",
                resource_type="task",
                resource_id=task_id,
                data_scope="necessary_facts,redacted_content",
                outcome="success",
                reason_code=None,
                occurred_at=datetime.now(UTC),
                facts={"task_kind": task["task_kind"], "object_version": task["version"]},
            )
        )

    @traced
    async def record_task_outcome(
        self,
        task_id: str,
        *,
        admin_id: str,
        request_id: str,
        action: str,
        outcome: Literal["denied", "conflict", "failure"],
        reason_code: str,
    ) -> None:
        await self.initialize()
        (await self._reload_tasks())
        task = self.tasks.get(task_id)
        if task is None or task.get("is_deleted", False):
            return
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="admin",
                actor_id=admin_id,
                capability="super_admin",
                action=action,
                resource_type="task",
                resource_id=task_id,
                data_scope="task_state,object_version",
                outcome=outcome,
                reason_code=reason_code,
                occurred_at=datetime.now(UTC),
                facts={"task_kind": task["task_kind"], "object_version": task["version"]},
            )
        )

    @task_mutation
    @traced
    async def claim(
        self,
        task_id: str,
        *,
        object_version: int,
        admin_id: str,
        request_id: str,
        idempotency_key: str,
    ) -> TaskMutationResult:
        task = await self._get_mutable(task_id, object_version, admin_id, idempotency_key)
        if task["state"] != "needs_action":
            raise ApiException(409, "VERSION_CONFLICT", current_version=task["version"])
        task.update(
            {
                "state": "claimed",
                "assigned_admin_id": admin_id,
                "version": task["version"] + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        (await self._save_task(task, expected_version=object_version))
        result = self._result(task, request_id)
        (await self._write_audit(request_id, task, "task_claim", "success", admin_id))
        return result

    @task_mutation
    @traced
    async def release(
        self,
        task_id: str,
        *,
        object_version: int,
        admin_id: str,
        request_id: str,
        idempotency_key: str,
    ) -> TaskMutationResult:
        task = await self._get_mutable(task_id, object_version, admin_id, idempotency_key)
        if task.get("assigned_admin_id") != admin_id or task["state"] != "claimed":
            raise ApiException(403, "FORBIDDEN")
        task.update(
            {
                "state": "needs_action",
                "assigned_admin_id": None,
                "version": task["version"] + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        (await self._save_task(task, expected_version=object_version))
        result = self._result(task, request_id)
        (await self._write_audit(request_id, task, "task_release", "success", admin_id))
        return result

    @task_mutation
    @traced
    async def decide(
        self,
        task_id: str,
        *,
        object_version: int,
        admin_id: str,
        request_id: str,
        idempotency_key: str,
        action: str,
        action_code: str | None = None,
        fact_note: str | None = None,
        due_at: datetime | None = None,
        internal_reason: str | None = None,
    ) -> TaskMutationResult:
        task = await self._get_mutable(task_id, object_version, admin_id, idempotency_key)
        if task.get("assigned_admin_id") != admin_id or task["state"] != "claimed":
            raise ApiException(403, "FORBIDDEN")
        allowed = set(self._allowed_actions(task["task_kind"], task.get("source_type")))
        if action not in allowed:
            raise ApiException(422, "VALIDATION_FAILED")
        if (
            task["task_kind"] == "followup"
            and action_code == "contact_made"
            and self.settings.environment_kind.value == "demo"
        ):
            raise ApiException(422, "VALIDATION_FAILED")
        task.update(
            {
                "state": "waiting_other" if action == "safety_review" else "completed",
                "version": task["version"] + 1,
                "updated_at": datetime.now(UTC),
            }
        )
        if fact_note or internal_reason or due_at:
            note = fact_note or internal_reason or ""
            task.setdefault("records", []).append(
                {
                    "label": "已记录事实",
                    "value": note,
                }
            )
            if due_at:
                task["records"].append({"label": "下一次跟进时间", "value": due_at.isoformat()})
        task["last_action"] = action
        task["object_version"] = task["version"]
        try:
            if task["task_kind"] == "content_review" and self.content_repository is not None:
                async with self.content_repository.transaction():
                    (await self._apply_content_decision(task, action))
                    (await self._save_task(task, expected_version=object_version))
            else:
                (await self._save_task(task, expected_version=object_version))
        except RepositoryNotFound as error:
            raise ApiException(404, "NOT_FOUND") from error
        except RepositoryVersionConflict as error:
            raise ApiException(
                409, "VERSION_CONFLICT", current_version=error.current_version
            ) from error
        except RepositoryCommitUncertain:
            raise
        except RepositoryError as error:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE") from error
        result = self._result(task, request_id)
        (await self._write_audit(request_id, task, action, "success", admin_id))
        return result

    @traced
    async def list_audit(self) -> list[AuditEvent]:
        return [
            AuditEvent(
                request_id=event.request_id,
                actor=event.actor_id,
                capability=event.capability or "",
                resource=f"{event.resource_type}:{event.resource_id}",
                action=event.action,
                data_scope=[part for part in event.data_scope.split(",") if part],
                outcome=cast(
                    Literal["success", "denied", "conflict", "failure"],
                    event.outcome
                    if event.outcome in {"success", "denied", "conflict", "failure"}
                    else "failure",
                ),
                reason_code=event.reason_code,
                occurred_at=event.occurred_at,
                environment_kind=self.settings.environment_kind.value,
            )
            for event in (await self.audit.repository.list())
        ]

    @traced
    async def list_audit_page(
        self,
        *,
        from_at: datetime | None = None,
        to_at: datetime | None = None,
        resource_type: str | None = None,
        action: str | None = None,
        outcome: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> tuple[list[AuditEvent], str | None]:
        """Return a bounded, read-only audit projection with opaque offset cursors."""

        events = await self.list_audit()
        filtered = [
            event
            for event in events
            if (from_at is None or event.occurred_at >= from_at)
            and (to_at is None or event.occurred_at <= to_at)
            and (not resource_type or event.resource.startswith(f"{resource_type}:"))
            and (not action or event.action == action)
            and (not outcome or event.outcome == outcome)
        ]
        filtered.sort(key=lambda event: event.occurred_at, reverse=True)
        offset = self._decode_cursor(cursor)
        page_size = max(1, min(limit, 100))
        page = filtered[offset : offset + page_size]
        next_cursor = str(offset + len(page)) if offset + len(page) < len(filtered) else None
        return page, next_cursor

    @traced
    async def reset_demo(
        self, *, request_id: str, admin_id: str, scopes: list[str]
    ) -> list[dict[str, str]]:
        await self.initialize()
        if not self.settings.demo_reset_allowed or self.settings.environment_kind.value != "demo":
            (
                await self.audit.write(
                    request_id=request_id,
                    actor_type="admin",
                    actor_id=admin_id,
                    capability="super_admin",
                    action="demo_reset",
                    resource_type="demo",
                    resource_id="demo_namespace",
                    data_scope="demo_namespace",
                    outcome="denied",
                    reason_code="FORBIDDEN",
                    occurred_at=datetime.now(UTC),
                )
            )
            raise ApiException(403, "FORBIDDEN")
        self.tasks.clear()
        (await self._seed_demo_tasks())
        results = [{"collection": scope, "state": "completed"} for scope in scopes]
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="admin",
                actor_id=admin_id,
                capability="super_admin",
                action="demo_reset",
                resource_type="demo",
                resource_id="demo_namespace",
                data_scope=",".join(scopes),
                outcome="success",
                reason_code="demo_reset_confirmed",
                occurred_at=datetime.now(UTC),
            )
        )
        return results

    @traced
    async def _seed_demo_tasks(self) -> None:
        """Populate only synthetic, non-identifying tasks in the demo namespace."""

        if self.settings.environment_kind.value != "demo":
            return
        now = datetime.now(UTC)
        templates: list[tuple[str, TaskKind, str, list[dict[str, str]], str | None]] = [
            (
                "task-demo-content-01",
                "content_review",
                "树洞内容待人工确认",
                [{"label": "来源", "value": "匿名树洞"}, {"label": "进入时间", "value": "今日"}],
                "这是一段已脱敏的演示内容。",
            ),
            (
                "task-demo-safety-01",
                "safety_support",
                "安全支持记录待处理",
                [
                    {"label": "来源", "value": "安全确认流程"},
                    {"label": "当前状态", "value": "待确认"},
                ],
                None,
            ),
            (
                "task-demo-identity-01",
                "identity_access",
                "身份授权申请待审批",
                [
                    {"label": "申请范围", "value": "遮罩姓名、学号后四位"},
                    {"label": "有效期", "value": "24 小时"},
                ],
                None,
            ),
            (
                "task-demo-followup-01",
                "followup",
                "跟进事实待记录",
                [
                    {"label": "来源", "value": "演示跟进"},
                    {"label": "当前状态", "value": "等待后续事实"},
                ],
                None,
            ),
        ]
        self.tasks = {
            task_id: {
                "task_id": task_id,
                "task_kind": task_kind,
                "state": "needs_action",
                "created_at": now - timedelta(minutes=index * 7),
                "updated_at": now - timedelta(minutes=index * 7),
                "assigned_admin_id": None,
                "safe_summary": safe_summary,
                "version": 1,
                "facts": facts,
                "records": [],
                "redacted_content": redacted_content,
                "is_deleted": False,
            }
            for index, (task_id, task_kind, safe_summary, facts, redacted_content) in enumerate(
                templates
            )
        }
        if self.task_repository is not None:
            for task_id, task in tuple(self.tasks.items()):
                current = await self.task_repository.get(task_id)
                if current is None:
                    (await self.task_repository.create(task))
                    continue
                task["version"] = int(current["version"]) + 1
                task["object_version"] = task["version"]
                (await self.task_repository.save(task, expected_version=int(current["version"])))
            (await self._reload_tasks())

    @traced
    async def _get_mutable(
        self, task_id: str, object_version: int, admin_id: str, key: str
    ) -> dict[str, Any]:
        (await self._reload_tasks())
        task = self.tasks.get(task_id)
        if task is None or task.get("is_deleted", False):
            raise ApiException(404, "NOT_FOUND")
        if int(task["version"]) != object_version:
            raise ApiException(409, "VERSION_CONFLICT", current_version=task["version"])
        return deepcopy(task)

    @traced
    async def _reload_tasks(self) -> None:
        if self.task_repository is not None:
            self.tasks = {task["task_id"]: task for task in (await self.task_repository.list())}
        elif self.content_repository is not None:
            for document in await self.content_repository.list_work_tasks():
                task = document.model_dump(by_alias=True, mode="python")
                task["task_id"] = task.pop("_id")
                self.tasks[str(task["task_id"])] = task

    @traced
    async def _save_task(self, task: dict[str, Any], *, expected_version: int) -> None:
        task["object_version"] = task["version"]
        if self.task_repository is not None:
            (await self.task_repository.save(task, expected_version=expected_version))
        elif self.content_repository is not None:
            try:
                (await self.content_repository.get_work_task(str(task["task_id"])))
            except RepositoryNotFound:
                pass
            else:
                payload: dict[str, Any] = {"_id": task["task_id"]}
                for field in WorkTaskDocument.model_fields:
                    if field != "document_id" and field in task:
                        payload[field] = task[field]
                (
                    await self.content_repository.save_work_task(
                        WorkTaskDocument.model_validate(payload),
                        expected_version=expected_version,
                    )
                )
        self.tasks[str(task["task_id"])] = task

    @traced
    async def _apply_content_decision(self, task: dict[str, Any], action: str) -> None:
        if self.content_repository is None:
            return
        source_type = task.get("source_type")
        source_id = task.get("source_id")
        if source_type not in {"post", "response"} or not isinstance(source_id, str):
            return
        if source_id == task.get("task_id"):
            return  # Built-in workbench fixture with no student content behind it.
        if source_type == "post":
            post = await self.content_repository.get_treehole_post(source_id)
            if post.deleted_at is not None:
                raise RepositoryNotFound("treehole post is deleted")
            target = {
                "publish": "published",
                "protect": "protected",
                "unpublish": "unpublished",
                "safety_review": "safety_priority",
            }[action]
            (
                await self.content_repository.save_treehole_post(
                    post.model_copy(
                        update={
                            "visibility_state": target,
                            "review_state": "decided",
                            "safety_state": (
                                "needs_support_review"
                                if action == "safety_review"
                                else post.safety_state
                            ),
                        }
                    ),
                    expected_version=post.version,
                )
            )
            return
        if action == "protect":
            raise ApiException(422, "VALIDATION_FAILED", "树洞回应不能使用保护展示")
        response = await self.content_repository.get_treehole_response(source_id)
        if response.deleted_at is not None:
            raise RepositoryNotFound("treehole response is deleted")
        target = "published" if action == "publish" else "unpublished"
        if action == "safety_review":
            target = "checking"
        (
            await self.content_repository.save_treehole_response(
                response.model_copy(update={"state": target}),
                expected_version=response.version,
            )
        )

    @staticmethod
    @traced
    def _decode_cursor(cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            return max(0, int(cursor))
        except ValueError as error:
            raise ApiException(400, "INVALID_REQUEST") from error

    @staticmethod
    @traced
    def _in_section(task: dict[str, Any], section: WorkbenchSection, admin_id: str) -> bool:
        state = task["state"]
        if section == "needs_action":
            return state == "needs_action" or (
                state == "claimed" and task.get("assigned_admin_id") == admin_id
            )
        if section == "waiting_other":
            return state == "waiting_other" or (
                state == "claimed" and task.get("assigned_admin_id") != admin_id
            )
        if section == "recent":
            return state in {"completed", "cancelled"}
        return True

    @traced
    def _summary(self, task: dict[str, Any], *, admin_id: str) -> TaskSummary:
        assigned = task.get("assigned_admin_id")
        return TaskSummary(
            task_id=task["task_id"],
            task_kind=task["task_kind"],
            state=task["state"],
            created_at=task["created_at"],
            updated_at=task["updated_at"],
            assigned_admin_display=("当前工作人员" if assigned == admin_id else "其他工作人员")
            if assigned
            else None,
            safe_summary=task["safe_summary"],
            object_version=task["version"],
        )

    @traced
    def _detail(self, task: dict[str, Any]) -> TaskDetail:
        return TaskDetail(
            task_id=task["task_id"],
            task_kind=task["task_kind"],
            state=task["state"],
            object_version=task["version"],
            facts=[TaskFact(**fact) for fact in task.get("facts", [])],
            redacted_content=task.get("redacted_content"),
            allowed_actions=self._allowed_actions(task["task_kind"], task.get("source_type")),
            records=[TaskFact(**fact) for fact in task.get("records", [])],
            environment_kind=self.settings.environment_kind.value,
        )

    @staticmethod
    @traced
    def _allowed_actions(task_kind: TaskKind, source_type: str | None = None) -> list[str]:
        actions = {
            "content_review": ["publish", "protect", "unpublish", "safety_review"],
            "safety_support": ["record_support", "set_followup", "complete"],
            "identity_access": ["approve", "deny", "revoke"],
            "followup": ["record_followup", "complete"],
        }[task_kind]
        return [
            action for action in actions if not (source_type == "response" and action == "protect")
        ]

    @staticmethod
    @traced
    def _result(task: dict[str, Any], request_id: str) -> TaskMutationResult:
        return TaskMutationResult(
            task_id=task["task_id"],
            new_state=task["state"],
            new_object_version=task["version"],
            audit_request_id=request_id,
        )

    @traced
    async def _write_audit(
        self, request_id: str, task: dict[str, Any], action: str, outcome: str, admin_id: str
    ) -> None:
        (
            await self.audit.write(
                request_id=request_id,
                actor_type="admin",
                actor_id=admin_id,
                capability="super_admin",
                action=action,
                resource_type="task",
                resource_id=task["task_id"],
                data_scope="task_state,object_version",
                outcome=outcome,
                reason_code=None,
                occurred_at=datetime.now(UTC),
                facts={"task_kind": task["task_kind"], "object_version": task["version"]},
            )
        )
