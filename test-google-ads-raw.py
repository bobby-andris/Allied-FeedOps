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
# Note: GAQL doesn't support SUM/GROUP BY like SQL, so we get raw rows
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
  segments.date BETWEEN '{start_date}' AND '{end_date}'
  AND metrics.impressions > 0
ORDER BY metrics.impressions DESC
LIMIT 100
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

    print(f"✅ Found {len(rows)} rows with impressions\n")

    # Aggregate by product to get unique products
    from collections import defaultdict
    products = defaultdict(lambda: {"impressions": 0, "clicks": 0, "campaign_types": set(), "dates": set()})

    for row in rows:
        segments = row.get("segments", {})
        campaign = row.get("campaign", {})
        metrics = row.get("metrics", {})

        product_id = segments.get("product_item_id", "N/A")
        campaign_type = campaign.get("advertising_channel_type", "N/A")
        date_val = segments.get("date", "")
        impressions = int(metrics.get("impressions", 0) or 0)
        clicks = int(metrics.get("clicks", 0) or 0)

        products[product_id]["impressions"] += impressions
        products[product_id]["clicks"] += clicks
        products[product_id]["campaign_types"].add(campaign_type)
        products[product_id]["dates"].add(date_val)
        products[product_id]["campaign_name"] = campaign.get("name", "N/A")[:40]

    print(f"Unique products: {len(products)}\n")
    print("Top products by impressions:")
    print("-" * 100)

    sorted_products = sorted(products.items(), key=lambda x: x[1]["impressions"], reverse=True)

    for i, (product_id, data) in enumerate(sorted_products[:20], 1):
        campaign_types = ", ".join(sorted(data["campaign_types"]))
        print(f"{i:2}. {product_id[:60]:60}")
        print(f"    Campaign types: {campaign_types}")
        print(f"    Impressions: {data['impressions']:,} | Clicks: {data['clicks']}")
        print(f"    Days with data: {len(data['dates'])}")
        print()

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
