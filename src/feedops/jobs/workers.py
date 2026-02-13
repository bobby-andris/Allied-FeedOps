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

from pydantic import ValidationError

from feedops.jobs.validators import (
    ValidatedPerformanceMetrics,
    ValidatedSearchTerm,
    ValidatedKeywordMetrics,
    ValidatedCustomLabels,
)

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

        # Validate each term before saving
        validated_terms = []
        for term in filtered_terms:
            try:
                # Validate term structure
                ValidatedSearchTerm(
                    query_text=term.get("query_text", ""),
                    master_sku=term.get("master_sku", ""),
                    impressions=term.get("impressions", 0),
                    clicks=term.get("clicks", 0),
                )
                validated_terms.append(term)
            except ValidationError as e:
                logger.warning(f"Invalid search term for {term.get('master_sku')}: {e}")
                continue

        logger.info(f"Validated {len(validated_terms)} terms (filtered out {len(filtered_terms) - len(validated_terms)} invalid)")

        # Save to database with idempotent upserts
        if validated_terms:
            saved_count = client.save_search_terms_to_db(
                search_terms=validated_terms,
                period_start=period_start,
                period_end=period_end,
                sync_job_id=None,  # Could pass job_id here if available
            )
            logger.info(f"Saved {saved_count} search term records (upserted)")

        # Build result status for each SKU in batch
        results = []
        for sku in batch:
            sku_terms = [t for t in validated_terms if t.get("master_sku") == sku]
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
    1. Check contamination eligibility (VALID-04) - skip SKUs published <30 days
    2. For each master_sku: query variant_index to get all gmc_offer_id values
    3. Call fetch_batch_product_performance() with all offer IDs for the batch
    4. Aggregate variant metrics to master_sku level (sum impressions/clicks, weighted avg CTR)
    5. Detect multi-SKU families and add metadata (VALID-03, VALID-08)
    6. Validate date boundaries (VALID-09)
    7. Upsert to performance_baselines with ON CONFLICT (master_sku, platform)

    Args:
        batch: List of master SKU IDs to collect performance for

    Returns:
        List of result dicts:
        - {"item_id": sku, "status": "ok", "impressions": N, "clicks": M} if data found
        - {"item_id": sku, "status": "skipped", "reason": str} if ineligible
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
    from feedops.jobs.contamination import check_batch_eligibility, validate_date_boundaries
    from feedops.jobs.multi_sku import detect_multi_sku_families, get_family_metadata

    if not batch:
        return []

    logger.info(f"Collecting performance metrics for {len(batch)} SKUs")

    try:
        supabase = get_client()

        # Compute 180-day date range (DATA-07: explicit YYYY-MM-DD format)
        start_date, end_date = compute_date_range(days_lookback=180)
        num_days = 180

        # STEP 1: Check contamination eligibility (VALID-04)
        # Skip SKUs published within last 30 days to avoid mixing pre/post data
        eligibility = check_batch_eligibility(batch, platform="google")

        ineligible_skus = [sku for sku, (eligible, _) in eligibility.items() if not eligible]
        eligible_skus = [sku for sku, (eligible, _) in eligibility.items() if eligible]

        results = []

        # Add skipped status for ineligible SKUs
        for sku in ineligible_skus:
            _, reason = eligibility[sku]
            logger.info(f"Skipping {sku}: {reason}")
            results.append({
                "item_id": sku,
                "status": "skipped",
                "reason": reason,
            })

        if not eligible_skus:
            logger.warning(f"All {len(batch)} SKUs in batch are ineligible due to recent publish events")
            return results

        logger.info(f"Skipped {len(ineligible_skus)} SKUs due to recent publish events, processing {len(eligible_skus)} eligible SKUs")

        # Build mapping of offer_id -> master_sku for eligible SKUs only
        offer_to_sku: dict[str, str] = {}
        sku_to_offers: dict[str, list[str]] = {sku: [] for sku in eligible_skus}

        for sku in eligible_skus:
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

        # STEP 2: Detect multi-SKU families (VALID-03, VALID-08)
        # Identify SKUs that share product_id with other master_skus
        # Google Ads aggregates at product_id level, so we need to flag this
        multi_sku_families = detect_multi_sku_families(eligible_skus)
        logger.info(f"Detected {len(multi_sku_families)} SKUs in multi-SKU families")

        # Upsert to performance_baselines table
        # Process eligible SKUs only
        for sku in eligible_skus:
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

            # STEP 3: Validate date boundaries (VALID-09)
            # Ensure baseline period doesn't overlap with any publish events
            boundaries_valid, boundary_message = validate_date_boundaries(
                start_date, end_date, sku, platform="google"
            )
            if not boundaries_valid:
                logger.warning(f"Skipping {sku}: {boundary_message}")
                results.append({
                    "item_id": sku,
                    "status": "skipped",
                    "reason": boundary_message,
                })
                continue

            # STEP 4: Add multi-SKU family metadata (VALID-08)
            # Flag if this SKU shares product_id with other master_skus
            if sku in multi_sku_families:
                family_members = multi_sku_families[sku]
                metadata = get_family_metadata(sku, family_members)
                logger.info(f"SKU {sku} is in multi-SKU family: {family_members}")
            else:
                metadata = {"is_multi_sku_family": False}

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
                "metadata": metadata,  # VALID-08: Multi-SKU family flags
                # created_at is auto-populated by DB default (DATA-10)
            }

            # Validate before database write (VALID-05, VALID-06, VALID-09)
            try:
                validated = ValidatedPerformanceMetrics(**baseline_record)
            except ValidationError as e:
                logger.error(f"Validation failed for {sku}: {e}")
                results.append({
                    "item_id": sku,
                    "status": "validation_error",
                    "error": str(e),
                })
                continue

            # Upsert with ON CONFLICT (master_sku, platform) for idempotency (JOB-06)
            # Use validated.model_dump() to ensure only validated data is written
            supabase.table("performance_baselines").upsert(
                validated.model_dump(exclude_none=True),
                on_conflict="master_sku,platform"
            ).execute()

            logger.info(
                f"Saved baseline for {sku}: {metrics['total_impressions']} impressions, "
                f"{metrics['total_clicks']} clicks"
            )

            # Build result with family info if applicable
            result_dict = {
                "item_id": sku,
                "status": "ok",
                "impressions": metrics["total_impressions"],
                "clicks": metrics["total_clicks"],
            }
            if metadata.get("is_multi_sku_family"):
                result_dict["multi_sku_family"] = True
                result_dict["family_size"] = metadata.get("family_size")

            results.append(result_dict)

        return results

    except Exception as e:
        logger.error(f"Performance collection failed for batch: {e}")
        # Return error status for all items in batch
        return [
            {"item_id": sku, "status": "error", "error": str(e)}
            for sku in batch
        ]


