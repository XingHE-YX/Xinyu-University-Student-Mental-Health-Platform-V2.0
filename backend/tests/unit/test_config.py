from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.infra.config.settings import Settings
from app.infra.config.validation import (
    ConfigurationError,
    EnvironmentKind,
    EnvironmentMismatchError,
)
from app.main import create_app
from tests.helpers.password_fixtures import TEST_HASH


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


def test_settings_accepts_cloudbase_managed_api_key_variable() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_APIKEY"] = environment.pop("CLOUDBASE_API_KEY")

    settings = Settings.from_environment(environment, demo_env_ids={"demo-env"})

    assert settings.cloudbase_secret == "cloudbase-secret"
    assert "cloudbase_api_key" not in settings.missing_requirements


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


def test_demo_uses_registered_synthetic_identity_and_support_resources() -> None:
    environment = complete_environment()
    environment.pop("SUPPORT_RESOURCE_VERSION")
    environment.pop("SCHOOL_IDENTITY_PROVIDER_URL")
    environment.pop("DEEPSEEK_API_KEY")

    settings = Settings.from_environment(environment, demo_env_ids={"demo-env"})

    assert settings.environment_kind is EnvironmentKind.DEMO
    assert settings.configuration_status == "ready"
    assert settings.support_resource_version == "support-v1"
    assert settings.demo_reset_allowed is True
    assert "deepseek_api_key" not in settings.missing_requirements


