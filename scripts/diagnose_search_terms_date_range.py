#!/usr/bin/env python3
"""
Diagnosis script for search terms date-range bug.

Bug: fetch_search_terms(start_date=X, end_date=Y) returns 0 results while
     fetch_search_terms(days=30) returns ~10,000 results for the SAME 30-day window.

Strategy: Run both code paths side-by-side and log every intermediate step.
Identifies which step diverges (produces 0 vs non-zero results).

Usage:
    cd /Users/bobby/Documents/GitHub/Allied-FeedOps
    source .venv/bin/activate
    set -a && source .env.vercel && set +a
    export GOOGLE_ADS_API_ENABLED=1
    PYTHONPATH=./src python scripts/diagnose_search_terms_date_range.py
"""
import logging
import sys
import time
from datetime import date, timedelta

# Set up detailed logging so we can see every step
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("diagnose")

from feedops.integrations.google_ads_search_terms import SearchTermsClient

# Use the same 30-day window for both approaches
end = date.today()
start = end - timedelta(days=30)

print("=" * 70)
print(f"DIAGNOSIS: Search Terms Date-Range Bug")
print(f"Window: {start} to {end} (30 days)")
print("=" * 70)

client = SearchTermsClient()


def diagnose_step(step_name: str, result, context: str = ""):
    """Log a diagnostic step with clear pass/fail indication."""
    count = len(result) if isinstance(result, (list, dict)) else result
    status = "OK" if count > 0 else "ZERO"
    print(f"\n  [{status}] Step: {step_name}")
    print(f"         Count: {count}")
    if context:
        print(f"         Context: {context}")
    return count


print("\n" + "=" * 70)
print("PATH A: days=30 (KNOWN WORKING)")
print("=" * 70)

print("\nStep A1: _fetch_campaign_products(days=30)")
t0 = time.time()
cp_days = client._fetch_campaign_products(days=30)
elapsed = time.time() - t0
diagnose_step("campaign_products (days=30)", cp_days,
              f"{elapsed:.1f}s, {sum(len(v) for v in cp_days.values())} total product-campaign combos")
for cid, items in list(cp_days.items())[:3]:
    print(f"         Campaign {cid}: {len(items)} items (first few: {items[:3]})")

print("\nStep A2: fetch_search_terms(days=30, limit=100)")
print("  (using limit=100 to keep it fast for diagnosis)")
t0 = time.time()
try:
    terms_days = client.fetch_search_terms(days=30, limit=100)
    elapsed = time.time() - t0
    diagnose_step("search_terms (days=30)", terms_days, f"{elapsed:.1f}s")
    if terms_days:
        print(f"         Sample: {terms_days[0].get('search_term')} | master_sku={terms_days[0].get('master_sku')}")
except Exception as e:
    print(f"  [ERROR] Exception in days=30 path: {e}")
    terms_days = []


print("\n" + "=" * 70)
print("PATH B: start_date/end_date (REPORTEDLY BROKEN)")
print("=" * 70)

print(f"\nStep B1: _fetch_campaign_products(start_date={start}, end_date={end})")
t0 = time.time()
cp_dates = client._fetch_campaign_products(start_date=start, end_date=end)
elapsed = time.time() - t0
diagnose_step("campaign_products (start_date/end_date)", cp_dates,
              f"{elapsed:.1f}s, {sum(len(v) for v in cp_dates.values())} total product-campaign combos")
for cid, items in list(cp_dates.items())[:3]:
    print(f"         Campaign {cid}: {len(items)} items (first few: {items[:3]})")

print(f"\nStep B2: fetch_search_terms(start_date={start}, end_date={end}, limit=100)")
t0 = time.time()
try:
    terms_dates = client.fetch_search_terms(start_date=start, end_date=end, limit=100)
    elapsed = time.time() - t0
    diagnose_step("search_terms (start_date/end_date)", terms_dates, f"{elapsed:.1f}s")
    if terms_dates:
        print(f"         Sample: {terms_dates[0].get('search_term')} | master_sku={terms_dates[0].get('master_sku')}")
