"""Map typed errors to the common safe HTTP envelope."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.infra.database.common import (
    RepositoryError,
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.logger.common import get_logger
from app.infra.serializer.envelope import ApiEnvelope
from app.infra.serializer.error.common import ApiException, status_error
from app.routers.dependencies import request_id

logger = get_logger(__name__)


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
