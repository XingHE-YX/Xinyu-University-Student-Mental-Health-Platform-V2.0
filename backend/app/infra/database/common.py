"""Repository contracts shared by CloudBase and local test implementations."""

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from app.infra.logger.common import traced
from app.infra.serializer.error.database import RepositoryError as RepositoryError
from app.infra.serializer.error.database import RepositoryNotFound as RepositoryNotFound
from app.infra.serializer.error.database import RepositoryUnavailable as RepositoryUnavailable
from app.infra.serializer.error.database import (
    RepositoryVersionConflict as RepositoryVersionConflict,
)

JsonDocument = dict[str, Any]


@dataclass(frozen=True, slots=True)
class DocumentPage:
    items: tuple[JsonDocument, ...]
    next_cursor: str | None


class DocumentRepository(Protocol):
    def transaction(self) -> AbstractAsyncContextManager[None]: ...

    async def get(self, collection: str, document_id: str) -> JsonDocument: ...

    async def insert(self, collection: str, document: Mapping[str, Any]) -> None: ...

    async def aclose(self) -> None: ...

    @traced
    async def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DocumentPage: ...

    @traced
    async def conditional_update(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
        updates: Mapping[str, Any],
    ) -> JsonDocument: ...

    @traced
    async def logical_delete(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
    ) -> JsonDocument: ...
