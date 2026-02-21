---
phase: 16-fix-google-ads-backfill-pipeline-search-terms-performance-metrics
plan: "02"
subsystem: infra
tags: [google-ads, gaql, backfill, performance-metrics, search-terms, parallelization, python]

# Dependency graph
requires:
  - phase: 16-01
    provides: chunked GAQL IN() clause, full backfill job 2c738140 (now killed and restarted)
provides:
  - ThreadPoolExecutor(max_workers=5) in fetch_batch_product_performance: 3.4x speedup
  - _preload_variant_cache() in SearchTermsClient: 72,023 rows in 7.7s vs N+1 queries
  - Batch upsert in collect_performance_batch: 1 DB call per batch instead of N
  - Search terms date-range bug diagnosed: already fixed in 16-01, both paths produce identical results
  - Full 2,784-SKU performance backfill restarted (job 3da77cd6) with ~9-19h ETA
  - Search terms sync started for window 6 (2026-01-20 to 2026-02-19) — job ca19f9fa
affects: [16-03, performance-baselines table, search_queries table]

# Tech tracking
tech-stack:
  added:
    - "concurrent.futures.ThreadPoolExecutor for parallel GAQL chunk execution"
  patterns:
    - "ThreadPoolExecutor(max_workers=5) for parallel API calls: 3.4x speedup (3.9s vs 13.2s for 250 IDs)"
    - "Bulk paginated Supabase pre-load: 72,023 rows in 7.7s via 1000-row pages"
    - "Collect-then-batch-upsert pattern: replace N individual upserts with 1 batch call"

key-files:
  created:
    - scripts/test_parallel_perf_chunks.py
    - scripts/diagnose_search_terms_date_range.py
  modified:
    - src/feedops/integrations/google_ads_performance.py
    - src/feedops/integrations/google_ads_search_terms.py
    - src/feedops/jobs/workers.py

key-decisions:
  - "ThreadPoolExecutor(max_workers=5): matches OFFER_ID_CHUNK_SIZE=25 design — each 10-SKU batch has ~7-12 chunks so 5 workers gives near-full parallelism without over-subscribing gRPC connections"
  - "Search terms date-range bug was already fixed in 16-01: diagnosis confirmed both paths return identical results; 180-day backfill via 6x30-day windows is viable"
  - "Batch upsert placed after per-SKU loop: individual logging/validation per SKU retained for observability, only DB write batched"
  - "Search terms 180-day backfill uses start_date/end_date windows (not days=N) since bug is confirmed fixed"

patterns-established:
  - "Parallel GAQL: ThreadPoolExecutor for any multi-chunk API call where each chunk is independent"
  - "Pre-load pattern: bulk-load lookup tables at operation start instead of N+1 individual queries"
  - "Batch DB writes: collect validated records in list, upsert in single call at end"

requirements-completed: []

# Metrics
duration: 27min
completed: 2026-02-20
---

# Phase 16 Plan 02: Pipeline Performance Optimizations Summary

**3.4x GAQL speedup via ThreadPoolExecutor; 72K variant cache pre-load eliminates N+1 queries; date-range bug confirmed fixed; full backfill restarted at 9-19h ETA**

## Performance

- **Duration:** ~27 min (code + local tests + deploy + job cleanup + backfill restart)
- **Started:** 2026-02-19T23:42:38Z
- **Completed:** 2026-02-20T00:10:04Z
- **Tasks:** 3 of 3 complete
- **Files modified:** 5 (google_ads_performance.py, google_ads_search_terms.py, workers.py, 2 new scripts)

## Accomplishments

### Fix A: Parallel GAQL chunk execution (google_ads_performance.py)

Added `ThreadPoolExecutor(max_workers=5)` to replace the sequential `for chunk in _chunks(...)` loop in `fetch_batch_product_performance`. The `_fetch_chunk_data` helper function encapsulates per-chunk logic and is thread-safe (each call creates its own gRPC `search_stream`).

