from __future__ import annotations

from typing import Literal, cast

from app.infra.config.settings import Settings
from app.infra.logger.common import traced
from app.infra.security.tokens import TokenManager
from app.infra.serializer.error.common import ApiException
from app.models.v2.responses.student_core import (
    AnonymousIdentityProjection,
    BootstrapProjection,
    ConsentProjection,
)
from app.services.v2.identity_service import IdentityService
from app.services.v2.repositories import DomainRepository, SessionRepository
from app.services.v2.today_service import TodayService


class BootstrapService:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: DomainRepository,
        session_repository: SessionRepository,
        token_manager: TokenManager,
        identity_service: IdentityService,
        today_service: TodayService | None = None,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.sessions = session_repository
        self.tokens = token_manager
        self.identity = identity_service
        self.today = today_service

    @traced
    async def get(self, access_token: str) -> BootstrapProjection:
        subject = await self.tokens.authenticate_access(access_token, self.sessions)
        if subject.subject_type != "student":
            raise ApiException(403, "FORBIDDEN")
        user = await self.repository.get_user(subject.subject_id)
        identity_status = cast(
            Literal["unverified", "pending", "verified"],
            (await self.identity.get_identity_status(access_token))["identity_status"],
        )
        anonymous = None
        if user.anonymous_identity_id:
            try:
                item = await self.repository.get_anonymous_identity(user.anonymous_identity_id)
                if item.user_id == user.document_id:
                    anonymous = AnonymousIdentityProjection(
                        anonymous_identity_id=item.document_id,
                        display_name=item.display_name,
                        display_scope="treehole_only",
                        generation_version=item.generation_version,
                        status=item.status,
                    )
            except Exception:
                anonymous = None
        complete = user.base_consent_status == "accepted"
        today_summary = None
        if complete and self.today is not None and identity_status == "verified":
            try:
                today_summary = (await self.today.get_today(access_token)).model_dump(mode="json")
            except Exception:
                today_summary = None
        raw_community_status = user.community_consent_status
        community_status = cast(
            Literal["required", "accepted", "withdrawn"],
            raw_community_status,
        )
        if raw_community_status == "not_accepted":
            community_status = "required"
        return BootstrapProjection(
            account_status=user.status,
            object_version=user.version,
            base_consent=ConsentProjection(
                status="accepted" if complete else "required", version=user.base_consent_version
            ),
            community_consent=ConsentProjection(
                status=community_status, version=user.community_consent_version
            ),
            identity_status=identity_status,
            anonymous_identity_summary=anonymous,
            today_summary=today_summary,
            module_summaries=[],
            feature_flags={
                "community": complete and raw_community_status == "accepted",
                "assessment": complete and identity_status == "verified",
            },
        )
