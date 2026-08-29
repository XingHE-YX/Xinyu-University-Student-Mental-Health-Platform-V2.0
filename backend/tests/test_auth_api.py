from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.integrations.wechat_auth import WechatIdentity
from app.main import create_app
from app.security.passwords import hash_password


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
            "ADMIN_PASSWORD_HASH": hash_password("correct-password", salt=b"test-salt"),
            "ADMIN_SESSION_SECRET": "admin-session-secret",
            "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
            "SUPPORT_RESOURCE_VERSION": "support-v1",
            "DEMO_MODE": "true",
        },
        demo_env_ids={"demo-env"},
    )


def test_student_login_and_me_use_the_server_subject_not_client_identity_fields() -> None:
    app = create_app(configured_settings(), wechat_client=FakeWechatClient())
    client = TestClient(app)

    login = client.post(
        "/api/v1/auth/wechat/session",
        json={"code": "one-time-code", "client_version": "0.1.0", "user_id": "attacker"},
    )

    assert login.status_code == 422
    assert login.json()["error"]["code"] == "VALIDATION_FAILED"

    valid_login = client.post(
        "/api/v1/auth/wechat/session",
        json={"code": "one-time-code", "client_version": "0.1.0"},
    )
    assert valid_login.status_code == 200
    access_token = valid_login.json()["data"]["access_token"]

    me = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert me.status_code == 200
    assert me.json()["data"] == {
        "subject_type": "student",
        "subject_id": "student-subject-hash",
        "account_status": "active",
    }


def test_admin_login_uses_fixed_account_and_refresh_rotation() -> None:
    app = create_app(configured_settings(), wechat_client=FakeWechatClient())
    client = TestClient(app)

    login = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "心理健康中心工作人员", "password": "correct-password"},
    )

    assert login.status_code == 200
    data = login.json()["data"]
    assert data["display_name"] == "心理健康中心工作人员"
    assert data["capability_label"] == "超级管理员"

    refresh = client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert refresh.status_code == 200
    rotated = refresh.json()["data"]

    old_refresh = client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": data["refresh_token"]},
    )
    assert old_refresh.status_code == 401
    assert old_refresh.json()["error"]["code"] == "SESSION_EXPIRED"

    me = client.get(
        "/api/v1/admin/me",
        headers={"Authorization": f"Bearer {rotated['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["data"]["capability_label"] == "超级管理员"


def test_student_and_admin_refresh_endpoints_cannot_cross_subject_types() -> None:
    app = create_app(configured_settings(), wechat_client=FakeWechatClient())
    client = TestClient(app)
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "心理健康中心工作人员", "password": "correct-password"},
    )
    refresh_token = login.json()["data"]["refresh_token"]

    wrong_endpoint = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    correct_endpoint = client.post(
        "/api/v1/admin/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert wrong_endpoint.status_code == 401
    assert wrong_endpoint.json()["error"]["code"] == "AUTH_REQUIRED"
    assert correct_endpoint.status_code == 200


def test_student_logout_revokes_access_and_repeated_logout_is_safe() -> None:
    app = create_app(configured_settings(), wechat_client=FakeWechatClient())
    client = TestClient(app)
    login = client.post(
        "/api/v1/auth/wechat/session",
        json={"code": "one-time-code", "client_version": "0.1.0"},
    )
    access_token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    first_logout = client.post("/api/v1/auth/logout", headers=headers)
    second_logout = client.post("/api/v1/auth/logout", headers=headers)
    me = client.get("/api/v1/me", headers=headers)

    assert first_logout.status_code == 200
    assert second_logout.status_code == 200
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "SESSION_EXPIRED"
