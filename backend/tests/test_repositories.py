import json

import httpx
import pytest

from app.repositories.cloudbase_gateway import (
    CloudBaseGateway,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.repositories.in_memory import InMemoryDocumentRepository


def test_in_memory_repository_supports_cursor_query_versioned_update_and_logical_delete() -> None:
    repository = InMemoryDocumentRepository(
        {
            "treehole_posts": [
                {"_id": "post-1", "state": "published", "version": 1},
                {"_id": "post-2", "state": "published", "version": 1},
            ]
        }
    )

    first_page = repository.query("treehole_posts", {"state": "published"}, limit=1)
    assert [item["_id"] for item in first_page.items] == ["post-1"]
    assert first_page.next_cursor is not None
    second_page = repository.query(
        "treehole_posts",
        {"state": "published"},
        cursor=first_page.next_cursor,
        limit=1,
    )
    assert [item["_id"] for item in second_page.items] == ["post-2"]
    assert second_page.next_cursor is None

    updated = repository.conditional_update(
        "treehole_posts",
        "post-1",
        expected_version=1,
        updates={"state": "protected"},
    )
    assert updated["state"] == "protected"
    assert updated["version"] == 2

    with pytest.raises(RepositoryVersionConflict) as error:
        repository.conditional_update(
            "treehole_posts",
            "post-1",
            expected_version=1,
            updates={"state": "deleted"},
        )
    assert error.value.current_version == 2

    deleted = repository.logical_delete("treehole_posts", "post-1", expected_version=2)
    assert deleted["is_deleted"] is True


@pytest.mark.asyncio
async def test_cloudbase_gateway_maps_document_api_and_dependency_failures() -> None:
    requests: list[httpx.Request] = []

    def success_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"offset": 0, "limit": 20, "list": [{"_id": "post-1"}]},
        )

    gateway = CloudBaseGateway(
        base_url="https://cloudbase.example.test",
        environment_id="demo-env",
        api_key="cloudbase-secret",
        transport=httpx.MockTransport(success_handler),
    )
    page = await gateway.query("treehole_posts", {"state": "published"}, cursor=None, limit=20)

    assert page.items == ({"_id": "post-1"},)
    assert page.next_cursor is None
    assert requests[0].url.path == "/collections/treehole_posts/documents"
    assert requests[0].url.params["limit"] == "20"
    assert requests[0].headers["authorization"] == "Bearer cloudbase-secret"
    assert json.loads(requests[0].url.params["query"]) == {"state": "published"}

    def failure_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "database offline"})

    unavailable_gateway = CloudBaseGateway(
        base_url="https://cloudbase.example.test",
        environment_id="demo-env",
        api_key="cloudbase-secret",
        transport=httpx.MockTransport(failure_handler),
    )
    with pytest.raises(RepositoryUnavailable):
        await unavailable_gateway.query("treehole_posts", {}, cursor=None, limit=20)


@pytest.mark.asyncio
async def test_cloudbase_gateway_rejects_a_success_http_status_with_an_api_error_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "DATABASE_ERROR", "message": "internal"})

    gateway = CloudBaseGateway(
        base_url="https://cloudbase.example.test",
        environment_id="demo-env",
        api_key="cloudbase-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RepositoryUnavailable):
        await gateway.query("treehole_posts", {}, cursor=None, limit=20)


@pytest.mark.asyncio
async def test_cloudbase_gateway_uses_version_conditions_for_update_and_logical_delete() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "PATCH":
            return httpx.Response(200, json={"matched": 1, "updated": 1, "upsert_id": ""})
        requested_version = (
            1 if len([item for item in requests if item.method == "PATCH"]) == 0 else 2
        )
        return httpx.Response(
            200,
            json={
                "offset": 0,
                "limit": 1,
                "list": [{"_id": "post-1", "version": requested_version}],
            },
        )

    gateway = CloudBaseGateway(
        base_url="https://cloudbase.example.test",
        environment_id="demo-env",
        api_key="cloudbase-secret",
        transport=httpx.MockTransport(handler),
    )
    updated = await gateway.conditional_update(
        "treehole_posts",
        "post-1",
        expected_version=1,
        updates={"state": "protected"},
    )
    deleted = await gateway.logical_delete("treehole_posts", "post-1", expected_version=2)

    assert updated["version"] == 2
    assert deleted["version"] == 3
    update_request = next(item for item in requests if item.method == "PATCH")
    update_body = json.loads(update_request.content)
    assert update_body["query"] == {"_id": "post-1", "version": 1}
    assert update_body["data"]["$set"]["state"] == "protected"
    assert update_body["data"]["$set"]["version"] == 2


@pytest.mark.asyncio
async def test_cloudbase_gateway_returns_current_version_when_update_matches_nothing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"offset": 0, "limit": 1, "list": [{"_id": "post-1", "version": 3}]},
        )

    gateway = CloudBaseGateway(
        base_url="https://cloudbase.example.test",
        environment_id="demo-env",
        api_key="cloudbase-secret",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RepositoryVersionConflict) as error:
        await gateway.conditional_update(
            "treehole_posts",
            "post-1",
            expected_version=1,
            updates={"state": "protected"},
        )
    assert error.value.current_version == 3
