from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config.settings import Settings
from app.main import create_app
from app.repositories.protocols import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.schemas.errors import ApiException


def test_invalid_request_id_returns_the_standard_error_envelope() -> None:
    client = TestClient(create_app(Settings.from_environment({})))

    response = client.get("/api/v1/health", headers={"X-Request-Id": "not valid"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"] == {
        "code": "INVALID_REQUEST",
        "message": "请求编号格式不正确",
        "retryable": False,
        "current_version": None,
    }


def test_unknown_routes_are_wrapped_without_internal_details() -> None:
    client = TestClient(create_app(Settings.from_environment({})))

    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    assert payload["data"] is None
    assert payload["error"]["code"] == "NOT_FOUND"
    assert "Route" not in payload["error"]["message"]
    assert "Traceback" not in response.text


def test_unhandled_exceptions_do_not_leak_stack_traces() -> None:
    app = create_app(Settings.from_environment({}))

    @app.get("/_test/internal-error")
    async def internal_error() -> None:
        raise RuntimeError("database password=secret-value")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_test/internal-error")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret-value" not in response.text
    assert "Traceback" not in response.text


def test_repository_failures_are_mapped_to_stable_api_errors() -> None:
    app = create_app(Settings.from_environment({}))

    @app.get("/_test/version-conflict")
    async def version_conflict() -> None:
        raise RepositoryVersionConflict(4)

    @app.get("/_test/not-found")
    async def not_found() -> None:
        raise RepositoryNotFound("internal document id")

    @app.get("/_test/unavailable")
    async def unavailable() -> None:
        raise RepositoryUnavailable("database password=secret-value")

    client = TestClient(app, raise_server_exceptions=False)
    conflict = client.get("/_test/version-conflict")
    missing = client.get("/_test/not-found")
    unavailable_response = client.get("/_test/unavailable")

    assert conflict.status_code == 409
    assert conflict.json()["error"] == {
        "code": "VERSION_CONFLICT",
        "message": "内容刚刚发生变化，请刷新后查看最新状态",
        "retryable": False,
        "current_version": 4,
    }
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert unavailable_response.status_code == 503
    assert unavailable_response.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert "secret-value" not in unavailable_response.text


def test_required_idempotency_header_is_validated_at_the_boundary() -> None:
    from app.api.dependencies import require_idempotency_key

    request = Request({"type": "http", "headers": []})
    try:
        require_idempotency_key(request)
    except ApiException as error:
        assert error.status_code == 400
        assert error.code == "INVALID_REQUEST"
    else:
        raise AssertionError("missing idempotency key should fail")
