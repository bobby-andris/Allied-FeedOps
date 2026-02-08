"""Performance Baseline API endpoints for Cloud Run.

Provides endpoints for capturing and querying baseline performance metrics
for master SKUs across platforms (Google Ads, Bing, Shopify).
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.integrations.google_ads_performance import (
    fetch_batch_product_performance,
    _load_client,
    _run_gaql_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance Baselines"])


# =============================================================================
# Request/Response Models
# =============================================================================


class CaptureBaselineRequest(BaseModel):
    """Request to capture performance baselines for master SKUs."""

    master_skus: list[str] = Field(
        ..., min_length=1, max_length=100, description="Master SKUs to capture baselines for"
    )
    days_lookback: int = Field(
        default=30, ge=7, le=90, description="Days of historical data to fetch"
    )
    platforms: list[Literal["google", "bing", "shopify"]] = Field(
        default=["google"], description="Platforms to capture baselines for"
    )


class CaptureBaselineResponse(BaseModel):
    """Response from baseline capture endpoint."""

    success: bool
    message: str
    skus_processed: int
    skus_with_data: int
    platforms: list[str]
    errors: list[str] | None = None


class BaselineStatusResponse(BaseModel):
    """Response from baseline status endpoint."""

    master_sku: str
    platforms: dict[str, dict]  # platform -> baseline metrics
    last_updated: str | None


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/capture-baseline", response_model=CaptureBaselineResponse)
async def capture_baseline(request: CaptureBaselineRequest):
    """Capture performance baselines for master SKUs.

    Fetches historical performance data (30-day default) from Google Ads
    and calculates average metrics for baseline comparison.

    Steps:
    1. Get all variants for each master SKU from variant_index
    2. Fetch performance data for variants from Google Ads
    3. Aggregate metrics by master SKU and platform
    4. Insert/update performance_baselines table
    """
    try:
        supabase = get_client()
        end_date = date.today()
        start_date = end_date - timedelta(days=request.days_lookback)

        skus_processed = 0
        skus_with_data = 0
        errors = []

        for master_sku in request.master_skus:
            try:
                # Get all variants (offer_ids) for this master SKU
                variant_result = supabase.table("variant_index").select(
                    "gmc_offer_id"
                ).eq("master_sku", master_sku).execute()

                if not variant_result.data:
                    logger.warning(f"No variants found for master_sku={master_sku}")
                    errors.append(f"{master_sku}: No variants found")
                    continue

                offer_ids = [v["gmc_offer_id"] for v in variant_result.data if v.get("gmc_offer_id")]

                if not offer_ids:
                    logger.warning(f"No GMC offer IDs found for master_sku={master_sku}")
                    errors.append(f"{master_sku}: No GMC offer IDs")
                    continue

                # Process Google platform
                if "google" in request.platforms:
                    google_metrics = _capture_google_baseline(
                        supabase=supabase,
                        master_sku=master_sku,
                        offer_ids=offer_ids,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                    )

                    if google_metrics and google_metrics.get("impressions", 0) > 0:
                        skus_with_data += 1

                # TODO: Add Bing and Shopify platform support when needed

                skus_processed += 1

            except Exception as e:
                logger.error(f"Failed to capture baseline for {master_sku}: {e}")
                errors.append(f"{master_sku}: {str(e)}")

        return CaptureBaselineResponse(
            success=True,
            message=f"Processed {skus_processed} SKUs, {skus_with_data} with performance data",
            skus_processed=skus_processed,
            skus_with_data=skus_with_data,
            platforms=request.platforms,
            errors=errors if errors else None,
        )

    except Exception as e:
        logger.error(f"Baseline capture failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/baseline/{master_sku}", response_model=BaselineStatusResponse)
async def get_baseline_status(master_sku: str):
    """Get baseline status for a master SKU."""
    try:
        supabase = get_client()

        # Fetch baselines for all platforms
        result = supabase.table("performance_baselines").select("*").eq(
            "master_sku", master_sku
        ).execute()

        if not result.data:
            return BaselineStatusResponse(
                master_sku=master_sku,
                platforms={},
                last_updated=None,
            )

        # Group by platform
        platforms = {}
        last_updated = None

        for baseline in result.data:
            platform = baseline["platform"]
            platforms[platform] = {
                "avg_impressions": baseline.get("avg_impressions", 0),
                "avg_clicks": baseline.get("avg_clicks", 0),
                "avg_ctr": baseline.get("avg_ctr", 0.0),
                "avg_conversions": baseline.get("avg_conversions", 0),
                "avg_cost": baseline.get("avg_cost", 0.0),
                "avg_roas": baseline.get("avg_roas", 0.0),
                "baseline_start_date": baseline.get("baseline_start_date"),
                "baseline_end_date": baseline.get("baseline_end_date"),
            }

            # Track most recent update
            updated_at = baseline.get("updated_at") or baseline.get("created_at")
            if updated_at:
                if not last_updated or updated_at > last_updated:
                    last_updated = updated_at

        return BaselineStatusResponse(
            master_sku=master_sku,
            platforms=platforms,
            last_updated=last_updated,
        )

    except Exception as e:
        logger.error(f"Failed to get baseline status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Helper Functions
# =============================================================================


def _capture_google_baseline(
    supabase,
    master_sku: str,
    offer_ids: list[str],
    start_date: str,
    end_date: str,
) -> dict:
    """Capture Google Ads baseline for a master SKU.

    Args:
        supabase: Supabase client
        master_sku: Master SKU identifier
        offer_ids: List of GMC offer IDs for all variants
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dictionary with aggregated metrics
    """
    try:
        # Check if API is enabled
        api_enabled = os.getenv("GOOGLE_ADS_API_ENABLED", "").lower() in {"1", "true", "yes"}
        if not api_enabled:
            logger.warning("Google Ads API not enabled, skipping Google baseline")
            return {}

        # Fetch performance data for all variants
        performance_data = fetch_batch_product_performance(
            offer_ids=offer_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if not performance_data:
            logger.warning(f"No performance data returned for {master_sku}")
            return {}

        # Aggregate metrics across all variants
        total_impressions = 0
        total_clicks = 0
        total_conversions = 0
        total_conversion_value = 0.0
        total_cost = 0.0
        variants_with_data = 0

        for offer_id, metrics in performance_data.items():
            if metrics.get("impressions", 0) > 0:
                variants_with_data += 1
                total_impressions += metrics.get("impressions", 0)
                total_clicks += metrics.get("clicks", 0)
                total_conversions += metrics.get("conversions", 0)
                total_conversion_value += metrics.get("conversion_value", 0.0)
                total_cost += metrics.get("cost", 0.0)

        if variants_with_data == 0:
            logger.info(f"No performance data found for {master_sku} in date range")
            return {}

        # Calculate averages
        avg_impressions = total_impressions / variants_with_data
        avg_clicks = total_clicks / variants_with_data
        avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        avg_conversions = total_conversions / variants_with_data
        avg_cost = total_cost / variants_with_data
        avg_roas = total_conversion_value / total_cost if total_cost > 0 else 0.0

        # Calculate CVR (conversion rate)
        avg_cvr = total_conversions / total_clicks if total_clicks > 0 else 0.0

        # Insert or update baseline
        baseline_data = {
            "master_sku": master_sku,
            "platform": "google",
            "avg_impressions": round(avg_impressions, 2),
            "avg_clicks": round(avg_clicks, 2),
            "avg_ctr": round(avg_ctr, 4),
            "avg_conversions": round(avg_conversions, 2),
            "avg_cvr": round(avg_cvr, 4),
            "avg_cost": round(avg_cost, 2),
            "avg_roas": round(avg_roas, 2),
            "baseline_start_date": start_date,
            "baseline_end_date": end_date,
        }

        # Upsert baseline
        supabase.table("performance_baselines").upsert(
            baseline_data,
            on_conflict="master_sku,platform",
        ).execute()

        logger.info(
            f"Captured Google baseline for {master_sku}: "
            f"{avg_impressions:.0f} impr, {avg_clicks:.0f} clicks, {avg_ctr:.2%} CTR"
        )

        return baseline_data

    except Exception as e:
        logger.error(f"Failed to capture Google baseline for {master_sku}: {e}")
        raise


@router.get("/diagnose-products")
async def diagnose_products():
    """Check what products actually exist in Google Ads with impressions.

    This endpoint queries Google Ads for ANY products with impressions
    in the last 7 days, regardless of whether they're in our database.

    Use this to:
    1. Verify products are active in Google Ads campaigns
    2. Check if offer IDs match our variant_index format
    3. See what campaign types are returning data
    """
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")

        if not customer_id:
            raise HTTPException(status_code=500, detail="GOOGLE_ADS_CUSTOMER_ID not set")

        client = _load_client()

        # Query for ANY products with impressions (no product filter)
        query = f"""
        SELECT
          segments.product_item_id,
          campaign.advertising_channel_type,
          campaign.name,
          metrics.impressions,
          metrics.clicks
        FROM shopping_performance_view
        WHERE
          segments.date BETWEEN '{start_date}' AND '{end_date}'
          AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 50
        """

        rows = _run_gaql_query(client, customer_id, query)

        if not rows:
            return {
                "error": "NO products found with impressions in Google Ads",
                "date_range": f"{start_date} to {end_date}",
                "possible_reasons": [
                    "No active Shopping or Performance Max campaigns",
                    "No products have impressions in date range",
                    "Customer ID is incorrect"
                ],
                "products": [],
            }

        # Analyze what we found
        campaign_types = defaultdict(int)
        products = []
        our_format_count = 0

        for row in rows[:50]:
            segments = row.get("segments", {})
            campaign = row.get("campaign", {})
            metrics = row.get("metrics", {})

            product_id = segments.get("product_item_id", "")
            campaign_type = campaign.get("advertising_channel_type", "UNKNOWN")
            impressions = int(metrics.get("impressions", 0) or 0)
            clicks = int(metrics.get("clicks", 0) or 0)

            campaign_types[campaign_type] += 1

            if "shopify_US_" in product_id:
                our_format_count += 1

            products.append({
                "product_id": product_id,
                "campaign_type": campaign_type,
                "campaign_name": campaign.get("name", "")[:40],
                "impressions": impressions,
                "clicks": clicks,
                "matches_our_format": "shopify_US_" in product_id,
            })

        return {
            "date_range": f"{start_date} to {end_date}",
            "total_products_found": len(rows),
            "products_shown": len(products),
            "campaign_types": dict(campaign_types),
            "products_matching_our_format": our_format_count,
            "products": products[:20],  # Return top 20
        }

    except Exception as e:
        logger.error(f"Product diagnostic failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnose-query")
async def diagnose_query():
    """Diagnostic endpoint to test Google Ads queries and see what data returns.

    This endpoint:
    1. Gets SKUs with generated content
    2. Queries Google Ads API with campaign.advertising_channel_type
    3. Shows what campaign types return data
    4. Identifies which offer IDs have performance data

    Use this to diagnose why baseline capture returns zeros for some SKUs.
    """
    try:
        supabase = get_client()

        # Get sample SKUs with content
        result = supabase.table("generated_content").select(
            "master_sku"
        ).limit(15).execute()

        if not result.data:
            return {
                "error": "No SKUs with generated content found",
                "test_results": {},
            }

        sample_skus = list(set(row["master_sku"] for row in result.data))
        logger.info(f"Testing {len(sample_skus)} SKUs")

        # Test first 5 SKUs
        test_results: dict[str, dict[str, Any]] = {}
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")

        if not customer_id:
            raise HTTPException(status_code=500, detail="GOOGLE_ADS_CUSTOMER_ID not set")

        client = _load_client()

        for master_sku in sample_skus[:5]:
            # Get variants
            variant_result = supabase.table("variant_index").select(
                "gmc_offer_id, finish_code"
            ).eq("master_sku", master_sku).execute()

            if not variant_result.data:
                test_results[master_sku] = {"error": "No variants found"}
                continue

            offer_ids = [v["gmc_offer_id"] for v in variant_result.data if v.get("gmc_offer_id")]

            if not offer_ids:
                test_results[master_sku] = {"error": "No GMC offer IDs"}
                continue

            # Query Google Ads API (limit to first 10 variants)
            safe_ids = [oid.replace("'", "\\'") for oid in offer_ids[:10]]
            ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)

            query = f"""
            SELECT
              segments.product_item_id,
              segments.date,
              campaign.advertising_channel_type,
              campaign.name,
              metrics.impressions,
              metrics.clicks
            FROM shopping_performance_view
            WHERE
              segments.product_item_id IN ({ids_clause})
              AND segments.date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY metrics.impressions DESC
            LIMIT 50
            """

            try:
                rows = _run_gaql_query(client, customer_id, query)

                # Analyze results
                campaign_types = defaultdict(int)
                offer_ids_found = set()
                total_impressions = 0
                total_clicks = 0
                sample_rows = []

                for row in rows:
                    segments = row.get("segments", {})
                    campaign = row.get("campaign", {})
                    metrics = row.get("metrics", {})

                    campaign_type = campaign.get("advertising_channel_type", "UNKNOWN")
                    campaign_types[campaign_type] += 1

                    offer_id = segments.get("product_item_id", "")
                    if offer_id:
                        offer_ids_found.add(offer_id)

                    impressions = int(metrics.get("impressions", 0) or 0)
                    clicks = int(metrics.get("clicks", 0) or 0)

                    total_impressions += impressions
                    total_clicks += clicks

                    # Save first few rows as samples
                    if len(sample_rows) < 3 and impressions > 0:
                        sample_rows.append({
                            "offer_id": offer_id[-20:],  # Last 20 chars
                            "date": segments.get("date", ""),
                            "campaign_type": campaign_type,
                            "campaign_name": campaign.get("name", "")[:30],
                            "impressions": impressions,
                            "clicks": clicks,
                        })

                test_results[master_sku] = {
                    "total_variants": len(offer_ids),
                    "variants_queried": len(safe_ids),
                    "rows_returned": len(rows),
                    "campaign_types": dict(campaign_types),
                    "variants_with_data": len(offer_ids_found),
                    "total_impressions": total_impressions,
                    "total_clicks": total_clicks,
                    "sample_rows": sample_rows,
                }

            except Exception as e:
                test_results[master_sku] = {"error": str(e)}

        return {
            "date_range": f"{start_date} to {end_date}",
            "skus_tested": len(test_results),
            "test_results": test_results,
        }

    except Exception as e:
        logger.error(f"Diagnostic query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
