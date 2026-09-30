import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from app.infra.config.settings import Settings
from app.infra.config.validation import EnvironmentKind
from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.common import RepositoryUnavailable
from app.infra.database.memory.audit import InMemoryAuditRepository
from app.infra.database.records import AuditEventRecord
from app.infra.serializer.error.common import ApiException
from app.infra.serializer.error.database import (
    CommitOutcomeUnknownCancellation,
    RepositoryCommitUncertain,
)
from app.services.v2.admin_workbench_service import AdminWorkbenchService
from app.services.v2.idempotency_service import IdempotencyService


class FailingAudit(InMemoryAuditRepository):
    async def append(self, event: AuditEventRecord) -> AuditEventRecord:
        raise RepositoryUnavailable("test failure")


class BlockingAudit(InMemoryAuditRepository):
    async def append(self, event: AuditEventRecord) -> AuditEventRecord:
        await asyncio.Event().wait()
        raise AssertionError("cancelled append returned")


@pytest.mark.parametrize("cancel", [False, True])
async def test_admin_mutation_rolls_back_and_completes_failure_after_audit_error(
    cancel: bool,
) -> None:
    audit = BlockingAudit() if cancel else FailingAudit()
    service = AdminWorkbenchService(
        Settings(environment_kind=EnvironmentKind.DEMO), audit_repository=audit
    )
    await service.initialize()
    task_id = "task-demo-content-01"
    operation = asyncio.ensure_future(
        service.claim(
            task_id,
            object_version=1,
            admin_id="admin-42",
            request_id="req-1",
            idempotency_key="claim",
        )
    )
    if cancel:
        await asyncio.sleep(0)
        operation.cancel()
        with pytest.raises(asyncio.CancelledError):
            await operation
    else:
        with pytest.raises(ApiException) as error:
            await operation
        assert error.value.status_code == 503
    task = await service.task_repository.get(task_id)
    assert task is not None and task["state"] == "needs_action" and task["version"] == 1
    record = await service.idempotency.repository.get(
        "admin", "admin-42", f"/admin/tasks/{task_id}/claim", "claim", now=datetime.now(UTC)
    )
    assert record is not None and record.outcome == "failure"
    assert await audit.list() == ()


async def test_task_release_audit_preserves_request_actor() -> None:
    service = AdminWorkbenchService(Settings(environment_kind=EnvironmentKind.DEMO))
    await service.claim(
        "task-demo-content-01",
        object_version=1,
        admin_id="admin-42",
        request_id="claim",
        idempotency_key="claim",
    )
    await service.release(
        "task-demo-content-01",
        object_version=2,
        admin_id="admin-42",
        request_id="release",
        idempotency_key="release",
    )
    events = await service.audit.repository.list()
    assert [(event.action, event.actor_id) for event in events] == [
        ("task_claim", "admin-42"),
        ("task_release", "admin-42"),
    ]


async def test_cancelled_cloudbase_commit_preserves_unknown_outcome() -> None:
    entered = asyncio.Event()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/transactions"):
            return httpx.Response(201, json={"transactionId": "cancelled-commit"})
        if request.url.path.endswith("/commit"):
            entered.set()
            await asyncio.Event().wait()
        return httpx.Response(204)

    store = CloudBaseStore("demo-env", "secret", transport=httpx.MockTransport(handler))
    idempotency = IdempotencyService()
    reservation = await idempotency.begin("student", "user", "/route", "key", {})

    async def write() -> None:
        try:
            async with store.transaction():
                pass
        except asyncio.CancelledError as error:
            await idempotency.cancel(reservation, error)
            raise

    task = asyncio.create_task(write())
    await entered.wait()
    task.cancel()
    with pytest.raises(CommitOutcomeUnknownCancellation):
        await task
    record = await idempotency.repository.get(
        "student", "user", "/route", "key", now=datetime.now(UTC)
    )
    assert record is not None and record.outcome == "processing"
    await store.aclose()


async def test_admin_unknown_commit_does_not_finish_reservation_as_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AdminWorkbenchService(Settings(environment_kind=EnvironmentKind.DEMO))
    await service.initialize()

    async def uncertain(*args: object, **kwargs: object) -> None:
        raise RepositoryCommitUncertain("test uncertain outcome")

    monkeypatch.setattr(service, "_save_task", uncertain)
    with pytest.raises(RepositoryCommitUncertain):
        await service.claim(
            "task-demo-content-01",
            object_version=1,
            admin_id="admin-42",
            request_id="req",
            idempotency_key="key",
        )
    record = await service.idempotency.repository.get(
        "admin", "admin-42", "/admin/tasks/task-demo-content-01/claim", "key", now=datetime.now(UTC)
    )
    assert record is not None and record.outcome == "processing"
