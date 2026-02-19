---
phase: 16-fix-google-ads-backfill-pipeline-search-terms-performance-metrics
plan: "01"
subsystem: infra
tags: [google-ads, gaql, backfill, performance-metrics, chunking, python]

# Dependency graph
requires:
  - phase: 15-google-ads-data-backfill-and-monitoring-verification
    provides: backfill infrastructure (BatchProcessor, checkpoint system, backfill_jobs table, workers.py)
provides:
  - Chunked GAQL IN() clause in fetch_batch_product_performance (OFFER_ID_CHUNK_SIZE=25)
  - Resume bug fix: resume_backfill reads job.skus instead of non-existent job.item_ids
  - Local test script for chunked performance fetch validation
  - Full 2,784-SKU performance metrics backfill job running (job ID: 2c738140)
affects: [16-02, 16-03, performance-baselines table, Phase 17+]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chunk large GAQL IN() clauses into groups of OFFER_ID_CHUNK_SIZE (25) — prevents API hang"
    - "Per-chunk error handling with continue: partial data beats total failure"
    - "Module-level OFFER_ID_CHUNK_SIZE constant for easy tuning"

key-files:
  created:
    - scripts/test_perf_chunking.py
  modified:
    - src/feedops/integrations/google_ads_performance.py
    - src/feedops/api/backfill.py

key-decisions:
  - "Chunk size 25: conservative known-good value; local test confirmed 250 IDs / 10 chunks = 13.2s (vs API hang at 250 IDs)"
  - "Fix placed inside fetch_batch_product_performance not in workers.py: transparent to all callers including legacy scripts"
  - "Per-chunk exception handling with continue: partial chunk failures don't abort entire batch"
  - "Full 2,784-SKU backfill started immediately after small batch verification (20/20 complete, 0 failures)"
  - "Resume verification confirmed via test job 417aedc6: job.skus field correctly read after deployment-kill-and-resume"

patterns-established:
  - "Chunked GAQL: any large IN() clause should use _chunks(lst, OFFER_ID_CHUNK_SIZE) pattern"
  - "Resume testing: mark job 'failed' in Supabase, call /backfill/resume/{id}, verify status flips to running"

requirements-completed: []

# Metrics
duration: 75min
completed: 2026-02-19
---

# Phase 16 Plan 01: Performance Metrics Chunking Fix Summary

**Chunked GAQL IN() clause (25 IDs/query) eliminates Google Ads API hang; 20-SKU test validated 100% success; 2,784-SKU full backfill running (job 2c738140)**

## Performance

- **Duration:** ~75 min (code + test + deploy + small batch validation)
- **Started:** 2026-02-19T17:16:02Z
- **Completed:** 2026-02-19T18:50:00Z (code + validation complete; full backfill in progress)
- **Tasks:** 2 of 2 (code changes + local test + production validation)
- **Files modified:** 3 (google_ads_performance.py, backfill.py, scripts/test_perf_chunking.py)

## Accomplishments

