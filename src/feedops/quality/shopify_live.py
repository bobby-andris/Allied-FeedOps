"""Helpers for optionally fetching current ("live") Shopify content in the dashboard.

This module is intentionally defensive:
- Missing Shopify credentials should not crash the dashboard.
- Network/API failures should surface as user-facing errors, not exceptions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from feedops.loaders.unified_loader import (
    get_cached_shopify_age_hours,
    load_parent_sku_unified_with_status,
)


@dataclass
class ShopifyLiveSnapshot:
    title: str = ""
    description: str = ""
    data_source: str | None = None  # shopify_cached/shopify_fresh
    age_hours: float | None = None
    error: str | None = None


def load_shopify_live_snapshot(
    master_sku: str,
    *,
    force_refresh: bool = False,
    cache_ttl_hours: float = 24.0,
    catalog_path: str | None = None,
) -> ShopifyLiveSnapshot:
    """Load current Shopify title/description for a master SKU.

    Uses the unified loader (DB cache → Shopify API → fallback). For dashboard display, we
    only accept actual Shopify sources ("shopify_cached" or "shopify_fresh").
    """
    master_sku = (master_sku or "").strip()
    if not master_sku:
        return ShopifyLiveSnapshot(error="Missing SKU.")

    if not os.environ.get("SHOPIFY_STORE_URL") or not os.environ.get("SHOPIFY_ACCESS_TOKEN"):
        return ShopifyLiveSnapshot(
            error="Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    try:
        parent, status = load_parent_sku_unified_with_status(
            master_sku=master_sku,
            force_refresh=force_refresh,
            catalog_path=catalog_path,
            cache_ttl_hours=cache_ttl_hours,
        )
    except Exception as exc:
        return ShopifyLiveSnapshot(error=str(exc))

    if not parent or not status.data_source:
        return ShopifyLiveSnapshot(error=status.api_error or "Unable to load Shopify data.")

    if status.data_source not in {"shopify_cached", "shopify_fresh"}:
        # The unified loader can fall back to CSV; that's not "live Shopify".
        return ShopifyLiveSnapshot(
            error=status.api_error
            or "Shopify data unavailable (fallback data loaded instead)."
        )

    return ShopifyLiveSnapshot(
        title=parent.current_title or "",
        description=parent.current_description or "",
        data_source=status.data_source,
        age_hours=get_cached_shopify_age_hours(master_sku),
    )

