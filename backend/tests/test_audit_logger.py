import asyncio
import io
import json
import logging
import queue

import httpx
from fastapi import FastAPI

from app.infra.logger.common import get_logger, traced
from app.infra.logger.context import request_id_context
from app.infra.logger.formatter import AuditFormatter
from app.infra.logger.handlers import AuditQueueHandler
from app.infra.serializer.error.common import ApiException
from app.routers.middleware.request_context import RequestContextMiddleware


def test_five_columns_single_line_safe_fields_and_real_callsite() -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(AuditFormatter())
    logger = logging.getLogger("xinyu")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        get_logger("auth.admin").info(
            ApiException(401, "INVALID_CREDENTIALS", "password=secret"),
            request_id="req_test",
            password="secret",
            body="private\ncontent",
        )
    finally:
        logger.removeHandler(handler)
    lines = output.getvalue().splitlines()
    assert len(lines) == 1
    level, timestamp, position, scope, content = lines[0].split(" ", 4)
    assert level == "INFO" and timestamp.endswith("Z")
    assert position.startswith("tests/test_audit_logger.py:")
    assert scope == "auth.admin"
    assert json.loads(content)["error_code"] == "INVALID_CREDENTIALS"
    assert "secret" not in lines[0] and "private" not in lines[0]


async def test_concurrent_contexts_are_isolated_and_traced_errors_are_safe() -> None:
    @traced
    async def current(value: str) -> str | None:
        token = request_id_context.set(value)
        try:
            await asyncio.sleep(0)
            return request_id_context.get()
        finally:
            request_id_context.reset(token)

    assert tuple(await asyncio.gather(current("req_a"), current("req_b"))) == ("req_a", "req_b")
    assert request_id_context.get() is None


async def test_request_middleware_isolates_concurrent_ids_and_resets_context() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/context")
    async def context() -> dict[str, str | None]:
        await asyncio.sleep(0)
        return {"request_id": request_id_context.get()}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        first, second = await asyncio.gather(
            client.get("/context", headers={"X-Request-Id": "req_first"}),
            client.get("/context", headers={"X-Request-Id": "req_second"}),
        )
    assert first.json()["request_id"] == first.headers["X-Request-Id"] == "req_first"
    assert second.json()["request_id"] == second.headers["X-Request-Id"] == "req_second"
    assert request_id_context.get() is None


def test_full_queue_counts_drops_and_emits_warning_to_emergency_sink() -> None:
    records: queue.Queue[logging.LogRecord | None] = queue.Queue(1)
    output = io.StringIO()
    sink = logging.StreamHandler(output)
    sink.setFormatter(AuditFormatter())
    handler = AuditQueueHandler(records, sink)
    info = logging.LogRecord("test", logging.INFO, __file__, 1, "safe", (), None)
    warning = logging.LogRecord("test", logging.WARNING, __file__, 2, "safe", (), None)
    handler.enqueue(info)
    handler.enqueue(info)
    handler.enqueue(warning)
    assert handler.dropped == 2
    assert output.getvalue().startswith("WARNING ")
