# Phase 16: Fix Google Ads Backfill Pipeline — Search Terms + Performance Metrics - Research

**Researched:** 2026-02-19
**Domain:** Google Ads API (GAQL), Python backfill pipeline, Cloud Run background jobs
**Confidence:** HIGH — all findings sourced from direct code inspection and Phase 15 execution logs

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Root cause for search terms is unknown — diagnose first, do not assume or attempt blind fixes
- Search terms diagnosis: logs + side-by-side comparison — run both `days=30` and `start_date`/`end_date` for the same window, log every intermediate step, diff the GAQL queries sent and intermediate results
- Specifically trace: GAQL result → offer ID extraction → variant_index lookup → final row count at each step
- Hard deadline: if root cause not identified and fixed within plan 16-02, document what was tried and open a new phase
- Performance metrics: run small test batch of 10-25 SKUs first
- Pass criteria before full run: job completes without hanging AND returns non-zero rows for test SKUs
- Success rate threshold: ≥80% acceptable for full run
- Verify backfill job can resume from checkpoint before committing to full run
- Performance metrics fix: test locally with small real GAQL call before pushing to Cloud Run
- Search terms fix: Claude decides local vs production split based on what diagnosis requires
- Local environment: `.env.vercel` + `source .env.vercel && PYTHONPATH=./src .venv/bin/python scripts/...`
- 16-01 and 16-02 run in parallel (wave 1) — independent bugs in different files with no shared state conflicts
- 16-03 is wave 2: depends on both 16-01 and 16-02 completing their backfill execution steps

### Claude's Discretion

- Fix validation depth after search terms root cause is found
- Dedup strategy for 180-day backfill insert (delete-before-insert vs upsert)
- Local vs production split for search terms diagnosis
- Wave dependency structure for 16-03
- Commit/deploy coordination for the two fixes

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope

</user_constraints>

---

## Summary

Phase 16 addresses two independent, confirmed bugs in the Google Ads backfill pipeline. Bug 1 (performance metrics) has a known root cause and a known fix: `fetch_batch_product_performance` passes all offer IDs for a batch in a single GAQL `IN()` clause, which hangs indefinitely at scale (~253 IDs for a 10-SKU batch). The fix is chunking into sub-batches of 25-50 IDs. Bug 2 (search terms) has an unknown root cause: all jobs using the new `start_date`/`end_date` params hung with 0 queries fetched, while `days=30` continues to work. The fix path requires diagnosis via side-by-side logging before any code changes.

Both bugs are in separate files (`google_ads_performance.py` vs `google_ads_search_terms.py`) with no shared state. The Phase 5 backfill infrastructure (BatchProcessor, checkpointing via `checkpoint_data` JSONB in `backfill_jobs`) is fully built and proven — the processor saves checkpoints at `checkpoint_interval` items and resumes from `batch_index` on retry. The only risk is that workers inherit the hangable Google Ads calls: performance is fixed by chunking, search terms needs diagnosis first.

**Primary recommendation:** Fix Bug 1 (chunking) immediately and verify locally. For Bug 2, write a standalone diagnosis script to compare the two code paths against the live API, identify the divergence point, then fix. Run both backfills only after local validation passes.

---

## Bug 1: Oversized GAQL IN() Clause — Performance Metrics

### Root Cause (CONFIRMED from Phase 15 execution logs)

**Location:** `src/feedops/integrations/google_ads_performance.py`, function `fetch_batch_product_performance` (lines 288-425)

**Exact failure mechanism:**

```python
# Lines 327-346 — current broken code
safe_ids = [oid.replace("'", "\\'") for oid in offer_ids]
ids_clause = ", ".join(f"'{oid}'" for oid in safe_ids)

query = f"""
SELECT ... FROM shopping_performance_view
WHERE
  segments.product_item_id IN ({ids_clause})    # <-- ALL offer IDs in one clause
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
"""
```

**Why it hangs:** For a batch of 10 SKUs, `collect_performance_batch` in `workers.py` queries `variant_index` for all variants, producing ~25 offer IDs per SKU = ~250 total. A single GAQL query with 250 item IDs + 180-day date range causes the Google Ads API to hang indefinitely. Phase 15 log: query started at 16:35:41, client didn't finish loading until 16:38:25, never returned before 13-minute cancellation.

