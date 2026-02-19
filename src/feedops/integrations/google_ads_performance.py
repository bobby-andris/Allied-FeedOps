"""Google Ads Performance API integration.

Fetches shopping performance metrics (impressions, clicks, conversions, ROAS) for
products via the Google Ads API shopping_performance_view.

This module supports two execution modes:
- API mode (preferred): uses the official google-ads Python client library.
- MCP mode (Cursor-only): uses the Google Ads MCP server if available.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

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


def _load_client():
    """Load Google Ads API client (google-ads library).

    Config resolution order:
    1. Environment variables (GOOGLE_ADS_* vars) - best for Cloud Run with Secrets
    2. GOOGLE_ADS_CONFIG_PATH (explicit file path)
    3. Default google-ads.yaml resolution (library default)
    """
    from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import-not-found]

    # Try environment variables first (best for Cloud Run / serverless)
    developer_token = _truthy_env("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = _truthy_env("GOOGLE_ADS_CLIENT_ID")
    client_secret = _truthy_env("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = _truthy_env("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = _truthy_env("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

    if all([developer_token, client_id, client_secret, refresh_token]):
        logger.info("Loading Google Ads client from environment variables")
        config = {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "use_proto_plus": True,
        }
        if login_customer_id:
            config["login_customer_id"] = login_customer_id
        return GoogleAdsClient.load_from_dict(config)

    # Fall back to config file
    config_path = _truthy_env("GOOGLE_ADS_CONFIG_PATH")
    if config_path:
        logger.info(f"Loading Google Ads client from config file: {config_path}")
        return GoogleAdsClient.load_from_storage(path=config_path)

    # Default location
    logger.info("Loading Google Ads client from default location")
    return GoogleAdsClient.load_from_storage()


OFFER_ID_CHUNK_SIZE = 25  # Max offer IDs per GAQL IN() clause — prevents API hang


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _run_gaql_query(client, customer_id: str, query: str) -> list[dict]:
    """Execute a GAQL query and return results as dicts."""
    from google.protobuf.json_format import MessageToDict  # type: ignore[import-not-found]

    ga_service = client.get_service("GoogleAdsService")
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    results: list[dict] = []
    for batch in stream:
        for row in batch.results:
            results.append(MessageToDict(row._pb, preserving_proto_field_name=True))
    return results


def fetch_product_performance(
    offer_id: str,
    start_date: str,
    end_date: str,
    *,
    customer_id: str | None = None,
    merchant_id: str | None = None,
) -> dict[str, Any]:
    """Fetch Google Shopping performance metrics for a product.

    Uses Google Ads API shopping_performance_view to retrieve metrics.
    Ref: https://developers.google.com/google-ads/api/fields/v16/shopping_performance_view

    Args:
        offer_id: Product offer ID (e.g., 'shopify_US_7721863643362_42804912849122').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        customer_id: Google Ads customer ID. Falls back to GOOGLE_ADS_CUSTOMER_ID env var.
        merchant_id: Google Merchant Center ID (optional, for filtering).

    Returns:
        Dictionary with aggregated metrics:
        {
            'impressions': int,
            'clicks': int,
            'ctr': float (0.0 to 1.0),
            'conversions': int,
            'conversion_value': float,
            'cost': float,
            'roas': float,
            'daily_data': list[dict]  # Per-day breakdown
        }

    Raises:
        ValueError: If API is not enabled or customer_id is missing.
    """
    customer_id = customer_id or _truthy_env("GOOGLE_ADS_CUSTOMER_ID")

    if _api_enabled():
        if not customer_id:
            raise ValueError(
                "GOOGLE_ADS_CUSTOMER_ID is required for performance fetching."
            )

        try:
            client = _load_client()
        except Exception as e:
            logger.error("Failed to load Google Ads client: %s", e)
            raise ValueError(f"Failed to load Google Ads client: {e}") from e

        return _fetch_performance_via_api(
            client,
            customer_id=customer_id,
            offer_id=offer_id,
            start_date=start_date,
            end_date=end_date,
        )

    if _mcp_enabled():
        logger.warning(
            "Google Ads MCP mode is enabled but not implemented for performance "
            "fetching. Please enable API mode with GOOGLE_ADS_API_ENABLED=1"
        )
        return _empty_performance_result()

    # Neither API nor MCP enabled
    logger.warning(
        "Google Ads API is not enabled. Set GOOGLE_ADS_API_ENABLED=1 to fetch "
        "performance metrics."
    )
    return _empty_performance_result()


def _empty_performance_result() -> dict[str, Any]:
    """Return an empty performance result structure."""
    return {
        "impressions": 0,
        "clicks": 0,
        "ctr": 0.0,
        "conversions": 0,
        "conversion_value": 0.0,
        "cost": 0.0,
        "roas": 0.0,
        "daily_data": [],
    }


def _fetch_performance_via_api(
    client,
    *,
    customer_id: str,
    offer_id: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    """Fetch performance metrics using the Google Ads API.

    GAQL Query on shopping_performance_view:
    - segments.product_item_id: The product offer ID
    - segments.date: Date for daily breakdown
    - metrics.impressions: Number of times ad was shown
    - metrics.clicks: Number of clicks
    - metrics.ctr: Click-through rate
    - metrics.conversions: Number of conversions
    - metrics.conversions_value: Total conversion value
    - metrics.cost_micros: Cost in micros (divide by 1,000,000 for dollars)
    """
    # Escape single quotes in offer_id for GAQL
    safe_offer_id = offer_id.replace("'", "\\'")

    query = f"""
    SELECT
      segments.product_item_id,
      segments.date,
      campaign.advertising_channel_type,
      metrics.impressions,
      metrics.clicks,
      metrics.ctr,
      metrics.conversions,
      metrics.conversions_value,
      metrics.cost_micros
    FROM shopping_performance_view
    WHERE
      segments.product_item_id = '{safe_offer_id}'
      AND segments.date BETWEEN '{start_date}' AND '{end_date}'
    ORDER BY segments.date
    """

    try:
        rows = _run_gaql_query(client, customer_id, query)
    except Exception as e:
        logger.error("Failed to fetch shopping performance for %s: %s", offer_id, e)
        raise ValueError(f"Failed to fetch performance data: {e}") from e

    if not rows:
        logger.info("No performance data found for offer_id=%s", offer_id)
        return _empty_performance_result()

    # Aggregate metrics across all days
    total_impressions = 0
    total_clicks = 0
    total_conversions = 0.0
    total_conversion_value = 0.0
    total_cost_micros = 0
    daily_data: list[dict] = []

    for row in rows:
        segments = row.get("segments", {})
        metrics = row.get("metrics", {})

        impressions = int(metrics.get("impressions", 0) or 0)
        clicks = int(metrics.get("clicks", 0) or 0)
        conversions = float(metrics.get("conversions", 0.0) or 0.0)
        conversions_value = float(metrics.get("conversions_value", 0.0) or 0.0)
        cost_micros = int(metrics.get("cost_micros", 0) or 0)

        total_impressions += impressions
        total_clicks += clicks
        total_conversions += conversions
        total_conversion_value += conversions_value
        total_cost_micros += cost_micros

        # Store daily breakdown
        cost_dollars = cost_micros / 1_000_000
        daily_ctr = clicks / impressions if impressions > 0 else 0.0
        daily_roas = conversions_value / cost_dollars if cost_dollars > 0 else 0.0

        daily_data.append(
            {
                "date": segments.get("date", ""),
                "impressions": impressions,
                "clicks": clicks,
                "ctr": daily_ctr,
                "conversions": int(conversions),
                "conversion_value": conversions_value,
                "cost": cost_dollars,
                "roas": daily_roas,
            }
        )

    # Calculate aggregate metrics
    total_cost = total_cost_micros / 1_000_000
    ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
    roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

    return {
        "impressions": total_impressions,
        "clicks": total_clicks,
        "ctr": ctr,
        "conversions": int(total_conversions),
        "conversion_value": total_conversion_value,
        "cost": total_cost,
        "roas": roas,
        "daily_data": daily_data,
    }


def fetch_batch_product_performance(
    offer_ids: list[str],
    start_date: str,
    end_date: str,
    *,
    customer_id: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch performance metrics for multiple products in a single query.

    More efficient than calling fetch_product_performance() for each product.

    Args:
        offer_ids: List of product offer IDs.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        customer_id: Google Ads customer ID.

    Returns:
        Dictionary mapping offer_id to performance metrics.
    """
    customer_id = customer_id or _truthy_env("GOOGLE_ADS_CUSTOMER_ID")

    if not _api_enabled():
        logger.warning("Google Ads API is not enabled for batch performance fetch.")
        return {oid: _empty_performance_result() for oid in offer_ids}

    if not customer_id:
        raise ValueError("GOOGLE_ADS_CUSTOMER_ID is required for batch performance.")

    if not offer_ids:
        return {}

    try:
        client = _load_client()
    except Exception as e:
        logger.error("Failed to load Google Ads client: %s", e)
        raise ValueError(f"Failed to load Google Ads client: {e}") from e

    # Chunk offer IDs to prevent oversized IN() clause (Bug 1: Phase 16)
    # 250+ IDs in a single GAQL query causes the Google Ads API to hang indefinitely.
    # Chunking into groups of 25 keeps each query fast (~2-5 seconds).
    safe_ids = [oid.replace("'", "\\'") for oid in offer_ids]

    grouped: dict[str, list[dict]] = defaultdict(list)

    for chunk in _chunks(safe_ids, OFFER_ID_CHUNK_SIZE):
        ids_clause = ", ".join(f"'{oid}'" for oid in chunk)

        query = f"""
        SELECT
          segments.product_item_id,
          segments.date,
          campaign.advertising_channel_type,
          metrics.impressions,
          metrics.clicks,
          metrics.ctr,
          metrics.conversions,
          metrics.conversions_value,
          metrics.cost_micros
        FROM shopping_performance_view
        WHERE
          segments.product_item_id IN ({ids_clause})
          AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY segments.product_item_id, segments.date
        """

        try:
            rows = _run_gaql_query(client, customer_id, query)
            logger.info("Chunk of %d IDs returned %d rows", len(chunk), len(rows))
        except Exception as e:
            logger.error("Failed to fetch chunk of %d IDs: %s", len(chunk), e)
            # Continue with remaining chunks — partial data is better than none
            continue

        for row in rows:
            segments = row.get("segments", {})
            product_id = segments.get("product_item_id", "")
            if product_id:
                grouped[product_id].append(row)

    # Aggregate each product's metrics
    results: dict[str, dict[str, Any]] = {}
    for offer_id in offer_ids:
        product_rows = grouped.get(offer_id, [])
        if not product_rows:
            results[offer_id] = _empty_performance_result()
            continue

        total_impressions = 0
        total_clicks = 0
        total_conversions = 0.0
        total_conversion_value = 0.0
        total_cost_micros = 0
        daily_data: list[dict] = []

        for row in product_rows:
            segments = row.get("segments", {})
            metrics = row.get("metrics", {})

            impressions = int(metrics.get("impressions", 0) or 0)
            clicks = int(metrics.get("clicks", 0) or 0)
            conversions = float(metrics.get("conversions", 0.0) or 0.0)
            conversions_value = float(metrics.get("conversions_value", 0.0) or 0.0)
            cost_micros = int(metrics.get("cost_micros", 0) or 0)

            total_impressions += impressions
            total_clicks += clicks
            total_conversions += conversions
            total_conversion_value += conversions_value
            total_cost_micros += cost_micros

            cost_dollars = cost_micros / 1_000_000
            daily_ctr = clicks / impressions if impressions > 0 else 0.0
            daily_roas = conversions_value / cost_dollars if cost_dollars > 0 else 0.0

            daily_data.append(
                {
                    "date": segments.get("date", ""),
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr": daily_ctr,
                    "conversions": int(conversions),
                    "conversion_value": conversions_value,
                    "cost": cost_dollars,
                    "roas": daily_roas,
                }
            )

        total_cost = total_cost_micros / 1_000_000
        ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

        results[offer_id] = {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "ctr": ctr,
            "conversions": int(total_conversions),
            "conversion_value": total_conversion_value,
            "cost": total_cost,
            "roas": roas,
            "daily_data": daily_data,
        }

    return results