**Local test results:**
- Sequential baseline (16-01): 13.2s for 250 offer IDs (10 chunks × ~1.3s each)
- Parallel with 5 workers: **3.9s** (3.4x speedup)
- Cloud Run logs confirm parallel execution: multiple chunks returning at same timestamp (`00:06:21.741`, `00:06:21.584`, `00:06:21.577`, `00:06:21.446`)

### Fix B: Bulk variant_index pre-load (google_ads_search_terms.py)

Added `_preload_variant_cache()` method that bulk-loads all `variant_index` rows via paginated Supabase queries (1000 rows/page) before the search term processing loop. Called at the start of `fetch_search_terms` when cache is empty.

**Local test results:**
- Loaded **72,023 rows** (more than expected ~69,600 — table grown since plan written) in **7.7 seconds** via 73 pages
- Cache lookup verified: sample offer ID resolves correctly to master_sku
- Eliminates N+1: tens of thousands of individual Supabase queries → 73 paginated queries

### Fix C: Batched performance_baselines upsert (workers.py)

Modified `collect_performance_batch` to collect all validated `PerformanceMetrics` records in `all_baseline_records` list during the per-SKU loop, then execute a single `supabase.table("performance_baselines").upsert(all_baseline_records, ...)` after the loop. Individual per-SKU validation and logging retained for observability.

**Expected improvement:** 10 individual upserts → 1 batch upsert per 10-SKU batch (minor reduction in DB round trips; more significant at scale)

### Task 3: Search terms date-range diagnosis

Created `scripts/diagnose_search_terms_date_range.py` that runs both `days=30` and `start_date`/`end_date` code paths side-by-side with per-step logging.

**Diagnosis result:** Bug is already fixed (resolved in 16-01 when `start_date`/`end_date` params were threaded through).

Per-step comparison:
| Step | days=30 | start_date/end_date |
|------|---------|---------------------|
| _fetch_campaign_products | 258 campaigns, 34,490 combos | 258 campaigns, 34,489 combos |
| fetch_search_terms (recent) | 1,000 results, 145 unique SKUs | 1,000 results, 145 unique SKUs |
| fetch_search_terms (historical: Nov-Dec 2025) | N/A | 1,995 results, 119 unique SKUs |

Both paths produce identical results. Historical windows work correctly. 180-day backfill via 6x30-day windows is viable.

## Task 2: Orphaned Job Cleanup and Backfill Restart

### Jobs killed

| Job ID | Table | Reason |
|--------|-------|--------|
| 2c738140-df86-464f-b7ea-0b70702d79c2 | backfill_jobs | Killed by 16-01 Cloud Run redeployment at 90/2784 — restarted with optimized code |
| 031c9e27-4a5b-4adf-8b91-121ffabda400 | search_query_sync_jobs | Hung with 0 queries_fetched since 18:51 UTC |
| d44cc763-cbe4-47f0-a735-8176530e409f | search_query_sync_jobs | Hung with 0 queries_fetched since 18:51 UTC |
| da7cfbed-812d-4d4f-9695-4a05a219c315 | search_query_sync_jobs | Hung with 0 queries_fetched since 18:51 UTC |
| 124c17b0-a91e-47ac-9a51-5200f9963244 | search_query_sync_jobs | Hung with 0 queries_fetched since 18:51 UTC |

### Test batch result

- **Job ID:** 9004c217-e5dd-4b55-a6df-2c29d0d6089d
- **SKUs:** 10 (101, 1016, 101A, 102, 1020-1025)
- **Result:** status=complete, completed=10/10, failed=0
- **Duration:** ~110 seconds (~11s per SKU vs ~60s per SKU in 16-01 sequential)
- **Cloud Run logs:** "Processing 159 offer IDs in 7 chunks (max 5 parallel)" confirmed

Note: First test batch (a939983d) was killed by Cloud Run redeployment of the second commit (e79883e8). Marked as failed and re-run. Second test batch (9004c217) completed 10/10 successfully.

### Full performance backfill

- **Job ID:** 3da77cd6-1e8c-4897-b2c7-634f3e4412db
- **SKUs:** 2,784
- **Started:** 2026-02-20T00:00:40Z
- **Status at plan completion:** running, 20/2784 (0.7%)
- **ETA:** 9-19 hours (estimated, fluctuates during cache warming)
- **pre-restart performance_baselines rows:** 189

