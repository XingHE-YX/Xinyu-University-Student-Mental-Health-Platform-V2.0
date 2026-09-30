"""Request context is isolated across concurrent ASGI tasks."""

from contextvars import ContextVar

request_id_context: ContextVar[str | None] = ContextVar("audit_request_id", default=None)
