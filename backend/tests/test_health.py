import re

from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app

client = TestClient(create_app(Settings.from_environment({})))


def test_health_returns_public_service_status() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert re.fullmatch(r"req_[0-9a-f]{32}", payload["request_id"])
    assert payload == {
        "request_id": payload["request_id"],
        "data": {
            "service": "xinyu-v2-backend",
            "version": "0.1.0",
            "environment_kind": "unconfigured",
            "status": "degraded",
        },
        "error": None,
    }
