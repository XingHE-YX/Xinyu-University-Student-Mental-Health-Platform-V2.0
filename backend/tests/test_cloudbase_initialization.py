from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from app.repositories.collection_registry import COLLECTIONS, build_index_projection
from app.repositories.protocols import RepositoryVersionConflict
from scripts.initialize_cloudbase import (
    demo_seed_collections,
    initialize_demo,
    read_environment,
    refresh_demo_support_resources,
)


class ProvisioningStore:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict[str, Any]]] = {}
        self.commands_run: list[list[dict[str, Any]]] = []

    def create_collection(self, collection: str) -> None:
        if collection in self.collections:
            raise RepositoryVersionConflict(None)
        self.collections[collection] = {}

    def commands(self, commands: list[dict[str, Any]]) -> list[Any]:
        self.commands_run.append(commands)
        return [[{"ok": 1}]]

    def query(
        self,
        collection: str,
        where: dict[str, Any] | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        del offset
        return [
            dict(item)
            for item in self.collections[collection].values()
            if all(item.get(key) == value for key, value in (where or {}).items())
        ][:limit]

    def insert(self, collection: str, document: dict[str, Any]) -> None:
        self.collections[collection][str(document["_id"])] = dict(document)

    def replace(self, collection: str, document: dict[str, Any], expected_version: int) -> None:
        current = self.collections[collection][str(document["_id"])]
        if current.get("version") != expected_version:
            raise RepositoryVersionConflict(current.get("version"))
        self.collections[collection][str(document["_id"])] = dict(document)

    @contextmanager
    def transaction(self):  # type: ignore[no-untyped-def]
        yield


def test_environment_reader_does_not_require_or_echo_secrets(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text("# private\nDEMO_MODE=true\nCLOUDBASE_API_KEY=secret=value\n")

    assert read_environment(file) == {
        "DEMO_MODE": "true",
        "CLOUDBASE_API_KEY": "secret=value",
    }


def test_environment_reader_rejects_invalid_lines(tmp_path: Path) -> None:
    file = tmp_path / ".env"
    file.write_text("not-an-entry\n")

    with pytest.raises(ValueError, match="line 1"):
        read_environment(file)


def test_initializer_is_repeatable_and_applies_every_collection_and_index() -> None:
    store = ProvisioningStore()
    first = initialize_demo(store)  # type: ignore[arg-type]
    second = initialize_demo(store)  # type: ignore[arg-type]
    expected_documents = sum(len(items) for items in demo_seed_collections().values())
    expected_indexes = sum(len(items) for items in build_index_projection().values())

    assert set(store.collections) == set(COLLECTIONS)
    assert first.collections_created == len(COLLECTIONS)
    assert first.indexes_applied == expected_indexes
    assert first.documents_inserted == expected_documents
    assert second.collections_existing == len(COLLECTIONS)
    assert second.documents_existing == expected_documents
    assert second.documents_inserted == 0
    assert second.support_resources_refreshed == 0
    assert sum(len(group[0]["indexes"]) for group in store.commands_run) == 2 * expected_indexes


def test_support_resource_refresh_is_scoped_versioned_and_repeatable() -> None:
    store = ProvisioningStore()
    initialize_demo(store)  # type: ignore[arg-type]
    resources = store.collections["support_resources"]
    resources["support-demo-001"]["title"] = "旧演示标题"
    resources["support-demo-002"]["action_target"] = "https://example.invalid"
    resources["support-demo-003"]["availability_text"] = "旧演示说明"

    assert refresh_demo_support_resources(store) == 3  # type: ignore[arg-type]
    assert refresh_demo_support_resources(store) == 0  # type: ignore[arg-type]
    assert {item["version"] for item in resources.values()} == {2}
    assert all(item["action_target"] is None for item in resources.values())
    assert all(
        item["availability_text"] == "待学校授权，暂无真实联系方式" for item in resources.values()
    )
