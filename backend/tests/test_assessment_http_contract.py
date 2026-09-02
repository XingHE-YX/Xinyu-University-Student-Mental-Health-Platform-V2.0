from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app

from .test_assessment_service import configured_settings, seed_rules_repository


def build_client() -> tuple[TestClient, str]:
    app = create_app(configured_settings(), domain_repository=seed_rules_repository())
    token = app.state.auth_service.tokens.issue(
        "student",
        "user-1",
        app.state.auth_service.sessions,
    ).access_token
    return TestClient(app), token


def test_assessment_catalog_start_and_abandon_are_enveloped_and_owner_scoped() -> None:
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}

    catalog = client.get("/api/v1/assessment-modules", headers=headers)
    assert catalog.status_code == 200
    assert [item["module_code"] for item in catalog.json()["data"]["modules"]] == [
        "phq9",
        "gad7",
        "sleep_observation",
    ]

    started = client.post(
        "/api/v1/assessment-sessions",
        headers=headers,
        json={"module_code": "phq9", "client_start_key": "start-http-1"},
    )
    assert started.status_code == 200
    session = started.json()["data"]

    abandoned = client.post(
        f"/api/v1/assessment-sessions/{session['session_id']}/abandon",
        headers={**headers, "Idempotency-Key": "abandon-http-1"},
        json={"object_version": session["object_version"]},
    )
    assert abandoned.status_code == 200
    assert abandoned.json()["data"]["state"] == "abandoned"


def test_assessment_complete_rejects_client_owned_score_and_safety_fields() -> None:
    client, token = build_client()
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "complete-http-1"}
    response = client.post(
        "/api/v1/assessment-sessions/session-does-not-matter/complete",
        headers=headers,
        json={
            "answers": [],
            "object_version": 1,
            "score": 42,
            "safety_state": "can_be_safe",
            "environment_id": "authorized-env",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


def test_assessment_result_delete_reads_object_version_from_request_body() -> None:
    client, token = build_client()

    response = client.request(
        "DELETE",
        "/api/v1/assessment-results/missing-result",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "delete-http-1"},
        json={"object_version": 1},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
