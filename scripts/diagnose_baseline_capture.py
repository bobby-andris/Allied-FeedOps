#!/usr/bin/env python3
"""Diagnostic script to investigate Google Ads baseline capture issues.

This script:
1. Finds all SKUs with generated content (approval_status != 'none')
2. Gets their GMC offer IDs from variant_index
3. Queries Google Ads API directly to see what data returns
4. Reports detailed results for debugging

Run from repo root:
    PYTHONPATH=./src python scripts/diagnose_baseline_capture.py
"""

import os
import sys
from datetime import date, timedelta
from collections import defaultdict

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import fetch_batch_product_performance


def get_skus_with_content():
    """Get all master SKUs that have generated content."""
    supabase = get_client()

    result = supabase.table("generated_content").select(
        "master_sku"
    ).neq("approval_status", "none").execute()

    if not result.data:
        print("❌ No SKUs with generated content found")
        return []

    # Get unique master SKUs
    master_skus = list(set(row["master_sku"] for row in result.data))
    print(f"✅ Found {len(master_skus)} unique SKUs with generated content")
    return sorted(master_skus)


def get_offer_ids_for_sku(supabase, master_sku):
    """Get all GMC offer IDs for a master SKU."""
    result = supabase.table("variant_index").select(
        "gmc_offer_id, finish_name"
    ).eq("master_sku", master_sku).execute()

    if not result.data:
        return []

    return [
        {
            "offer_id": row["gmc_offer_id"],
            "finish": row.get("finish_name", "unknown")
        }
        for row in result.data
        if row.get("gmc_offer_id")
    ]


def test_google_ads_query(offer_ids, start_date, end_date):
    """Test Google Ads API query with offer IDs."""
    print(f"\n🔍 Querying Google Ads API...")
    print(f"   Date range: {start_date} to {end_date}")
    print(f"   Offer IDs: {len(offer_ids)}")

    try:
        performance_data = fetch_batch_product_performance(
            offer_ids=[oid["offer_id"] for oid in offer_ids],
            start_date=start_date,
            end_date=end_date,
        )
        return performance_data
    except Exception as e:
        print(f"❌ API query failed: {e}")
        return {}


def analyze_results(master_sku, offer_ids, performance_data):
    """Analyze and report results for a SKU."""
    print(f"\n📊 Results for {master_sku}:")
    print(f"   Variants: {len(offer_ids)}")

    variants_with_data = 0
    total_impressions = 0
    total_clicks = 0

    for offer_info in offer_ids:
        offer_id = offer_info["offer_id"]
        finish = offer_info["finish"]
        metrics = performance_data.get(offer_id, {})

        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)

        if impressions > 0:
            variants_with_data += 1
            total_impressions += impressions
            total_clicks += clicks
            print(f"   ✅ {finish[:20]:20} → {impressions:>6,} impr, {clicks:>4} clicks")
        else:
            print(f"   ⚠️  {finish[:20]:20} → NO DATA")

    print(f"\n   Summary: {variants_with_data}/{len(offer_ids)} variants with data")
    if variants_with_data > 0:
        print(f"   Total: {total_impressions:,} impressions, {total_clicks:,} clicks")

    return variants_with_data > 0


def main():
    """Main diagnostic flow."""
    print("=" * 80)
    print("Google Ads Baseline Capture Diagnostic")
    print("=" * 80)

    # Check environment
    if not os.getenv("GOOGLE_ADS_API_ENABLED"):
        print("\n⚠️  Warning: GOOGLE_ADS_API_ENABLED is not set")
        print("   Set to '1' or 'true' to enable API mode")

    # Date range (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    print(f"\n📅 Date range: {start_date} to {end_date}")

    # Get SKUs with content
    print("\n" + "=" * 80)
    print("Step 1: Finding SKUs with generated content")
    print("=" * 80)

    master_skus = get_skus_with_content()
    if not master_skus:
        return

    # Sample first 10 SKUs for testing (avoid overwhelming output)
    test_skus = master_skus[:10]
    print(f"\n📋 Testing first {len(test_skus)} SKUs (out of {len(master_skus)} total)")
    print(f"   SKUs: {', '.join(test_skus)}")

    # Get offer IDs for each SKU
    print("\n" + "=" * 80)
    print("Step 2: Getting GMC offer IDs from variant_index")
    print("=" * 80)

    supabase = get_client()
    skus_with_offers = {}

    for master_sku in test_skus:
        offer_ids = get_offer_ids_for_sku(supabase, master_sku)
        if offer_ids:
            skus_with_offers[master_sku] = offer_ids
            print(f"✅ {master_sku}: {len(offer_ids)} variants")
        else:
            print(f"⚠️  {master_sku}: NO VARIANTS FOUND")

    if not skus_with_offers:
        print("\n❌ No SKUs have variant offer IDs - cannot query Google Ads")
        return

    # Test Google Ads queries
    print("\n" + "=" * 80)
    print("Step 3: Querying Google Ads API")
    print("=" * 80)

    skus_with_data = 0
    skus_without_data = 0

    for master_sku, offer_ids in skus_with_offers.items():
        performance_data = test_google_ads_query(
            offer_ids,
            start_date.isoformat(),
            end_date.isoformat()
        )

        has_data = analyze_results(master_sku, offer_ids, performance_data)

        if has_data:
            skus_with_data += 1
        else:
            skus_without_data += 1

    # Final summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"SKUs tested: {len(skus_with_offers)}")
    print(f"✅ SKUs with data: {skus_with_data}")
    print(f"❌ SKUs without data: {skus_without_data}")

    if skus_without_data > 0:
        print("\n🔍 Possible reasons for missing data:")
        print("   1. Products not active in Google Ads campaigns")
        print("   2. Products in campaigns but no impressions in date range")
        print("   3. Offer IDs don't match between Shopify/GMC/Google Ads")
        print("   4. Campaign type filter issue (Shopping vs Performance Max)")
        print("\n💡 Next steps:")
        print("   - Check if products are enabled in Google Ads")
        print("   - Verify GMC offer IDs match Google Ads product_item_id")
        print("   - Try expanding date range (60-90 days)")

    # Show sample offer ID for verification
    if skus_with_offers:
        sample_sku = list(skus_with_offers.keys())[0]
        sample_offer = skus_with_offers[sample_sku][0]["offer_id"]
        print(f"\n📝 Sample offer ID format: {sample_offer}")
        print("   Expected: shopify_US_{{product_id}}_{{variant_id}}")


if __name__ == "__main__":
    main()
