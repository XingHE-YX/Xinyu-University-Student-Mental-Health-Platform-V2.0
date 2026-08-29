"""HTTP-only CloudBase document database gateway.

Business services use repository contracts and never assemble CloudBase requests
themselves. The adapter speaks the documented CloudBase Open API and keeps
CloudBase-specific paths, headers and EJSON serialization in one place.
"""

import base64
import binascii
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from app.repositories.protocols import (
    DocumentPage,
    JsonDocument,
    RepositoryError,
    RepositoryNotFound,
    RepositoryUnavailable,
    RepositoryVersionConflict,
)

__all__ = [
    "CloudBaseGateway",
    "RepositoryError",
    "RepositoryNotFound",
    "RepositoryUnavailable",
    "RepositoryVersionConflict",
]


class CloudBaseGateway:
    """The only adapter allowed to know CloudBase document API details."""

    DEFAULT_BASE_URL = "https://tcb-api.tencentcloudapi.com"

    def __init__(
        self,
        *,
        environment_id: str,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        session_token: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 8.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.environment_id = environment_id
        self.api_key = api_key
        self.session_token = session_token
        self.transport = transport
        self.timeout = timeout

    async def query(
        self,
        collection: str,
        where: Mapping[str, Any] | None = None,
        *,
        cursor: str | None = None,
        limit: int = 20,
    ) -> DocumentPage:
        page_size = max(1, min(limit, 100))
        offset = _decode_cursor(cursor)
        payload = await self._request(
            "find",
            collection,
            params={
                "limit": str(page_size),
                "skip": str(offset),
                "fields": "{}",
                "sort": '{"_id":1}',
            },
            body={"query": _ejson(where or {})},
        )
        data = self._data(payload)
        raw_documents = data.get("list", [])
        if not isinstance(raw_documents, list):
            raise RepositoryUnavailable("CloudBase returned an invalid query list")
        documents = tuple(_decode_document(item) for item in raw_documents)
        response_limit = data.get("limit", page_size)
        if not isinstance(response_limit, int) or response_limit < 1:
            raise RepositoryUnavailable("CloudBase returned an invalid query limit")
        next_cursor = (
            _encode_cursor(offset + len(documents)) if len(documents) >= response_limit else None
        )
        return DocumentPage(documents, next_cursor)

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
        payload = await self._request(
            "updateOne",
            collection,
            body={
                "query": _ejson({"_id": document_id, "version": expected_version}),
                "data": _ejson({"$set": dict(updates), "$inc": {"version": 1}}),
            },
        )
        await self._require_update_match(payload, collection, document_id, expected_version)
        return await self._find_by_id(collection, document_id)

    async def logical_delete(
        self,
        collection: str,
        document_id: str,
        *,
        expected_version: int,
    ) -> JsonDocument:
        deleted_at = datetime.now(UTC).isoformat()
        payload = await self._request(
            "updateOne",
            collection,
            body={
                "query": _ejson({"_id": document_id, "version": expected_version}),
                "data": _ejson(
                    {
                        "$set": {"is_deleted": True, "deleted_at": deleted_at},
                        "$inc": {"version": 1},
                    }
                ),
            },
        )
        await self._require_update_match(payload, collection, document_id, expected_version)
        return await self._find_by_id(collection, document_id)

    async def _find_by_id(self, collection: str, document_id: str) -> JsonDocument:
        page = await self.query(collection, {"_id": document_id}, limit=1)
        if not page.items:
            raise RepositoryNotFound("CloudBase document not found")
        return page.items[0]

    async def _request(
        self,
        operation: str,
        collection: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = (
            f"{self.base_url}/api/v2/envs/{self.environment_id}/databases/"
            f"{collection}/documents:{operation}"
        )
        headers = {
            "X-CloudBase-Authorization": self.api_key,
            "X-CloudBase-TimeStamp": str(int(datetime.now(UTC).timestamp())),
            "Content-Type": "application/json",
        }
        if self.session_token:
            headers["X-CloudBase-SessionToken"] = self.session_token
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(url, params=params, headers=headers, json=body or {})
        except httpx.HTTPError as error:
            raise RepositoryUnavailable("CloudBase HTTP request failed") from error

        if response.status_code == 404:
            raise RepositoryNotFound("CloudBase document not found")
        if response.status_code == 409:
            raise RepositoryVersionConflict(_current_version(response))
        if response.status_code >= 400:
            raise RepositoryUnavailable("CloudBase returned a dependency error")
        try:
            payload = response.json()
        except ValueError as error:
            raise RepositoryUnavailable("CloudBase returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise RepositoryUnavailable("CloudBase returned an invalid response")
        response_code = payload.get("code")
        if response_code not in (None, 0, "0", "OK", "SUCCESS"):
            if response_code in {"VERSION_CONFLICT", "CONFLICT"}:
                raise RepositoryVersionConflict(_current_version_from_payload(payload))
            raise RepositoryUnavailable("CloudBase returned a dependency error")
        return payload

    @staticmethod
    def _data(payload: Mapping[str, Any]) -> dict[str, Any]:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise RepositoryUnavailable("CloudBase returned invalid data")
        return dict(data)

    async def _require_update_match(
        self,
        payload: Mapping[str, Any],
        collection: str,
        document_id: str,
        expected_version: int,
    ) -> None:
        data = self._data(payload)
        matched = data.get("matched")
        updated = data.get("updated")
        if not isinstance(matched, int) or not isinstance(updated, int):
            raise RepositoryUnavailable("CloudBase returned an invalid update result")
        if matched > 0 and updated > 0:
            return
        try:
            current_document = await self._find_by_id(collection, document_id)
        except RepositoryNotFound:
            raise RepositoryNotFound("CloudBase document not found") from None
        current_version = current_document.get("version")
        raise RepositoryVersionConflict(
            current_version if isinstance(current_version, int) else None
        )


def _ejson(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$date": int(value.timestamp() * 1000)}
    raise TypeError(f"unsupported CloudBase value: {type(value).__name__}")


def _decode_document(value: Any) -> JsonDocument:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError as error:
            raise RepositoryUnavailable("CloudBase returned invalid document data") from error
        if isinstance(parsed, dict):
            return parsed
    raise RepositoryUnavailable("CloudBase returned invalid document data")


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, int(base64.urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")))
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise ValueError("invalid cursor") from error


def _current_version(response: httpx.Response) -> int | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return _current_version_from_payload(payload) if isinstance(payload, dict) else None


def _current_version_from_payload(payload: Mapping[str, Any]) -> int | None:
    value = payload.get("current_version")
    return value if isinstance(value, int) else None
