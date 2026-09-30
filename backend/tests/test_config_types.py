import pytest
from pydantic import ValidationError

from app.infra.config.settings import Settings
from app.infra.config.types import AIConfig, DatabaseConfig, PasswordConfig, SessionConfig


def test_code_defaults_are_validated_and_immutable() -> None:
    settings = Settings.from_environment({})
    assert settings.ai.provider == "deepseek"
    assert settings.password.memory_cost_kib == 65536
    with pytest.raises(ValidationError):
        settings.password.time_cost = 1


def test_invalid_cost_pool_lifetime_and_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PasswordConfig(memory_cost_kib=1024)
    with pytest.raises(ValidationError):
        DatabaseConfig(max_connections=1, max_keepalive_connections=2)
    with pytest.raises(ValidationError):
        SessionConfig(access_ttl_seconds=3600, admin_refresh_ttl_seconds=900)
    with pytest.raises(ValidationError):
        Settings.model_validate({"unsupported": True})


def test_endpoints_origins_and_errors_do_not_expose_credentials() -> None:
    with pytest.raises(ValidationError) as caught:
        AIConfig(endpoint="https://username:secret@example.test/chat")
    assert "secret" not in str(caught.value)
    with pytest.raises(ValidationError):
        Settings(admin_web_origins=("https://example.test/app",))
    with pytest.raises(ValidationError):
        Settings(demo_reset_allowed=True)
    assert Settings(admin_web_origins=("https://example.test/",)).admin_web_origins == (
        "https://example.test",
    )
