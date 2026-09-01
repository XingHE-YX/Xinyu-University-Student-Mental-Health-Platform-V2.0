"""FastAPI application factory and dependency-free health endpoint."""

from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.api.admin_auth import router as admin_auth_router
from app.api.assessment import router as assessment_router
from app.api.auth import me_router
from app.api.auth import router as auth_router
from app.api.dependencies import (
    _error_response,
    register_exception_handlers,
    resolve_request_id,
)
from app.audit.writer import AuditWriter
from app.config.settings import Settings
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.envelope import ApiEnvelope
from app.schemas.errors import ApiException
from app.security.tokens import TokenManager
from app.services.assessment_service import AssessmentService
from app.services.auth_service import AuthService, WechatClient
from app.services.idempotency_service import IdempotencyService
from app.services.safety_service import SafetyService


class HealthData(BaseModel):
    service: str
    version: str
    environment_kind: str
    status: str


def create_app(
    settings: Settings | None = None,
    *,
    wechat_client: WechatClient | None = None,
    session_repository: InMemorySessionRepository | None = None,
    token_manager: TokenManager | None = None,
    domain_repository: InMemoryDomainDataRepository | None = None,
    idempotency_repository: InMemoryIdempotencyRepository | None = None,
    audit_repository: InMemoryAuditRepository | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    runtime_sessions = session_repository or InMemorySessionRepository()
    runtime_tokens = token_manager or TokenManager(
        runtime_settings.session_secret or "local-development-session-secret"
    )
    runtime_domain_repository = domain_repository or InMemoryDomainDataRepository()
    runtime_idempotency = IdempotencyService(idempotency_repository)
    runtime_audit = AuditWriter(
        audit_repository,
        environment_id=runtime_settings.cloudbase_env_id or "unconfigured",
    )
    app = FastAPI(title="心语 V2 API", version="0.1.0")
    app.state.settings = runtime_settings
    app.state.auth_service = AuthService(
        runtime_settings,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        wechat_client=wechat_client,
    )
    app.state.assessment_service = AssessmentService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    app.state.safety_service = SafetyService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> Any:
        try:
            request.state.request_id = resolve_request_id(request.headers.get("X-Request-Id"))
        except ApiException as error:
            request.state.request_id = f"req_invalid_{resolve_request_id(None)[4:]}"
            response = _error_response(request, error)
            response.headers["X-Request-Id"] = request.state.request_id
            return response
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.get("/api/v1/health")
    async def health(request: Request) -> ApiEnvelope[HealthData]:
        settings = request.app.state.settings
        data = HealthData(
            service="xinyu-v2-backend",
            version="0.1.0",
            environment_kind=settings.environment_kind.value,
            status="ok" if settings.configuration_status == "ready" else "degraded",
        )
        return ApiEnvelope.success(request_id=request.state.request_id, data=data)

    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(admin_auth_router)
    app.include_router(assessment_router)
    return app


app = create_app()
