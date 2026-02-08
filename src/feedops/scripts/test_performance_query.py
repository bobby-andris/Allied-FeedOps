#!/usr/bin/env python3
"""Test Google Ads performance queries directly.

This script runs IN Cloud Run environment where credentials are available.
Deploy it and call via endpoint to diagnose baseline capture issues.

Usage:
    Add this as a Cloud Run endpoint and call it to test queries.
"""

from datetime import date, timedelta
import logging
import os
from collections import defaultdict

from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import (
    fetch_batch_product_performance,
    _load_client,
    _run_gaql_query,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_raw_query():
    """Test the raw Google Ads query to see what data comes back."""

    # Get SKUs with content
    supabase = get_client()

    # Get a sample of SKUs with content
    result = supabase.table("generated_content").select(
        "master_sku"
    ).limit(10).execute()

    sample_skus = list(set(row["master_sku"] for row in result.data))
    logger.info(f"Testing {len(sample_skus)} SKUs: {sample_skus}")

    # Get offer IDs for first 3 SKUs
    test_results = {}

    for master_sku in sample_skus[:3]:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing SKU: {master_sku}")
        logger.info(f"{'='*80}")

        # Get variants
        variant_result = supabase.table("variant_index").select(
            "gmc_offer_id, finish_code"
        ).eq("master_sku", master_sku).execute()

        if not variant_result.data:
            logger.warning(f"No variants found for {master_sku}")
            continue

        offer_ids = [v["gmc_offer_id"] for v in variant_result.data if v.get("gmc_offer_id")]
        logger.info(f"Found {len(offer_ids)} offer IDs")

        if not offer_ids:
            logger.warning(f"No GMC offer IDs for {master_sku}")
            continue

        # Show sample offer ID
        logger.info(f"Sample offer ID: {offer_ids[0]}")

        # Test the query
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        try:
            # First, test with the RAW query to see ALL data
            customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID")
            client = _load_client()

            # Build query with campaign type to see what we get
            safe_ids = [oid.replace("'", "\\'") for oid in offer_ids[:5]]  # Test first 5
            ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)

            query = f"""
            SELECT
              segments.product_item_id,
              segments.date,
              campaign.advertising_channel_type,
              campaign.name,
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
            LIMIT 100
            """

            logger.info(f"Running query for {len(safe_ids)} offer IDs...")
            rows = _run_gaql_query(client, customer_id, query)

            logger.info(f"Query returned {len(rows)} rows")

            if rows:
                # Analyze what campaign types we're seeing
                campaign_types = defaultdict(int)
                offer_ids_found = set()
                total_impressions = 0

                for row in rows:
                    segments = row.get("segments", {})
                    campaign = row.get("campaign", {})
                    metrics = row.get("metrics", {})

                    campaign_type = campaign.get("advertising_channel_type", "UNKNOWN")
                    campaign_types[campaign_type] += 1

                    offer_id = segments.get("product_item_id", "")
                    if offer_id:
                        offer_ids_found.add(offer_id)

                    total_impressions += int(metrics.get("impressions", 0) or 0)

                logger.info(f"\nCampaign type breakdown:")
                for ctype, count in campaign_types.items():
                    logger.info(f"  {ctype}: {count} rows")

                logger.info(f"\nOffer IDs with data: {len(offer_ids_found)} out of {len(safe_ids)}")
                logger.info(f"Total impressions: {total_impressions:,}")

                # Show a few sample rows
                logger.info(f"\nSample rows:")
                for i, row in enumerate(rows[:5]):
                    segments = row.get("segments", {})
                    campaign = row.get("campaign", {})
                    metrics = row.get("metrics", {})

                    logger.info(
                        f"  Row {i+1}: "
                        f"offer_id={segments.get('product_item_id', 'N/A')[:40]}, "
                        f"date={segments.get('date', 'N/A')}, "
                        f"campaign_type={campaign.get('advertising_channel_type', 'N/A')}, "
                        f"impressions={metrics.get('impressions', 0)}, "
                        f"clicks={metrics.get('clicks', 0)}"
                    )

                test_results[master_sku] = {
                    "rows_returned": len(rows),
                    "campaign_types": dict(campaign_types),
                    "offer_ids_found": len(offer_ids_found),
                    "total_offer_ids": len(safe_ids),
                    "total_impressions": total_impressions,
                }
            else:
                logger.warning(f"NO DATA returned for {master_sku}")
                test_results[master_sku] = {
                    "rows_returned": 0,
                    "error": "No data returned from query"
                }

        except Exception as e:
            logger.error(f"Query failed for {master_sku}: {e}", exc_info=True)
            test_results[master_sku] = {
                "error": str(e)
            }

    # Print summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}")

    for sku, result in test_results.items():
        logger.info(f"\n{sku}:")
        if "error" in result:
            logger.info(f"  ❌ Error: {result['error']}")
        else:
            logger.info(f"  ✅ Rows: {result['rows_returned']}")
            logger.info(f"  Campaign types: {result.get('campaign_types', {})}")
            logger.info(f"  Offer IDs with data: {result['offer_ids_found']}/{result['total_offer_ids']}")
            logger.info(f"  Total impressions: {result['total_impressions']:,}")

    return test_results


if __name__ == "__main__":
    test_raw_query()
