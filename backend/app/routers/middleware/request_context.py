from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.infra.logger.context import request_id_context
from app.infra.serializer.error.common import ApiException
from app.infra.serializer.handlers import _error_response
from app.routers.dependencies import resolve_request_id


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        failure: ApiException | None = None
        try:
            request_id = resolve_request_id(request.headers.get("X-Request-Id"))
        except ApiException as error:
            request_id = f"req_invalid_{resolve_request_id(None)[4:]}"
            failure = error
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message = {**message, "headers": [*headers, (b"x-request-id", request_id.encode())]}
            await send(message)

        try:
            if failure is not None:
                await _error_response(request, failure)(scope, receive, send_with_id)
            else:
                await self.app(scope, receive, send_with_id)
        finally:
            request_id_context.reset(token)
