"""Scoped logging and instrumentation with an explicit metadata allowlist."""

import asyncio
import inspect
import logging
import re
from collections.abc import Awaitable, Callable
from functools import wraps
from time import monotonic
from typing import Any, cast

from app.infra.logger.context import request_id_context
from app.infra.logger.formatter import code_position
from app.infra.serializer.error.common import AppError, ErrorCode

SAFE_FIELDS = frozenset(
    {
        "request_id",
        "actor_type",
        "resource_type",
        "resource_id",
        "method",
        "route",
        "duration_ms",
        "outcome",
        "status_code",
        "error_code",
        "error_type",
        "current_version",
        "object_version",
        "prompt_version",
        "model_version",
        "provider",
        "action",
        "reason_code",
        "queue_dropped",
        "operation",
        "task_kind",
        "scope_kind",
    }
)
EVENT_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class AuditLogger:
    def __init__(self, scope: str) -> None:
        self.scope = re.sub(r"[^A-Za-z0-9_.:-]", "_", scope)[:192]
        self.logger = logging.getLogger("xinyu")

    def _emit(
        self,
        level: int,
        event: str | AppError,
        **facts: object,
    ) -> None:
        content: dict[str, object] = {
            "event": event
            if isinstance(event, str) and EVENT_PATTERN.fullmatch(event)
            else "error.reported"
            if isinstance(event, AppError)
            else "log.message"
        }
        if request_id := request_id_context.get():
            content["request_id"] = request_id
        for key, value in facts.items():
            if key in SAFE_FIELDS and (value is None or isinstance(value, (str, int, float, bool))):
                content[key] = value[:256] if isinstance(value, str) else value
        if isinstance(event, AppError):
            content.update(event.log_fields())
        extra: dict[str, object] = {"scope": self.scope, "safe_content": content}
        if isinstance(code_pos := facts.get("code_pos"), str):
            extra["code_pos"] = code_pos
        self.logger.log(level, content["event"], extra=extra, stacklevel=3)

    def debug(self, event: str | AppError, *args: object, **facts: object) -> None:
        self._emit(logging.DEBUG, event, **facts)

    def info(self, event: str | AppError, *args: object, **facts: object) -> None:
        self._emit(logging.INFO, event, **facts)

    def warning(self, event: str | AppError, *args: object, **facts: object) -> None:
        self._emit(logging.WARNING, event, **facts)

    def error(self, event: str | AppError, *args: object, **facts: object) -> None:
        self._emit(logging.ERROR, event, **facts)


def get_logger(scope: str) -> AuditLogger:
    return AuditLogger(scope)


def traced[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    log = get_logger(f"{function.__module__}.{function.__qualname__}")
    position = code_position(function.__code__.co_filename, function.__code__.co_firstlineno)

    def completed(started: float) -> None:
        log._emit(
            logging.DEBUG if function.__name__.startswith("_") else logging.INFO,
            "operation.completed",
            code_pos=position,
            outcome="success",
            duration_ms=round((monotonic() - started) * 1000, 3),
        )

    def failed(error: BaseException, started: float) -> None:
        if isinstance(error, asyncio.CancelledError):
            log.warning(
                "operation.cancelled",
                error_code=ErrorCode.OPERATION_CANCELLED,
                code_pos=position,
                outcome="cancelled",
            )
        else:
            log.warning(
                error if isinstance(error, AppError) else "operation.failed",
                error_type=type(error).__name__,
                code_pos=position,
                outcome="failure",
                duration_ms=round((monotonic() - started) * 1000, 3),
            )

    if inspect.iscoroutinefunction(function):

        @wraps(function)
        async def asynchronous(*args: P.args, **kwargs: P.kwargs) -> Any:
            started = monotonic()
            log.debug("operation.started", code_pos=position)
            try:
                result = await cast(Awaitable[Any], function(*args, **kwargs))
            except BaseException as error:
                failed(error, started)
                raise
            completed(started)
            return result

        return cast(Callable[P, R], asynchronous)

    @wraps(function)
    def synchronous(*args: P.args, **kwargs: P.kwargs) -> R:
        started = monotonic()
        log.debug("operation.started", code_pos=position)
        try:
            result = function(*args, **kwargs)
        except BaseException as error:
            failed(error, started)
            raise
        completed(started)
        return result

    return synchronous
