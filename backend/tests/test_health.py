from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_public_service_status() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "health-check",
        "data": {
            "service": "xinyu-v2-backend",
            "version": "0.1.0",
            "environment_kind": "demo",
            "status": "ok",
        },
        "error": None,
    }
