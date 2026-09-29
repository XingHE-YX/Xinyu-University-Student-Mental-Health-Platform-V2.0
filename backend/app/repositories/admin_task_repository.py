"""Persistence boundary for the admin workbench's safe task projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from app.repositories.cloudbase_store import CloudBaseStore
from app.repositories.protocols import RepositoryNotFound


class AdminTaskRepository(Protocol):
    def list(self) -> tuple[dict[str, Any], ...]: ...

    def get(self, task_id: str) -> dict[str, Any] | None: ...

    def create(self, task: dict[str, Any]) -> None: ...

    def save(self, task: dict[str, Any], *, expected_version: int) -> None: ...


class CloudBaseAdminTaskRepository:
    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    def list(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            task
            for row in self.store.all("work_tasks")
            if not (task := self._from_document(row)).get("is_deleted", False)
        )

    def get(self, task_id: str) -> dict[str, Any] | None:
        try:
            task = self._from_document(self.store.get("work_tasks", task_id))
        except RepositoryNotFound:
            return None
        return None if task.get("is_deleted", False) else task

    def create(self, task: dict[str, Any]) -> None:
        self.store.insert("work_tasks", self._to_document(task))

    def save(self, task: dict[str, Any], *, expected_version: int) -> None:
        self.store.replace("work_tasks", self._to_document(task), expected_version)

    @staticmethod
    def _from_document(document: dict[str, Any]) -> dict[str, Any]:
        task = deepcopy(document)
        task["task_id"] = str(task.pop("_id"))
        task.setdefault("facts", [])
        task.setdefault("records", [])
        task.setdefault("redacted_content", None)
        task.setdefault("is_deleted", False)
        return task

    @staticmethod
    def _to_document(task: dict[str, Any]) -> dict[str, Any]:
        document = deepcopy(task)
        task_id = str(document.pop("task_id"))
        task_kind = str(document["task_kind"])
        source_types = {
            "content_review": "post",
            "safety_support": "support_task",
            "identity_access": "identity_request",
            "followup": "support_task",
        }
        document.setdefault("source_type", source_types[task_kind])
        document.setdefault("source_id", task_id)
        document.setdefault("available_capability", task_kind)
        document.setdefault("object_version", int(document["version"]))
        document.setdefault("last_action", None)
        return {"_id": task_id, **document}
