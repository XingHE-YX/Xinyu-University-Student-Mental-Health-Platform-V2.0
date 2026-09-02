"""Authentication use cases shared by the student and admin API routes."""

import secrets
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from app.config.settings import Settings
from app.domain.models import UserAccountDocument
from app.integrations.wechat_auth import WechatAuthClient, WechatIdentity
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.repositories.session_repository import InMemorySessionRepository
from app.schemas.auth import AdminSessionData, StudentSessionData, TokenData
from app.schemas.errors import ApiException
from app.security.passwords import verify_password
from app.security.tokens import AuthenticatedSubject, TokenManager, TokenPair, TokenSubjectType


class WechatClient(Protocol):
    async def exchange_code(self, code: str) -> WechatIdentity: ...


class AuthService:
    ADMIN_LOGIN_NAME = "心理健康中心工作人员"
    ADMIN_DISPLAY_NAME = "心理健康中心工作人员"
    ADMIN_CAPABILITY = "super_admin"
    ADMIN_CAPABILITY_LABEL = "超级管理员"

    def __init__(
        self,
        settings: Settings,
        *,
        session_repository: InMemorySessionRepository | None = None,
        token_manager: TokenManager | None = None,
        wechat_client: WechatClient | None = None,
        domain_repository: InMemoryDomainDataRepository | None = None,
    ) -> None:
        self.settings = settings
        self.sessions = session_repository or InMemorySessionRepository()
        self.tokens = token_manager or TokenManager(
            settings.session_secret or secrets.token_urlsafe(32)
        )
        self.wechat = wechat_client or WechatAuthClient(
            appid=settings.wechat_appid,
            appsecret=settings.wechat_secret,
        )
        self.domain_repository = domain_repository

    async def login_student(self, code: str, *, client_version: str) -> StudentSessionData:
        del client_version
        self._require_ready()
        identity = await self.wechat.exchange_code(code)
        user = self._ensure_student_user(identity.subject_id)
        pair = self.tokens.issue("student", identity.subject_id, self.sessions)
        return StudentSessionData(
            **_pair_data(pair),
            account_status=_session_account_status(user.status),
            base_consent_status=(
                "accepted" if user.base_consent_status == "accepted" else "required"
            ),
            community_consent_status=(
                "accepted" if user.community_consent_status == "accepted" else "required"
            ),
            identity_status=("verified" if user.identity_record_id else "unverified"),
        )

    def login_admin(self, login_name: str, password: str) -> AdminSessionData:
        self._require_ready()
        if login_name != self.ADMIN_LOGIN_NAME or not self.settings.password_hash:
            raise ApiException(401, "AUTH_REQUIRED")
        if not verify_password(password, self.settings.password_hash):
            raise ApiException(401, "AUTH_REQUIRED")
        pair = self.tokens.issue(
            "admin",
            "admin:fixed-super-admin",
            self.sessions,
            capability=self.ADMIN_CAPABILITY,
        )
        return AdminSessionData(
            **_pair_data(pair),
            display_name=self.ADMIN_DISPLAY_NAME,
            capability_label=self.ADMIN_CAPABILITY_LABEL,
        )

    def refresh(
        self,
        refresh_token: str,
        *,
        expected_subject_type: TokenSubjectType | None = None,
    ) -> TokenData | StudentSessionData | AdminSessionData:
        pair = self.tokens.refresh(
            refresh_token,
            self.sessions,
            expected_subject_type=expected_subject_type,
        )
        record = self.sessions.get_by_session_id(pair.session_id)
        if record is None:
            raise ApiException(401, "SESSION_EXPIRED")
        if record.subject_type == "admin":
            return AdminSessionData(
                **_pair_data(pair),
                display_name=self.ADMIN_DISPLAY_NAME,
                capability_label=self.ADMIN_CAPABILITY_LABEL,
            )
        return StudentSessionData(
            **_pair_data(pair),
            account_status="active",
            base_consent_status="required",
            community_consent_status="required",
            identity_status="unverified",
        )

    def authenticate(self, access_token: str) -> AuthenticatedSubject:
        return self.tokens.authenticate_access(access_token, self.sessions)

    def logout(
        self,
        access_token: str,
        *,
        expected_subject_type: TokenSubjectType | None = None,
    ) -> None:
        self.tokens.logout(
            access_token,
            self.sessions,
            expected_subject_type=expected_subject_type,
        )

    def _require_ready(self) -> None:
        if self.settings.configuration_status != "ready":
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "服务环境尚未完成配置")

    def _ensure_student_user(self, subject_id: str) -> UserAccountDocument:
        if self.domain_repository is None:
            return _ephemeral_user(subject_id)
        existing = self.domain_repository.get_user_by_auth_subject_hash(subject_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        user = UserAccountDocument(
            _id=subject_id,
            auth_subject_hash=subject_id,
            status="active",
            base_consent_status="not_accepted",
            community_consent_status="not_accepted",
            created_at=now,
            updated_at=now,
            version=1,
        )
        try:
            return self.domain_repository.create_user(user)
        except Exception:
            existing = self.domain_repository.get_user_by_auth_subject_hash(subject_id)
            if existing is not None:
                return existing
            raise


def _pair_data(pair: TokenPair) -> dict[str, Any]:
    return {
        "access_token": pair.access_token,
        "refresh_token": pair.refresh_token,
        "access_expires_at": pair.access_expires_at,
        "refresh_expires_at": pair.refresh_expires_at,
    }


def _ephemeral_user(subject_id: str) -> UserAccountDocument:
    now = datetime.now(UTC)
    return UserAccountDocument(
        _id=subject_id,
        auth_subject_hash=subject_id,
        status="active",
        base_consent_status="not_accepted",
        community_consent_status="not_accepted",
        created_at=now,
        updated_at=now,
        version=1,
    )


def _session_account_status(
    status: str,
) -> Literal["active", "recovery_pending", "stopped", "purged"]:
    return (
        status  # type: ignore[return-value]
        if status in {"active", "recovery_pending", "stopped", "purged"}
        else "active"
    )
