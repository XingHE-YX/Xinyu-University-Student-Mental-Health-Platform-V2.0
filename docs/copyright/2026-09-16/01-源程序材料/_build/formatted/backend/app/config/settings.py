"""Typed server configuration with an explicit safe unconfigured state."""

import os
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.config.environments import (
    EnvironmentKind,
    parse_demo_mode,
    resolve_environment,
)


class Settings(BaseModel):
    """Runtime settings.

    Secret values are kept in memory for integrations, but public status output is
    deliberately assembled by :meth:`public_snapshot` instead of serializing this model.
    """

    model_config = ConfigDict(extra="forbid")

    wechat_appid: str | None = None
    wechat_appsecret: SecretStr | None = Field(default=None, exclude=True)
    cloudbase_env_id: str | None = Field(default=None, exclude=True)
    cloudbase_api_key: SecretStr | None = Field(default=None, exclude=True)
    deepseek_api_key: SecretStr | None = Field(default=None, exclude=True)
    admin_password_hash: SecretStr | None = Field(default=None, exclude=True)
    admin_session_secret: SecretStr | None = Field(default=None, exclude=True)
    school_identity_provider_url: str | None = None
    support_resource_version: str | None = None
    demo_mode: bool | None = None

    demo_env_ids: tuple[str, ...] = Field(default=(), exclude=True)
    authorized_env_ids: tuple[str, ...] = Field(default=(), exclude=True)
    declared_environment_kind: EnvironmentKind = EnvironmentKind.UNCONFIGURED
    environment_kind: EnvironmentKind = EnvironmentKind.UNCONFIGURED
    configuration_status: Literal["ready", "unconfigured"] = "unconfigured"
    missing_requirements: tuple[str, ...] = ()
    demo_reset_allowed: bool = False

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        demo_env_ids: Iterable[str] = (),
        authorized_env_ids: Iterable[str] = (),
    ) -> "Settings":
        """Build settings from server variables without exposing their raw values."""

        source = dict(os.environ if environment is None else environment)
        parsed_demo_mode = parse_demo_mode(source.get("DEMO_MODE"))
        normalized_demo_ids = tuple(sorted({item.strip() for item in demo_env_ids if item.strip()}))
        normalized_authorized_ids = tuple(
            sorted({item.strip() for item in authorized_env_ids if item.strip()})
        )
        decision = resolve_environment(
            demo_mode=parsed_demo_mode,
            cloudbase_env_id=source.get("CLOUDBASE_ENV_ID"),
            demo_env_ids=normalized_demo_ids,
            authorized_env_ids=normalized_authorized_ids,
        )

        missing: list[str] = []
        required_values = {
            "cloudbase_env_id": source.get("CLOUDBASE_ENV_ID"),
            "cloudbase_api_key": source.get("CLOUDBASE_API_KEY"),
            "wechat_appid": source.get("WECHAT_APPID"),
            "wechat_appsecret": source.get("WECHAT_APPSECRET"),
            "admin_password_hash": source.get("ADMIN_PASSWORD_HASH"),
            "admin_session_secret": source.get("ADMIN_SESSION_SECRET"),
            "identity_provider": source.get("SCHOOL_IDENTITY_PROVIDER_URL"),
            "support_resources": source.get("SUPPORT_RESOURCE_VERSION"),
            "deepseek_api_key": source.get("DEEPSEEK_API_KEY"),
        }
        missing.extend(
            name for name, value in required_values.items() if not value or not value.strip()
        )
        if parsed_demo_mode is None:
            missing.append("environment_mode")
        if (
            decision.matched_kind is EnvironmentKind.UNCONFIGURED
            and "environment_registry" not in missing
        ):
            missing.append("environment_registry")

        ready = decision.matched_kind is not EnvironmentKind.UNCONFIGURED and not missing
        environment_kind = decision.matched_kind if ready else EnvironmentKind.UNCONFIGURED
        return cls(
            wechat_appid=source.get("WECHAT_APPID"),
            wechat_appsecret=_secret(source.get("WECHAT_APPSECRET")),
            cloudbase_env_id=source.get("CLOUDBASE_ENV_ID"),
            cloudbase_api_key=_secret(source.get("CLOUDBASE_API_KEY")),
            deepseek_api_key=_secret(source.get("DEEPSEEK_API_KEY")),
            admin_password_hash=_secret(source.get("ADMIN_PASSWORD_HASH")),
            admin_session_secret=_secret(source.get("ADMIN_SESSION_SECRET")),
            school_identity_provider_url=source.get("SCHOOL_IDENTITY_PROVIDER_URL"),
            support_resource_version=source.get("SUPPORT_RESOURCE_VERSION"),
            demo_mode=parsed_demo_mode,
            demo_env_ids=normalized_demo_ids,
            authorized_env_ids=normalized_authorized_ids,
            declared_environment_kind=decision.declared_kind,
            environment_kind=environment_kind,
            configuration_status="ready" if ready else "unconfigured",
            missing_requirements=tuple(sorted(set(missing))),
            demo_reset_allowed=environment_kind is EnvironmentKind.DEMO,
        )

    def public_snapshot(self) -> dict[str, object]:
        """Return the only configuration projection allowed in API responses."""

        return {
            "environment_kind": self.environment_kind.value,
            "configuration_status": self.configuration_status,
            "declared_environment_kind": self.declared_environment_kind.value,
            "missing_requirements": list(self.missing_requirements),
            "demo_reset_allowed": self.demo_reset_allowed,
        }

    @property
    def session_secret(self) -> str | None:
        return self.admin_session_secret.get_secret_value() if self.admin_session_secret else None

    @property
    def password_hash(self) -> str | None:
        return self.admin_password_hash.get_secret_value() if self.admin_password_hash else None

    @property
    def wechat_secret(self) -> str | None:
        return self.wechat_appsecret.get_secret_value() if self.wechat_appsecret else None

    @property
    def cloudbase_secret(self) -> str | None:
        return self.cloudbase_api_key.get_secret_value() if self.cloudbase_api_key else None


def _secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value else None
