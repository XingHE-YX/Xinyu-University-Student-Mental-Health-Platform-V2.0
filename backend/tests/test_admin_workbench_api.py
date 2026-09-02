from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from app.security.passwords import hash_password


def settings_for(environment: str = "demo") -> Settings:
    return Settings.from_environment(
        {
            "WECHAT_APPID": "wx-demo",
            "WECHAT_APPSECRET": "wechat-secret",
            "CLOUDBASE_ENV_ID": f"{environment}-env",
            "CLOUDBASE_API_KEY": "cloudbase-secret",
            "DEEPSEEK_API_KEY": "deepseek-secret",
            "ADMIN_PASSWORD_HASH": hash_password("correct-password", salt=b"test-salt"),
            "ADMIN_SESSION_SECRET": "admin-session-secret",
            "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
            "SUPPORT_RESOURCE_VERSION": "support-v1",
            "DEMO_MODE": "true" if environment == "demo" else "false",
        },
        demo_env_ids={"demo-env"},
        authorized_env_ids={"authorized-env"},
    )


def authenticated_client(environment: str = "demo") -> tuple[TestClient, dict[str, str]]:
    client = TestClient(create_app(settings_for(environment)))
    login = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "心理健康中心工作人员", "password": "correct-password"},
    )
    token = login.json()["data"]["access_token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_workbench_requires_admin_session_and_projects_only_safe_fields() -> None:
    client = TestClient(create_app(settings_for()))
    unauthenticated = client.get("/api/v1/admin/workbench?section=all")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTH_REQUIRED"

    client, headers = authenticated_client()
    response = client.get("/api/v1/admin/workbench?section=all", headers=headers)
    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert set(item) == {
        "task_id",
        "task_kind",
        "state",
        "created_at",
        "updated_at",
        "assigned_admin_display",
        "safe_summary",
        "object_version",
    }
    assert "student_name" not in item


def test_task_mutations_require_idempotency_and_reject_stale_versions() -> None:
    client, headers = authenticated_client()
    item = client.get("/api/v1/admin/workbench?section=needs_action", headers=headers).json()[
        "data"
    ]["items"][0]
    task_id = item["task_id"]
    missing_key = client.post(
        f"/api/v1/admin/tasks/{task_id}/claim",
        headers=headers,
        json={"object_version": 1},
    )
    assert missing_key.status_code == 400

    claimed = client.post(
        f"/api/v1/admin/tasks/{task_id}/claim",
        headers={**headers, "Idempotency-Key": "claim-1"},
        json={"object_version": 1},
    )
    assert claimed.status_code == 200
    stale = client.post(
        f"/api/v1/admin/tasks/{task_id}/decision",
        headers={**headers, "Idempotency-Key": "decision-1"},
        json={"object_version": 1, "action": "publish", "internal_reason": "事实"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"


def test_detail_view_and_decision_are_recorded_in_read_only_audit() -> None:
    client, headers = authenticated_client()
    task_id = "task-demo-content-01"
    client.get(f"/api/v1/admin/tasks/{task_id}", headers=headers)
    client.post(
        f"/api/v1/admin/tasks/{task_id}/claim",
        headers={**headers, "Idempotency-Key": "claim-audit"},
        json={"object_version": 1},
    )
    client.post(
        f"/api/v1/admin/tasks/{task_id}/decision",
        headers={**headers, "Idempotency-Key": "decision-audit"},
        json={"object_version": 2, "action": "publish", "internal_reason": "事实"},
    )
    audit = client.get("/api/v1/admin/audit-events", headers=headers)
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.json()["data"]["items"]]
    assert "task_view" in actions
    assert "task_claim" in actions
    assert "publish" in actions


def test_demo_reset_is_rejected_in_authorized_environment_before_mutation() -> None:
    client, headers = authenticated_client("authorized")
    response = client.post(
        "/api/v1/admin/demo/reset",
        headers={**headers, "Idempotency-Key": "reset-authorized"},
        json={"confirmation_text": "确认重置", "reset_scope": ["tasks"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
