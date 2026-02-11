"""Runtime observability helpers for request-scoped logs and IDs."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import time
import uuid
from collections.abc import Iterator
from typing import Any

_REQUEST_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "feedops_request_id", default="-"
)


def get_request_id() -> str:
    """Return the active request ID (or '-' when unset)."""
    return _REQUEST_ID.get()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    """Set the active request ID and return the context token."""
    return _REQUEST_ID.set(request_id or "-")


def reset_request_id(token: contextvars.Token[str]) -> None:
    """Reset the request ID context to a previous token."""
    _REQUEST_ID.reset(token)


@contextlib.contextmanager
def request_context(request_id: str | None = None) -> Iterator[str]:
    """Bind a request ID for nested logs/metrics in this context."""
    resolved = (request_id or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    token = set_request_id(resolved)
    try:
        yield resolved
    finally:
        reset_request_id(token)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit one structured JSON log line with request ID context."""
    payload: dict[str, Any] = {
        "ts": time.time(),
        "event": event,
        "request_id": get_request_id(),
    }
    payload.update(fields)
    logger.log(level, json.dumps(payload, default=str, sort_keys=True))