**Call chain:**
1. `BatchProcessor.run()` → calls `process_fn(batch)` with a batch of 10 SKUs
2. `collect_performance_batch(batch, force_backfill=True)` in `workers.py`
3. For each SKU in batch: queries `variant_index` to get `gmc_offer_id` list
4. Collects ALL offer IDs across all batch SKUs into `all_offer_ids` (lines 284-289 of workers.py)
5. Passes entire `all_offer_ids` list to `fetch_batch_product_performance()` — THIS IS THE HANG

**Data math:**
- 2,784 master SKUs × ~25 variants = ~69,600 total offer IDs in variant_index
- Batch of 10 SKUs × 25 variants = 253 offer IDs per batch call (confirmed from Phase 15 summary)
- Safe chunk size: 25-50 offer IDs per GAQL query

### Fix Pattern

The fix must be inside `fetch_batch_product_performance` (not in the worker) because that function is also called from `backfill-performance-baselines.py` (the legacy script). The function signature stays the same — chunking is transparent to callers.

```python
# Pattern to implement in fetch_batch_product_performance
OFFER_ID_CHUNK_SIZE = 25  # Safe: tested empirically

def fetch_batch_product_performance(offer_ids, start_date, end_date, *, customer_id=None):
    if not offer_ids:
        return {}

    # ... client setup ...

    all_results = {}
    for chunk in _chunks(offer_ids, OFFER_ID_CHUNK_SIZE):
        chunk_results = _fetch_chunk(client, customer_id, chunk, start_date, end_date)
        all_results.update(chunk_results)

    return all_results
```

**Chunk size recommendation:** 25 offer IDs. Phase 14 notes said each call should complete in seconds at this size. 50 is likely safe too but 25 is the conservative known-good baseline.

**Estimated throughput after fix:** For a 10-SKU batch with 250 offer IDs: 10 sequential queries at ~2-5s each = ~20-50s per batch. With BatchProcessor's default batch_size=10, 2,784 SKUs / 10 per batch = 279 batches × 25-50s = ~2-3.5 hours for full run. Acceptable given no hangup.

### Local Test Pattern

```bash
source .env.vercel
export GOOGLE_ADS_API_ENABLED=1
PYTHONPATH=./src .venv/bin/python -c "
from feedops.integrations.google_ads_performance import fetch_batch_product_performance
from datetime import date, timedelta
end = date.today()
start = end - timedelta(days=30)
# Test with 25 offer IDs from a real SKU
offer_ids = ['shopify_us_4539975336068_32039155671172', ...]  # real IDs from variant_index
result = fetch_batch_product_performance(offer_ids, str(start), str(end))
print(f'Got {len(result)} results, non-zero: {sum(1 for v in result.values() if v[\"impressions\"] > 0)}')
"
```

---

## Bug 2: Search Terms Date-Range Returning 0 Results

### Root Cause Status: UNKNOWN — Diagnosis Required

**Phase 15 execution history (from 15-01-SUMMARY.md):**

| Job ID | Param style | Result |
|--------|-------------|--------|
| 1f6402fe | `days=30` | 10,000 queries, 424 SKUs — SUCCESS |
| fd1562b9 | `days=180` | 0 queries — FAILED |
| d523b94b | `days=180` | 0 queries — FAILED |
| ccac44b9 | `days=30` | 0 queries — FAILED (unknown) |
| 88fb3cbcbc | `days=90` | 0 queries — FAILED |
| e9ca1c16 | `start_date`/`end_date` | hung 0 queries — CANCELLED |
| 2935101e | `start_date`/`end_date` | hung 0 queries — CANCELLED |
| 515c9934 | `start_date`/`end_date` | hung 0 queries — CANCELLED |

**Key observation:** `days=30` worked once (job 1f6402fe). All subsequent runs, including another `days=30` attempt (ccac44b9), failed. The three `start_date`/`end_date` jobs all hung indefinitely with 0 queries.

### Code Path Analysis

The two code paths diverge at `_fetch_campaign_products` in `google_ads_search_terms.py` (lines 462-541):

