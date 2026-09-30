"""Small in-memory repository used by unit tests and local development."""

import base64
import binascii
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.infra.database.common import (
    DocumentPage,
    JsonDocument,
    RepositoryNotFound,
    RepositoryVersionConflict,
)
from app.infra.database.memory.transaction import MemoryUnitOfWork
from app.infra.logger.common import traced


class InMemoryDocumentRepository:
    def __init__(self, collections: Mapping[str, list[Mapping[str, Any]]] | None = None) -> None:
        self._lock = MemoryUnitOfWork()
        self._lock.register(self)
        self._collections: dict[str, dict[str, JsonDocument]] = {}
        for collection, documents in (collections or {}).items():
            self._collections[collection] = {
                str(document["_id"]): deepcopy(dict(document)) for document in documents
            }

    def transaction(self) -> AbstractAsyncContextManager[None]:
        return self._lock.transaction()

    @traced
    async def aclose(self) -> None:
        pass

    @traced
    async def get(self, collection: str, document_id: str) -> JsonDocument:
        async with self._lock:
            return deepcopy(self._get(collection, document_id))

    @traced
    async def insert(self, collection: str, document: Mapping[str, Any]) -> None:
        async with self._lock:
            items = self._collections.setdefault(collection, {})
            document_id = str(document["_id"])
            if document_id in items:
                raise RepositoryVersionConflict(int(items[document_id].get("version", 1)))
            items[document_id] = deepcopy(dict(document))

    @traced
    async def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DocumentPage:
        async with self._lock:
            documents = list(self._collections.get(collection, {}).values())
            filters = where or {}
            matched = [
                document
                for document in documents
                if not document.get("is_deleted", False)
                and all(document.get(key) == value for key, value in filters.items())
            ]
            matched.sort(key=lambda document: str(document.get("_id", "")))
            offset = self._decode_cursor(cursor)
            page_size = max(1, min(limit, 100))
            page = matched[offset : offset + page_size]
            next_offset = offset + page_size
            next_cursor = self._encode_cursor(next_offset) if next_offset < len(matched) else None
            return DocumentPage(tuple(deepcopy(item) for item in page), next_cursor)

    @traced
    async def conditional_update(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
        updates: Mapping[str, Any],
    ) -> JsonDocument:
        async with self._lock:
            document = self._get(collection, document_id)
            current_version = int(document.get("version", 1))
            if current_version != expected_version:
                raise RepositoryVersionConflict(current_version)
            if "_id" in updates or "version" in updates:
                raise ValueError("_id and version are managed by the repository")
            document.update(deepcopy(dict(updates)))
            document["version"] = current_version + 1
            document["updated_at"] = datetime.now(UTC).isoformat()
            return deepcopy(document)

    @traced
    async def logical_delete(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
    ) -> JsonDocument:
        async with self._lock:
            document = self._get(collection, document_id)
            current_version = int(document.get("version", 1))
            if current_version != expected_version:
                raise RepositoryVersionConflict(current_version)
            if not document.get("is_deleted", False):
                document["is_deleted"] = True
                document["deleted_at"] = datetime.now(UTC).isoformat()
                document["version"] = current_version + 1
                document["updated_at"] = document["deleted_at"]
            return deepcopy(document)

    @traced
    def _get(self, collection: str, document_id: str) -> JsonDocument:
        document = self._collections.get(collection, {}).get(document_id)
        if document is None:
            raise RepositoryNotFound("document not found")
        return document

    @staticmethod
    @traced
    def _encode_cursor(offset: int) -> str:
        return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")

    @staticmethod
    @traced
    def _decode_cursor(cursor: str | None) -> int:
        if not cursor:
            return 0
        try:
            value = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
            offset = int(value)
        except (ValueError, UnicodeDecodeError, binascii.Error) as error:
            raise ValueError("invalid cursor") from error
        if offset < 0:
            raise ValueError("invalid cursor")
        return offset