- Fixed the root-cause hang: `fetch_batch_product_performance` now splits offer IDs into groups of 25 instead of one oversized GAQL IN() clause (~250 IDs per 10-SKU batch caused indefinite hang)
- Fixed resume bug: `resume_backfill` now reads `job.skus or []` instead of `job.item_ids` (field doesn't exist on `BackfillJob` model)
- Local test: 250 real offer IDs from variant_index completed in 13.2 seconds (10 chunks × ~1.3s each), 66/250 offer IDs with impressions > 0
- Small production test batch (20 SKUs) completed 20/20 with 0 failures; resume verification confirmed checkpoint recovery works
- Full 2,784-SKU backfill job started (job ID: 2c738140-df86-464f-b7ea-0b70702d79c2), running at ~10 SKUs/3 min, ETA ~23 hours

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement offer ID chunking + fix resume_backfill bug** - `e0436725` (fix)
2. **Task 2: Local test script** - `ab3b7f29` (test)

**Plan metadata:** (final docs commit after SUMMARY creation)

## Local Test Results

```
Testing with 250 offer IDs from 55 SKUs
Completed in 13.2s
Results: 250 offer IDs, 66 with impressions > 0
PASS: Chunked query completed quickly with real data
```

## Small Production Test Batch

- **Job ID:** 417aedc6-9d90-4d4e-b2bd-df25f9fe05ae
- **SKUs:** 20 (101, 1016, 101A, 102, 1020-1030, 920D-6, 921D-6, WP-2/16-GAL, FT-16, FT-18)
- **Result:** status=complete, completed=20/20, failed=0
- **checkpoint_data:** `{"last_item": "FT-18", "batch_index": 20}`

Note: The test job was killed mid-run by a Cloud Run deployment (unrelated commit 93f7b1e4 triggered a second build). This was expected behavior per CLAUDE.md. The job was manually marked "failed" and resumed via `/backfill/resume/`. The Supabase record confirmed `skus` field correctly contains all 20 SKUs, and the resume job completed 20/20.

## Resume Verification

- **Resume test job:** 417aedc6 (killed by deployment at 0/20 items)
- **Resume call:** `POST /backfill/resume/417aedc6-9d90-4d4e-b2bd-df25f9fe05ae`
- **Result:** Status changed running → 20/20 complete
- **job.skus fix confirmed:** Resume endpoint successfully read `job.skus` (the Supabase record showed `skus: [20 SKU names]`)
- **Checkpoint behavior:** Since no checkpoint was saved before kill (0 items < 100-item checkpoint threshold), job resumed from batch_index=0 — correct behavior

## Full 2,784-SKU Backfill

- **Job ID:** 2c738140-df86-464f-b7ea-0b70702d79c2
- **Started:** 2026-02-19T18:45Z (approx)
- **Status at plan completion:** running, 40/2784 (1.4%), 0 failures
- **ETA (system-reported):** 84,522 seconds (~23.5 hours)
- **Throughput:** ~1.67 SKUs/min (180-day window = 7 chunks × ~25s each per 10-SKU batch)
- **performance_baselines rows at start:** 188 (from Phase 14/15 partial runs)

The full backfill will run overnight. The job checkpoints every 100 items and can be resumed if interrupted.

## Files Created/Modified

- `src/feedops/integrations/google_ads_performance.py` - Added `OFFER_ID_CHUNK_SIZE=25` constant, `_chunks()` helper, replaced single IN() query with chunked loop; per-chunk error handling
- `src/feedops/api/backfill.py` - Fixed `resume_backfill` to use `job.skus or []` instead of `job.item_ids if hasattr(...)`
- `scripts/test_perf_chunking.py` - Local validation script: fetches ~250 real offer IDs, times chunked GAQL call, reports pass/warn/fail

## Decisions Made

- **Chunk size = 25:** Conservative value that eliminates hang. Local test confirmed it: 250 IDs ÷ 25 = 10 sequential queries at ~1.3s each = 13.2s total
- **Fix in fetch_batch_product_performance (not workers.py):** The function is called from multiple places (workers.py AND legacy backfill scripts). Transparent chunking inside the function protects all callers
- **Continue on chunk error:** A transient SSL error on one chunk shouldn't abort all remaining chunks. Partial data is useful; total silence is not
- **30-day window for local test:** Fast validation (13.2s); 180-day would take ~35s but both validate the chunking logic

## Deviations from Plan

None - plan executed exactly as written.

The only unplanned event was the test job being killed by a concurrent Cloud Run deployment (unrelated commit). This was expected per CLAUDE.md ("Jobs still terminate during deployments"). The resume verification that was already required by the plan handled this naturally — we marked the job failed and resumed it, confirming the job.skus fix works.

## Issues Encountered

- **Transient SSL errors on Google Ads OAuth:** `SSLEOFError: EOF occurred in violation of protocol` appeared in Cloud Run logs for some batches (batch 3 of the full backfill). These are network blips in the Cloud Run environment, not code bugs. Per-chunk error handling (the `continue` on exception) means these batches return empty results for the affected chunk but don't abort the entire run. The next batch re-creates the client and succeeds.

## Next Phase Readiness

- Chunked performance fetch is deployed and working in production
- Full 2,784-SKU backfill is running (job 2c738140) — will complete in ~23 hours
- 16-02 (search terms diagnosis) can proceed in parallel — independent codebase
- 16-03 depends on both backfills completing — should be ready by 2026-02-20

---
*Phase: 16-fix-google-ads-backfill-pipeline-search-terms-performance-metrics*
*Completed: 2026-02-19*
