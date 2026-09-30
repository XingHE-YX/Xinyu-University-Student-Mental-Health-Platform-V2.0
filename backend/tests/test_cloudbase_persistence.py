import inspect
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from app.infra.config.settings import Settings
from app.infra.database.cloudbase.client import CloudBaseStore, decode_ejson, encode_ejson
from app.infra.database.cloudbase.domain import CloudBaseDomainDataRepository
from app.infra.database.cloudbase.security import (
    CloudBaseAuditRepository,
    CloudBaseIdempotencyRepository,
    CloudBaseSessionRepository,
)
from app.infra.database.cloudbase.tasks import CloudBaseAdminTaskRepository
from app.infra.database.common import RepositoryUnavailable, RepositoryVersionConflict
from app.infra.database.memory.domain import InMemoryDomainDataRepository
from app.infra.database.memory.session import AuthSessionRecord
from app.infra.logger.audit import AuditWriter
from app.infra.serializer.error.common import ApiException
from app.main import create_app
from app.models.v2.documents import UserAccountDocument
from app.services.v2.admin_workbench_service import AdminWorkbenchService
from app.services.v2.idempotency_service import IdempotencyService


def cloudbase_settings() -> Settings:
    return Settings.from_environment(
        {
            "PERSISTENCE_BACKEND": "cloudbase",
            "WECHAT_APPID": "wx-demo",
            "WECHAT_APPSECRET": "wechat-secret",
            "CLOUDBASE_ENV_ID": "demo-env",
            "CLOUDBASE_ENV_ID_DEMO": "demo-env",
            "CLOUDBASE_API_KEY": "cloudbase-secret",
            "ADMIN_PASSWORD_HASH": "pbkdf2_sha256$1$salt$digest",
            "ADMIN_SESSION_SECRET": "session-secret",
            "SCHOOL_IDENTITY_PROVIDER_URL": "https://identity.example.test",
            "SUPPORT_RESOURCE_VERSION": "support-v1",
            "DEMO_MODE": "true",
        }
    )


def test_ejson_round_trip_keeps_utc_datetimes_and_numbers() -> None:
    moment = datetime(2026, 9, 17, 10, 30, tzinfo=UTC)
    encoded = encode_ejson({"created_at": moment, "items": [1, True]})
    decoded = decode_ejson(
        {
            **encoded,
            "version": {"$numberInt": "2"},
            "total": {"$numberLong": "9"},
        }
    )

    assert decoded == {"created_at": moment, "items": [1, True], "version": 2, "total": 9}


def test_store_uses_current_gateway_bearer_auth_and_commits_transactions() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/transactions"):
            return httpx.Response(201, json={"transactionId": "txn-1"})
        if request.url.path.endswith("/transactions/txn-1/commit"):
            return httpx.Response(204)
        if request.method == "POST" and request.url.path.endswith("/collections/users/documents"):
            return httpx.Response(201, json={"insertedIds": ["user-1"]})
        if request.method == "GET" and request.url.path.endswith("/collections/users/documents"):
            return httpx.Response(
                200,
                json={
                    "offset": 0,
                    "limit": 100,
                    "list": [{"_id": "user-1", "version": {"$numberInt": "1"}}],
                },
            )
        raise AssertionError(f"unexpected request {request.method} {request.url.path}")

    store = CloudBaseStore("demo-env", "secret", transport=httpx.MockTransport(handler))
    with store.transaction():
        store.insert(
            "users",
            {"_id": "user-1", "created_at": datetime(2026, 9, 17, tzinfo=UTC)},
        )
        assert store.get("users", "user-1")["version"] == 1

    assert all(item.headers["authorization"] == "Bearer secret" for item in requests)
    insert_body = json.loads(requests[1].content)
    assert insert_body["transactionId"] == "txn-1"
    assert insert_body["data"][0]["created_at"] == {"$date": {"$numberLong": "1789603200000"}}
    assert requests[2].url.params["transactionId"] == "txn-1"
    assert requests[-1].url.path.endswith("/transactions/txn-1/commit")


