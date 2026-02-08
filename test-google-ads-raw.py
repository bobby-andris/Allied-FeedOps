#!/usr/bin/env python3
"""Quick script to test raw Google Ads query without any filters.

This will show us what product_item_ids Google Ads actually has,
so we can compare against what's in our variant_index table.
"""

import os
import sys

# Set up path
sys.path.insert(0, 'src')

from feedops.integrations.google_ads_performance import _load_client, _run_gaql_query
from datetime import date, timedelta

# Date range
end_date = date.today()
start_date = end_date - timedelta(days=7)  # Just last 7 days
customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "6253381786")

print("Loading Google Ads client...")
client = _load_client()

# Query for ANY products with impressions in last 7 days
query = f"""
SELECT
  segments.product_item_id,
  campaign.advertising_channel_type,
  campaign.name,
  SUM(metrics.impressions) as total_impressions,
  SUM(metrics.clicks) as total_clicks
FROM shopping_performance_view
WHERE
  segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND metrics.impressions > 0
GROUP BY segments.product_item_id, campaign.advertising_channel_type, campaign.name
ORDER BY total_impressions DESC
LIMIT 20
"""

print(f"\nQuerying Google Ads API for products with impressions...")
print(f"Date range: {start_date} to {end_date}")
print(f"Customer ID: {customer_id}\n")

try:
    rows = _run_gaql_query(client, customer_id, query)

    if not rows:
        print("❌ NO PRODUCTS FOUND with impressions in Google Ads!")
        print("\nPossible reasons:")
        print("1. No active Shopping or Performance Max campaigns")
        print("2. No products have impressions in the date range")
        print("3. Customer ID is incorrect")
        sys.exit(1)

    print(f"✅ Found {len(rows)} products with impressions\n")
    print("Top products by impressions:")
    print("-" * 100)

    for i, row in enumerate(rows[:20], 1):
        segments = row.get("segments", {})
        campaign = row.get("campaign", {})
        metrics = row.get("metrics", {})

        product_id = segments.get("product_item_id", "N/A")
        campaign_type = campaign.get("advertising_channel_type", "N/A")
        campaign_name = campaign.get("name", "N/A")[:40]
        impressions = metrics.get("total_impressions", 0)
        clicks = metrics.get("total_clicks", 0)

        print(f"{i:2}. {product_id[:50]:50} | {campaign_type:15} | {impressions:>6,} impr | {clicks:>4} clicks")
        print(f"    Campaign: {campaign_name}")

    print("\n" + "=" * 100)
    print("ANALYSIS:")

    # Check if any match our format
    our_format = "shopify_US_"
    matching = [r for r in rows if our_format in r.get("segments", {}).get("product_item_id", "")]

    if matching:
        print(f"✅ {len(matching)} products match our format ({our_format}*)")
    else:
        print(f"❌ NO products match our expected format ({our_format}*)")
        print("\n⚠️  This means the offer IDs in Google Ads don't match variant_index!")

except Exception as e:
    print(f"❌ Query failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
