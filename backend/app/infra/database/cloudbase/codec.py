"""CloudBase Extended JSON codec."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

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