def test_authorized_environment_requires_identity_and_support_configuration() -> None:
    environment = complete_environment()
    environment.update(CLOUDBASE_ENV_ID="authorized-env", DEMO_MODE="false")
    environment.pop("SUPPORT_RESOURCE_VERSION")
    environment.pop("SCHOOL_IDENTITY_PROVIDER_URL")

    settings = Settings.from_environment(
        environment,
        demo_env_ids={"demo-env"},
        authorized_env_ids={"authorized-env"},
    )

    assert settings.environment_kind is EnvironmentKind.UNCONFIGURED
    assert settings.configuration_status == "unconfigured"
    assert set(settings.missing_requirements) >= {
        "support_resources",
        "identity_provider",
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


@pytest.mark.parametrize("mode", ["demo", "authorized"])
@pytest.mark.parametrize("api_key", [None, "", "   ", "${SECRET_REF:DEEPSEEK_API_KEY_DEMO}"])
def test_optional_ai_key_does_not_disable_core_services(mode: str, api_key: str | None) -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID"] = f"{mode}-env"
    environment["CLOUDBASE_ENV_ID_DEMO"] = "demo-env"
    environment["CLOUDBASE_ENV_ID_AUTHORIZED"] = "authorized-env"
    environment["DEMO_MODE"] = "true" if mode == "demo" else "false"
    environment.pop("DEEPSEEK_API_KEY")
    if api_key is not None:
        environment["DEEPSEEK_API_KEY"] = api_key

    settings = Settings.from_environment(environment)

    assert settings.environment_kind == mode
    assert settings.configuration_status == "ready"
    assert settings.missing_requirements == ()
    assert settings.deepseek_api_key is None
    assert settings.demo_reset_allowed is (mode == "demo")


@pytest.mark.parametrize("mode", ["demo", "authorized"])
def test_default_app_startup_reads_registry_and_allows_admin_login_without_ai(mode: str) -> None:
    environment = complete_environment()
    environment.pop("DEEPSEEK_API_KEY")
    environment["ADMIN_PASSWORD_HASH"] = TEST_HASH
    environment["CLOUDBASE_ENV_ID"] = f"{mode}-env"
    environment["CLOUDBASE_ENV_ID_DEMO"] = "demo-env"
    environment["CLOUDBASE_ENV_ID_AUTHORIZED"] = "authorized-env"
    environment["DEMO_MODE"] = "true" if mode == "demo" else "false"
    with patch.dict("os.environ", environment, clear=True):
        app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/v2/health")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ok"
        assert response.json()["data"]["environment_kind"] == mode
        login = client.post(
            "/api/v2/admin/auth/login",
            json={"login_name": "心理健康中心工作人员", "password": "test-password"},
        )
        assert login.status_code == 200
    assert app.state.settings.deepseek_api_key is None
    assert app.state.settings.demo_reset_allowed is (mode == "demo")


@pytest.mark.parametrize("registered_id", [None, "", "   ", "${CLOUDBASE_ENV_ID_DEMO}"])
def test_target_environment_is_never_automatically_registered(registered_id: str | None) -> None:
    environment = complete_environment()
    if registered_id is not None:
        environment["CLOUDBASE_ENV_ID_DEMO"] = registered_id

    settings = Settings.from_environment(environment)

    assert settings.environment_kind is EnvironmentKind.UNCONFIGURED
    assert settings.missing_requirements == ("environment_registry",)
    assert settings.demo_reset_allowed is False


def test_explicit_empty_registry_overrides_environment_variables() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID_DEMO"] = "demo-env"

    settings = Settings.from_environment(environment, demo_env_ids=())

    assert settings.environment_kind is EnvironmentKind.UNCONFIGURED
    assert settings.demo_env_ids == ()


def test_first_demo_deployment_can_omit_the_uncreated_authorized_environment() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID_DEMO"] = "demo-env"
    environment.pop("DEEPSEEK_API_KEY")

    settings = Settings.from_environment(environment)

    assert settings.configuration_status == "ready"
    assert settings.environment_kind is EnvironmentKind.DEMO
    assert settings.authorized_env_ids == ()


def test_explicit_registry_and_whitespace_remain_supported() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID"] = " demo-env "
    environment["CLOUDBASE_ENV_ID_DEMO"] = "ignored-env"

    settings = Settings.from_environment(environment, demo_env_ids={" demo-env ", "demo-env"})

    assert settings.environment_kind is EnvironmentKind.DEMO
    assert settings.cloudbase_env_id == "demo-env"
    assert settings.demo_env_ids == ("demo-env",)


@pytest.mark.parametrize("target, demo_mode", [("authorized-env", "true"), ("demo-env", "false")])
def test_runtime_registry_rejects_wrong_environment_mode(target: str, demo_mode: str) -> None:
    environment = complete_environment()
    environment.update(
        CLOUDBASE_ENV_ID=target,
        CLOUDBASE_ENV_ID_DEMO="demo-env",
        CLOUDBASE_ENV_ID_AUTHORIZED="authorized-env",
        DEMO_MODE=demo_mode,
    )

    with patch.dict("os.environ", environment, clear=True):
        with pytest.raises(EnvironmentMismatchError):
            create_app()


def test_runtime_registry_rejects_overlapping_environments_without_exposing_ids() -> None:
    environment = complete_environment()
    environment["CLOUDBASE_ENV_ID_DEMO"] = "demo-env"
    environment["CLOUDBASE_ENV_ID_AUTHORIZED"] = "demo-env"

    with pytest.raises(ConfigurationError) as error:
        Settings.from_environment(environment)
    assert "demo-env" not in str(error.value)


def test_explicit_environment_mapping_does_not_inherit_process_registry() -> None:
    with patch.dict("os.environ", {"CLOUDBASE_ENV_ID_DEMO": "demo-env"}, clear=True):
        settings = Settings.from_environment(complete_environment())

    assert settings.environment_kind is EnvironmentKind.UNCONFIGURED


@pytest.mark.parametrize("value", ["", "   ", "${SECRET_REF:WECHAT_APPSECRET_DEMO}"])
def test_core_credentials_are_still_required(value: str) -> None:
    environment = complete_environment()
    environment["WECHAT_APPSECRET"] = value

    settings = Settings.from_environment(environment, demo_env_ids={"demo-env"})

    assert settings.configuration_status == "unconfigured"
    assert settings.missing_requirements == ("wechat_appsecret",)
    assert settings.wechat_appsecret is None
    assert settings.demo_reset_allowed is False