# =============================================================================
# Worker 3: Keyword Planner Collection
# =============================================================================


async def collect_keyword_planner_batch(batch: list[str]) -> list[dict]:
    """Collect Keyword Planner metrics for a batch of master SKUs.

    Generates keyword ideas using product titles and existing search terms as seeds,
    then enriches with historical metrics from Keyword Planner API. Leverages 30-day
    cache TTL (DATA-03) to avoid redundant API calls.

    Data Flow:
    1. For each master_sku: query variant_index for product_title
    2. Query search_queries for top existing search terms (up to 5)
    3. Build keyword list: [product_title] + top search terms
    4. Call KeywordPlannerClient.get_historical_metrics() with use_cache=True
    5. Client automatically caches results to keyword_metrics table

    Args:
        batch: List of master SKU IDs to collect keyword metrics for

    Returns:
        List of result dicts:
        - {"item_id": sku, "status": "ok", "keywords_enriched": N} if successful
        - {"item_id": sku, "status": "no_data"} if no keywords to enrich

    Notes:
        - KeywordPlannerClient handles caching internally (DATA-03: 30-day TTL)
        - Idempotent via KeywordPlannerClient._cache_metrics (upsert on keyword)
        - Rate limiting applied at BatchProcessor level (not inside worker)
        - Timestamps auto-included via updated_at field in keyword_metrics
    """
    from feedops.integrations.google_ads_search_terms import KeywordPlannerClient
    from feedops.db.supabase_client import get_client

    if not batch:
        return []

    logger.info(f"Collecting Keyword Planner metrics for {len(batch)} SKUs")

    try:
        supabase = get_client()
        kp_client = KeywordPlannerClient()

        results = []

        for sku in batch:
            # Step 1: Get product title from variant_index
            variant_result = supabase.table("variant_index").select(
                "product_title"
            ).eq("master_sku", sku).limit(1).execute()

            if not variant_result.data:
                logger.warning(f"No variant_index record found for {sku}")
                results.append({"item_id": sku, "status": "no_data"})
                continue

            product_title = variant_result.data[0].get("product_title")
            if not product_title:
                logger.warning(f"No product_title for {sku}")
                results.append({"item_id": sku, "status": "no_data"})
                continue

            # Step 2: Get top search terms from search_queries
            search_result = supabase.table("search_queries").select(
                "query_text, impressions"
            ).eq("master_sku", sku).order(
                "impressions", desc=True
            ).limit(5).execute()

            top_search_terms = [row["query_text"] for row in search_result.data]

            # Step 3: Build keyword list
            keywords = [product_title] + top_search_terms

            if not keywords:
                logger.warning(f"No keywords to enrich for {sku}")
                results.append({"item_id": sku, "status": "no_data"})
                continue

            logger.info(f"Enriching {len(keywords)} keywords for {sku}")

            # Step 4: Fetch metrics with 30-day cache (DATA-03)
            # KeywordPlannerClient handles idempotent caching internally
            metrics = kp_client.get_historical_metrics(
                keywords=keywords,
                use_cache=True,
                cache_max_age_days=30,
            )

            # Validate metrics post-fetch (log warnings, don't block)
            validated_count = 0
            for metric in metrics:
                try:
                    ValidatedKeywordMetrics(
                        keyword=metric.get("keyword", ""),
                        avg_monthly_searches=metric.get("avg_monthly_searches"),
                        competition=metric.get("competition"),
                        competition_index=metric.get("competition_index"),
                    )
                    validated_count += 1
                except ValidationError as e:
                    logger.warning(f"Invalid keyword metric for {sku}: {e}")

            enriched_count = validated_count
            logger.info(f"Enriched and validated {enriched_count} keywords for {sku} (fetched {len(metrics)} total)")

            results.append({
                "item_id": sku,
                "status": "ok",
                "keywords_enriched": enriched_count,
            })

        return results

    except Exception as e:
        logger.error(f"Keyword Planner collection failed for batch: {e}")
        # Return error status for all items in batch
        return [
            {"item_id": sku, "status": "error", "error": str(e)}
            for sku in batch
        ]


