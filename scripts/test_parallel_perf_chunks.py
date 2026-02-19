#!/usr/bin/env python3
"""
Local test for parallel fetch_batch_product_performance and _preload_variant_cache.

Tests:
  1. Parallel GAQL chunk execution: ~250 offer IDs should complete in <8s
     (baseline from 16-01: 13.2s sequential; target: <8s with 5 parallel workers)
  2. _preload_variant_cache bulk load: all ~69,600 variant_index rows in a few seconds

Usage:
    cd /Users/bobby/Documents/GitHub/Allied-FeedOps
    source .venv/bin/activate
    set -a && source .env.vercel && set +a
    export GOOGLE_ADS_API_ENABLED=1
    PYTHONPATH=./src python scripts/test_parallel_perf_chunks.py
"""
import time
from datetime import date, timedelta

from feedops.db.supabase_client import get_client
from feedops.integrations.google_ads_performance import fetch_batch_product_performance
from feedops.integrations.google_ads_search_terms import SearchTermsClient

supabase = get_client()

print("=" * 60)
print("TEST 1: Parallel GAQL chunk execution")
print("=" * 60)

# Get ~250 offer IDs (same as 16-01 baseline test)
result = supabase.table("variant_index").select("gmc_offer_id, master_sku").limit(250).execute()
offer_ids = [r["gmc_offer_id"] for r in result.data if r.get("gmc_offer_id")]
unique_skus = set(r["master_sku"] for r in result.data if r.get("master_sku"))

print(f"Testing with {len(offer_ids)} offer IDs from {len(unique_skus)} SKUs")

end = date.today()
start = end - timedelta(days=30)  # 30-day window for speed (same as 16-01 baseline)

t0 = time.time()
results = fetch_batch_product_performance(offer_ids, str(start), str(end))
elapsed = time.time() - t0

non_zero = sum(1 for v in results.values() if v.get("impressions", 0) > 0)
print(f"Completed in {elapsed:.1f}s")
print(f"Results: {len(results)} offer IDs, {non_zero} with impressions > 0")
print(f"Baseline (16-01 sequential): 13.2s")
print(f"Target (parallel, 5 workers): <8s")

if elapsed > 60:
    print("FAIL: Took >60 seconds — parallel execution may not be working")
elif elapsed > 13.2:
    print(f"WARN: Slower than sequential baseline ({elapsed:.1f}s vs 13.2s) — check worker count")
elif elapsed > 8.0:
    print(f"WARN: Faster than sequential but missed <8s target ({elapsed:.1f}s) — acceptable")
else:
    print(f"PASS: Parallel fetch completed in {elapsed:.1f}s (better than <8s target vs 13.2s baseline)")

print()
print("=" * 60)
print("TEST 2: _preload_variant_cache bulk load")
print("=" * 60)

client = SearchTermsClient()

t0 = time.time()
loaded = client._preload_variant_cache()
elapsed_cache = time.time() - t0

print(f"Loaded {loaded} rows in {elapsed_cache:.1f}s")
print(f"Cache size: {len(client._variant_cache)} entries")

if loaded < 60000:
    print(f"WARN: Expected ~69,600 rows but got {loaded} — check variant_index row count")
elif elapsed_cache > 30:
    print(f"FAIL: Took {elapsed_cache:.1f}s — pagination may be broken")
elif elapsed_cache > 10:
    print(f"WARN: Took {elapsed_cache:.1f}s (>10s target) but loaded {loaded} rows successfully")
else:
    print(f"PASS: Loaded {loaded} rows in {elapsed_cache:.1f}s")

# Verify cache lookup works for a known offer ID
sample_offer_id = offer_ids[0].lower() if offer_ids else None
if sample_offer_id:
    cached = client._variant_cache.get(sample_offer_id)
    if cached:
        print(f"PASS: Cache lookup works for {sample_offer_id} -> master_sku={cached.get('master_sku')}")
    else:
        print(f"WARN: Sample offer ID {sample_offer_id} not found in cache (may be OK if not in variant_index)")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"  Parallel GAQL fetch: {elapsed:.1f}s for {len(offer_ids)} offer IDs")
print(f"  Sequential baseline: 13.2s (from 16-01)")
print(f"  Speedup: {13.2 / elapsed:.1f}x" if elapsed > 0 else "  Speedup: N/A")
print(f"  Variant cache load: {elapsed_cache:.1f}s for {loaded} rows")
