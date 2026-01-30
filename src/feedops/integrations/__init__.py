"""Integrations package.

Keep imports lazy to avoid circular-import issues between pipeline/orchestration code
and integration modules.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "fetch_high_performing_keywords",
    "fetch_product_metrics",
    "fetch_competitor_titles",
    "fetch_mapi_requirements",
    "merchant_center",
    "shopify_catalog",
    "google_supplemental",
    "google_feed_upload",
    "google_sheets",
    "bing_catalog",
]


def __getattr__(name: str) -> Any:  # pragma: no cover
    if name in {
        "merchant_center",
        "shopify_catalog",
        "google_supplemental",
        "google_feed_upload",
        "google_sheets",
        "bing_catalog",
        "google_ads",
        "analytics",
        "apify",
        "mapi_docs",
    }:
        return importlib.import_module(f"{__name__}.{name}")

    if name == "fetch_product_metrics":
        from feedops.integrations.analytics import fetch_product_metrics

        return fetch_product_metrics
    if name == "fetch_competitor_titles":
        from feedops.integrations.apify import fetch_competitor_titles

        return fetch_competitor_titles
    if name == "fetch_high_performing_keywords":
        from feedops.integrations.google_ads import fetch_high_performing_keywords

        return fetch_high_performing_keywords
    if name == "fetch_mapi_requirements":
        from feedops.integrations.mapi_docs import fetch_mapi_requirements

        return fetch_mapi_requirements

    raise AttributeError(name)
