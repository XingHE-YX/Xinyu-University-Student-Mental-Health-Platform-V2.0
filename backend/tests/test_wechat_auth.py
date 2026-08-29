import httpx
import pytest

from app.integrations.wechat_auth import WechatAuthClient
from app.schemas.errors import ApiException


@pytest.mark.asyncio
async def test_wechat_code_exchange_returns_a_non_reversible_subject_reference() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"openid": "openid-raw", "session_key": "secret"})

    client = WechatAuthClient(
        appid="wx-demo",
        appsecret="wechat-secret",
        transport=httpx.MockTransport(handler),
        endpoint="https://wechat.example.test/jscode2session",
    )

    identity = await client.exchange_code("one-time-code")

    assert identity.subject_id != "openid-raw"
    assert len(identity.subject_id) == 64
    assert requests[0].url.params["js_code"] == "one-time-code"
    assert "openid-raw" not in identity.subject_id
    assert not hasattr(identity, "union_id")
    assert "session_key" not in identity.__dict__


@pytest.mark.asyncio
async def test_missing_wechat_configuration_is_a_dependency_error() -> None:
    client = WechatAuthClient(appid=None, appsecret=None)

    with pytest.raises(ApiException) as error:
        await client.exchange_code("one-time-code")

    assert error.value.status_code == 503
    assert error.value.code == "DEPENDENCY_UNAVAILABLE"
