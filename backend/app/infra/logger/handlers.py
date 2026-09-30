"""Bounded logging queue shared by active application lifespans."""

import logging
import logging.handlers
import queue
import sys
from threading import Lock

from app.infra.config.types import LoggerConfig
from app.infra.logger.formatter import AuditFormatter

_lock = Lock()
_users = 0
_listener: logging.handlers.QueueListener | None = None
_handler: logging.Handler | None = None


class AuditQueueHandler(logging.handlers.QueueHandler):
    def __init__(
        self, records: queue.Queue[logging.LogRecord | None], emergency: logging.Handler
    ) -> None:
        super().__init__(records)
        self.emergency = emergency
        self.dropped = 0

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1
            if record.levelno >= logging.WARNING:
                self.emergency.handle(record)


class AuditQueueListener(logging.handlers.QueueListener):
    def __init__(
        self, records: queue.Queue[logging.LogRecord | None], sink: logging.Handler
    ) -> None:
        self.records = records
        super().__init__(records, sink)

    def enqueue_sentinel(self) -> None:
        self.records.put(None)


def start_logging(config: LoggerConfig) -> None:
    global _users, _listener, _handler
    with _lock:
        _users += 1
        if _listener is not None:
            return
        sink = logging.StreamHandler(sys.stderr)
        sink.setFormatter(AuditFormatter())
        records: queue.Queue[logging.LogRecord | None] = queue.Queue(config.queue_capacity)
        _handler = AuditQueueHandler(records, sink)
        _listener = AuditQueueListener(records, sink)
        logger = logging.getLogger("xinyu")
        logger.setLevel(config.level)
        logger.propagate = False
        logger.addHandler(_handler)
        _listener.start()


def stop_logging() -> None:
    global _users, _listener, _handler
    with _lock:
        _users -= 1
        if _users > 0 or _listener is None:
            return
        logger = logging.getLogger("xinyu")
        if isinstance(_handler, AuditQueueHandler) and _handler.dropped:
            from app.infra.logger.common import get_logger

            get_logger("logger.queue").warning(
                "logger.queue_overflow", queue_dropped=_handler.dropped
            )
        _listener.stop()
        if _handler is not None:
            logger.removeHandler(_handler)
            _handler.close()
        logger.propagate = True
        _listener = None
        _handler = None
        _users = 0
