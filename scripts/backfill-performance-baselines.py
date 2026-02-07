#!/usr/bin/env python3
"""
Backfill performance baselines for all SKUs missing baseline data.

Fetches 30-day historical metrics from Google Ads, Bing Ads, and Shopify
and stores them in the performance_baselines table.
"""
from __future__ import annotations

import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import fetch_product_performance
from feedops.integrations.bing_ads_performance import fetch_bing_product_performance
from feedops.integrations.shopify_analytics import fetch_shopify_product_analytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_skus_missing_baselines(platform: str | None = None) -> list[dict]:
    """Get list of SKUs missing performance baselines."""
    supabase = get_client()

    # Get all SKUs from variant_index
    all_skus_result = supabase.table("variant_index").select(
        "master_sku, gmc_offer_id"
    ).execute()

    all_skus = {}
    for row in all_skus_result.data:
        sku = row["master_sku"]
        if sku not in all_skus:
            all_skus[sku] = {
                "master_sku": sku,
                "offer_id": row["gmc_offer_id"]
            }

    # Get SKUs that already have baselines
    existing_query = supabase.table("performance_baselines").select("master_sku, platform")
    if platform:
        existing_query = existing_query.eq("platform", platform)

    existing_result = existing_query.execute()
    existing_keys = {(row["master_sku"], row["platform"]) for row in existing_result.data}

    # Calculate missing SKUs
    platforms = [platform] if platform else ["google", "bing", "shopify"]
    missing = []

    for sku_data in all_skus.values():
        for plat in platforms:
            if (sku_data["master_sku"], plat) not in existing_keys:
                missing.append({
                    **sku_data,
                    "platform": plat
                })

    return missing


def fetch_baseline_metrics(
    offer_id: str,
    platform: str,
    start_date: str,
    end_date: str
) -> dict | None:
    """Fetch baseline metrics for a SKU from the appropriate platform."""
    try:
        if platform == "google":
            return fetch_product_performance(offer_id, start_date, end_date)
        elif platform == "bing":
            return fetch_bing_product_performance(offer_id, start_date, end_date)
        elif platform == "shopify":
            return fetch_shopify_product_analytics(offer_id, start_date, end_date)
        else:
            logger.error(f"Unknown platform: {platform}")
            return None
    except Exception as e:
        logger.error(f"Error fetching {platform} metrics for {offer_id}: {e}")
        return None


def save_baseline(
    master_sku: str,
    platform: str,
    start_date: str,
    end_date: str,
    metrics: dict,
    days: int
) -> bool:
    """Save baseline metrics to database."""
    supabase = get_client()

    impressions = metrics.get("impressions", 0)
    clicks = metrics.get("clicks", 0)
    conversions = metrics.get("conversions", 0)
    conversion_value = metrics.get("conversion_value", 0.0)
    cost = metrics.get("cost", 0.0)
    ctr = metrics.get("ctr", 0.0)
    roas = metrics.get("roas", 0.0)

    try:
        supabase.table("performance_baselines").upsert({
            "master_sku": master_sku,
            "platform": platform,
            "baseline_start_date": start_date,
            "baseline_end_date": end_date,
            "avg_impressions": impressions / days,
            "avg_clicks": clicks / days,
            "avg_ctr": ctr,
            "avg_conversions": conversions / days,
            "avg_conversion_value": conversion_value / days,
            "avg_cvr": conversions / clicks if clicks > 0 else 0.0,
            "avg_cost": cost / days,
            "avg_roas": roas,
        }, on_conflict="master_sku,platform").execute()

        return True
    except Exception as e:
        logger.error(f"Error saving baseline for {master_sku} ({platform}): {e}")
        return False


def main():
    """Run baseline backfill for all missing SKUs."""
    # Calculate 30-day baseline period (ending yesterday)
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)
    days = 30

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    logger.info(f"Backfilling baselines for period: {start_str} to {end_str}")

    # Get missing SKUs
    logger.info("Fetching list of SKUs missing baselines...")
    missing = get_skus_missing_baselines()

    logger.info(f"Found {len(missing)} SKU+platform combinations missing baselines")

    # Group by platform for reporting
    by_platform = {}
    for item in missing:
        platform = item["platform"]
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(item)

    for platform, items in by_platform.items():
        logger.info(f"  {platform}: {len(items)} SKUs")

    # Process each missing baseline
    success_count = 0
    error_count = 0

    for i, item in enumerate(missing, 1):
        sku = item["master_sku"]
        offer_id = item["offer_id"]
        platform = item["platform"]

        if i % 10 == 0:
            logger.info(f"Progress: {i}/{len(missing)} ({i/len(missing)*100:.1f}%)")

        # Fetch metrics
        metrics = fetch_baseline_metrics(offer_id, platform, start_str, end_str)

        if not metrics:
            logger.warning(f"No metrics returned for {sku} ({platform})")
            error_count += 1
            continue

        # Save to database
        if save_baseline(sku, platform, start_str, end_str, metrics, days):
            success_count += 1
            logger.debug(f"✓ Saved baseline for {sku} ({platform})")
        else:
            error_count += 1

    # Final report
    logger.info("\n" + "="*60)
    logger.info("Backfill Complete")
    logger.info("="*60)
    logger.info(f"Total processed: {len(missing)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Success rate: {success_count/len(missing)*100:.1f}%")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
