"""Server-only NoSQL HTTP API with native transactions and strict EJSON decoding."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from contextvars import ContextVar
from typing import Any

import httpx

from app.infra.config.types import DatabaseConfig
from app.infra.database.cloudbase.codec import decode_ejson as decode_ejson
from app.infra.database.cloudbase.codec import encode_ejson as encode_ejson
from app.infra.database.cloudbase.transaction import transaction
from app.infra.database.common import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.logger.common import traced


class CloudBaseStore:
    """Each instance owns a connection pool; transaction IDs are request-context local."""

    def __init__(
        self,
        environment_id: str,
        api_key: str,
        *,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 8.0,
        config: DatabaseConfig | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9-]+", environment_id) or not api_key.strip():
            raise ValueError("CloudBase credentials are not configured")
        self.environment_id = environment_id
        self.base_url = (
            base_url
            or (
                f"https://{environment_id}.api.tcloudbasegateway.com"
                "/v1/database/instances/(default)/databases/(default)"
            )
        ).rstrip("/")
        self.config = config or DatabaseConfig(timeout_seconds=timeout)
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=self.config.timeout_seconds,
            limits=httpx.Limits(
                max_connections=self.config.max_connections,
                max_keepalive_connections=self.config.max_keepalive_connections,
            ),
            transport=transport,
            follow_redirects=False,
        )
        self._transaction: ContextVar[str | None] = ContextVar(
            "cloudbase_transaction", default=None
        )

    @traced
    async def aclose(self) -> None:
        await self._client.aclose()

    @traced
    async def request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        params: Mapping[str, str | int] | None = None,
        in_transaction: bool = True,
    ) -> dict[str, Any]:
        data, query = dict(body or {}), dict(params or {})
        transaction_id = self._transaction.get() if in_transaction else None
        if transaction_id:
            if method in {"GET", "DELETE"}:
                query["transactionId"] = transaction_id
            else:
                data["transactionId"] = transaction_id
        try:
            response = await self._client.request(
                method,
                self.base_url + path,
                params=query,
                json=encode_ejson(data) if method not in {"GET", "DELETE"} else None,
            )
        except httpx.HTTPError:
            raise RepositoryUnavailable("CloudBase HTTP request failed") from None
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            raise RepositoryUnavailable("CloudBase response is not JSON") from None
        if not isinstance(payload, dict):
            raise RepositoryUnavailable("CloudBase response is not an object")
        code = payload.get("code")
        if code in {"DATABASE_TRANSACTION_CONFLICT", "DATABASE_DUPLICATE_WRITE"}:
            raise RepositoryVersionConflict(None)
        if response.status_code == 404:
            raise RepositoryNotFound("CloudBase resource not found")
        if response.status_code == 409:
            raise RepositoryVersionConflict(None)
        if not 200 <= response.status_code < 300 or code not in (None, 0, "0", "OK", "SUCCESS"):
            # Never include remote messages, requests, headers or secrets in errors.
            raise RepositoryUnavailable("CloudBase rejected the request")
        try:
            decoded: dict[str, Any] = decode_ejson(payload)
            return decoded
        except ValueError, TypeError, OverflowError:
            raise RepositoryUnavailable("CloudBase EJSON is invalid") from None

    def transaction(self) -> AbstractAsyncContextManager[None]:
        return transaction(self)

    @staticmethod
    @traced
    def collection_path(collection: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", collection):
            raise ValueError("invalid collection name")
        return f"/collections/{collection}/documents"

    @traced
    async def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        result = await self.request(
            "GET",
            self.collection_path(collection),
            params={
                "query": json.dumps(encode_ejson(where or {})),
                "limit": limit,
                "offset": offset,
                "order": '[{"field":"_id","direction":"asc"}]',
            },
        )
        items = result.get("list")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RepositoryUnavailable("CloudBase query result is invalid")
        return items

    @traced
    async def all(
        self, collection: str, where: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        while True:
            page = await self.query(collection, where, offset=len(documents))
            documents.extend(page)
            if len(page) < 100:
                return documents

    @traced
    async def get(self, collection: str, document_id: str) -> dict[str, Any]:
        items = await self.query(collection, {"_id": document_id}, limit=1)
        if not items:
            raise RepositoryNotFound("CloudBase document not found")
        return items[0]

    @traced
    async def insert(self, collection: str, document: Mapping[str, Any]) -> None:
        result = await self.request(
            "POST", self.collection_path(collection), body={"data": [document]}
        )
        if not isinstance(result.get("insertedIds"), list) or len(result["insertedIds"]) != 1:
            raise RepositoryUnavailable("CloudBase insert result is invalid")

    @traced
    async def replace(
        self, collection: str, document: Mapping[str, Any], expected_version: int
    ) -> None:
        values = dict(document)
        document_id = values.pop("_id")
        result = await self.request(
            "PATCH",
            self.collection_path(collection),
            body={
                "query": {"_id": document_id, "version": expected_version},
                "data": {"$set": values},
                "multi": False,
                "upsert": False,
            },
        )
        if result.get("matched") != 1:
            current = await self.get(collection, document_id)
            raise RepositoryVersionConflict(current.get("version"))
        if result.get("updated") != 1:
            raise RepositoryUnavailable("CloudBase update was not applied")

    @traced
    async def create_collection(self, collection: str) -> None:
        self.collection_path(collection)
        (
            await self.request(
                "POST", "/collections", body={"collectionName": collection}, in_transaction=False
            )
        )

    @traced
    async def commands(self, commands: list[dict[str, Any]]) -> list[Any]:
        result = await self.request("POST", "/commands", body={"commands": commands})
        items = result.get("list")
        if not isinstance(items, list) or len(items) != len(commands):
            raise RepositoryUnavailable("CloudBase command result is invalid")
        for group in items:
            for item in group if isinstance(group, list) else [group]:
                if isinstance(item, dict) and (item.get("ok", 1) != 1 or item.get("writeErrors")):
                    raise RepositoryUnavailable("CloudBase command failed")
        return items
