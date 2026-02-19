---
phase: 15-google-ads-data-backfill-and-monitoring-verification
plan: "01"
status: partial
completed_at: 2026-02-19
---

# 15-01 Summary: Search Terms Backfill — Partial (Debugging Deferred)

## What Was Accomplished

### Tasks 1 & 2: Code Changes + SKU Selection (COMPLETE)

**Code changes deployed** (commits 38ea3483, 4646aac8):
- `src/feedops/api/search_insights.py`: Added `start_date`, `end_date`, `filter_skus` to `SyncSearchTermsRequest`
- `src/feedops/integrations/google_ads_search_terms.py`: Updated `fetch_search_terms` and `_fetch_campaign_products` to accept explicit date params
- `scripts/select_test_skus.py`: Strategic SKU selection script written and committed

### Task 3: Targeted test — SKIPPED (user decision)
User opted to skip the targeted smoke test and go straight to full account backfill.

### Task 4: Chunked 180-day Backfill — FAILED (debugging deferred)

## Search Terms Job History

| Job ID | Type | Status | Queries | Days | Notes |
|--------|------|--------|---------|------|-------|
| 1f6402fe | search_terms | ✓ completed | 10,000 | 30 | Used old `days=30` param |
| fd1562b9 | search_terms | ✗ failed | 0 | 180 | LAST_N_DAYS likely still present |
| d523b94b | search_terms | ✗ failed | 0 | 180 | Same as above |
| ccac44b9 | search_terms | ✗ failed | 0 | 30 | Unknown failure |
| 88fb3cbcbc | search_terms | ✗ failed | 0 | 90 | Unknown failure |
| e9ca1c16 | search_terms | cancelled | 0 | - | New start_date/end_date — hung with 0 queries |
| 2935101e | search_terms | cancelled | 0 | - | New start_date/end_date — hung with 0 queries |
| 515c9934 | search_terms | cancelled | 0 | - | New start_date/end_date — hung with 0 queries |

## Current search_queries State

| Metric | Value |
|--------|-------|
| Total rows | 16,587 |
| Distinct master_skus | 424 / 2,784 (15.2%) |
| Post-fix rows (synced_at IS NOT NULL) | 9,691 |
| Pre-backfill baseline | 7,891 rows, 125 SKUs |
| Oldest period | 2026-01-06 (~44 days back) |
| Newest period | 2026-02-19 |

**Note**: Only ~44 days of historical data reached (not the target 180 days). The single successful job (1f6402fe) used `days=30` and fetched 10,000 queries, growing coverage from 125 → 424 SKUs.

## Root Cause Analysis (Hypothesis)

### Problem 1: Jobs using new start_date/end_date params hang with 0 queries fetched
The 3 jobs started with explicit `start_date`/`end_date` params (e9ca1c16, 2935101e, 515c9934) all hung indefinitely with 0 queries. This suggests the new code path may have a bug:
- Possible: the `start_date`/`end_date` param threading into `_fetch_campaign_products` produces no results (empty campaign-to-product mapping for historical windows)
- Possible: the Cloud Run container silently crashes when given older date ranges (OOM, timeout)
- Possible: the Google Ads API returns 0 results for date windows without active campaigns in that period

### Problem 2: Jobs with days=180 consistently fail with 0 queries
Jobs fd1562b9 and d523b94b used `days=180` and failed. This could be:
- LAST_N_DAYS syntax still present in some code path (Phase 14 fix may not have covered all occurrences)
- Google Ads API does not support 180-day windows in search_term_view (max retention may be shorter)

### Problem 3: Status "running" with 0 queries = silent failure
The monitoring shows jobs as "running" indefinitely (no timeout). The process either:
- Hangs on the Google Ads API call
- Silently crashes without updating job status to "failed"
- The background thread dies without cleanup

## What Was NOT Achieved

- ❌ 180-day historical backfill (oldest data is only 44 days)
- ❌ Chunked window approach (all start_date/end_date jobs hung)
- ❌ distinct_skus >> 125 (achieved 424 from one successful job, but target was full coverage)

## What IS Working

- ✓ `days=30` approach still works (1f6402fe fetched 10,000 queries successfully)
- ✓ Coverage grew 125 → 424 SKUs from that single job
- ✓ Post-fix rows (synced_at IS NOT NULL): 9,691 confirmed written correctly
- ✓ Code changes deployed (start_date/end_date params exist in production)

## Recommended Next Steps (New Phase Required)

A dedicated debugging phase is needed for search terms:

1. **Investigate job hang** — Add explicit timeout and logging to the background thread. Check if `_fetch_campaign_products` returns 0 results for historical windows (the campaign-products join may not work for past periods).

2. **Test start_date/end_date locally** — Run `fetch_search_terms(start_date=date(2025,12,1), end_date=date(2025,12,31))` locally with PYTHONPATH=./src to see actual Google Ads response.

3. **Check search_term_view retention** — Google Ads may limit search_term_view to 6-8 weeks (not 180 days). Verify what the actual API retention limit is.

4. **Fix or remove LAST_N_DAYS** — Audit google_ads_search_terms.py again; the days=180 failures suggest LAST_N_DAYS may still be present in the search_term_view query (even if _fetch_campaign_products was fixed).

5. **Add job timeout** — Implement a max-runtime guard so background threads that hang for >15 minutes auto-fail the job with a descriptive error.

## Deviations

- Plan intended: 6 sequential windows → 180 days coverage
- Actual: 1 successful job (30 days) + multiple failures/hangs
- User decision: Defer search terms debugging to Phase 16, proceed with performance metrics now