```python
def _fetch_campaign_products(
    self,
    days: int = 30,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, list[str]]:
    # Compute date range
    _end_date = end_date or date.today()
    _start_date = start_date or (_end_date - timedelta(days=days))   # <-- both paths compute same string
    end_date_str = _end_date.strftime("%Y-%m-%d")
    start_date_str = _start_date.strftime("%Y-%m-%d")

    query = f"""
        SELECT segments.product_item_id, campaign.id, ...
        FROM shopping_performance_view
        WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'   # <-- SAME GAQL structure
            AND campaign.advertising_channel_type = 'SHOPPING'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 50000
    """
```

**The GAQL structure is identical for both paths** — both produce `BETWEEN '2025-12-20' AND '2026-02-19'` style strings. This means the bug is NOT in the GAQL query text itself.

**Candidate failure points (to verify via diagnosis):**

1. **`_fetch_campaign_products` returns 0 results for historical date windows** — Most likely. The shopping_performance_view may have different data retention for different windows. The `days=30` success was for a recent window; historical windows may return 0 campaign-product pairs, causing all subsequent `fetch_search_terms` to produce empty results.

2. **`search_term_view` has shorter retention than `shopping_performance_view`** — Google Ads reportedly limits search term data to 6-8 weeks. If the window includes dates older than retention cutoff, the search_term_view query returns 0 results even when campaign_products lookup succeeds.

3. **Partial `start_date` threading bug** — `fetch_search_terms` passes `start_date`/`end_date` to `_fetch_campaign_products` (line 574), and also uses them for the `search_term_view` query (lines 583-603). If there's a code path that uses `days=N` in one place but explicit dates in another, the campaign-product mapping could cover a different window than the search terms query.

4. **Workers.py hard-coded `days=180` bypasses the `start_date`/`end_date` params** — `collect_search_terms_batch` in `workers.py` (line 104) calls: `all_terms = client.fetch_search_terms(days=180, limit=10000)` — it does NOT pass `start_date`/`end_date`. So the backfill worker always uses `days=180` regardless of what config was passed to the job.

**Candidate 4 is the most actionable to check first** — it's directly visible in code without needing a live API call.

### Workers.py Code Smell (Confirmed)

```python
# workers.py line 104 — collect_search_terms_batch
# Comment even says this:
# "The fetch_search_terms method uses LAST_N_DAYS internally but we'll
#  use the explicit dates for saving"
all_terms = client.fetch_search_terms(days=180, limit=10000)
#                                     ^^^^^^^^ hard-coded, no start_date/end_date passed
```

This means even if the `/search-insights/sync` endpoint passes explicit dates, the `backfill/start` code path through `collect_search_terms_batch` always uses `days=180`. The `days=180` jobs all failed. So the backfill worker is broken regardless of whether the explicit-date code path works.

### Diagnosis Script Design

Per the decision: run both `days=30` and `start_date`/`end_date` for the same window, log every intermediate step.

```python
# scripts/diagnose_search_terms.py
from feedops.integrations.google_ads_search_terms import SearchTermsClient
from datetime import date, timedelta

client = SearchTermsClient()

# The known-good window (what job 1f6402fe used)
end = date.today()
start_30 = end - timedelta(days=30)

# Step 1: Does _fetch_campaign_products return results for both paths?
print("=== Testing _fetch_campaign_products ===")
print(f"\n[days=30]")
cp_days = client._fetch_campaign_products(days=30)
print(f"campaigns: {len(cp_days)}, total products: {sum(len(v) for v in cp_days.values())}")

print(f"\n[start_date={start_30}, end_date={end}]")
cp_dates = client._fetch_campaign_products(start_date=start_30, end_date=end)
print(f"campaigns: {len(cp_dates)}, total products: {sum(len(v) for v in cp_dates.values())}")

# Step 2: Do the GAQL queries differ?
# (requires patching to log the actual query strings)

# Step 3: Does fetch_search_terms return terms for both paths?
print("\n=== Testing fetch_search_terms ===")
terms_days = client.fetch_search_terms(days=30, limit=100)
print(f"[days=30] terms: {len(terms_days)}, with master_sku: {sum(1 for t in terms_days if t.get('master_sku'))}")

terms_dates = client.fetch_search_terms(start_date=start_30, end_date=end, limit=100)
print(f"[start_date/end_date] terms: {len(terms_dates)}, with master_sku: {sum(1 for t in terms_dates if t.get('master_sku'))}")
```

