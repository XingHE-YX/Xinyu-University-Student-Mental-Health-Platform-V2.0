from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.security.tokens import TokenManager

from .test_safety_service import build_services, phq9_safety_answers


def test_safety_confirmation_api_rejects_client_state_tampering() -> None:
    assessment, safety, _, sessions, _, _ = build_services()
    app = create_app()
    app.state.assessment_service = assessment
    app.state.safety_service = safety
    client = TestClient(app)
    access_token = TokenManager("student-session-secret").issue("student", "user-1", sessions)
    started = assessment.start_session(
        access_token.access_token,
        module_code="phq9",
        request_id="req-api-start",
        idempotency_key="api-start",
    )

    response = client.post(
        f"/api/v1/assessment-sessions/{started.session_id}/safety-confirmation",
        headers={
            "Authorization": f"Bearer {access_token.access_token}",
            "Idempotency-Key": "api-safe-tampered",
            "X-Request-Id": "req-api-safe-tampered",
        },
        json={
            "state": "can_be_safe",
            "object_version": started.object_version,
            "answers": phq9_safety_answers("1"),
            "user_id": "attacker",
            "safety_state": "can_be_safe",
            "environment_id": "authorized-env",
        },
    )

    assert response.status_code == 422
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_safety_confirmation_and_resource_ack_api_return_enveloped_minimal_projection() -> None:
    assessment, safety, _, sessions, _, _ = build_services()
    app = create_app()
    app.state.assessment_service = assessment
    app.state.safety_service = safety
    client = TestClient(app)
    access_token = TokenManager("student-session-secret").issue("student", "user-1", sessions)
    started = assessment.start_session(
        access_token.access_token,
        module_code="phq9",
        request_id="req-api-start-2",
        idempotency_key="api-start-2",
    )

    confirmation = client.post(
        f"/api/v1/assessment-sessions/{started.session_id}/safety-confirmation",
        headers={
            "Authorization": f"Bearer {access_token.access_token}",
            "Idempotency-Key": "api-uncertain",
            "X-Request-Id": "req-api-uncertain",
        },
        json={
            "state": "uncertain",
            "object_version": started.object_version,
            "answers": phq9_safety_answers("1"),
        },
    )
    assert confirmation.status_code == 200
    data = confirmation.json()["data"]
    assert data["next_step"] == "show_support_resources"
    assert data["result_id"] is None
    assert data["visible_projection"]["current_selection"] == "uncertain"
    assert "score" not in data["visible_projection"]
    assert "user_id" not in data["visible_projection"]

    ack = client.post(
        f"/api/v1/assessment-sessions/{started.session_id}/support-resource-ack",
        headers={
            "Authorization": f"Bearer {access_token.access_token}",
            "Idempotency-Key": "api-ack",
            "X-Request-Id": "req-api-ack",
        },
        json={
            "resource_context": "safety",
            "resource_version": "support-v1",
            "object_version": started.object_version + 1,
        },
    )

    assert ack.status_code == 200
    assert ack.json()["data"]["resource_version"] == "support-v1"
    assert ack.json()["data"]["version"] == started.object_version + 2
