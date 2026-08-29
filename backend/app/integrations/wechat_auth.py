"""WeChat one-time code exchange. Raw WeChat identifiers never leave this adapter."""

import hashlib
from dataclasses import dataclass

import httpx

from app.schemas.errors import ApiException


@dataclass(frozen=True)
class WechatIdentity:
    subject_id: str


class WechatAuthClient:
    def __init__(
        self,
        *,
        appid: str | None,
        appsecret: str | None,
        endpoint: str = "https://api.weixin.qq.com/sns/jscode2session",
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.appid = appid
        self.appsecret = appsecret
        self.endpoint = endpoint
        self.transport = transport
        self.timeout = timeout

    async def exchange_code(self, code: str) -> WechatIdentity:
        if not self.appid or not self.appsecret:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "微信登录暂未配置")
        if not code.strip():
            raise ApiException(400, "INVALID_REQUEST")
        params = {
            "appid": self.appid,
            "secret": self.appsecret,
            "js_code": code,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.get(self.endpoint, params=params)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "微信登录服务暂时不可用") from error
        if not isinstance(body, dict):
            raise ApiException(503, "DEPENDENCY_UNAVAILABLE", "微信登录服务暂时不可用")
        if body.get("errcode") not in (None, 0):
            raise ApiException(401, "AUTH_REQUIRED", "微信登录凭证无效或已过期")
        openid = body.get("openid")
        unionid = body.get("unionid")
        if not isinstance(openid, str) or not openid:
            raise ApiException(401, "AUTH_REQUIRED", "微信登录凭证无效或已过期")
        identity_key = unionid if isinstance(unionid, str) and unionid else openid
        subject_id = hashlib.sha256(f"{self.appid}:{identity_key}".encode()).hexdigest()
        return WechatIdentity(subject_id=subject_id)
