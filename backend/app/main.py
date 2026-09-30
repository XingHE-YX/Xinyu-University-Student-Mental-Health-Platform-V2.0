"""FastAPI application factory and dependency-free health endpoint."""

from typing import Any

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.infra.config.settings import Settings
from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.cloudbase.domain import CloudBaseDomainDataRepository
from app.infra.database.cloudbase.security import (
    CloudBaseAuditRepository,
    CloudBaseIdempotencyRepository,
    CloudBaseSessionRepository,
)
from app.infra.database.cloudbase.tasks import CloudBaseAdminTaskRepository
from app.infra.database.memory.audit import AuditRepository, InMemoryAuditRepository
from app.infra.database.memory.domain import InMemoryDomainDataRepository
from app.infra.database.memory.idempotency import (
    IdempotencyRepository,
    InMemoryIdempotencyRepository,
)
from app.infra.database.memory.session import InMemorySessionRepository
from app.infra.logger.audit import AuditWriter
from app.infra.security.tokens import TokenManager
from app.infra.serializer.envelope import ApiEnvelope
from app.infra.serializer.error.common import ApiException
from app.routers.controller.v2.admin.auth import router as admin_auth_router
from app.routers.controller.v2.admin.identity import router as admin_identity_router
from app.routers.controller.v2.admin.workbench import router as admin_workbench_router
from app.routers.controller.v2.assessment import contract_router as assessment_contract_router
from app.routers.controller.v2.assessment import router as assessment_router
from app.routers.controller.v2.auth import me_router
from app.routers.controller.v2.auth import router as auth_router
from app.routers.controller.v2.student_core import router as student_core_router
from app.routers.controller.v2.treehole import router as treehole_router
from app.routers.controller.v2.treehole import student_router as treehole_student_router
from app.routers.dependencies import (
    _error_response,
    register_exception_handlers,
    resolve_request_id,
)
from app.services.v2.account_service import AccountService
from app.services.v2.admin_workbench_service import AdminWorkbenchService
from app.services.v2.ai_assist_service import AiAssistService
from app.services.v2.assessment_service import AssessmentService
from app.services.v2.auth_service import AuthService, WechatClient
from app.services.v2.bootstrap_service import BootstrapService
from app.services.v2.consent_service import ConsentService
from app.services.v2.idempotency_service import IdempotencyService
from app.services.v2.identity_access_service import IdentityAccessService
from app.services.v2.identity_service import IdentityService
from app.services.v2.mood_service import MoodService
from app.services.v2.quote_service import QuoteService
from app.services.v2.safety_service import SafetyService
from app.services.v2.support_resource_service import SupportResourceService
from app.services.v2.today_service import TodayService
from app.services.v2.treehole_service import TreeholeService


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
    admin_workbench_service: AdminWorkbenchService | None = None,
    ai_assist_service: AiAssistService | None = None,
    domain_repository: InMemoryDomainDataRepository | None = None,
    idempotency_repository: IdempotencyRepository | None = None,
    audit_repository: AuditRepository | None = None,
) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    cloudbase_store: CloudBaseStore | None = None
    runtime_admin_task_repository: CloudBaseAdminTaskRepository | None = None
    runtime_sessions: InMemorySessionRepository
    runtime_domain_repository: InMemoryDomainDataRepository
    if (
        session_repository is None
        and domain_repository is None
        and idempotency_repository is None
        and audit_repository is None
        and runtime_settings.cloudbase_persistence_ready
    ):
        cloudbase_store = CloudBaseStore(
            runtime_settings.cloudbase_env_id or "",
            runtime_settings.cloudbase_secret or "",
        )
        runtime_sessions = CloudBaseSessionRepository(cloudbase_store)
        runtime_domain_repository = CloudBaseDomainDataRepository(cloudbase_store)
        runtime_idempotency_repository: IdempotencyRepository = CloudBaseIdempotencyRepository(
            cloudbase_store
        )
        runtime_audit_repository: AuditRepository = CloudBaseAuditRepository(cloudbase_store)
        runtime_admin_task_repository = CloudBaseAdminTaskRepository(cloudbase_store)
    else:
        runtime_sessions = session_repository or InMemorySessionRepository()
        runtime_domain_repository = domain_repository or InMemoryDomainDataRepository()
        runtime_idempotency_repository = idempotency_repository or InMemoryIdempotencyRepository()
        runtime_audit_repository = audit_repository or InMemoryAuditRepository()
    runtime_tokens = token_manager or TokenManager(
        runtime_settings.session_secret or "local-development-session-secret"
    )
    runtime_idempotency = IdempotencyService(runtime_idempotency_repository)
    runtime_audit = AuditWriter(
        runtime_audit_repository,
        environment_id=runtime_settings.cloudbase_env_id or "unconfigured",
    )
    app = FastAPI(title="心语 V2 API", version="0.1.0")
    app.state.settings = runtime_settings
    app.state.persistence_backend = "cloudbase" if cloudbase_store else "memory"
    app.state.cloudbase_store = cloudbase_store
    app.state.auth_service = AuthService(
        runtime_settings,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        wechat_client=wechat_client,
        domain_repository=runtime_domain_repository,
    )
    app.state.admin_workbench_service = admin_workbench_service or AdminWorkbenchService(
        runtime_settings,
        audit_repository=runtime_audit_repository,
        task_repository=runtime_admin_task_repository,
        content_repository=runtime_domain_repository,
    )
    app.state.ai_assist_service = ai_assist_service or AiAssistService(
        runtime_settings,
        audit_writer=runtime_audit,
        repository=runtime_domain_repository,
    )
    app.state.assessment_service = AssessmentService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        ai_assist_service=app.state.ai_assist_service,
    )
    app.state.safety_service = SafetyService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    app.state.consent_service = ConsentService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    app.state.identity_service = IdentityService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    support_service = SupportResourceService(
        settings=runtime_settings, repository=runtime_domain_repository
    )
    app.state.support_resource_service = support_service
    app.state.mood_service = MoodService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    app.state.today_service = TodayService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        quote_service=QuoteService(repository=runtime_domain_repository),
        support_resource_service=support_service,
    )
    app.state.account_service = AccountService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    app.state.bootstrap_service = BootstrapService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        identity_service=app.state.identity_service,
        today_service=app.state.today_service,
    )
    app.state.treehole_service = TreeholeService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        consent_service=app.state.consent_service,
        ai_assist_service=app.state.ai_assist_service,
    )
    app.state.identity_access_service = IdentityAccessService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        identity_service=app.state.identity_service,
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
    app.include_router(admin_workbench_router)
    app.include_router(admin_identity_router)
    app.include_router(assessment_router)
    app.include_router(assessment_contract_router)
    app.include_router(treehole_router)
    app.include_router(treehole_student_router)
    app.include_router(student_core_router)
    return app


app = create_app()
