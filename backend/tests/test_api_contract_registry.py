from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.domain_data_repository import InMemoryDomainDataRepository

from .test_auth_api import FakeWechatClient, configured_settings


def test_wechat_login_provisions_a_domain_user_for_follow_up_services() -> None:
    repository = InMemoryDomainDataRepository()
    app = create_app(
        configured_settings(),
        wechat_client=FakeWechatClient(),
        domain_repository=repository,
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/auth/wechat/session",
        json={"code": "one-time-code", "client_version": "0.1.0"},
    )

    assert response.status_code == 200
    user = repository.get_user_by_auth_subject_hash("student-subject-hash")
    assert user is not None
    assert user.status == "active"
