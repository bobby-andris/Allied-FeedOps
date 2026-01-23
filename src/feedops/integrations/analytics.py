"""Analytics MCP integration (optional)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return os.getenv("ANALYTICS_MCP_ENABLED", "").lower() in {"1", "true", "yes"}


def fetch_product_metrics(master_sku: str) -> dict | None:
    """Return product metrics for a SKU.

    Stub implementation: returns None unless MCP is enabled and wired.
    """
    if not _enabled():
        return None
    logger.warning("Analytics MCP enabled but no runtime client is configured.")
    return None
