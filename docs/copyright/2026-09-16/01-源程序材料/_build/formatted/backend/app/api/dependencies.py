"""HTTP request context, authentication dependencies and safe exception mapping."""

import logging
import re
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.repositories.protocols import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.schemas.envelope import ApiEnvelope
from app.schemas.errors import ApiException, status_error
from app.security.tokens import AuthenticatedSubject
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str


def create_request_id() -> str:
    return f"req_{uuid4().hex}"


def resolve_request_id(value: str | None) -> str:
    if value is None or value == "":
        return create_request_id()
    if not REQUEST_ID_PATTERN.fullmatch(value):
        raise ApiException(400, "INVALID_REQUEST", "请求编号格式不正确")
    return value


def request_id(request: Request) -> str:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, str) else create_request_id()


def bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise ApiException(401, "AUTH_REQUIRED")
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise ApiException(401, "AUTH_REQUIRED")
    return token.strip()


def current_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    token = bearer_token(authorization)
    service = cast(AuthService, request.app.state.auth_service)
    return service.authenticate(token)


def student_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = current_subject(request, authorization)
    if subject.subject_type != "student":
        raise ApiException(403, "FORBIDDEN")
    return subject


def admin_subject(request: Request, authorization: str | None) -> AuthenticatedSubject:
    subject = current_subject(request, authorization)
    if subject.subject_type != "admin":
        raise ApiException(403, "FORBIDDEN")
    return subject


def require_idempotency_key(request: Request) -> str:
    value = request.headers.get("Idempotency-Key")
    if not value or len(value) > 128 or not value.strip():
        raise ApiException(400, "INVALID_REQUEST", "缺少有效的幂等键")
    return value.strip()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def api_exception_handler(request: Request, error: ApiException) -> JSONResponse:
        return _error_response(request, error)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        del error
        return _error_response(request, ApiException(422, "VALIDATION_FAILED"))

    @app.exception_handler(RepositoryVersionConflict)
    async def repository_version_conflict_handler(
        request: Request,
        error: RepositoryVersionConflict,
    ) -> JSONResponse:
        return _error_response(
            request,
            ApiException(409, "VERSION_CONFLICT", current_version=error.current_version),
        )

    @app.exception_handler(RepositoryNotFound)
    async def repository_not_found_handler(
        request: Request,
        error: RepositoryNotFound,
    ) -> JSONResponse:
        del error
        return _error_response(request, ApiException(404, "NOT_FOUND"))

    @app.exception_handler(RepositoryUnavailable)
    async def repository_unavailable_handler(
        request: Request,
        error: RepositoryUnavailable,
    ) -> JSONResponse:
        del error
        return _error_response(request, ApiException(503, "DEPENDENCY_UNAVAILABLE"))

    @app.exception_handler(RepositoryError)
    async def repository_error_handler(
        request: Request,
        error: RepositoryError,
    ) -> JSONResponse:
        del error
        return _error_response(request, ApiException(503, "DEPENDENCY_UNAVAILABLE"))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        error: StarletteHTTPException,
    ) -> JSONResponse:
        return _error_response(request, status_error(error.status_code))

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, error: Exception) -> JSONResponse:
        logger.error("unhandled backend exception type=%s", type(error).__name__)
        return _error_response(request, ApiException(500, "INTERNAL_ERROR"))


def _error_response(request: Request, error: ApiException) -> JSONResponse:
    payload: ApiEnvelope[object] = ApiEnvelope.failure(request_id(request), error.to_error())
    return JSONResponse(status_code=error.status_code, content=payload.model_dump(mode="json"))