def test_store_rolls_back_and_never_exposes_remote_error_or_key() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/transactions"):
            return httpx.Response(201, json={"transactionId": "txn-private"})
        if request.url.path.endswith("/rollback"):
            return httpx.Response(204)
        return httpx.Response(500, json={"code": "SYS_ERR", "message": "secret remote detail"})

    store = CloudBaseStore("demo-env", "do-not-print-key", transport=httpx.MockTransport(handler))
    with pytest.raises(RepositoryUnavailable) as error:
        with store.transaction():
            store.insert("users", {"_id": "user-1"})

    assert "secret remote detail" not in str(error.value)
    assert "do-not-print-key" not in str(error.value)
    assert requests[-1].url.path.endswith("/transactions/txn-private/rollback")


class MemoryStore:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}

    @contextmanager
    def transaction(self):  # type: ignore[no-untyped-def]
        yield

    def insert(self, collection: str, document: dict[str, Any]) -> None:
        items = self.collections.setdefault(collection, {})
        if document["_id"] in items:
            raise RepositoryVersionConflict(items[document["_id"]].get("version"))
        items[str(document["_id"])] = dict(document)

    def get(self, collection: str, document_id: str) -> dict[str, Any]:
        try:
            return dict(self.collections[collection][document_id])
        except KeyError:
            from app.infra.database.common import RepositoryNotFound

            raise RepositoryNotFound("not found") from None

    def query(
        self,
        collection: str,
        where: dict[str, Any] | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        def matches(document: dict[str, Any]) -> bool:
            for key, expected in (where or {}).items():
                if isinstance(expected, dict) and "$in" in expected:
                    if document.get(key) not in expected["$in"]:
                        return False
                elif document.get(key) != expected:
                    return False
            return True

        items = sorted(self.collections.get(collection, {}).values(), key=lambda item: item["_id"])
        return [dict(item) for item in items if matches(item)][offset : offset + limit]

    def all(self, collection: str, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.query(collection, where, limit=10_000)

    def replace(self, collection: str, document: dict[str, Any], expected_version: int) -> None:
        current = self.get(collection, str(document["_id"]))
        if current.get("version") != expected_version:
            raise RepositoryVersionConflict(current.get("version"))
        self.collections[collection][str(document["_id"])] = dict(document)


def test_cloud_domain_repository_overrides_every_public_in_memory_operation() -> None:
    base_methods = {
        name
        for name, method in inspect.getmembers(
            InMemoryDomainDataRepository, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    assert base_methods <= CloudBaseDomainDataRepository.__dict__.keys()


def test_domain_session_idempotency_and_audit_persist_across_instances() -> None:
    store = MemoryStore()
    domain = CloudBaseDomainDataRepository(store)  # type: ignore[arg-type]
    now = datetime(2026, 9, 17, tzinfo=UTC)
    user = UserAccountDocument(
        _id="user-1",
        auth_subject_hash="hash-1",
        status="active",
        base_consent_status="not_accepted",
        community_consent_status="not_accepted",
        created_at=now,
        updated_at=now,
        version=1,
    )
    domain.create_user(user)
    second_domain = CloudBaseDomainDataRepository(store)  # type: ignore[arg-type]
    assert second_domain.get_user_by_auth_subject_hash("hash-1") == user
    saved = second_domain.save_user(
        user.model_copy(update={"base_consent_status": "accepted"}), expected_version=1
    )
    assert saved.version == 2

    sessions = CloudBaseSessionRepository(store)  # type: ignore[arg-type]
    session = AuthSessionRecord(
        session_id="sess-1",
        subject_type="student",
        subject_id="user-1",
        capability=None,
        access_token_hash="access-hash",
        refresh_token_hash="refresh-hash",
        access_expires_at=now + timedelta(minutes=15),
        refresh_expires_at=now + timedelta(days=30),
        status="active",
        created_at=now,
        updated_at=now,
    )
    sessions.save(session)
    assert CloudBaseSessionRepository(store).get_by_access_token_hash("access-hash") == session  # type: ignore[arg-type]

    idempotency = IdempotencyService(CloudBaseIdempotencyRepository(store))  # type: ignore[arg-type]
    reserved = idempotency.begin(
        "student", "user-1", "/moods/today", "mood-1", {"mood": "calm"}, now=now
    )
    idempotency.complete(reserved, status_code=200, response_digest="saved", now=now)
    replayed = IdempotencyService(CloudBaseIdempotencyRepository(store)).begin(  # type: ignore[arg-type]
        "student", "user-1", "/moods/today", "mood-1", {"mood": "calm"}, now=now
    )
    assert replayed.replayed is True
    assert replayed.record.response_status == 200

    writer = AuditWriter(CloudBaseAuditRepository(store), environment_id="demo-env")  # type: ignore[arg-type]
    writer.write(
        request_id="req-1",
        actor_type="student",
        actor_id="user-1",
        capability=None,
        action="mood_saved",
        resource_type="mood",
        resource_id="mood-1",
        data_scope="object_version",
        outcome="success",
        reason_code=None,
        occurred_at=now,
        facts={"object_version": 1, "body": "not stored"},
    )
    events = CloudBaseAuditRepository(store).list()  # type: ignore[arg-type]
    assert events[0].details == {"object_version": 1}
    assert "not stored" not in str(store.collections["audit_events"])


def test_application_selects_cloudbase_only_when_explicitly_configured() -> None:
    cloud_settings = cloudbase_settings()
    assert cloud_settings.cloudbase_persistence_ready is True
    cloud_app = create_app(
        cloud_settings,
        admin_workbench_service=AdminWorkbenchService(cloud_settings),
    )
    assert cloud_app.state.persistence_backend == "cloudbase"
    assert isinstance(cloud_app.state.auth_service.sessions, CloudBaseSessionRepository)
    assert isinstance(cloud_app.state.assessment_service.repository, CloudBaseDomainDataRepository)

    memory_values = {
        key: value
        for key, value in {
            "PERSISTENCE_BACKEND": "memory",
            "CLOUDBASE_ENV_ID": "demo-env",
            "CLOUDBASE_ENV_ID_DEMO": "demo-env",
            "CLOUDBASE_API_KEY": "cloudbase-secret",
            "DEMO_MODE": "true",
        }.items()
    }
    memory_app = create_app(Settings.from_environment(memory_values))
    assert memory_app.state.persistence_backend == "memory"


def test_admin_tasks_survive_a_new_service_instance_and_keep_version_checks() -> None:
    store = MemoryStore()
    settings = cloudbase_settings()
    tasks = CloudBaseAdminTaskRepository(store)  # type: ignore[arg-type]
    first = AdminWorkbenchService(settings, task_repository=tasks)

    page = first.list_tasks("needs_action", admin_id="admin-1", cursor=None, limit=20)
    task = next(item for item in page.items if item.task_id == "task-demo-content-01")
    result = first.claim(
        task.task_id,
        object_version=task.object_version,
        admin_id="admin-1",
        request_id="req-claim",
        idempotency_key="claim-1",
    )

    second = AdminWorkbenchService(settings, task_repository=tasks)
    restored = second.get_task(task.task_id, admin_id="admin-1")
    assert restored.state == "claimed"
    assert restored.object_version == result.new_object_version == 2
    with pytest.raises(ApiException) as error:
        second.release(
            task.task_id,
            object_version=1,
            admin_id="admin-1",
            request_id="req-release",
            idempotency_key="release-1",
        )
    assert getattr(error.value, "code", None) == "VERSION_CONFLICT"
