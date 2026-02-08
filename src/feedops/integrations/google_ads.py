"""Google Ads integration (optional).

This module supports two execution modes:
- API mode (preferred for local/CI): uses the official google-ads Python client library.
- MCP mode (Cursor-only): stubbed in this repo unless wired at runtime.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
import logging
import os

logger = logging.getLogger(__name__)


def _mcp_enabled() -> bool:
    return os.getenv("GOOGLE_ADS_MCP_ENABLED", "").lower() in {"1", "true", "yes"}


def _api_enabled() -> bool:
    return os.getenv("GOOGLE_ADS_API_ENABLED", "").lower() in {"1", "true", "yes"}


def _truthy_env(name: str) -> str | None:
    val = os.getenv(name)
    if not val:
        return None
    val = val.strip()
    return val or None


def _normalize_item_ids_for_ads(item_ids: list[str]) -> list[str]:
    """Normalize item IDs for Ads listing-group matching (case-insensitive)."""
    normalized = []
    for item_id in item_ids:
        value = str(item_id).strip().lower()
        if value:
            normalized.append(value)
    return normalized


def _load_client():
    """Load Google Ads API client (google-ads library).

    Config resolution order:
    1. GOOGLE_ADS_CONFIG_PATH (explicit yaml path)
    2. Environment variables (Cloud Run, CI/CD)
    3. google-ads.yaml in home directory (local development)
    """
    # Lazy import: keeps this dependency optional until API mode is enabled.
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import-not-found]

    # If explicit config path is set, use it
    config_path = _truthy_env("GOOGLE_ADS_CONFIG_PATH")
    if config_path:
        return GoogleAdsClient.load_from_storage(path=config_path)

    # Try loading from environment variables (preferred for Cloud Run)
    try:
        return GoogleAdsClient.load_from_env()
    except Exception:
        # Fall back to yaml file for local development
        return GoogleAdsClient.load_from_storage()


def _fetch_search_terms_for_item_ids(
    client,
    *,
    customer_id: str,
    item_ids: list[str],
    start_date: str,
    end_date: str,
    limit: int,
) -> list[dict]:
    """Fetch raw search-term rows for the provided item_ids.

    Strategy:
    1) Find ad groups whose listing group partitions contain those item_ids.
    2) Query search_term_view for those ad groups within the date range.

    Note: This assumes your Shopping account structure uses listing groups that include
    product_item_id nodes (SKU-level partitioning). If not, this will return [].
    """
    item_ids = _normalize_item_ids_for_ads(item_ids)
    if not item_ids:
        return []

    # Lazy import: keeps test/runtime light unless API is enabled.
    from google.protobuf.json_format import MessageToDict  # type: ignore[import-not-found]

    def run_search_stream(query: str) -> list[dict]:
        ga_service = client.get_service("GoogleAdsService")
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        out: list[dict] = []
        for batch in stream:
            for row in batch.results:
                out.append(
                    MessageToDict(row._pb, preserving_proto_field_name=True)  # type: ignore[attr-defined]
                )
        return out

    # 1) Listing-group lookup: item_id -> ad_group.id
    item_ids_str = ", ".join(f"'{i}'" for i in item_ids)
    listing_query = f"""
    SELECT
      ad_group.id,
      ad_group_criterion.listing_group.case_value.product_item_id.value
    FROM ad_group_criterion
    WHERE ad_group_criterion.type = LISTING_GROUP
      AND ad_group_criterion.listing_group.case_value.product_item_id.value IN ({item_ids_str})
    """
    listing_rows = run_search_stream(listing_query)
    ad_group_ids = sorted(
        {
            row.get("ad_group", {}).get("id")
            for row in listing_rows
            if row.get("ad_group", {}).get("id")
        }
    )
    if not ad_group_ids:
        return []

    # 2) Served terms for those ad groups
    ad_group_ids_str = ", ".join(f"'{ag}'" for ag in ad_group_ids)
    terms_query = f"""
    SELECT
      search_term_view.search_term,
      metrics.impressions,
      metrics.clicks,
      metrics.conversions
    FROM search_term_view
    WHERE ad_group.id IN ({ad_group_ids_str})
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
      AND campaign.advertising_channel_type = SHOPPING
      AND metrics.clicks > 0
    ORDER BY metrics.conversions DESC, metrics.clicks DESC, metrics.impressions DESC
    LIMIT {int(limit)}
    """
    rows = run_search_stream(terms_query)

    # Normalize to a stable shape for downstream aggregation.
    out: list[dict] = []
    for row in rows:
        term = row.get("search_term_view", {}).get("search_term")
        if not term:
            continue
        metrics = row.get("metrics", {}) or {}
        out.append(
            {
                "term": term,
                "impressions": int(metrics.get("impressions", 0) or 0),
                "clicks": int(metrics.get("clicks", 0) or 0),
                "conversions": float(metrics.get("conversions", 0.0) or 0.0),
            }
        )
    return out


def fetch_master_sku_keywords(
    item_group_id: str | None,
    item_ids: list[str] | None = None,
    category: str | None = None,
) -> list[str]:
    """Return high-performing search terms for a MasterSKU (variant group).

    Intended semantics:
    - In Merchant Center, a MasterSKU maps to the variant group (item_group_id).
    - In Google Ads, we aggregate search terms across all item_ids (variants) in that group.

    Notes:
    - API mode is enabled with GOOGLE_ADS_API_ENABLED=1 and requires GOOGLE_ADS_CUSTOMER_ID
      plus a valid google-ads.yaml configuration (either default or via GOOGLE_ADS_CONFIG_PATH).
    - MCP mode remains stubbed unless wired at runtime.
    """
    item_ids = list(item_ids or [])

    # Preferred: direct Google Ads API.
    if _api_enabled():
        customer_id = _truthy_env("GOOGLE_ADS_CUSTOMER_ID")
        if not customer_id:
            logger.warning(
                "Google Ads API enabled but GOOGLE_ADS_CUSTOMER_ID is not set; returning []."
            )
            return []

        # Default to a recent window; keep configurable but simple.
        days = int(os.getenv("GOOGLE_ADS_LOOKBACK_DAYS", "90") or "90")
        end = date.today()
        start = end - timedelta(days=max(days, 1))
        start_s = start.isoformat()
        end_s = end.isoformat()
        limit = int(os.getenv("GOOGLE_ADS_TERMS_LIMIT", "200") or "200")

        try:
            client = _load_client()
        except Exception as e:
            logger.warning(
                "Google Ads API enabled but client could not be loaded (%s); returning [].", e
            )
            return []

        try:
            rows = _fetch_search_terms_for_item_ids(
                client,
                customer_id=customer_id,
                item_ids=item_ids,
                start_date=start_s,
                end_date=end_s,
                limit=limit,
            )
        except Exception as e:
            logger.warning(
                "Google Ads API query failed (%s) for item_group_id=%s item_ids=%s; returning [].",
                e,
                item_group_id,
                (len(item_ids) if item_ids else 0),
            )
            return []

        # Aggregate duplicates and rank.
        agg: dict[str, dict[str, float]] = defaultdict(lambda: {"clicks": 0.0, "impressions": 0.0, "conversions": 0.0})
        for r in rows:
            term = str(r.get("term") or "").strip()
            if not term:
                continue
            a = agg[term]
            a["clicks"] += float(r.get("clicks", 0) or 0)
            a["impressions"] += float(r.get("impressions", 0) or 0)
            a["conversions"] += float(r.get("conversions", 0) or 0)

        ranked = sorted(
            agg.items(),
            key=lambda kv: (kv[1]["conversions"], kv[1]["clicks"], kv[1]["impressions"]),
            reverse=True,
        )
        return [term for term, _ in ranked[:50]]

    # Fallback: MCP stub (Cursor-only; not wired here).
    if not _mcp_enabled():
        return []
    logger.warning(
        "Google Ads MCP enabled but no runtime client is configured. "
        "Requested keywords for item_group_id=%s category=%s item_ids=%s",
        item_group_id,
        category,
        (len(item_ids) if item_ids else 0),
    )
    return []


def fetch_high_performing_keywords(category: str | None = None) -> list[str]:
    """Return high-performing search terms for a category.

    Stub implementation: returns empty list unless MCP is enabled and wired.
    """
    if not _mcp_enabled():
        return []
    logger.warning("Google Ads MCP enabled but no runtime client is configured.")
    return []
