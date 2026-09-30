import pytest
from fastapi.testclient import TestClient

from app.infra.config.settings import Settings
from app.infra.integrations.school_identity import HttpSchoolIdentityProvider
from app.infra.integrations.wechat import WechatAuthClient
from app.main import create_app


def test_lifespan_closes_all_pooled_clients() -> None:
    wechat = WechatAuthClient(appid=None, appsecret=None)
    school = HttpSchoolIdentityProvider(provider_url=None)
    app = create_app(Settings.from_environment({}), wechat_client=wechat)
    app.state.container.identity_service.school = school
    ai = app.state.container.ai_assist_service.client
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert not wechat._client.is_closed
        assert not school._client.is_closed
        assert not ai._client.is_closed
    assert wechat._client.is_closed
    assert school._client.is_closed
    assert ai._client.is_closed


def test_initialization_failure_still_closes_resources() -> None:
    wechat = WechatAuthClient(appid=None, appsecret=None)
    app = create_app(Settings.from_environment({}), wechat_client=wechat)

    async def fail() -> None:
        raise RuntimeError("startup failed")

    app.state.container.admin_workbench_service.initialize = fail
    with pytest.raises(RuntimeError, match="startup failed"):
        with TestClient(app):
            pass
    assert wechat._client.is_closed
    assert app.state.container.ai_assist_service.client._client.is_closed
