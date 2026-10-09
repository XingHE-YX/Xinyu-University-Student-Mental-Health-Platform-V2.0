"""Admin task projection over the shared typed memory domain store."""

from contextlib import AbstractAsyncContextManager
from typing import Any

from app.infra.database.common import RepositoryNotFound
from app.infra.logger.common import traced
from app.models.v2.documents import WorkTaskDocument
from app.services.v2.repositories import DomainRepository


class MemoryAdminTaskRepository:
    def __init__(self, domain: DomainRepository) -> None:
        self.domain = domain

    def transaction(self) -> AbstractAsyncContextManager[None]:
        return self.domain.transaction()

    @traced
    async def list(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._project(item) for item in await self.domain.list_work_tasks())

    @traced
    async def get(self, task_id: str) -> dict[str, Any] | None:
        try:
            return self._project(await self.domain.get_work_task(task_id))
        except RepositoryNotFound:
            return None

    @traced
    async def create(self, task: dict[str, Any]) -> None:
        await self.domain.create_work_task(self._document(task))

    @traced
    async def save(self, task: dict[str, Any], *, expected_version: int) -> None:
        await self.domain.save_work_task(self._document(task), expected_version=expected_version)

    @staticmethod
    def _project(task: WorkTaskDocument) -> dict[str, Any]:
        values = task.model_dump(by_alias=True)
        values["task_id"] = values.pop("_id")
        return values

    @staticmethod
    def _document(task: dict[str, Any]) -> WorkTaskDocument:
        values = {key: value for key, value in task.items() if key in WorkTaskDocument.model_fields}
        values["_id"] = task["task_id"]
        values.setdefault(
            "source_type",
            {"content_review": "post", "identity_access": "identity_request"}.get(
                task["task_kind"], "support_task"
            ),
        )
        values.setdefault("source_id", task["task_id"])
        values.setdefault("available_capability", task["task_kind"])
        values.setdefault("object_version", task["version"])
        return WorkTaskDocument.model_validate(values)
