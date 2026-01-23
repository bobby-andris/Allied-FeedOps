"""Apify MCP integration (optional)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("APIFY_MCP_ENABLED", "").lower() in {"1", "true", "yes"}


def fetch_competitor_titles(category: str | None = None) -> list[str]:
    """Return competitor titles for a category.

    Stub implementation: returns empty list unless MCP is enabled and wired.
    """
    if not _enabled():
        return []
    logger.warning("Apify MCP enabled but no runtime client is configured.")
    return []
