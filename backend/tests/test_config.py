import pytest

from app.config.environments import EnvironmentKind, EnvironmentMismatchError
from app.config.settings import Settings


def complete_environment() -> dict[str, str]:
    return {
        "WECHAT_APPID": "wx-demo",
        "WECHAT_APPSECRET": "wechat-secret",
        "CLOUDBASE_ENV_ID": "demo-env",
        "CLOUDBASE_API_KEY": "cloudbase-secret",
        "DEEPSEEK_API_KEY": "deepseek-secret",
        "ADMIN_PASSWORD_HASH": "pbkdf2_sha256$1$salt$digest",
        "ADMIN_SESSION_SECRET": "admin-session-secret",
        "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
        "SUPPORT_RESOURCE_VERSION": "support-v1",
        "DEMO_MODE": "true",
    }


def test_settings_classifies_a_complete_known_demo_environment() -> None:
    settings = Settings.from_environment(
        complete_environment(),
        demo_env_ids={"demo-env"},
        authorized_env_ids={"authorized-env"},
    )

    assert settings.environment_kind is EnvironmentKind.DEMO
    assert settings.configuration_status == "ready"
    assert settings.missing_requirements == ()


def test_settings_never_serializes_secrets_or_real_environment_id() -> None:
    settings = Settings.from_environment(
        complete_environment(),
        demo_env_ids={"demo-env"},
    )

    public = settings.public_snapshot()
    serialized = str(public)

    assert public["environment_kind"] == "demo"
    assert "wechat-secret" not in serialized
    assert "cloudbase-secret" not in serialized
    assert "deepseek-secret" not in serialized
    assert "demo-env" not in serialized
    assert "ADMIN_PASSWORD_HASH" not in public

    model_dump = settings.model_dump()
    assert "wechat_appsecret" not in model_dump
    assert "cloudbase_api_key" not in model_dump
    assert "deepseek_api_key" not in model_dump
    assert "admin_password_hash" not in model_dump
    assert "admin_session_secret" not in model_dump
    assert "cloudbase_env_id" not in model_dump


def test_missing_support_identity_or_ai_configuration_is_unconfigured() -> None:
    environment = complete_environment()
    environment.pop("SUPPORT_RESOURCE_VERSION")
    environment.pop("SCHOOL_IDENTITY_PROVIDER_URL")
    environment.pop("DEEPSEEK_API_KEY")

    settings = Settings.from_environment(environment, demo_env_ids={"demo-env"})

    assert settings.environment_kind is EnvironmentKind.UNCONFIGURED
    assert settings.configuration_status == "unconfigured"
    assert settings.demo_reset_allowed is False
    assert set(settings.missing_requirements) >= {
        "support_resources",
        "identity_provider",
        "deepseek_api_key",
    }


def test_demo_mode_cannot_be_used_for_a_known_authorized_environment() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID"] = "authorized-env"

    with pytest.raises(EnvironmentMismatchError):
        Settings.from_environment(
            environment,
            demo_env_ids={"demo-env"},
            authorized_env_ids={"authorized-env"},
        )


def test_known_authorized_environment_is_classified_only_when_mode_matches() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID"] = "authorized-env"
    environment["DEMO_MODE"] = "false"

    settings = Settings.from_environment(
        environment,
        demo_env_ids={"demo-env"},
        authorized_env_ids={"authorized-env"},
    )

    assert settings.environment_kind is EnvironmentKind.AUTHORIZED
    assert settings.demo_reset_allowed is False
