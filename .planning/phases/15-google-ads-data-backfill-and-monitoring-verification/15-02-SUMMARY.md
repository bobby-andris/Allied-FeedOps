---
phase: 15-google-ads-data-backfill-and-monitoring-verification
plan: "02"
status: failed
completed_at: 2026-02-19
---

# 15-02 Summary: Performance Metrics Backfill — Failed (Root Cause Identified)

## What Happened

### Targeted test (10-15 SKUs) — Misleading success
Job 280d7ea3 completed 13/13 in 21 seconds with 0 failures. This appeared successful but wrote
**zero new rows** to performance_baselines. Root cause: all 13 test SKUs were published within
the last 30 days, so the contamination check skipped them all. They were counted as
"completed_items" without any Google Ads API calls being made.

### Full backfill attempts — Both failed

**Job 3c71fef2** (2784 SKUs, old code with contamination check):
- Cancelled after 7 minutes at 110/2784 (4%)
- Was processing ~15 items/min, but most were contamination-skipped (no API calls)
- Cancelled to restart with force_backfill=True

**Job bd3665f0** (2784 SKUs, force_backfill=True):
- Cancelled after 13+ minutes at 0/2784 (0%)
- Root cause identified: `fetch_batch_product_performance` stuffs ALL offer IDs
  for a batch into one GAQL `IN (...)` clause

## Root Cause: Oversized GAQL Query

`fetch_batch_product_performance` in `google_ads_performance.py` builds:
```sql
SELECT ... FROM shopping_performance_view
WHERE segments.product_item_id IN ('id1', 'id2', ..., 'id253')
  AND segments.date BETWEEN '2025-08-22' AND '2026-02-19'
```

For the first batch of 10 SKUs (101, 1016, 101A, ..., 102), there were **253 offer IDs**
(~25 variants per SKU). A 180-day query with 253 offer IDs in the IN clause causes the
Google Ads API to hang indefinitely (observed: 13+ minutes with no response).

Logs confirmed the query was initiated at 16:35:41 but the Google Ads client didn't even
finish loading until 16:38:25, and the actual query never returned before cancellation.

## Why Previous Jobs Appeared to Work

Job 3c71fef2 showed 60 items in 4.4 minutes (~15 items/min). This was NOT real throughput —
the contamination check was skipping ~95%+ of items without hitting the Google Ads API.
The "completed_items" counter counts skips as completions, masking the true API call rate.

## What performance_baselines Looks Like Now

| Metric | Value |
|--------|-------|
| distinct_skus | 96 (unchanged from pre-Phase-15) |
| total_rows | 188 (unchanged) |
| Most recent write | 2026-02-19 06:15 UTC |

## Required Fix (for Phase 16)

`fetch_batch_product_performance` must chunk offer IDs into sub-batches of 25-50 max:

```python
OFFER_ID_CHUNK_SIZE = 25

def fetch_batch_product_performance(offer_ids, start_date, end_date, ...):
    all_results = {}
    for chunk in _chunks(offer_ids, OFFER_ID_CHUNK_SIZE):
        # Build IN clause with only 25 IDs
        # Run query, merge results
        all_results.update(_fetch_chunk(client, chunk, start_date, end_date))
    return all_results
```

At 25 offer IDs per query, a batch of 10 SKUs (avg 25 variants each) = ~10 sequential
Google Ads API calls instead of 1 massive one. Each call should complete in seconds.

## Also Needed (force_backfill flag deployed)

Commit 34b14ae4 added `force_backfill: true` config option — this is correctly deployed
and working (logs confirmed "force_backfill=True: skipping contamination check").
The contamination check bypass is correct and should be kept for historical backfills.

## Deviations

- Plan assumed performance pipeline was "known clean" — it is for single-SKU calls,
  but the batch function has a query size bug not previously tested at scale
- No data written to performance_baselines during Phase 15
- Both full backfill jobs cancelled due to performance issues
