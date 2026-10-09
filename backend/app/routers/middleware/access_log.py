from time import monotonic

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.infra.logger.common import get_logger


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.log = get_logger("http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = monotonic()
        status = 500

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture)
        finally:
            route = getattr(scope.get("route"), "path", "<unmatched>")
            self.log.info(
                "http.completed",
                method=scope.get("method"),
                route=route,
                status_code=status,
                outcome="success" if status < 400 else "failure",
                duration_ms=round((monotonic() - started) * 1000, 3),
            )
