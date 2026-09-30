"""Typed server configuration with an explicit safe unconfigured state."""

import os
from collections.abc import Iterable, Mapping
from typing import Literal, cast

from pydantic import SecretStr

from app.infra.config.types import RuntimeConfig
from app.infra.config.validation import (
    EnvironmentKind,
    parse_demo_mode,
    resolve_environment,
)
from app.infra.logger.common import traced


class Settings(RuntimeConfig):
    """Runtime settings.

    Secret values are kept in memory for integrations, but public status output is
    deliberately assembled by :meth:`public_snapshot` instead of serializing this model.
    """

    @classmethod
    @traced
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        demo_env_ids: Iterable[str] | None = None,
        authorized_env_ids: Iterable[str] | None = None,
    ) -> Settings:
        """Build settings from server variables without exposing their raw values."""

        source = {
            key: normalized
            for key, value in (os.environ if environment is None else environment).items()
            if (normalized := _configured_value(value)) is not None
        }
        parsed_demo_mode = parse_demo_mode(source.get("DEMO_MODE"))
        normalized_demo_ids = _environment_ids(demo_env_ids, source.get("CLOUDBASE_ENV_ID_DEMO"))
        normalized_authorized_ids = _environment_ids(
            authorized_env_ids, source.get("CLOUDBASE_ENV_ID_AUTHORIZED")
        )
        decision = resolve_environment(
            demo_mode=parsed_demo_mode,
            cloudbase_env_id=source.get("CLOUDBASE_ENV_ID"),
            demo_env_ids=normalized_demo_ids,
            authorized_env_ids=normalized_authorized_ids,
        )
        demo_environment = decision.matched_kind is EnvironmentKind.DEMO
        support_resource_version = source.get("SUPPORT_RESOURCE_VERSION") or (
            "support-v1" if demo_environment else None
        )
        persistence_backend = source.get("PERSISTENCE_BACKEND", "memory")
        if persistence_backend not in {"memory", "cloudbase"}:
            raise ValueError("PERSISTENCE_BACKEND must be memory or cloudbase")
        cloudbase_api_key = source.get("CLOUDBASE_API_KEY") or source.get("CLOUDBASE_APIKEY")

        missing: list[str] = []
        # Optional AI assistance must not disable core services when its key is absent.
        required_values = {
            "cloudbase_env_id": source.get("CLOUDBASE_ENV_ID"),
            "cloudbase_api_key": cloudbase_api_key,
            "wechat_appid": source.get("WECHAT_APPID"),
            "wechat_appsecret": source.get("WECHAT_APPSECRET"),
            "admin_password_hash": source.get("ADMIN_PASSWORD_HASH"),
            "admin_session_secret": source.get("ADMIN_SESSION_SECRET"),
            "identity_provider": source.get("SCHOOL_IDENTITY_PROVIDER_URL")
            or ("demo-synthetic" if demo_environment else None),
            "support_resources": support_resource_version,
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
            cloudbase_api_key=_secret(cloudbase_api_key),
            deepseek_api_key=_secret(source.get("DEEPSEEK_API_KEY")),
            admin_password_hash=_secret(source.get("ADMIN_PASSWORD_HASH")),
            admin_session_secret=_secret(source.get("ADMIN_SESSION_SECRET")),
            school_identity_provider_url=source.get("SCHOOL_IDENTITY_PROVIDER_URL"),
            support_resource_version=support_resource_version,
            demo_mode=parsed_demo_mode,
            persistence_backend=cast(Literal["memory", "cloudbase"], persistence_backend),
            demo_env_ids=normalized_demo_ids,
            authorized_env_ids=normalized_authorized_ids,
            declared_environment_kind=decision.declared_kind,
            persistence_environment_kind=decision.matched_kind,
            environment_kind=environment_kind,
            configuration_status="ready" if ready else "unconfigured",
            missing_requirements=tuple(sorted(set(missing))),
            demo_reset_allowed=environment_kind is EnvironmentKind.DEMO,
            admin_web_origins=tuple(
                value for key in ("ADMIN_WEB_ORIGIN",) if (value := source.get(key))
            ),
        )

    @traced
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

    @property
    def cloudbase_persistence_ready(self) -> bool:
        return (
            self.persistence_backend == "cloudbase"
            and self.persistence_environment_kind is not EnvironmentKind.UNCONFIGURED
            and self.cloudbase_env_id is not None
            and self.cloudbase_secret is not None
        )

    @property
    def student_login_ready(self) -> bool:
        persistence_ready = self.persistence_backend == "memory" or self.cloudbase_persistence_ready
        return (
            self.persistence_environment_kind is not EnvironmentKind.UNCONFIGURED
            and self.wechat_appid is not None
            and self.wechat_secret is not None
            and self.session_secret is not None
            and persistence_ready
        )


@traced
def _secret(value: str | None) -> SecretStr | None:
    return SecretStr(value) if value else None


@traced
def _configured_value(value: str) -> str | None:
    """Blank values and unrendered deployment references are not credentials."""

    normalized = value.strip()
    if (
        not normalized
        or "${" in normalized
        or (normalized.startswith("<") and normalized.endswith(">"))
        or "://<" in normalized
    ):
        return None
    return normalized


@traced
def _environment_ids(explicit: Iterable[str] | None, registered: str | None) -> tuple[str, ...]:
    # Explicit registries (including empty ones) override deployment variables.
    # Never register the target CLOUDBASE_ENV_ID automatically from DEMO_MODE.
    values = explicit if explicit is not None else (registered,) if registered else ()
    return tuple(sorted({normalized for item in values if (normalized := _configured_value(item))}))
