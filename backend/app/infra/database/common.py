"""Repository contracts shared by CloudBase and local test implementations."""

from collections.abc import Mapping
from typing import Any, Protocol

from app.infra.database.atomic import UnitOfWork
from app.infra.database.query import DocumentPage as DocumentPage
from app.infra.database.query import JsonDocument as JsonDocument
from app.infra.logger.common import traced
from app.infra.serializer.error.database import RepositoryError as RepositoryError
from app.infra.serializer.error.database import RepositoryNotFound as RepositoryNotFound
from app.infra.serializer.error.database import RepositoryUnavailable as RepositoryUnavailable
from app.infra.serializer.error.database import (
    RepositoryVersionConflict as RepositoryVersionConflict,
)


class DocumentRepository(UnitOfWork, Protocol):
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
