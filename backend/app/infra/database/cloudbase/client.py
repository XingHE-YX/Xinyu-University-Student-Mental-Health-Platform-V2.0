"""Server-only NoSQL HTTP API with native transactions and strict EJSON decoding."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.infra.database.common import (
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)
from app.infra.logger.common import traced


@traced
def encode_ejson(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$date": {"$numberLong": str(int(value.timestamp() * 1000))}}
    if isinstance(value, Mapping):
        return {key: encode_ejson(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_ejson(item) for item in value]
    return value


@traced
def decode_ejson(value: Any) -> Any:
    if isinstance(value, list):
        return [decode_ejson(item) for item in value]
    if isinstance(value, dict):
        if len(value) == 1:
            for key in ("$numberInt", "$numberLong"):
                if key in value:
                    return int(value[key])
            if "$numberDouble" in value:
                return float(value["$numberDouble"])
            if "$oid" in value:
                return str(value["$oid"])
            if "$date" in value:
                raw = decode_ejson(value["$date"])
                if isinstance(raw, (int, float)):
                    return datetime.fromtimestamp(raw / 1000, UTC)
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return {key: decode_ejson(item) for key, item in value.items()}
    return value


class CloudBaseStore:
    """Each instance owns a connection pool; transaction IDs are request-context local."""

    def __init__(
        self,
        environment_id: str,
        api_key: str,
        *,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 8.0,
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
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            timeout=timeout,
            transport=transport,
            follow_redirects=False,
        )
        self._transaction: ContextVar[str | None] = ContextVar(
            "cloudbase_transaction", default=None
        )

    @traced
    def close(self) -> None:
        self._client.close()

    @traced
    def request(
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
            response = self._client.request(
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

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._transaction.get() is not None:
            yield
            return
        data = self.request("POST", "/transactions", in_transaction=False)
        transaction_id = data.get("transactionId")
        if not isinstance(transaction_id, str) or not transaction_id:
            raise RepositoryUnavailable("CloudBase transaction ID is missing")
        token = self._transaction.set(transaction_id)
        path = f"/transactions/{quote(transaction_id, safe='')}"
        try:
            yield
            self.request("POST", path + "/commit", in_transaction=False)
        except BaseException:
            try:
                self.request("POST", path + "/rollback", in_transaction=False)
            except RepositoryUnavailable, RepositoryNotFound, RepositoryVersionConflict:
                pass  # Preserve the original failure; never report a failed commit as success.
            raise
        finally:
            self._transaction.reset(token)

    @staticmethod
    @traced
    def collection_path(collection: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", collection):
            raise ValueError("invalid collection name")
        return f"/collections/{collection}/documents"

    @traced
    def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        result = self.request(
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
    def all(self, collection: str, where: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        while True:
            page = self.query(collection, where, offset=len(documents))
            documents.extend(page)
            if len(page) < 100:
                return documents

    @traced
    def get(self, collection: str, document_id: str) -> dict[str, Any]:
        items = self.query(collection, {"_id": document_id}, limit=1)
        if not items:
            raise RepositoryNotFound("CloudBase document not found")
        return items[0]

    @traced
    def insert(self, collection: str, document: Mapping[str, Any]) -> None:
        result = self.request("POST", self.collection_path(collection), body={"data": [document]})
        if not isinstance(result.get("insertedIds"), list) or len(result["insertedIds"]) != 1:
            raise RepositoryUnavailable("CloudBase insert result is invalid")

    @traced
    def replace(self, collection: str, document: Mapping[str, Any], expected_version: int) -> None:
        values = dict(document)
        document_id = values.pop("_id")
        result = self.request(
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
            current = self.get(collection, document_id)
            raise RepositoryVersionConflict(current.get("version"))
        if result.get("updated") != 1:
            raise RepositoryUnavailable("CloudBase update was not applied")

    @traced
    def create_collection(self, collection: str) -> None:
        self.collection_path(collection)
        self.request(
            "POST", "/collections", body={"collectionName": collection}, in_transaction=False
        )

    @traced
    def commands(self, commands: list[dict[str, Any]]) -> list[Any]:
        result = self.request("POST", "/commands", body={"commands": commands})
        items = result.get("list")
        if not isinstance(items, list) or len(items) != len(commands):
            raise RepositoryUnavailable("CloudBase command result is invalid")
        for group in items:
            for item in group if isinstance(group, list) else [group]:
                if isinstance(item, dict) and (item.get("ok", 1) != 1 or item.get("writeErrors")):
                    raise RepositoryUnavailable("CloudBase command failed")
        return items
