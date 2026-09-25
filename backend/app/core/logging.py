"""Structured (JSON) logging + request-ID propagation.

Phase 6 hardening (§4 Observability, §8 Security in docs/ARCHITECTURE.md):
every request gets a request ID (accepted from ``X-Request-ID`` or minted),
which is carried through async code via a contextvar and stamped onto every
log line, so a demo/incident can be traced end-to-end. JSON lines are used
because they drop straight into any log collector without a parser.

Nothing here touches the stdlib root configuration at import time —
``configure_logging`` is called once from the app factory and is idempotent.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

REQUEST_ID_HEADER = "X-Request-ID"

_request_id: ContextVar[str | None] = ContextVar("weathergpt_request_id", default=None)


def set_request_id(value: str | None):
    """Bind a request ID to the current context; returns the contextvar token."""
    return _request_id.set(value)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str | None:
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """One JSON object per line, with the active request ID when present."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or get_request_id()
        if request_id:
            payload["request_id"] = request_id
        payload.update(getattr(record, "extra_fields", {}) or {})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_HANDLER_MARKER = "_weathergpt_handler"


def configure_logging(level: str = "INFO") -> None:
    """Attach the JSON formatter to the root logger (idempotent)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root.removeHandler(handler)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
    root.setLevel((level or "INFO").upper())


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """Emit a structured event; ``fields`` are merged into the JSON payload."""
    logger.log(level, event, extra={"extra_fields": fields})
