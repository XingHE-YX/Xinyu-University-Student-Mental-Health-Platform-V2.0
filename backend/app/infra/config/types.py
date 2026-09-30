"""Validated, immutable configuration types shared by runtime adapters."""

from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from app.infra.config.validation import EnvironmentKind


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, validate_default=True, hide_input_in_errors=True
    )


class DatabaseConfig(ConfigModel):
    timeout_seconds: float = Field(default=8.0, gt=0, le=120)
    max_connections: int = Field(default=20, ge=1, le=200)
    max_keepalive_connections: int = Field(default=10, ge=0)
    rollback_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        if self.max_keepalive_connections > self.max_connections:
            raise ValueError("keepalive connections exceed pool capacity")
        return self


class PasswordConfig(ConfigModel):
    memory_cost_kib: int = Field(default=65536, ge=19456, le=262144)
    time_cost: int = Field(default=3, ge=2, le=10)
    parallelism: int = Field(default=1, ge=1, le=8)
    max_concurrency: int = Field(default=2, ge=1, le=16)
    max_pbkdf2_iterations: int = Field(default=2_000_000, ge=310_000, le=10_000_000)


class AIConfig(ConfigModel):
    provider: str = Field(default="deepseek", pattern=r"^[a-z][a-z0-9_]*$")
    endpoint: str = "https://api.deepseek.com/chat/completions"
    model: str = Field(default="deepseek-v4-flash", min_length=1, max_length=128)
    resolved_model_version: str = "DeepSeek-V4-Flash-0731"
    timeout_seconds: float = Field(default=8.0, gt=0, le=120)
    max_concurrency: int = Field(default=4, ge=1, le=32)
    temperature: float = Field(default=0.2, ge=0, le=2)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("AI endpoint must be HTTPS without embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("AI endpoint must not contain a query or fragment")
        return value


class LoggerConfig(ConfigModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    queue_capacity: int = Field(default=4096, ge=1, le=100_000)


class SessionConfig(ConfigModel):
    access_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    student_refresh_ttl_seconds: int = Field(default=2_592_000, ge=3600)
    admin_refresh_ttl_seconds: int = Field(default=28_800, ge=900)

    @model_validator(mode="after")
    def validate_expiry(self) -> Self:
        if (
            min(self.student_refresh_ttl_seconds, self.admin_refresh_ttl_seconds)
            <= self.access_ttl_seconds
        ):
            raise ValueError("refresh token lifetime must exceed access token lifetime")
        return self


class RuntimeConfig(ConfigModel):
    wechat_appid: str | None = None
    wechat_appsecret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    cloudbase_env_id: str | None = Field(default=None, exclude=True, repr=False)
    cloudbase_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    deepseek_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    admin_password_hash: SecretStr | None = Field(default=None, exclude=True, repr=False)
    admin_session_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    school_identity_provider_url: str | None = None
    support_resource_version: str | None = None
    demo_mode: bool | None = None
    persistence_backend: Literal["memory", "cloudbase"] = "memory"
    demo_env_ids: tuple[str, ...] = Field(default=(), exclude=True, repr=False)
    authorized_env_ids: tuple[str, ...] = Field(default=(), exclude=True, repr=False)
    declared_environment_kind: EnvironmentKind = EnvironmentKind.UNCONFIGURED
    persistence_environment_kind: EnvironmentKind = Field(
        default=EnvironmentKind.UNCONFIGURED, exclude=True
    )
    environment_kind: EnvironmentKind = EnvironmentKind.UNCONFIGURED
    configuration_status: Literal["ready", "unconfigured"] = "unconfigured"
    missing_requirements: tuple[str, ...] = ()
    demo_reset_allowed: bool = False
    admin_web_origins: tuple[str, ...] = ()
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    password: PasswordConfig = Field(default_factory=PasswordConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)

    @field_validator("admin_web_origins")
    @classmethod
    def validate_origins(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            parsed = urlsplit(value)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("admin origins must be HTTPS origins without credentials")
        return tuple(value.rstrip("/") for value in values)

    @model_validator(mode="after")
    def validate_isolation(self) -> Self:
        if set(self.demo_env_ids) & set(self.authorized_env_ids):
            raise ValueError("environment registries must not overlap")
        if self.demo_reset_allowed and self.environment_kind is not EnvironmentKind.DEMO:
            raise ValueError("demo reset requires a registered demo environment")
        return self