except Exception as e:
    print(f"  [ERROR] Exception in start_date/end_date path: {e}")
    import traceback
    traceback.print_exc()
    terms_dates = []


print("\n" + "=" * 70)
print("COMPARISON ANALYSIS")
print("=" * 70)

print(f"\ncampaign_products (days=30):          {sum(len(v) for v in cp_days.values())} product-campaign combos across {len(cp_days)} campaigns")
print(f"campaign_products (start/end_date):   {sum(len(v) for v in cp_dates.values())} product-campaign combos across {len(cp_dates)} campaigns")
print(f"search_terms (days=30):               {len(terms_days)} results")
print(f"search_terms (start/end_date):        {len(terms_dates)} results")

# Identify divergence point
if len(cp_days) > 0 and len(cp_dates) == 0:
    print("\n>>> DIVERGENCE FOUND at _fetch_campaign_products")
    print(">>> Campaign query returns 0 results for explicit date range")
    print(">>> Root cause: campaign query likely uses a date filter incompatible with start_date/end_date")
elif len(cp_days) == 0:
    print("\n>>> UNEXPECTED: days=30 path also returned 0 campaign products")
    print(">>> Check Google Ads API connectivity and Shopping campaign configuration")
elif len(terms_days) > 0 and len(terms_dates) == 0:
    print("\n>>> DIVERGENCE FOUND at fetch_search_terms (search_term_view query)")
    print(">>> Campaign products look OK but search_term_view query returns 0 with explicit dates")
    print(">>> Root cause: search_term_view GAQL date clause may be malformed for explicit dates")
elif len(terms_days) == len(terms_dates):
    print("\n>>> NO DIVERGENCE: Both paths return the same count")
    print(">>> The reported bug may be intermittent or already fixed")
else:
    print(f"\n>>> PARTIAL DIVERGENCE: days=30 returns {len(terms_days)}, start/end returns {len(terms_dates)}")
    print(">>> May be due to slight timing differences or limit hit")

# Test a historical window too (60-90 days ago)
print("\n" + "=" * 70)
print("PATH B (HISTORICAL): start_date/end_date for 60-90 days ago window")
print("=" * 70)

hist_end = date.today() - timedelta(days=60)
hist_start = hist_end - timedelta(days=30)

print(f"\nStep C1: _fetch_campaign_products(start_date={hist_start}, end_date={hist_end})")
t0 = time.time()
cp_hist = client._fetch_campaign_products(start_date=hist_start, end_date=hist_end)
elapsed = time.time() - t0
diagnose_step("campaign_products (historical)", cp_hist,
              f"{elapsed:.1f}s, window: {hist_start} to {hist_end}")

print(f"\nStep C2: fetch_search_terms(start_date={hist_start}, end_date={hist_end}, limit=50)")
t0 = time.time()
try:
    terms_hist = client.fetch_search_terms(start_date=hist_start, end_date=hist_end, limit=50)
    elapsed = time.time() - t0
    diagnose_step("search_terms (historical)", terms_hist, f"{elapsed:.1f}s")
except Exception as e:
    print(f"  [ERROR] Exception in historical date-range path: {e}")
    terms_hist = []

print("\n" + "=" * 70)
print("FINAL DIAGNOSIS SUMMARY")
print("=" * 70)
print(f"  days=30 campaign products: {sum(len(v) for v in cp_days.values())}")
print(f"  explicit date campaign products (recent): {sum(len(v) for v in cp_dates.values())}")
print(f"  explicit date campaign products (historical): {sum(len(v) for v in cp_hist.values())}")
print(f"  days=30 search terms: {len(terms_days)}")
print(f"  explicit date search terms (recent): {len(terms_dates)}")
print(f"  explicit date search terms (historical): {len(terms_hist)}")
