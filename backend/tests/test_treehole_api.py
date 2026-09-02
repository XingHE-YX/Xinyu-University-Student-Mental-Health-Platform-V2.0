from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from fastapi.testclient import TestClient

from app.domain.models import (
    AnonymousIdentityDocument,
    IdentityRecordDocument,
    TreeholePostDocument,
    UserAccountDocument,
)
from app.main import create_app
from app.repositories.domain_data_repository import InMemoryDomainDataRepository

from .test_assessment_service import configured_settings


def build_client() -> tuple[TestClient, InMemoryDomainDataRepository, str]:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    user = UserAccountDocument(
        _id="user-1",
        auth_subject_hash="student-subject-hash",
        status="active",
        base_consent_status="accepted",
        base_consent_version="base-v1",
        community_consent_status="accepted",
        community_consent_version="community-v1",
        identity_record_id="identity-1",
        anonymous_identity_id="anonymous-1",
        created_at=now,
        updated_at=now,
        version=3,
    )
    identity = IdentityRecordDocument(
        _id="identity-1",
        user_id="user-1",
        verification_status="verified",
        student_name_ciphertext="cipher-name",
        student_number_ciphertext="cipher-number",
        provider_reference_hash="provider-ref",
        verified_at=now,
        access_version=1,
        created_at=now,
        updated_at=now,
        version=1,
    )
    anonymous = AnonymousIdentityDocument(
        _id="anonymous-1",
        user_id="user-1",
        display_name="树洞同学ABC123",
        generation_version="anon-v1",
        status="active",
        created_at=now,
        updated_at=now,
        version=1,
    )
    repository = InMemoryDomainDataRepository(
        users=[user], identities=[identity], anonymous_identities=[anonymous]
    )
    app = create_app(configured_settings(), domain_repository=repository)
    token = app.state.auth_service.tokens.issue(
        "student", "user-1", app.state.auth_service.sessions
    ).access_token
    return TestClient(app), repository, token


def test_treehole_create_hides_unpublished_body_from_public_list_and_supports_owner_view() -> None:
    client, repository, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/treehole/posts",
        headers=headers,
        json={"body": "一段只想先放下的心事", "client_idempotency_key": "post-1"},
    )
    assert created.status_code == 200
    post_id = created.json()["data"]["post_id"]
    assert created.json()["data"]["display_projection"]["body_sanitized"] is None
    assert client.get("/api/v1/treehole/posts", headers=headers).json()["data"]["items"] == []
    assert client.get(f"/api/v1/treehole/posts/{post_id}", headers=headers).json()["data"]["mine"]
    assert repository.extra_collection("content_review_tasks")


def test_treehole_post_rejects_client_visibility_and_cross_user_mutation() -> None:
    client, _, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    tampered = client.post(
        "/api/v1/treehole/posts",
        headers=headers,
        json={
            "body": "内容",
            "client_idempotency_key": "post-2",
            "visibility_state": "published",
            "safety_state": "handled",
        },
    )
    assert tampered.status_code == 422
    assert tampered.json()["error"]["code"] == "VALIDATION_FAILED"


def test_treehole_create_requires_idempotency_header_for_withdraw_and_delete() -> None:
    client, _, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/treehole/posts",
        headers=headers,
        json={"body": "内容", "client_idempotency_key": "post-3"},
    )
    post_id = created.json()["data"]["post_id"]
    version = created.json()["data"]["object_version"]
    missing = client.post(
        f"/api/v1/treehole/posts/{post_id}/withdraw",
        headers=headers,
        json={"object_version": version},
    )
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "INVALID_REQUEST"


def test_treehole_confirmed_sort_prioritizes_protected_posts() -> None:
    client, repository, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime(2026, 9, 2, tzinfo=UTC)
    for index, state in enumerate(("published", "protected"), start=1):
        repository.create_treehole_post(
            TreeholePostDocument(
                _id=f"post-{index}",
                author_user_id="user-1",
                anonymous_identity_id="anonymous-1",
                display_name_snapshot="树洞同学ABC123",
                body_original_ciphertext="enc:v1:placeholder",
                body_sanitized=f"内容{index}",
                body_hash=f"hash-{index}",
                visibility_state=cast(
                    Literal[
                        "checking",
                        "published",
                        "protected",
                        "pending_confirmation",
                        "unpublished",
                        "safety_priority",
                        "deleted",
                    ],
                    state,
                ),
                review_state="decided",
                safety_state="not_triggered",
                community_consent_version="community-v1",
                created_at=now,
                updated_at=now,
                version=1,
            )
        )

    response = client.get("/api/v1/treehole/posts?sort=confirmed", headers=headers)

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["visibility_state"] == "protected"
