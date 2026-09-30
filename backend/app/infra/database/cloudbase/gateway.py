"""Compatibility facade over the current CloudBase NoSQL REST store."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Any

import httpx

from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.common import (
    DocumentPage,
    JsonDocument,
    RepositoryError,
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.database.query import decode_cursor, encode_cursor
from app.infra.logger.common import traced

__all__ = [
    "CloudBaseGateway",
    "RepositoryError",
    "RepositoryNotFound",
    "RepositoryUnavailable",
    "RepositoryVersionConflict",
]


class CloudBaseGateway:
    """Retain the original async document interface for existing callers."""

    def __init__(
        self,
        *,
        environment_id: str,
        api_key: str,
        base_url: str | None = None,
        session_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 8.0,
    ) -> None:
        if session_token:
            raise ValueError("session tokens are not supported by the service API key facade")
        self.store = CloudBaseStore(
            environment_id,
            api_key,
            base_url=base_url,
            transport=transport,
            timeout=timeout,
        )

    def transaction(self) -> AbstractAsyncContextManager[None]:
        return self.store.transaction()

    @traced
    async def aclose(self) -> None:
        await self.store.aclose()

    @traced
    async def get(self, collection: str, document_id: str) -> JsonDocument:
        return await self.store.get(collection, document_id)

    @traced
    async def insert(self, collection: str, document: Mapping[str, Any]) -> None:
        await self.store.insert(collection, document)

    @traced
    async def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DocumentPage:
        page_size = max(1, min(limit, 100))
        offset = decode_cursor(cursor)
        documents = await self.store.query(
            collection,
            where,
            limit=page_size,
            offset=offset,
        )
        next_cursor = (
            encode_cursor(offset + len(documents)) if len(documents) >= page_size else None
        )
        return DocumentPage(tuple(documents), next_cursor)

    @traced
    async def conditional_update(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
        updates: Mapping[str, Any],
    ) -> JsonDocument:
        if "_id" in updates or "version" in updates:
            raise ValueError("_id and version are managed by the repository")
        current = await self.store.get(collection, document_id)
        if current.get("version") != expected_version:
            raise RepositoryVersionConflict(_version(current))
        updated = {
            **current,
            **dict(updates),
            "updated_at": datetime.now(UTC),
            "version": expected_version + 1,
        }
        await self.store.replace(collection, updated, expected_version)
        return updated

    @traced
    async def logical_delete(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
    ) -> JsonDocument:
        return await self.conditional_update(
            collection,
            document_id,
            expected_version=expected_version,
            updates={"is_deleted": True, "deleted_at": datetime.now(UTC)},
        )


@traced
def _version(document: Mapping[str, Any]) -> int | None:
    value = document.get("version")
    return value if isinstance(value, int) else None
