"""MAPI Docs MCP integration (optional)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("MAPI_DOCS_MCP_ENABLED", "").lower() in {"1", "true", "yes"}


def fetch_mapi_requirements() -> dict | None:
    """Return latest MAPI requirements (stub)."""
    if not _enabled():
        return None
    logger.warning("MAPI Docs MCP enabled but no runtime client is configured.")
    return None
