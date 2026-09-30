"""Persistence boundary for the admin workbench's safe task projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol

from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.common import RepositoryNotFound
from app.infra.logger.common import traced


class AdminTaskRepository(Protocol):
    @traced
    def list(self) -> tuple[dict[str, Any], ...]: ...

    @traced
    def get(self, task_id: str) -> dict[str, Any] | None: ...

    @traced
    def create(self, task: dict[str, Any]) -> None: ...

    @traced
    def save(self, task: dict[str, Any], *, expected_version: int) -> None: ...


class CloudBaseAdminTaskRepository:
    def __init__(self, store: CloudBaseStore) -> None:
        self.store = store

    @traced
    def list(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            task
            for row in self.store.all("work_tasks")
            if not (task := self._from_document(row)).get("is_deleted", False)
        )

    @traced
    def get(self, task_id: str) -> dict[str, Any] | None:
        try:
            task = self._from_document(self.store.get("work_tasks", task_id))
        except RepositoryNotFound:
            return None
        return None if task.get("is_deleted", False) else task

    @traced
    def create(self, task: dict[str, Any]) -> None:
        self.store.insert("work_tasks", self._to_document(task))

    @traced
    def save(self, task: dict[str, Any], *, expected_version: int) -> None:
        self.store.replace("work_tasks", self._to_document(task), expected_version)

    @staticmethod
    @traced
    def _from_document(document: dict[str, Any]) -> dict[str, Any]:
        task = deepcopy(document)
        task["task_id"] = str(task.pop("_id"))
        task.setdefault("facts", [])
        task.setdefault("records", [])
        task.setdefault("redacted_content", None)
        task.setdefault("is_deleted", False)
        return task

    @staticmethod
    @traced
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
