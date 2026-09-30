from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Literal, cast

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.infra.ai.client.abstract import AIClient
from app.infra.ai.client.types import AIRequest, AIResponse
from app.infra.database.memory.domain import InMemoryDomainDataRepository
from app.main import create_app
from app.models.v2.documents import (
    AnonymousIdentityDocument,
    IdentityRecordDocument,
    TreeholePostDocument,
    UserAccountDocument,
)
from app.services.v2.ai_assist_service import AiAssistService
from tests.password_fixtures import ADMIN_HASH

from .test_assessment_service import configured_settings


def build_client() -> tuple[TestClient, InMemoryDomainDataRepository, str]:
    class StubTreeholeAiClient(AIClient):
        async def complete(self, request: AIRequest) -> AIResponse:
            payload = json.loads(request.messages[-1].content)
            task_type = payload["task_type"]
            source = str(payload["sanitized_text"])
            return AIResponse(
                content=json.dumps(
                    {
                        "task_type": task_type,
                        "status": "ok",
                        "content_safety": "clear",
                        "wellbeing_signal": "none",
                        "privacy_signal": "clear",
                        "community_issue": ["none"],
                        "evidence_spans": [source[:8]],
                        "recommended_route": "allow",
                        "review_note": "已完成受限辅助检查，最终状态仍由规则和人工决定。",
                    },
                    ensure_ascii=False,
                ),
                model="fake-model",
            )

        async def aclose(self) -> None:
            pass

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
    settings = configured_settings().model_copy(
        update={"admin_password_hash": SecretStr(ADMIN_HASH)}
    )
    app = create_app(
        settings,
        domain_repository=repository,
        ai_assist_service=AiAssistService(
            settings,
            client=StubTreeholeAiClient(),
            repository=repository,
        ),
    )
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
    assert created.json()["data"]["review_state"] == "automated_checked"
    assert client.get("/api/v1/treehole/posts", headers=headers).json()["data"]["items"] == []
    assert client.get(f"/api/v1/treehole/posts/{post_id}", headers=headers).json()["data"]["mine"]
    assert repository.extra_collection("content_review_tasks")
    work_tasks = repository.extra_collection("work_tasks")
    assert len(work_tasks) == 1
    assert work_tasks[0]["source_type"] == "post"
    assert work_tasks[0]["redacted_content"] == "一段只想先放下的心事"
    assert work_tasks[0]["records"][0]["label"] == "DeepSeek 建议"
    assert len(repository.extra_collection("ai_assist_snapshots")) == 1

    login = client.post(
        "/api/v1/admin/auth/login",
        json={"login_name": "心理健康中心工作人员", "password": "correct-password"},
    )
    admin_headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    task_id = f"content_review_{post_id}"
    detail = client.get(f"/api/v1/admin/tasks/{task_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["redacted_content"] == "一段只想先放下的心事"
    assert "publish" in detail.json()["data"]["allowed_actions"]
    claimed = client.post(
        f"/api/v1/admin/tasks/{task_id}/claim",
        headers={**admin_headers, "Idempotency-Key": "claim-live-post"},
        json={"object_version": detail.json()["data"]["object_version"]},
    )
    decided = client.post(
        f"/api/v1/admin/tasks/{task_id}/decision",
        headers={**admin_headers, "Idempotency-Key": "publish-live-post"},
        json={
            "object_version": claimed.json()["data"]["new_object_version"],
            "action": "publish",
            "internal_reason": "内容已完成脱敏与人工确认",
        },
    )

    assert decided.status_code == 200
    published = repository.get_treehole_post(post_id)
    assert published.visibility_state == "published"
    assert published.review_state == "decided"
    public_items = client.get("/api/v1/treehole/posts", headers=headers).json()["data"]["items"]
    assert public_items[0]["body_sanitized"] == "一段只想先放下的心事"


def test_treehole_response_persists_ai_snapshot_without_auto_publishing() -> None:
    client, repository, token = build_client()
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/treehole/posts",
        headers=headers,
        json={"body": "一段普通的演示内容", "client_idempotency_key": "post-response"},
    )
    post = repository.get_treehole_post(created.json()["data"]["post_id"])
    published = repository.save_treehole_post(
        post.model_copy(update={"visibility_state": "published", "review_state": "decided"}),
        expected_version=post.version,
    )

    response = client.post(
        f"/api/v1/treehole/posts/{published.document_id}/responses",
        headers=headers,
        json={
            "body": "谢谢你愿意分享这些感受",
            "object_version": published.version,
            "client_idempotency_key": "response-ai",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"]["state"] == "checking"
    stored = repository.get_treehole_response(response.json()["data"]["response_id"])
    assert stored.ai_assist_snapshot_id is not None
    assert len(repository.extra_collection("ai_assist_snapshots")) == 2
    work_tasks = repository.extra_collection("work_tasks")
    assert len(work_tasks) == 2
    assert work_tasks[-1]["source_type"] == "response"


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