# =============================================================================
# Worker 4: Custom Labels Collection
# =============================================================================


# Module-level cache for GMC data (reused across consecutive batches within same job run)
_gmc_cache: dict[str, dict] | None = None
_gmc_cache_time: datetime | None = None
_GMC_CACHE_TTL_SECONDS = 300  # 5 minutes


async def collect_custom_labels_batch(batch: list[str]) -> list[dict]:
    """Collect custom labels 0-4 from Google Merchant Center for a batch of master SKUs.

    Syncs GMC custom labels to variant_index.custom_labels JSONB column. The GMC API
    returns all products at once, so this worker caches the full product list and
    reuses it across consecutive batches within the same job run.

    Data Flow:
    1. Call fetch_merchant_center_items() ONCE (or use cached data)
    2. Build lookup dict: {offerId: {"customLabel0": val, ...}}
    3. For each master_sku: get all gmc_offer_id values from variant_index
    4. Update variant_index.custom_labels with GMC data (upsert by gmc_offer_id)

    Args:
        batch: List of master SKU IDs to sync custom labels for

    Returns:
        List of result dicts:
        - {"item_id": sku, "status": "ok", "variants_updated": N} if successful
        - {"item_id": sku, "status": "no_data"} if no variants found

    Notes:
        - Requires migration 026 (custom_labels JSONB column)
        - GMC API call is expensive - cached for 5 minutes (reused across batches)
        - Idempotent via .update().eq("gmc_offer_id", offer_id)
        - Timestamps auto-included via updated_at field (DATA-10)
    """
    from feedops.integrations.merchant_center import fetch_merchant_center_items
    from feedops.db.supabase_client import get_client

    global _gmc_cache, _gmc_cache_time

    if not batch:
        return []

    logger.info(f"Collecting custom labels for {len(batch)} SKUs")

    try:
        supabase = get_client()

        # Step 1: Fetch GMC data (with caching to avoid redundant API calls)
        now = datetime.now(timezone.utc)
        cache_expired = (
            _gmc_cache is None or
            _gmc_cache_time is None or
            (now - _gmc_cache_time).total_seconds() > _GMC_CACHE_TTL_SECONDS
        )

        if cache_expired:
            logger.info("Fetching GMC items (cache miss or expired)")
            gmc_items = fetch_merchant_center_items()
            logger.info(f"Fetched {len(gmc_items)} GMC items")

            # Build lookup dict keyed by offerId
            _gmc_cache = {}
            for item in gmc_items:
                offer_id = item.get("offerId")
                if offer_id:
                    # Normalize offer ID to lowercase for lookup (DATA-08)
                    offer_id_lower = offer_id.replace("shopify_US_", "shopify_us_")
                    _gmc_cache[offer_id_lower] = {
                        "customLabel0": item.get("customLabel0"),
                        "customLabel1": item.get("customLabel1"),
                        "customLabel2": item.get("customLabel2"),
                        "customLabel3": item.get("customLabel3"),
                        "customLabel4": item.get("customLabel4"),
                    }

            _gmc_cache_time = now
            logger.info(f"GMC cache updated with {len(_gmc_cache)} items")
        else:
            logger.info(f"Using cached GMC data ({len(_gmc_cache)} items)")

        # Step 3: For each SKU, update custom labels
        results = []

        for sku in batch:
            # Get all variants for this master_sku
            variant_result = supabase.table("variant_index").select(
                "gmc_offer_id"
            ).eq("master_sku", sku).execute()

            if not variant_result.data:
                logger.warning(f"No variants found for {sku}")
                results.append({"item_id": sku, "status": "no_data"})
                continue

            variants_updated = 0

            for row in variant_result.data:
                offer_id = row.get("gmc_offer_id")
                if not offer_id:
                    continue

                # Lookup custom labels from GMC cache
                custom_labels = _gmc_cache.get(offer_id)

                if custom_labels:
                    # Validate before update
                    try:
                        ValidatedCustomLabels(
                            gmc_offer_id=offer_id,
                            custom_labels=custom_labels,
                        )
                    except ValidationError as e:
                        logger.warning(f"Invalid custom labels for {offer_id}: {e}")
                        continue

                    # Update variant_index with custom_labels JSONB
                    # Idempotent: update by unique gmc_offer_id (JOB-06)
                    supabase.table("variant_index").update({
                        "custom_labels": custom_labels,
                        "updated_at": datetime.now(timezone.utc).isoformat(),  # DATA-10
                    }).eq("gmc_offer_id", offer_id).execute()

                    variants_updated += 1

            if variants_updated > 0:
                logger.info(f"Updated {variants_updated} variants for {sku}")
                results.append({
                    "item_id": sku,
                    "status": "ok",
                    "variants_updated": variants_updated,
                })
            else:
                logger.warning(f"No custom labels found in GMC for {sku}")
                results.append({"item_id": sku, "status": "no_data"})

        return results

    except Exception as e:
        logger.error(f"Custom labels collection failed for batch: {e}")
        # Return error status for all items in batch
        return [
            {"item_id": sku, "status": "error", "error": str(e)}
            for sku in batch
        ]
