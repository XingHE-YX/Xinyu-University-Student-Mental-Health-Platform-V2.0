from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.domain.models import IdentityRecordDocument, UserAccountDocument
from app.main import create_app
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.services.identity_service import HmacIdentityCipher

from .test_assessment_service import configured_settings


def build_client() -> tuple[TestClient, str, InMemoryDomainDataRepository]:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    settings = configured_settings()
    cipher = HmacIdentityCipher(settings.session_secret or "local-development-session-secret")
    user = UserAccountDocument(
        _id="user-1",
        auth_subject_hash="student-subject-hash",
        status="active",
        base_consent_status="accepted",
        community_consent_status="accepted",
        identity_record_id="identity-1",
        created_at=now,
        updated_at=now,
        version=1,
    )
    identity = IdentityRecordDocument(
        _id="identity-1",
        user_id="user-1",
        verification_status="verified",
        student_name_ciphertext=cipher.encrypt("张三"),
        student_number_ciphertext=cipher.encrypt("20260001"),
        provider_reference_hash="provider-ref",
        verified_at=now,
        access_version=1,
        created_at=now,
        updated_at=now,
        version=1,
    )
    repository = InMemoryDomainDataRepository(users=[user], identities=[identity])
    app = create_app(settings, domain_repository=repository)
    token = app.state.auth_service.tokens.issue(
        "admin",
        "admin:fixed-super-admin",
        app.state.auth_service.sessions,
        capability="super_admin",
    ).access_token
    return TestClient(app), token, repository


def test_identity_access_request_requires_admin_and_reads_only_approved_fields() -> None:
    client, token, _ = build_client()
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "identity-request-1"}
    created = client.post(
        "/api/v1/admin/identity-access-requests",
        headers=headers,
        json={
            "user_reference_id": "user-1",
            "requested_fields": ["student_name"],
            "reason_fact": "需要核对",
        },
    )
    assert created.status_code == 200
    request_id = created.json()["data"]["request_id"]
    denied = client.get(
        f"/api/v1/admin/identity-access-requests/{request_id}/identity",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert denied.status_code == 403
    assert "student_name" not in denied.text


def test_identity_access_request_rejects_client_scope_expansion() -> None:
    client, token, _ = build_client()
    response = client.post(
        "/api/v1/admin/identity-access-requests",
        headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "identity-request-2"},
        json={
            "user_reference_id": "user-1",
            "requested_fields": ["student_name"],
            "reason_fact": "事实理由",
            "valid_until": "2099-01-01T00:00:00Z",
            "capability": "super_admin",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
