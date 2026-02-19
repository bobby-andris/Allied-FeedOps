#!/usr/bin/env python3
"""
Local test for chunked fetch_batch_product_performance.
Fetches ~250 real offer IDs from variant_index and tests the chunked GAQL query.

Usage:
    source .env.vercel
    export GOOGLE_ADS_API_ENABLED=1
    PYTHONPATH=./src .venv/bin/python scripts/test_perf_chunking.py
"""
import time
from datetime import date, timedelta
from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import fetch_batch_product_performance

supabase = get_client()

# Get ~250 offer IDs (10 SKUs worth) from variant_index
result = supabase.table("variant_index").select("gmc_offer_id, master_sku").limit(250).execute()
offer_ids = [r["gmc_offer_id"] for r in result.data if r.get("gmc_offer_id")]
unique_skus = set(r["master_sku"] for r in result.data if r.get("master_sku"))

print(f"Testing with {len(offer_ids)} offer IDs from {len(unique_skus)} SKUs")

end = date.today()
start = end - timedelta(days=30)  # Use 30-day window for speed

t0 = time.time()
results = fetch_batch_product_performance(offer_ids, str(start), str(end))
elapsed = time.time() - t0

non_zero = sum(1 for v in results.values() if v.get("impressions", 0) > 0)
print(f"Completed in {elapsed:.1f}s")
print(f"Results: {len(results)} offer IDs, {non_zero} with impressions > 0")

if elapsed > 60:
    print("FAIL: Took >60 seconds — chunking may not be working")
elif non_zero == 0:
    print("WARN: No impressions found — check if these SKUs have Google Ads activity")
else:
    print("PASS: Chunked query completed quickly with real data")