### Search terms sync

- **Job ID:** ca19f9fa-9f32-46f2-ab9c-c8bca88d4b7f
- **Window:** 2026-01-20 to 2026-02-19 (30 days, most recent)
- **Started:** 2026-02-20T00:01:24Z
- **Status at plan completion:** running (campaign_products phase, ~34,539 combos found, queries_fetched=0 — GAQL not yet started)
- **Previous completed sync jobs:** 14547a15 (49,982 queries), 1201e5a6 (49,747 queries)

## Code Changes

### google_ads_performance.py
```python
# Before (sequential)
for chunk in _chunks(safe_ids, OFFER_ID_CHUNK_SIZE):
    rows = _run_gaql_query(client, customer_id, query)
    # process rows

# After (parallel)
MAX_PARALLEL_CHUNKS = 5
with ThreadPoolExecutor(max_workers=MAX_PARALLEL_CHUNKS) as executor:
    futures = {executor.submit(_fetch_chunk_data, client, customer_id, chunk, ...): i}
    for future in as_completed(futures):
        chunk_results = future.result()
        for product_id, row in chunk_results:
            grouped[product_id].append(row)
```

### google_ads_search_terms.py
```python
# New method
def _preload_variant_cache(self) -> int:
    """Bulk-load all 72,023 variant_index rows into _variant_cache."""
    # Paginated load: 1000 rows per page
    # Called at start of fetch_search_terms when cache is empty

# Called in fetch_search_terms
if not self._variant_cache:
    self._preload_variant_cache()
```

### workers.py
```python
# Before (N upserts in loop)
supabase.table("performance_baselines").upsert(validated.model_dump(...)).execute()

# After (collect then batch upsert)
all_baseline_records.append(validated.model_dump(exclude_none=True))
# After loop:
supabase.table("performance_baselines").upsert(all_baseline_records, on_conflict="master_sku,platform").execute()
```

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| f8508ca8 | perf | parallelize GAQL chunks, batch variant_index lookups, batch upserts |
| e79883e8 | test | add search terms date-range diagnosis script |

## Deviations from Plan

### Task ordering changed (minor)

Plan order was Task 1 → Task 2 → Task 3. Actual execution: Task 1 → Task 3 → Task 2. Task 3 (diagnosis) was run before Task 2 Step 5 (search terms backfill decision) as intended by the plan. The search terms sync was started in Task 2 using `start_date`/`end_date` based on Task 3 diagnosis confirming the fix.

### Search terms date-range bug already fixed

**Expected:** Bug present, requiring diagnosis + fix.
**Actual:** Both `days=30` and `start_date`/`end_date` paths return identical results. Bug was fixed in 16-01 when the parameters were properly threaded through `fetch_search_terms`. No code fix needed — diagnosis committed for documentation.

### Test batch killed by second redeployment

First test batch (a939983d) was killed by the redeployment triggered by the second push (e79883e8, diagnosis script). Expected behavior per CLAUDE.md ("Jobs still terminate during deployments"). Second test batch (9004c217) completed 10/10.

### search_query_sync_jobs.skus_covered column missing

The diagnosis query used `skus_covered` column per the plan template, but this column doesn't exist in the actual table schema. Used `queries_fetched` instead to identify hung jobs (4 jobs with `queries_fetched=0` for >10 minutes).

## Self-Check

### Files verified to exist
- `src/feedops/integrations/google_ads_performance.py` - ThreadPoolExecutor added ✓
- `src/feedops/integrations/google_ads_search_terms.py` - _preload_variant_cache added ✓
- `src/feedops/jobs/workers.py` - batch upsert pattern added ✓
- `scripts/test_parallel_perf_chunks.py` - created ✓
- `scripts/diagnose_search_terms_date_range.py` - created ✓

### Commits verified
- f8508ca8 exists ✓
- e79883e8 exists ✓

## Self-Check: PASSED

---
*Phase: 16-fix-google-ads-backfill-pipeline-search-terms-performance-metrics*
*Completed: 2026-02-20*
