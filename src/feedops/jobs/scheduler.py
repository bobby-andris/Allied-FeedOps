"""Job scheduling functions for incremental refresh and automation.

This module provides stale SKU detection and job configuration builders
for automated daily sync operations.

Functions:
- get_all_active_skus(): Returns all distinct master_sku values from variant_index
- get_stale_skus(): Identifies SKUs whose data is older than threshold (efficient SQL)
- build_incremental_job_config(): Builds job config for incremental refresh mode
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
DEFAULT_PAGE_SIZE = 1000


def _iter_table_rows(
    client,
    table_name: str,
    columns: str,
    *,
    order_by: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
):
    """Yield table rows using paginated Supabase queries.

    Supabase PostgREST defaults to a page limit, so callers must explicitly
    paginate to avoid silently truncating large datasets.
    """
    offset = 0
    while True:
        query = client.table(table_name).select(columns)
        if order_by:
            query = query.order(order_by, desc=False)
        result = query.range(offset, offset + page_size - 1).execute()
        rows = result.data or []
        if not rows:
            break
        for row in rows:
            yield row
        if len(rows) < page_size:
            break
        offset += page_size


def get_all_active_skus() -> list[str]:
    """Get all active master SKUs from variant_index.

    Returns:
        Sorted list of distinct master_sku strings
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    # Deduplicate and sort after reading all pages (default Supabase page is limited).
    skus = sorted(
        {
            row["master_sku"]
            for row in _iter_table_rows(
                client,
                "variant_index",
                "master_sku",
                order_by="master_sku",
            )
            if row.get("master_sku")
        }
    )
    logger.info(f"Found {len(skus)} active master SKUs")

    return skus


def get_stale_skus(days_threshold: int = 7) -> list[str]:
    """Identify SKUs whose data is older than threshold using efficient SQL.

    A SKU is considered stale if ANY of its data sources is older than the threshold
    or missing entirely:
    - search_queries.collected_at
    - performance_baselines.created_at (not captured_at - that field doesn't exist)

    Uses SQL aggregation to avoid per-SKU loops for performance.

    Args:
        days_threshold: Number of days before data is considered stale (default 7)

    Returns:
        List of stale master_sku strings

    Algorithm:
    1. Get all active SKUs from variant_index
    2. For each data source, find SKUs with MAX(timestamp) < cutoff OR no rows
    3. Union all stale SKU sets
    4. Return sorted list
    """
    from feedops.db.supabase_client import get_client

    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_threshold)).isoformat()

    logger.info(f"Detecting stale SKUs with threshold {days_threshold} days (cutoff: {cutoff})")

    # Get all active SKUs
    all_skus = set(get_all_active_skus())
    stale_skus = set()

    # Check search_queries (uses collected_at column)
    try:
        search_freshness: dict[str, str | None] = {}
        for row in _iter_table_rows(
            client,
            "search_queries",
            "master_sku,fetched_at,collected_at",
            order_by="master_sku",
        ):
            sku = row.get("master_sku")
            if not sku:
                continue

            # Prefer fetched_at (actual API pull timestamp), fallback to collected_at.
            freshness_ts = row.get("fetched_at") or row.get("collected_at")
            if sku not in search_freshness or (
                freshness_ts and freshness_ts > search_freshness.get(sku, "")
            ):
                search_freshness[sku] = freshness_ts

        # Find stale or missing
        search_stale = set()
        for sku in all_skus:
            if sku not in search_freshness or not search_freshness[sku] or search_freshness[sku] < cutoff:
                search_stale.add(sku)
        stale_skus.update(search_stale)

        logger.info(f"Search queries: {len(search_stale)} SKUs stale or missing")
    except Exception as e:
        logger.warning(f"Error checking search_queries freshness: {e}")

    # Check performance_baselines (uses created_at, not captured_at)
    try:
        baseline_freshness: dict[str, str | None] = {}
        for row in _iter_table_rows(
            client,
            "performance_baselines",
            "master_sku,created_at",
            order_by="master_sku",
        ):
            sku = row.get("master_sku")
            if not sku:
                continue
            created_at = row.get("created_at")
            if sku not in baseline_freshness or (
                created_at and created_at > baseline_freshness.get(sku, "")
            ):
                baseline_freshness[sku] = created_at

        baseline_stale = set()
        for sku in all_skus:
            if sku not in baseline_freshness or not baseline_freshness[sku] or baseline_freshness[sku] < cutoff:
                baseline_stale.add(sku)

        stale_skus.update(baseline_stale)
        logger.info(f"Performance baselines: {len(baseline_stale)} SKUs stale or missing")
    except Exception as e:
        logger.warning(f"Error checking performance_baselines freshness: {e}")

    # Return sorted list
    stale_list = sorted(stale_skus)
    logger.info(f"Total stale SKUs: {len(stale_list)}")

    return stale_list


def build_incremental_job_config(days_lookback: int = 1) -> dict:
    """Build job configuration for incremental refresh mode.

    Calls get_stale_skus() to identify SKUs needing refresh and builds
    a ready-to-use job configuration dict.

    Args:
        days_lookback: Number of days to look back for stale detection (default 1)

    Returns:
        Dict with keys:
        - skus: List of stale master SKU strings (may be empty)
        - config: Job config with days_lookback, batch_size, mode
        - job_type: Always "full_backfill"

    Note:
        If no stale SKUs found, returns empty skus list. Caller should
        skip job creation in this case.
    """
    stale_skus = get_stale_skus(days_threshold=days_lookback)

    config = {
        "days_lookback": days_lookback,
        "batch_size": 50,
        "mode": "incremental",
    }

    logger.info(f"Built incremental job config: {len(stale_skus)} SKUs, {days_lookback} days lookback")

    return {
        "skus": stale_skus,
        "config": config,
        "job_type": "full_backfill",
    }
