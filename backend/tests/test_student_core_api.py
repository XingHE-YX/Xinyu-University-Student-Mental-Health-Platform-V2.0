from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.integrations.wechat_auth import WechatIdentity
from app.main import create_app


class FakeWechatClient:
    async def exchange_code(self, code: str) -> WechatIdentity:
        return WechatIdentity(subject_id="student-subject-hash")


def configured_settings() -> Settings:
    return Settings.from_environment(
        {
            "WECHAT_APPID": "wx-demo",
            "WECHAT_APPSECRET": "wechat-secret",
            "CLOUDBASE_ENV_ID": "demo-env",
            "CLOUDBASE_API_KEY": "cloudbase-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
            "ADMIN_PASSWORD_HASH": "password-hash",
            "ADMIN_SESSION_SECRET": "admin-session-secret",
            "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
            "SUPPORT_RESOURCE_VERSION": "support-v1",
            "DEMO_MODE": "true",
        },
        demo_env_ids={"demo-env"},
    )


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/wechat/session",
        json={"code": "one-time-code", "client_version": "0.1.0"},
    )
    assert response.status_code == 200
    return cast(str, response.json()["data"]["access_token"])


def test_bootstrap_before_consent_returns_safe_configuration_and_base_consent_updates_account() -> (
    None
):
    client = TestClient(create_app(configured_settings(), wechat_client=FakeWechatClient()))
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    bootstrap = client.get("/api/v1/app/bootstrap", headers=headers)
    assert bootstrap.status_code == 200
    data = bootstrap.json()["data"]
    assert data["base_consent"]["status"] == "required"
    assert data["today_summary"] is None
    assert "student_name" not in str(data)

    consent = client.post(
        "/api/v1/consents/base",
        headers={**headers, "Idempotency-Key": "base-1"},
        json={"document_version": "base-v1", "action": "accepted", "object_version": 1},
    )
    assert consent.status_code == 200
    assert consent.json()["data"]["base_consent_status"] == "accepted"


def test_student_core_identity_status_and_account_stop_require_idempotency_and_are_versioned() -> (
    None
):
    client = TestClient(create_app(configured_settings(), wechat_client=FakeWechatClient()))
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}

    missing_key = client.post(
        "/api/v1/account/stop",
        headers=headers,
        json={"confirmation_text": "停止使用", "object_version": 1},
    )
    assert missing_key.status_code == 400
    assert missing_key.json()["error"]["code"] == "INVALID_REQUEST"

    stopped = client.post(
        "/api/v1/account/stop",
        headers={**headers, "Idempotency-Key": "stop-1"},
        json={"confirmation_text": "停止使用", "object_version": 1},
    )
    assert stopped.status_code == 200
    assert stopped.json()["data"]["status"] == "recovery_pending"

    status = client.get("/api/v1/account/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["data"]["can_recover"] is True
