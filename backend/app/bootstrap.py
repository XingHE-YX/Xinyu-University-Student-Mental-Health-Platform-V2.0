"""Typed dependency assembly and ownership of asynchronous resources."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from typing import TypedDict, cast

from fastapi import FastAPI

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
from app.infra.database.memory.transaction import share_memory_transaction
from app.infra.logger.audit import AuditWriter
from app.infra.logger.handlers import start_logging, stop_logging
from app.infra.security.tokens import TokenManager
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
from app.services.v2.repositories import DomainRepository, SessionRepository
from app.services.v2.safety_service import SafetyService
from app.services.v2.support_resource_service import SupportResourceService
from app.services.v2.today_service import TodayService
from app.services.v2.treehole_service import TreeholeService


class Overrides(TypedDict, total=False):
    wechat_client: WechatClient | None
    session_repository: SessionRepository | None
    token_manager: TokenManager | None
    admin_workbench_service: AdminWorkbenchService | None
    ai_assist_service: AiAssistService | None
    domain_repository: DomainRepository | None
    idempotency_repository: IdempotencyRepository | None
    audit_repository: AuditRepository | None


@dataclass(frozen=True, slots=True)
class Container:
    settings: Settings
    persistence_backend: str
    cloudbase_store: CloudBaseStore | None
    auth_service: AuthService
    admin_workbench_service: AdminWorkbenchService
    ai_assist_service: AiAssistService
    assessment_service: AssessmentService
    safety_service: SafetyService
    consent_service: ConsentService
    identity_service: IdentityService
    support_resource_service: SupportResourceService
    mood_service: MoodService
    today_service: TodayService
    account_service: AccountService
    bootstrap_service: BootstrapService
    treehole_service: TreeholeService
    identity_access_service: IdentityAccessService


def build_container(
    settings: Settings | None = None,
    *,
    wechat_client: WechatClient | None = None,
    session_repository: SessionRepository | None = None,
    token_manager: TokenManager | None = None,
    admin_workbench_service: AdminWorkbenchService | None = None,
    ai_assist_service: AiAssistService | None = None,
    domain_repository: DomainRepository | None = None,
    idempotency_repository: IdempotencyRepository | None = None,
    audit_repository: AuditRepository | None = None,
) -> Container:
    runtime_settings = settings or Settings.from_environment()
    cloudbase_store: CloudBaseStore | None = None
    runtime_admin_task_repository: CloudBaseAdminTaskRepository | None = None
    runtime_sessions: SessionRepository
    runtime_domain_repository: DomainRepository
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
            config=runtime_settings.database,
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
    share_memory_transaction(
        runtime_domain_repository,
        runtime_sessions,
        runtime_idempotency_repository,
        runtime_audit_repository,
    )
    runtime_tokens = token_manager or TokenManager(
        runtime_settings.session_secret or "local-development-session-secret",
        admin_password_hash=runtime_settings.password_hash,
    )
    runtime_idempotency = IdempotencyService(runtime_idempotency_repository)
    runtime_audit = AuditWriter(
        runtime_audit_repository,
        environment_id=runtime_settings.cloudbase_env_id or "unconfigured",
    )
    settings = runtime_settings
    persistence_backend = "cloudbase" if cloudbase_store else "memory"
    cloudbase_store = cloudbase_store
    auth_service = AuthService(
        runtime_settings,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        wechat_client=wechat_client,
        domain_repository=runtime_domain_repository,
    )
    admin_workbench_service = admin_workbench_service or AdminWorkbenchService(
        runtime_settings,
        audit_repository=runtime_audit_repository,
        task_repository=runtime_admin_task_repository,
        content_repository=runtime_domain_repository,
        idempotency_service=runtime_idempotency,
    )
    ai_assist_service = ai_assist_service or AiAssistService(
        runtime_settings,
        audit_writer=runtime_audit,
        repository=runtime_domain_repository,
    )
    assessment_service = AssessmentService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        ai_assist_service=ai_assist_service,
    )
    safety_service = SafetyService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    consent_service = ConsentService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    identity_service = IdentityService(
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
    support_resource_service = support_service
    mood_service = MoodService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    today_service = TodayService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        quote_service=QuoteService(repository=runtime_domain_repository),
        support_resource_service=support_service,
    )
    account_service = AccountService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
    )
    bootstrap_service = BootstrapService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        identity_service=identity_service,
        today_service=today_service,
    )
    treehole_service = TreeholeService(
        settings=runtime_settings,
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        consent_service=consent_service,
        ai_assist_service=ai_assist_service,
    )
    identity_access_service = IdentityAccessService(
        repository=runtime_domain_repository,
        session_repository=runtime_sessions,
        token_manager=runtime_tokens,
        idempotency_service=runtime_idempotency,
        audit_writer=runtime_audit,
        identity_service=identity_service,
    )

    return Container(
        settings=settings,
        persistence_backend=persistence_backend,
        cloudbase_store=cloudbase_store,
        auth_service=auth_service,
        admin_workbench_service=admin_workbench_service,
        ai_assist_service=ai_assist_service,
        assessment_service=assessment_service,
        safety_service=safety_service,
        consent_service=consent_service,
        identity_service=identity_service,
        support_resource_service=support_resource_service,
        mood_service=mood_service,
        today_service=today_service,
        account_service=account_service,
        bootstrap_service=bootstrap_service,
        treehole_service=treehole_service,
        identity_access_service=identity_access_service,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = cast(Container, app.state.container)
    start_logging(container.settings.logger)
    async with AsyncExitStack() as stack:
        stack.push_async_callback(asyncio.to_thread, stop_logging)
        for resource in (
            container.cloudbase_store,
            container.ai_assist_service,
            container.auth_service.wechat,
            container.identity_service.school,
        ):
            closer = getattr(resource, "aclose", None)
            if callable(closer):
                stack.push_async_callback(closer)
        await container.admin_workbench_service.initialize()
        yield


def install_container(app: FastAPI, container: Container) -> None:
    app.state.container = container
    # Retain explicit state access for existing fixtures and diagnostic scripts.
    for name in Container.__dataclass_fields__:
        setattr(app.state, name, getattr(container, name))
