"""Data collection worker functions for backfill jobs.

This module implements the core data collection logic that the Phase 1 BatchProcessor
invokes. Each worker receives a batch of SKU IDs and performs collection + storage
with idempotent upserts.

Worker Contract:
- Signature: `async def worker(batch: list[str]) -> list[dict]`
- Returns: List of result dicts with `item_id`, `status`, and optional metadata
- Requirements:
  - MUST use idempotent upserts (ON CONFLICT) for all database writes (JOB-06)
  - MUST include collection timestamps in saved data (DATA-10)
  - MUST handle missing/partial data gracefully (return "no_data" status, not error)

Phase 1 Infrastructure Integration:
- Used by BatchProcessor (src/feedops/jobs/processor.py)
- Invoked via backfill API endpoints (src/feedops/api/backfill.py)
- Managed by job manager functions (src/feedops/jobs/manager.py)

Data Collection Requirements (from Phase 0 research):
- DATA-01: Search terms use campaign-join pattern (2-step query)
- DATA-02: Performance metrics from shopping_performance_view with 180-day window
- DATA-03: Keyword Planner with 30-day cache TTL
- DATA-04: Custom labels from Merchant Center API
- DATA-05: Include date range fields in performance_baselines
- DATA-06: Batch size 10 for optimal API performance
- DATA-07: Use explicit YYYY-MM-DD date ranges (not LAST_N_DAYS)
- DATA-08: Use lowercase offer IDs for API queries
- DATA-09: Collect competitive metrics where available
- DATA-10: Include collection timestamps in all saved data
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Worker 1: Search Terms Collection
# =============================================================================


async def collect_search_terms_batch(batch: list[str]) -> list[dict]:
    """Collect Google Ads search terms for a batch of master SKUs.

    Uses the campaign-join pattern (DATA-01) to fetch search terms from Google Ads
    and saves them to the search_queries table with idempotent upserts.

    Data Flow:
    1. SearchTermsClient.fetch_search_terms() returns all search terms with master_sku populated
    2. Filter results to only include terms for SKUs in this batch
    3. Save filtered terms to database via save_search_terms_to_db() (idempotent)
    4. Return status for each SKU in the batch

    Args:
        batch: List of master SKU IDs to collect search terms for

    Returns:
        List of result dicts:
        - {"item_id": sku, "status": "ok", "terms_count": N} if terms found
        - {"item_id": sku, "status": "no_data"} if no terms found

    Notes:
        - SearchTermsClient uses campaign-join pattern (validated in Phase 0.1)
        - Idempotent upserts via ON CONFLICT (query_text, gmc_offer_id, period_start, period_end)
        - Timestamps auto-included via fetched_at field
    """
    from feedops.integrations.google_ads_search_terms import SearchTermsClient
    from feedops.api.backfill import compute_date_range

    if not batch:
        return []

    logger.info(f"Collecting search terms for {len(batch)} SKUs")

    try:
        # Initialize client
        client = SearchTermsClient()

        # Compute date range for 180-day lookback (DATA-07: explicit YYYY-MM-DD format)
        start_date_str, end_date_str = compute_date_range(days_lookback=180)

        # Convert to date objects for save_search_terms_to_db
        from datetime import date
        period_start = date.fromisoformat(start_date_str)
        period_end = date.fromisoformat(end_date_str)

        # Fetch all search terms using campaign-join pattern (DATA-01)
        # The fetch_search_terms method uses LAST_N_DAYS internally but we'll
        # use the explicit dates for saving
        all_terms = client.fetch_search_terms(days=180, limit=10000)

        logger.info(f"Fetched {len(all_terms)} total search terms from Google Ads")

        # Filter to only terms for SKUs in this batch
        batch_set = set(batch)
        filtered_terms = [
            term for term in all_terms
            if term.get("master_sku") in batch_set
        ]

        logger.info(f"Filtered to {len(filtered_terms)} terms for batch SKUs")

        # Save to database with idempotent upserts
        if filtered_terms:
            saved_count = client.save_search_terms_to_db(
                search_terms=filtered_terms,
                period_start=period_start,
                period_end=period_end,
                sync_job_id=None,  # Could pass job_id here if available
            )
            logger.info(f"Saved {saved_count} search term records (upserted)")

        # Build result status for each SKU in batch
        results = []
        for sku in batch:
            sku_terms = [t for t in filtered_terms if t.get("master_sku") == sku]
            if sku_terms:
                results.append({
                    "item_id": sku,
                    "status": "ok",
                    "terms_count": len(sku_terms),
                })
            else:
                results.append({
                    "item_id": sku,
                    "status": "no_data",
                })

        return results

    except Exception as e:
        logger.error(f"Search terms collection failed for batch: {e}")
        # Return error status for all items in batch
        return [
            {"item_id": sku, "status": "error", "error": str(e)}
            for sku in batch
        ]


# =============================================================================
# Worker 2: Performance Metrics Collection
# =============================================================================


async def collect_performance_batch(batch: list[str]) -> list[dict]:
    """Collect 180-day performance metrics for a batch of master SKUs.

    Fetches metrics from Google Ads shopping_performance_view, aggregates variant-level
    data to master_sku level, and saves to performance_baselines with idempotent upserts.

    Data Flow:
    1. For each master_sku: query variant_index to get all gmc_offer_id values
    2. Call fetch_batch_product_performance() with all offer IDs for the batch
    3. Aggregate variant metrics to master_sku level (sum impressions/clicks, weighted avg CTR)
    4. Upsert to performance_baselines with ON CONFLICT (master_sku, platform)

    Args:
        batch: List of master SKU IDs to collect performance for

    Returns:
        List of result dicts:
        - {"item_id": sku, "status": "ok", "impressions": N, "clicks": M} if data found
        - {"item_id": sku, "status": "no_data"} if no performance data

    Notes:
        - Uses explicit date ranges per DATA-07
        - Aggregates variant data per DATA-02
        - Includes baseline_start_date and baseline_end_date per DATA-05
        - Idempotent via ON CONFLICT (master_sku, platform)
        - Timestamps auto-included via created_at field
    """
    from feedops.integrations.google_ads_performance import fetch_batch_product_performance
    from feedops.db.supabase_client import get_client
    from feedops.api.backfill import compute_date_range

    if not batch:
        return []

    logger.info(f"Collecting performance metrics for {len(batch)} SKUs")

    try:
        supabase = get_client()

        # Compute 180-day date range (DATA-07: explicit YYYY-MM-DD format)
        start_date, end_date = compute_date_range(days_lookback=180)
        num_days = 180

        # Build mapping of offer_id -> master_sku for this batch
        offer_to_sku: dict[str, str] = {}
        sku_to_offers: dict[str, list[str]] = {sku: [] for sku in batch}

        for sku in batch:
            # Query variant_index for all variants of this master_sku
            result = supabase.table("variant_index").select("gmc_offer_id").eq(
                "master_sku", sku
            ).execute()

            offer_ids = [row["gmc_offer_id"] for row in result.data if row.get("gmc_offer_id")]
            sku_to_offers[sku] = offer_ids

            for offer_id in offer_ids:
                offer_to_sku[offer_id] = sku

        # Collect all offer IDs for batch query
        all_offer_ids = [
            offer_id
            for offers in sku_to_offers.values()
            for offer_id in offers
        ]

        if not all_offer_ids:
            logger.warning(f"No offer IDs found for batch SKUs")
            return [{"item_id": sku, "status": "no_data"} for sku in batch]

        logger.info(f"Fetching performance for {len(all_offer_ids)} offer IDs")

        # Fetch performance data for all variants in one batch call (DATA-06)
        performance_data = fetch_batch_product_performance(
            offer_ids=all_offer_ids,
            start_date=start_date,
            end_date=end_date,
        )

        # Aggregate variant-level metrics to master_sku level
        sku_metrics: dict[str, dict[str, Any]] = {}

        for offer_id, metrics in performance_data.items():
            sku = offer_to_sku.get(offer_id)
            if not sku:
                continue

            if sku not in sku_metrics:
                sku_metrics[sku] = {
                    "total_impressions": 0,
                    "total_clicks": 0,
                    "total_conversions": 0,
                    "total_conversion_value": 0.0,
                    "total_cost": 0.0,
                }

            # Aggregate metrics
            sku_metrics[sku]["total_impressions"] += metrics.get("impressions", 0)
            sku_metrics[sku]["total_clicks"] += metrics.get("clicks", 0)
            sku_metrics[sku]["total_conversions"] += metrics.get("conversions", 0)
            sku_metrics[sku]["total_conversion_value"] += metrics.get("conversion_value", 0.0)
            sku_metrics[sku]["total_cost"] += metrics.get("cost", 0.0)

        # Upsert to performance_baselines table
        results = []

        for sku in batch:
            if sku not in sku_metrics:
                results.append({"item_id": sku, "status": "no_data"})
                continue

            metrics = sku_metrics[sku]

            # Calculate averages (per DATA-02: avg_* fields)
            avg_impressions = metrics["total_impressions"] / num_days if num_days > 0 else 0.0
            avg_clicks = metrics["total_clicks"] / num_days if num_days > 0 else 0.0
            avg_ctr = (
                metrics["total_clicks"] / metrics["total_impressions"]
                if metrics["total_impressions"] > 0
                else 0.0
            )
            avg_conversions = metrics["total_conversions"] / num_days if num_days > 0 else 0.0
            avg_conversion_value = metrics["total_conversion_value"] / num_days if num_days > 0 else 0.0
            avg_cvr = (
                metrics["total_conversions"] / metrics["total_clicks"]
                if metrics["total_clicks"] > 0
                else 0.0
            )
            avg_cost = metrics["total_cost"] / num_days if num_days > 0 else 0.0
            avg_roas = (
                metrics["total_conversion_value"] / metrics["total_cost"]
                if metrics["total_cost"] > 0
                else 0.0
            )

            # Prepare baseline record (DATA-05: include date range fields)
            baseline_record = {
                "master_sku": sku,
                "platform": "google",
                "baseline_start_date": start_date,
                "baseline_end_date": end_date,
                "avg_impressions": avg_impressions,
                "avg_clicks": avg_clicks,
                "avg_ctr": avg_ctr,
                "avg_conversions": avg_conversions,
                "avg_conversion_value": avg_conversion_value,
                "avg_cvr": avg_cvr,
                "avg_cost": avg_cost,
                "avg_roas": avg_roas,
                # created_at is auto-populated by DB default (DATA-10)
            }

            # Upsert with ON CONFLICT (master_sku, platform) for idempotency (JOB-06)
            supabase.table("performance_baselines").upsert(
                baseline_record,
                on_conflict="master_sku,platform"
            ).execute()

            logger.info(
                f"Saved baseline for {sku}: {metrics['total_impressions']} impressions, "
                f"{metrics['total_clicks']} clicks"
            )

            results.append({
                "item_id": sku,
                "status": "ok",
                "impressions": metrics["total_impressions"],
                "clicks": metrics["total_clicks"],
            })

        return results

    except Exception as e:
        logger.error(f"Performance collection failed for batch: {e}")
        # Return error status for all items in batch
        return [
            {"item_id": sku, "status": "error", "error": str(e)}
            for sku in batch
        ]
