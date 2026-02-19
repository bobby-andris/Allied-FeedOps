#!/usr/bin/env python3
"""Diagnosis script: side-by-side comparison of search terms code paths.

Traces the full join path:
  GAQL result -> offer ID extraction -> variant_index lookup -> final row count

Compares:
  [A] days=30 parameter style
  [B] start_date/end_date explicit parameter style for the same 30-day window

Also probes the retention limit of search_term_view by testing progressively older
date windows.

Usage:
  source .env.vercel
  export GOOGLE_ADS_API_ENABLED=1
  PYTHONPATH=./src python scripts/diagnose_search_terms.py
"""

import logging
import os
import sys
from datetime import date, timedelta

# Enable verbose logging to see GAQL details
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Suppress noisy google-auth logs
logging.getLogger("google.auth").setLevel(logging.WARNING)
logging.getLogger("google.ads").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def check_api_enabled():
    """Verify required env vars are set."""
    api_enabled = os.getenv("GOOGLE_ADS_API_ENABLED")
    if api_enabled != "1":
        print("ERROR: GOOGLE_ADS_API_ENABLED=1 must be set.")
        print("Run: export GOOGLE_ADS_API_ENABLED=1")
        sys.exit(1)

    customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID") or "6253381786"
    print(f"Using customer_id: {customer_id}")
    return customer_id


