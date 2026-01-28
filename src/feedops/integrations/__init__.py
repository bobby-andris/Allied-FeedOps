"""Optional MCP integrations (stub implementations)."""

from feedops.integrations import (
    bing_catalog,
    google_feed_upload,
    google_supplemental,
    merchant_center,
    shopify_catalog,
)
from feedops.integrations.analytics import fetch_product_metrics
from feedops.integrations.apify import fetch_competitor_titles
from feedops.integrations.google_ads import fetch_high_performing_keywords
from feedops.integrations.mapi_docs import fetch_mapi_requirements

__all__ = [
    "fetch_high_performing_keywords",
    "fetch_product_metrics",
    "fetch_competitor_titles",
    "fetch_mapi_requirements",
    "merchant_center",
    "shopify_catalog",
    "google_supplemental",
    "google_feed_upload",
    "bing_catalog",
]
