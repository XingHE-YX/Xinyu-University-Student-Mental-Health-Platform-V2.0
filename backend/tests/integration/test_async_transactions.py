import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import httpx
import pytest

from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.common import RepositoryUnavailable, RepositoryVersionConflict
from app.infra.database.memory.audit import InMemoryAuditRepository
from app.infra.database.memory.documents import InMemoryDocumentRepository
from app.infra.database.memory.session import InMemorySessionRepository
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.security.tokens import TokenManager
from app.infra.serializer.error.common import ApiException
from app.infra.serializer.error.database import RepositoryCommitUncertain


async def test_memory_rollback_includes_sessions_audit_and_blocks_other_readers() -> None:
    documents = InMemoryDocumentRepository({"items": [{"_id": "one", "version": 1}]})
    sessions = InMemorySessionRepository()
    audit = InMemoryAuditRepository()
    share_memory_transaction(documents, sessions, audit)
    manager = TokenManager("test-secret")
    pair = await manager.issue("student", "student-1", sessions)
    entered, release = asyncio.Event(), asyncio.Event()

    async def writer() -> None:
        with pytest.raises(RuntimeError):
            async with documents.transaction():
                await documents.conditional_update(
                    "items", "one", expected_version=1, updates={"status": "pending"}
                )
                await sessions.revoke(pair.session_id, now=datetime.now(UTC))
                await AuditWriter(audit).write(
                    request_id="test",
                    actor_type="system",
                    actor_id="system",
                    capability=None,
                    action="test",
                    resource_type="item",
                    resource_id="one",
                    data_scope="version",
                    outcome="success",
                    reason_code=None,
                    occurred_at=datetime.now(UTC),
                )
                entered.set()
                await release.wait()
                raise RuntimeError("rollback")

    task = asyncio.create_task(writer())
    await entered.wait()
    reader = asyncio.create_task(documents.get("items", "one"))
    await asyncio.sleep(0)
    assert not reader.done()
    release.set()
    await task
    assert await reader == {"_id": "one", "version": 1}
    assert (await sessions.get_by_session_id(pair.session_id)).status == "active"  # type: ignore[union-attr]
    assert await audit.list() == ()


async def test_memory_refresh_compare_and_swap_only_accepts_one_version() -> None:
    sessions = InMemorySessionRepository()
    manager = TokenManager("test-secret")
    pair = await manager.issue("student", "student-1", sessions)
    record = await sessions.get_by_session_id(pair.session_id)
    assert record is not None
    rotated = replace(
        record,
        version=record.version + 1,
        access_token_hash="next-access",
        refresh_token_hash="next-refresh",
    )
    results = await asyncio.gather(
        sessions.replace(rotated), sessions.replace(rotated), return_exceptions=True
    )
    assert sum(result is None for result in results) == 1
    assert sum(isinstance(result, ApiException) for result in results) == 1


async def test_conditional_update_conflict_and_cancelled_transaction_roll_back() -> None:
    documents = InMemoryDocumentRepository({"items": [{"_id": "one", "version": 1}]})
    entered = asyncio.Event()

    async def write() -> None:
        async with documents.transaction():
            await documents.conditional_update(
                "items", "one", expected_version=1, updates={"value": 2}
            )
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(write())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await documents.get("items", "one") == {"_id": "one", "version": 1}
    with pytest.raises(RepositoryVersionConflict):
        await documents.conditional_update("items", "one", expected_version=2, updates={"value": 3})


async def test_cloudbase_awaits_network_and_rolls_back_after_cancellation() -> None:
    entered = asyncio.Event()
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/transactions"):
            return httpx.Response(201, json={"transactionId": "cancelled"})
        if request.url.path.endswith("/rollback"):
            return httpx.Response(204)
        entered.set()
        await asyncio.Event().wait()
        raise AssertionError("cancelled request unexpectedly returned")

    store = CloudBaseStore("demo-env", "test-secret", transport=httpx.MockTransport(handler))

    async def write() -> None:
        async with store.transaction():
            await store.insert("items", {"_id": "one"})

    task = asyncio.create_task(write())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert requests[-1].endswith("/transactions/cancelled/rollback")
    await store.aclose()


async def test_cloudbase_unknown_commit_is_never_reported_as_success_or_retried() -> None:
    requests: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/transactions"):
            return httpx.Response(201, json={"transactionId": "uncertain"})
        if request.url.path.endswith("/commit"):
            raise httpx.ReadTimeout("unknown remote outcome", request=request)
        return httpx.Response(204)

    store = CloudBaseStore("demo-env", "test-secret", transport=httpx.MockTransport(handler))
    with pytest.raises(RepositoryCommitUncertain):
        async with store.transaction():
            pass
    assert sum(path.endswith("/commit") for path in requests) == 1
    await store.aclose()


async def test_cloudbase_rejects_inherited_transaction_and_isolates_independent_tasks() -> None:
    requests: list[tuple[str, str | None]] = []
    count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        requests.append((request.url.path, request.url.params.get("transactionId")))
        if request.url.path.endswith("/transactions"):
            count += 1
            return httpx.Response(201, json={"transactionId": f"txn-{count}"})
        if request.url.path.endswith("/documents"):
            return httpx.Response(200, json={"list": []})
        return httpx.Response(204)

    store = CloudBaseStore("demo-env", "test-secret", transport=httpx.MockTransport(handler))
    entered, release = asyncio.Event(), asyncio.Event()

    async def first() -> None:
        async with store.transaction():
            entered.set()
            await release.wait()
            with pytest.raises(RepositoryUnavailable, match="across tasks"):
                await asyncio.create_task(store.query("items"))
            async with store.transaction():
                await store.query("items")

    task = asyncio.create_task(first())
    await entered.wait()
    async with store.transaction():
        await store.query("items")
    release.set()
    await task
    assert count == 2
    assert [identifier for path, identifier in requests if path.endswith("/documents")] == [
        "txn-2",
        "txn-1",
    ]
    assert store.transaction_id() is None
    await store.aclose()