def separator(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def step_header(label: str):
    print()
    print(f"--- {label} ---")


def main():
    check_api_enabled()

    from feedops.integrations.google_ads_search_terms import SearchTermsClient

    client = SearchTermsClient()

    end = date.today()
    start_30 = end - timedelta(days=30)

    print()
    print("Diagnosis date windows:")
    print(f"  30-day window: {start_30} to {end}")
    print(f"  Today: {end}")

    # =========================================================================
    # STEP 1: _fetch_campaign_products comparison
    # =========================================================================
    separator("STEP 1: _fetch_campaign_products — days=30 vs start_date/end_date")

    step_header("A. days=30")
    try:
        cp_days = client._fetch_campaign_products(days=30)
        total_products_days = sum(len(v) for v in cp_days.values())
        print(f"  Result: {len(cp_days)} campaigns, {total_products_days} total product-campaign pairs")
        if cp_days:
            sample_campaign = list(cp_days.keys())[0]
            sample_products = cp_days[sample_campaign]
            print(f"  Sample campaign {sample_campaign}: {len(sample_products)} products")
            print(f"  First 3 product_item_ids: {sample_products[:3]}")
        else:
            print("  WARNING: _fetch_campaign_products returned empty dict for days=30!")
    except Exception as e:
        print(f"  ERROR: {e}")
        cp_days = {}
        total_products_days = 0

    step_header(f"B. start_date={start_30}, end_date={end} (same 30-day window)")
    try:
        cp_dates = client._fetch_campaign_products(start_date=start_30, end_date=end)
        total_products_dates = sum(len(v) for v in cp_dates.values())
        print(f"  Result: {len(cp_dates)} campaigns, {total_products_dates} total product-campaign pairs")
        if cp_dates:
            sample_campaign = list(cp_dates.keys())[0]
            sample_products = cp_dates[sample_campaign]
            print(f"  Sample campaign {sample_campaign}: {len(sample_products)} products")
            print(f"  First 3 product_item_ids: {sample_products[:3]}")
        else:
            print("  WARNING: _fetch_campaign_products returned empty dict for explicit dates!")
    except Exception as e:
        print(f"  ERROR: {e}")
        cp_dates = {}
        total_products_dates = 0

    step_header("C. Comparison")
    if total_products_days == 0 and total_products_dates == 0:
        print("  FINDING: BOTH paths return 0 campaign-product pairs.")
        print("  This suggests a transient API issue or account-level data gap.")
        print("  The bug is NOT in date computation — both paths fail equally.")
    elif total_products_days > 0 and total_products_dates == 0:
        print("  FINDING: days=30 works, explicit dates return 0.")
        print("  ROOT CAUSE: Bug is in _fetch_campaign_products date handling.")
        print("  The explicit start_date/end_date path computes a different date window.")
    elif total_products_days == 0 and total_products_dates > 0:
        print("  FINDING: Explicit dates work, days=30 returns 0.")
        print("  This is unexpected. Check days parameter handling.")
    else:
        match = cp_days == cp_dates
        print(f"  FINDING: Both paths return data. Results match: {match}")
        print(f"  days=30: {total_products_days} pairs, explicit dates: {total_products_dates} pairs")
        if not match:
            print("  WARNING: Results differ — same window, different results!")
            print("  This suggests non-deterministic API behavior or date boundary difference.")

    # =========================================================================
    # STEP 2: fetch_search_terms comparison
    # =========================================================================
    separator("STEP 2: fetch_search_terms — days=30 vs start_date/end_date")

    step_header("A. days=30, limit=100")
    try:
        terms_days = client.fetch_search_terms(days=30, limit=100)
        with_sku = sum(1 for t in terms_days if t.get("master_sku"))
        without_sku = sum(1 for t in terms_days if not t.get("master_sku"))
        print(f"  Total terms: {len(terms_days)}")
        print(f"  With master_sku: {with_sku}")
        print(f"  Without master_sku (null): {without_sku}")
        if terms_days:
            sample = terms_days[0]
            print(f"  Sample: query='{sample.get('search_term', sample.get('query_text'))}', "
                  f"master_sku={sample.get('master_sku')}, impressions={sample.get('impressions')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        terms_days = []

    step_header(f"B. start_date={start_30}, end_date={end}, limit=100")
    try:
        terms_dates = client.fetch_search_terms(start_date=start_30, end_date=end, limit=100)
        with_sku2 = sum(1 for t in terms_dates if t.get("master_sku"))
        without_sku2 = sum(1 for t in terms_dates if not t.get("master_sku"))
        print(f"  Total terms: {len(terms_dates)}")
        print(f"  With master_sku: {with_sku2}")
        print(f"  Without master_sku (null): {without_sku2}")
        if terms_dates:
            sample2 = terms_dates[0]
            print(f"  Sample: query='{sample2.get('search_term', sample2.get('query_text'))}', "
                  f"master_sku={sample2.get('master_sku')}, impressions={sample2.get('impressions')}")
    except Exception as e:
        print(f"  ERROR: {e}")
        terms_dates = []

    step_header("C. Comparison")
    if len(terms_days) > 0 and len(terms_dates) == 0:
        print("  FINDING: days=30 returns terms but explicit dates return 0.")
        print("  ROOT CAUSE: Bug in how fetch_search_terms threads dates.")
        print("  Check _fetch_campaign_products is receiving both date params.")
    elif len(terms_days) == 0 and len(terms_dates) == 0:
        print("  FINDING: BOTH paths return 0 search terms.")
        print("  This explains all failed jobs. Check Step 1 result.")
        if total_products_days == 0:
            print("  ROOT CAUSE: _fetch_campaign_products returns empty for both paths.")
            print("  There are no campaign-product mappings for recent data.")
        else:
            print("  Odd: Step 1 returned data but Step 2 returns 0. Check search_term_view.")
    else:
        print(f"  Both paths return terms: days={len(terms_days)}, explicit={len(terms_dates)}")

    # =========================================================================
    # STEP 3: Retention limit probing via _fetch_campaign_products
    # =========================================================================
    separator("STEP 3: Retention limit probing (shopping_performance_view)")
    print("Testing progressively older date windows to find the data cutoff...")
    print()

    retention_limit_hit = None

    for days_ago in [7, 14, 30, 45, 56, 75, 90, 120, 150, 180]:
        # Test a 7-day window that ends `days_ago` days in the past
        window_end = end - timedelta(days=days_ago)
        window_start = window_end - timedelta(days=7)

        try:
            cp = client._fetch_campaign_products(start_date=window_start, end_date=window_end)
            total_products = sum(len(v) for v in cp.values())
            status = "OK" if total_products > 0 else "EMPTY"
            print(f"  [{status}] Window {window_start} to {window_end} "
                  f"({days_ago}d ago): {len(cp)} campaigns, {total_products} products")

            if total_products == 0 and retention_limit_hit is None:
                retention_limit_hit = days_ago
                print(f"  >>> RETENTION LIMIT LIKELY HIT: data appears empty at ~{days_ago} days ago")
        except Exception as e:
            print(f"  [ERROR] Window ending {days_ago}d ago: {e}")
            break

    if retention_limit_hit is None:
        print()
        print("  FINDING: Data available for all tested windows (up to 180 days)")
        print("  shopping_performance_view retention >= 180 days for this account.")
    else:
        print()
        print(f"  FINDING: Data cutoff at ~{retention_limit_hit} days ago")
        print(f"  shopping_performance_view retention for this account: ~{retention_limit_hit - 7} to {retention_limit_hit} days")
        print(f"  Maximum useful backfill window: {retention_limit_hit - 7} days")

    # =========================================================================
    # STEP 4: Check for null master_sku issue in DB
    # =========================================================================
    separator("STEP 4: Check existing search_queries for null master_sku rows")
    print("Checking search_queries table for diagnostic signals...")

    try:
        from feedops.integrations.google_ads_search_terms import SearchTermsClient as ST
        supabase_client = ST().supabase

        # Total rows
        total_result = supabase_client.table("search_queries").select("id", count="exact").execute()
        total_rows = total_result.count if hasattr(total_result, 'count') else len(total_result.data)
        print(f"  Total rows in search_queries: {total_rows}")

        # Rows with synced_at set (completed syncs)
        synced_result = supabase_client.table("search_queries").select(
            "id", count="exact"
        ).not_.is_("synced_at", "null").execute()
        synced_rows = synced_result.count if hasattr(synced_result, 'count') else len(synced_result.data)
        print(f"  Rows with synced_at (completed): {synced_rows}")

        # Rows with master_sku null
        null_sku_result = supabase_client.table("search_queries").select(
            "id", count="exact"
        ).is_("master_sku", "null").not_.is_("synced_at", "null").execute()
        null_sku_rows = null_sku_result.count if hasattr(null_sku_result, 'count') else len(null_sku_result.data)
        print(f"  Synced rows with null master_sku: {null_sku_rows}")

        # Rows with master_sku set
        valid_sku_result = supabase_client.table("search_queries").select(
            "id", count="exact"
        ).not_.is_("master_sku", "null").not_.is_("synced_at", "null").execute()
        valid_sku_rows = valid_sku_result.count if hasattr(valid_sku_result, 'count') else len(valid_sku_result.data)
        print(f"  Synced rows with valid master_sku: {valid_sku_rows}")

        # Count distinct SKUs
        distinct_result = supabase_client.table("search_queries").select(
            "master_sku"
        ).not_.is_("master_sku", "null").execute()
        distinct_skus = len(set(r["master_sku"] for r in distinct_result.data))
        print(f"  Distinct master_skus covered: {distinct_skus}")

    except Exception as e:
        print(f"  Could not query DB: {e}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    separator("SUMMARY & RECOMMENDATION")

    print()
    print("STEP 1 (campaign-product mapping):")
    print(f"  days=30:         {len(cp_days)} campaigns, {total_products_days} pairs")
    print(f"  explicit dates:  {len(cp_dates)} campaigns, {total_products_dates} pairs")

    print()
    print("STEP 2 (search terms fetch):")
    print(f"  days=30:         {len(terms_days)} terms")
    print(f"  explicit dates:  {len(terms_dates)} terms")

    print()
    print("DIAGNOSIS:")

    if total_products_days > 0 and total_products_dates > 0 and len(terms_days) > 0 and len(terms_dates) > 0:
        print("  Both code paths work correctly for a 30-day window.")
        print("  Root cause is likely retention limit or a transient issue in Phase 15.")
        print()
        print("RECOMMENDED FIX:")
        print("  1. Fix workers.py to pass explicit start_date/end_date (workers.py line 104)")
        print("  2. Use max-retention-window chunks for backfill (not 180 days)")
        if retention_limit_hit:
            print(f"  3. Retention limit: ~{retention_limit_hit} days — use {retention_limit_hit - 7}d chunks max")
        else:
            print("  3. Retention limit: >= 180 days (full backfill may be possible)")

    elif total_products_days == 0 and total_products_dates == 0:
        print("  CRITICAL: _fetch_campaign_products returns 0 for BOTH code paths.")
        print("  This account has no shopping campaign-product impressions in recent 30 days.")
        print("  Possible causes: Shopping campaigns paused, no recent impressions, API quota issue.")
        print()
        print("RECOMMENDED FIX:")
        print("  1. Check Google Ads account for active Shopping campaigns")
        print("  2. Verify campaigns have had impressions in the last 30 days")
        print("  3. Fix workers.py (line 104) regardless — it's broken code")

    elif total_products_days > 0 and total_products_dates == 0:
        print("  ROOT CAUSE FOUND: _fetch_campaign_products returns data for days=30")
        print("  but returns EMPTY for the equivalent explicit start_date/end_date.")
        print("  The date computation in _fetch_campaign_products has a bug.")
        print()
        print("RECOMMENDED FIX:")
        print("  Inspect the actual GAQL query strings being generated by both paths.")
        print("  Add temporary print statements to log query strings, then compare.")

    elif total_products_days > 0 and total_products_dates > 0 and len(terms_days) > 0 and len(terms_dates) == 0:
        print("  ROOT CAUSE FOUND: fetch_search_terms has a date threading bug.")
        print("  campaign_products returns data but search_term_view returns 0 with explicit dates.")
        print()
        print("RECOMMENDED FIX:")
        print("  The search_term_view GAQL query is not using the explicit dates correctly.")
        print("  Check fetch_search_terms lines 583-603 — the _end_date/_start_date computation")
        print("  may not be picking up the passed start_date/end_date parameters.")

    else:
        print("  INCONCLUSIVE: Pattern not matching known failure modes.")
        print("  Review the detailed output above for clues.")

    print()
    print("KNOWN FIX REQUIRED (regardless of above):")
    print("  workers.py line 104: change from `client.fetch_search_terms(days=180, limit=10000)`")
    print("  to: `client.fetch_search_terms(days=180, start_date=period_start, end_date=period_end, limit=10000)`")
    print("  This ensures explicit dates computed at lines 93-99 are passed through.")

    print()
    print("Diagnosis complete.")


if __name__ == "__main__":
    main()
