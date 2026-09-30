"""Common document page and opaque offset cursor codec."""

import base64
import binascii
from dataclasses import dataclass
from typing import Any

JsonDocument = dict[str, Any]


@dataclass(frozen=True, slots=True)
class DocumentPage:
    items: tuple[JsonDocument, ...]
    next_cursor: str | None


def encode_cursor(offset: int) -> str:
    if offset < 0:
        raise ValueError("cursor offset must be nonnegative")
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        value = base64.b64decode(cursor.encode("ascii"), altchars=b"-_", validate=True).decode(
            "ascii"
        )
        offset = int(value)
    except ValueError, UnicodeError, binascii.Error:
        raise ValueError("invalid cursor") from None
    if offset < 0:
        raise ValueError("invalid cursor")
    return offset
