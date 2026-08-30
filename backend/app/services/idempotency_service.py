"""Idempotency reservation and completion for mutating use cases."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.repositories.idempotency_repository import (
    IdempotencyRecord,
    IdempotencyRepository,
    InMemoryIdempotencyRepository,
)
from app.schemas.errors import ApiError, ApiException


@dataclass(frozen=True, slots=True)
class IdempotencyReservation:
    record: IdempotencyRecord
    replayed: bool


class IdempotencyService:
    TTL = timedelta(hours=24)

    def __init__(self, repository: IdempotencyRepository | None = None) -> None:
        self.repository = repository or InMemoryIdempotencyRepository()

    def begin(
        self,
        actor_type: str,
        actor_id: str,
        route_key: str,
        idempotency_key: str,
        request_body: Any,
        *,
        now: datetime | None = None,
    ) -> IdempotencyReservation:
        if not idempotency_key or len(idempotency_key) > 128:
            raise ApiException(400, "INVALID_REQUEST", "缺少有效的幂等键")
        current = _utc(now or datetime.now(UTC))
        request_hash = _hash_request(request_body)
        record = IdempotencyRecord(
            record_id=f"idem_{uuid4().hex}",
            actor_type=actor_type,
            actor_id=actor_id,
            route_key=route_key,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            outcome="processing",
            response_status=None,
            response_digest=None,
            expires_at=current + self.TTL,
            created_at=current,
            updated_at=current,
        )
        existing = self.repository.reserve(record, now=current)
        if existing is None:
            return IdempotencyReservation(record=record, replayed=False)
        if existing.request_hash != request_hash:
            raise ApiException(409, "IDEMPOTENCY_CONFLICT")
        if existing.outcome == "processing":
            raise ApiException(
                409,
                "IDEMPOTENCY_CONFLICT",
                "相同请求正在处理中，请稍后再试",
                retryable=True,
            )
        return IdempotencyReservation(record=existing, replayed=True)

    def complete(
        self,
        reservation: IdempotencyReservation,
        *,
        status_code: int,
        response_digest: str,
        now: datetime | None = None,
        outcome: str = "success",
    ) -> IdempotencyRecord:
        if reservation.replayed:
            return reservation.record
        if outcome not in {"success", "failure"}:
            raise ValueError("invalid idempotency outcome")
        current = _utc(now or datetime.now(UTC))
        return self.repository.complete(
            reservation.record.record_id,
            outcome=outcome,  # type: ignore[arg-type]
            response_status=status_code,
            response_digest=response_digest,
            now=current,
        )


def serialize_api_error(error: ApiException) -> str:
    """Serialize only the safe API error contract for a failure replay."""

    return json.dumps(
        {
            "status_code": error.status_code,
            "error": error.to_error().model_dump(),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def deserialize_api_error(response_digest: str | None) -> ApiException | None:
    """Restore a safe API error digest, while tolerating legacy failure digests."""

    if response_digest is None:
        return None
    try:
        data = json.loads(response_digest)
        if not isinstance(data, dict):
            return None
        if "error" in data:
            status_code = data.get("status_code")
            error_data = data["error"]
            if type(status_code) is not int or not isinstance(error_data, dict):
                return None
            error = ApiError.model_validate(error_data)
            return ApiException(
                status_code,
                error.code,
                error.message,
                retryable=error.retryable,
                current_version=error.current_version,
            )
        if "error_code" in data:
            return ApiException(int(data["status_code"]), str(data["error_code"]))
    except (KeyError, TypeError, ValueError):
        return None
    return None


def _hash_request(request_body: Any) -> str:
    canonical = json.dumps(
        request_body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
