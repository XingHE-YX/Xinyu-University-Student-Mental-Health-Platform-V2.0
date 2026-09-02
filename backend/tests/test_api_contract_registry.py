from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.domain_data_repository import InMemoryDomainDataRepository

from .test_auth_api import FakeWechatClient, configured_settings


def _normalize_route(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{param}", path)


def _declared_contract() -> set[tuple[str, str]]:
    document = Path(__file__).resolve().parents[2].joinpath("BACKEND_STRUCTURE.md").read_text()
    entries = re.findall(
        r"^####?\s+(GET|POST|PUT|DELETE|PATCH)\s+`?(/api/v1[^`\s]+)`?",
        document,
        re.MULTILINE,
    )
    entries.extend(
        re.findall(
            r"^###\s+(GET|POST|PUT|DELETE|PATCH)\s+(/api/v1[^\s]+)",
            document,
            re.MULTILINE,
        )
    )
    return {(method, _normalize_route(path)) for method, path in entries}


def test_fastapi_routes_match_backend_structure_contract() -> None:
    app = create_app(configured_settings())
    actual = {
        (method, _normalize_route(route.path))
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/v1")
        for method in route.methods
    }

    assert actual == _declared_contract()


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
