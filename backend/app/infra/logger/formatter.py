"""Five-column, single-line audit output."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[3]


def code_position(filename: str, line: int) -> str:
    path: Path | str
    try:
        path = Path(filename).resolve().relative_to(APP_ROOT)
    except ValueError:
        path = Path(filename).name
    return f"{path}:{line}"


class AuditFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = (
            datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        position = getattr(record, "code_pos", code_position(record.pathname, record.lineno))
        scope = getattr(record, "scope", record.name)
        content = getattr(record, "safe_content", {"event": "log.message"})
        return f"{record.levelname} {timestamp} {position} {scope} " + json.dumps(
            content, ensure_ascii=True, separators=(",", ":")
        )