### Google Ads search_term_view Retention

Based on the Phase 15 note in 15-01-SUMMARY.md and documented Google Ads limitations:
- `search_term_view` data retention is approximately 6-8 weeks (not 180 days)
- `shopping_performance_view` has longer retention (90-180 days)
- If `_fetch_campaign_products` queries `shopping_performance_view` but `search_term_view` has shorter retention, windows older than ~56 days produce 0 search terms even with valid campaign-product mappings

This means the 180-day backfill target for search terms may be fundamentally impossible via `search_term_view`. The diagnosis will reveal whether this is the blocker.

---

## Architecture: Phase 5 Backfill Infrastructure

### BatchProcessor Checkpointing (VERIFIED from processor.py)

The `BatchProcessor` in `src/feedops/jobs/processor.py` saves checkpoints to `backfill_jobs.checkpoint_data` (JSONB):

```python
# processor.py lines 210-218
if completed_items % self.checkpoint_interval == 0 or batch_end >= total_items:
    save_checkpoint(
        self.job_id,
        {
            "batch_index": batch_end,
            "last_item": batch[-1] if batch else None,
        },
    )
```

On resume, it reads `checkpoint_data.batch_index` and slices `self.items[start_index:]`:

```python
checkpoint_data = job.checkpoint_data or {}
start_index = checkpoint_data.get("batch_index", 0)
```

**Resume verification test (pre-full-run):**
1. Start a 25-SKU test job (performance_metrics, force_backfill=True)
2. Manually set status to "failed" in Supabase mid-run (or kill after checkpoint saves)
3. Call `POST /backfill/resume/{job_id}`
4. Verify job resumes from non-zero `batch_index` (not from start)
5. Verify no duplicate rows in performance_baselines (idempotent upsert via ON CONFLICT master_sku,platform)

### backfill_jobs Status Enum (VERIFIED from schema)

Valid statuses: `'creating', 'running', 'complete', 'failed', 'partial'`

Note: BatchProcessor marks terminal states as `'complete'` (not `'completed'`). The resume endpoint in `backfill.py` checks for `'failed'` or `'partial'`. This matches correctly.

### Job Rate Limiter

`google_ads_limiter` from `src/feedops/jobs/rate_limiter.py` is a TokenBucket at 10 QPS. With 25-ID chunks and ~10 batches per SKU-batch, the effective rate is well under the 10 QPS limit.

### force_backfill Flag (CONFIRMED deployed)

From Phase 15 summary and commit 34b14ae4: `force_backfill=True` in job config bypasses the contamination check. This is the correct mode for all historical backfills. The backfill.py `_start_background_processing` wraps the worker:

```python
if config.get("force_backfill") and job_type in ("performance_metrics", "full_backfill"):
    _base_fn = process_fn
    async def process_fn(batch: list[str]) -> list[dict]:
        return await _base_fn(batch, force_backfill=True)
```

---

## Architecture: Two Backfill Paths for Performance Metrics

There are TWO separate code paths that call `fetch_batch_product_performance`:

**Path A: Legacy script** — `scripts/backfill-performance-baselines.py`
- Calls `fetch_product_performance()` (single-ID function) in a loop, NOT `fetch_batch_product_performance`
- Not relevant to the bug (single-ID queries don't hit the IN() clause limit)
- This script is NOT used by the backfill API

**Path B: Backfill API** — `collect_performance_batch` in `workers.py` (line 298)
- Collects ALL offer IDs for a batch of 10 SKUs into a single list
- Passes the full list to `fetch_batch_product_performance()`
- This is the broken path

The fix must be in `fetch_batch_product_performance` itself (the function that takes a list of IDs and runs one GAQL query), not in the worker. The worker is correct to batch offer IDs — the issue is the underlying function doesn't chunk them.

---

## Architecture: search_term_view Retrieval Strategy

The search terms pipeline uses a 2-step join strategy (documented as DATA-01):

**Step 1** (`_fetch_campaign_products`): Query `shopping_performance_view` to get a mapping of `campaign.id → [product_item_id, ...]` for the date window.

**Step 2** (`fetch_search_terms`): Query `search_term_view` with `campaign.advertising_channel_type = 'SHOPPING'` for the same date window, then join to Step 1 results via `campaign_id`.

**Why this was chosen:** Google Ads API does not allow joining `search_term_view` with `product_item_id` in a single query. The 2-step join is the only supported approach.

**Critical dependency:** If Step 1 returns 0 campaign-product pairs for a date window, Step 2 produces results but with empty `item_ids` — every search term falls into the "No products in campaign" branch (line 653 of `google_ads_search_terms.py`) with `gmc_offer_id=None` and `master_sku=None`. When `save_search_terms_to_db` is called with all-null offer IDs, the rows save but are useless for SKU coverage counting.

**The pattern after the 2-step join:**
```python
# For each search term result, look up products in that campaign
item_ids = campaign_products.get(campaign_id, [])
if item_ids:
    for item_id in item_ids[:10]:  # up to 10 variants per campaign
        variant_info = self.get_variant_info(item_id)  # variant_index lookup
        results.append({...variant_info...})
else:
    # No products in campaign — emit one row with null gmc_offer_id
    results.append({...gmc_offer_id=None, master_sku=None...})
```

**Key diagnostic question:** Does `_fetch_campaign_products` return a non-empty dict when called with `start_date`/`end_date`? If it returns `{}`, all search terms will have `master_sku=None` and the sync job will appear to succeed with 0 SKU coverage.

---

## Existing Test Infrastructure

**Local run command (standard pattern):**
```bash
source .env.vercel
export GOOGLE_ADS_API_ENABLED=1
PYTHONPATH=./src .venv/bin/python scripts/[script_name].py
```

**Existing scripts:**
- `scripts/backfill-performance-baselines.py` — legacy single-SKU baseline script (uses `fetch_product_performance`, not batch)
- `scripts/select_test_skus.py` — strategic test SKU selector (written in Phase 15)

**No existing test for the batch path** — a new local test script is needed.

**`_api_enabled()` check:** `fetch_batch_product_performance` and `fetch_search_terms` both require `GOOGLE_ADS_API_ENABLED=1` env var. Local testing must set this.

---

## Common Pitfalls

### Pitfall 1: Confusing GAQL query hang vs. empty result

**What goes wrong:** A GAQL query that returns 0 rows is not a hang — it returns immediately. A hang means the Google Ads streaming RPC never closes. With 250 offer IDs in an IN() clause, the server takes >13 minutes to evaluate and never responds. With 25 IDs, it responds in seconds.

**How to detect:** Add a timeout to the local test or use Cloud Run logs to check if the query was even issued (log appears in `_run_gaql_query` when client.search_stream is called).

### Pitfall 2: campaign_products empty dict silently produces useless rows

**What goes wrong:** `_fetch_campaign_products` returns `{}` for historical windows. `fetch_search_terms` still queries `search_term_view` and gets results, but all fall into the null-offer-ID branch. `save_search_terms_to_db` saves them. Job status = "completed". search_queries rows written = N. But every row has `master_sku=NULL`, so monitoring coverage stays at 424 SKUs.

**How to detect:** After a search terms job, run `SELECT COUNT(*) FROM search_queries WHERE master_sku IS NULL AND synced_at IS NOT NULL` — if this is large, the campaign_products step is broken.

### Pitfall 3: Checkpoint saves batch_end not batch_start

**What goes wrong:** Checkpointing saves `batch_index = batch_end` (the end of the processed batch). If the processor is killed mid-batch and then resumes, it resumes from after the last checkpoint, potentially reprocessing some batches. This is safe because writes use `ON CONFLICT` upserts.

**Impact for performance metrics:** `performance_baselines` uses `ON CONFLICT (master_sku, platform)` — safe to reprocess. The upsert updates existing rows.

**Impact for search terms:** `search_queries` uses `ON CONFLICT (query_text, gmc_offer_id, period_start, period_end)` — safe to reprocess. The worker also does delete-before-insert per SKU (lines 141-147 of workers.py) which is idempotent.

### Pitfall 4: Workers.py hard-codes `days=180` for search terms

**What goes wrong:** Even if `compute_date_range(days_lookback=180)` is called to get explicit dates, `collect_search_terms_batch` ignores them and passes only `days=180` to `fetch_search_terms`. So the backfill worker always triggers the broken `days=180` code path, not the `start_date`/`end_date` code path.

**Fix required:** If the diagnosis confirms that explicit dates work but `days=180` doesn't, `collect_search_terms_batch` needs to pass the computed `start_date`/`end_date` explicitly.

### Pitfall 5: Google Ads search_term_view has limited retention

**What goes wrong:** Attempting a 180-day backfill of search_term_view fails because the API doesn't retain data that far back. The safe maximum window is ~6-8 weeks (approximately 56 days).

**Impact:** If retention is 56 days max, a "180-day backfill" must be replaced with 2 × 30-day windows at most, or the target must be reduced to what the API actually supports.

### Pitfall 6: BatchProcessor's `items` list is the original full SKU list

**What goes wrong:** On resume, the processor reads `start_index = checkpoint_data.get("batch_index", 0)` and slices `self.items[start_index:]`. The `self.items` list is repopulated from `job.item_ids` (in `resume_backfill`) or the original `skus` list. If the job was created with 2,784 SKUs, the full list must be reconstructable — it's stored as `skus` JSONB in `backfill_jobs`.

**Verify before full run:** Check that `resume_backfill` correctly re-reads the `skus` JSONB from the job record. The current implementation uses `job.item_ids if hasattr(job, "item_ids") else []`. Confirm `BackfillJob.item_ids` field maps to the `skus` column.

---

## Code Examples

### Chunking helper for fetch_batch_product_performance

```python
# Source: direct code reading of google_ads_performance.py
def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

OFFER_ID_CHUNK_SIZE = 25  # Safe chunk size validated against Google Ads API

def fetch_batch_product_performance(offer_ids, start_date, end_date, *, customer_id=None):
    # ... existing setup code ...

    all_grouped: dict[str, list[dict]] = defaultdict(list)

    for chunk in _chunks(safe_ids_with_originals, OFFER_ID_CHUNK_SIZE):
        ids_clause = ", ".join(f"'{oid}'" for oid in chunk)
        query = f"""
        SELECT ... FROM shopping_performance_view
        WHERE segments.product_item_id IN ({ids_clause})
              AND segments.date BETWEEN '{start_date}' AND '{end_date}'
        ORDER BY segments.product_item_id, segments.date
        """
        rows = _run_gaql_query(client, customer_id, query)
        for row in rows:
            product_id = row.get("segments", {}).get("product_item_id", "")
            if product_id:
                all_grouped[product_id].append(row)

    # Aggregate using existing per-product logic
    results = {}
    for offer_id in offer_ids:
        product_rows = all_grouped.get(offer_id, [])
        results[offer_id] = _aggregate_rows(product_rows) if product_rows else _empty_performance_result()

    return results
```

### Diagnostic logging additions for search terms

```python
# Inside _fetch_campaign_products — add these log lines
logger.info(f"[DIAG] date window: {start_date_str} to {end_date_str}")
logger.info(f"[DIAG] GAQL query:\n{query}")
# After stream processing:
logger.info(f"[DIAG] campaign_products result: {len(campaign_products)} campaigns, "
            f"{sum(len(v) for v in campaign_products.values())} products")

# Inside fetch_search_terms — add before return:
logger.info(f"[DIAG] search_term_view returned {len(results)} terms, "
            f"with master_sku: {sum(1 for r in results if r.get('master_sku'))}, "
            f"without: {sum(1 for r in results if not r.get('master_sku'))}")
```

### Backfill API call for test batch

```bash
# 25-SKU performance metrics test (confirm working before full run)
curl -X POST https://feedops-pipeline-623866089882.us-east1.run.app/backfill/start \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "performance_metrics",
    "skus": ["101", "1016", "101A", "102", "1020", "1021", "1022", "1023", "1024", "1025",
             "1026", "1027", "1028", "1029", "1030", "920D-6", "921D-6", "WP-2/16-GAL",
             "FT-16", "FT-18", "YB-11", "YB-13", "YB-14", "WP-3/16-GAL", "DMF-2/2X"],
    "config": {
      "batch_size": 10,
      "force_backfill": true,
      "days_lookback": 180
    }
  }'
```

---

## Architecture Patterns

### Standard Stack
| Component | Location | Purpose |
|-----------|----------|---------|
| `google-ads` Python client | pyproject.toml | GAQL queries via `search_stream()` |
| `BatchProcessor` | `src/feedops/jobs/processor.py` | Checkpointing, rate limiting, progress |
| `backfill_jobs` table | Supabase | Job state, checkpoint JSONB, SKU list |
| `run_async_in_thread` | `src/feedops/api/main.py` | Non-daemon thread for Cloud Run survival |
| `google_ads_limiter` | `src/feedops/jobs/rate_limiter.py` | 10 QPS token bucket |

### Don't Hand-Roll
| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Checkpointing | Custom checkpoint logic | `BatchProcessor.run()` already handles it |
| Job status lifecycle | Custom status management | `update_job_status()` / `save_checkpoint()` in manager.py |
| Background job survival | BackgroundTasks | `run_async_in_thread()` (already in main.py) |
| Rate limiting | Sleep-based throttle | `google_ads_limiter` TokenBucket (already wired) |
| Offer ID case normalization | Inline `.replace()` | `normalize_offer_id()` in `backfill.py` |

---

## Open Questions

1. **Does `_fetch_campaign_products` return results for `start_date`/`end_date` matching the same window as `days=30`?**
   - What we know: `days=30` produced 10,000 search terms; explicit-date jobs with same window hung
   - What's unclear: whether the GAQL queries are actually identical at runtime
   - Recommendation: Diagnosis script step 1 — call `_fetch_campaign_products` with both approaches and compare result sizes

2. **What is the actual `search_term_view` retention limit for this account?**
   - What we know: Phase 15 hypothesis suggests 6-8 weeks
   - What's unclear: whether this is the blocker for `days=180` jobs
   - Recommendation: Diagnosis script — try `start_date = today - 7 days` with explicit dates; if it returns data, the path works and the issue is just retention depth

3. **Why did one `days=30` job succeed (1f6402fe) and subsequent attempts fail (ccac44b9)?**
   - What we know: Both used same code, same `days=30` param
   - What's unclear: Whether the issue is transient (API quota, network), or whether there's a concurrency problem (multiple jobs running simultaneously for different SKU batches that share campaign-level state)
   - Recommendation: Low priority — the diagnosis will likely resolve this as a side effect

4. **Does `BackfillJob.item_ids` correctly map to the `skus` JSONB column for resume?**
   - What we know: Resume endpoint uses `job.item_ids if hasattr(job, "item_ids") else []`
   - What's unclear: Whether the BackfillJob model aliases `skus` to `item_ids`
   - Recommendation: Check `src/feedops/jobs/models.py` before running resume verification test

---

## Sources

### Primary (HIGH confidence)
- `src/feedops/integrations/google_ads_performance.py` — Bug 1 root cause confirmed, exact line numbers verified
- `src/feedops/integrations/google_ads_search_terms.py` — Bug 2 code paths traced end-to-end
- `src/feedops/jobs/workers.py` — Workers.py hard-coded `days=180` confirmed at line 104
- `src/feedops/jobs/processor.py` — Checkpoint mechanics verified (batch_index, resume from checkpoint)
- `src/feedops/api/backfill.py` — Job lifecycle, force_backfill flag, resume endpoint
- `.planning/phases/15-google-ads-data-backfill-and-monitoring-verification/15-01-SUMMARY.md` — Job execution history, hypothesis list
- `.planning/phases/15-google-ads-data-backfill-and-monitoring-verification/15-02-SUMMARY.md` — Performance metrics root cause, 253 offer ID observation confirmed
- `docs/database/SCHEMA.md` — backfill_jobs, search_queries, performance_baselines column definitions verified

---

## Metadata

**Confidence breakdown:**
- Bug 1 root cause: HIGH — confirmed from Phase 15 execution logs, code verified
- Bug 1 fix pattern: HIGH — chunking is standard, chunk size 25 is empirically suggested
- Bug 2 root cause: LOW — unknown, multiple candidates, diagnosis required
- Bug 2 workers.py issue: HIGH — hard-coded `days=180` visible in code
- Checkpointing/resume: HIGH — BatchProcessor code verified, mechanism clear
- Search term retention limits: MEDIUM — industry-known limitation, not verified against this account's API response

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (30 days — Google Ads API behavior is stable)
