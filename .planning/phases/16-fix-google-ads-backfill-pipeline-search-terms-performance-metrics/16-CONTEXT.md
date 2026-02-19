# Phase 16: Fix Google Ads Backfill Pipeline — Search Terms + Performance Metrics - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix two root-cause bugs blocking full 2,784-SKU Google Ads data backfill — performance metrics GAQL IN() clause oversize, and search terms date-range returning 0 results — then run both syncs to completion and verify monitoring page coverage numbers.

</domain>

<decisions>
## Implementation Decisions

### Search Terms Debug Strategy
- Root cause is unknown — **diagnose first**, do not assume or attempt blind fixes
- Suspected failure point: how search terms are mapped to internal product data (GAQL result → offer ID → variant_index lookup) — trace this specifically
- Diagnosis approach: **logs + side-by-side comparison** — run both `days=30` and `start_date`/`end_date` for the same window, log every intermediate step in both code paths, diff the GAQL queries sent and intermediate results
- Specifically trace the full join path: GAQL result → offer ID extraction → variant_index lookup → final row count at each step
- Fix validation strategy: Claude's discretion (pick appropriate depth based on what the diagnosis reveals)
- Dedup strategy for 180-day backfill insert: Claude's discretion
- **Hard deadline:** If root cause is not identified and fixed within plan 16-02, do NOT block the phase — document what was tried, open a new phase for the remaining search terms work

### Backfill Execution Confidence Gate
- **Performance metrics:** Run small test batch of 10-25 SKUs first before triggering full 2,784-SKU backfill
- **Pass criteria before full run:** Job completes without hanging AND returns non-zero rows for the test SKUs (both conditions must be true)
- **Success rate threshold for full run:** ≥80% is acceptable — some SKUs have no Google Ads impressions and will fail gracefully
- **Resumability:** The plan must verify that the backfill job can resume from a checkpoint before committing to the full run (Phase 5 infrastructure should support this — confirm it works)

### Local Testing Before Deploy
- **Performance metrics fix:** Test locally with a small real GAQL call against the live Google Ads API before pushing to Cloud Run
- **Search terms fix:** Claude decides the local vs production split based on what the diagnosis requires (some bugs can only be reproduced against real API data)
- **Local environment:** `.env.vercel` contains all needed credentials; use standard pattern: `source .env.vercel && PYTHONPATH=./src .venv/bin/python scripts/...`

### Plan Parallelism
- **16-01 and 16-02 run in parallel (wave 1)** — these are independent bugs in different files (`google_ads_performance.py` vs `google_ads_search_terms.py`) with no shared state conflicts
- **16-03 is wave 2:** Claude determines the exact dependency structure (likely depends_on both 16-01 and 16-02 completing their backfill execution steps)
- **Commit strategy:** Claude decides (single vs. separate commits)

### Claude's Discretion
- Fix validation depth after search terms root cause is found
- Dedup strategy for 180-day backfill insert (delete-before-insert vs upsert)
- Local vs production split for search terms diagnosis
- Wave dependency structure for 16-03
- Commit/deploy coordination for the two fixes

</decisions>

<specifics>
## Specific Ideas

- Trace the exact code path: `_fetch_campaign_products` → campaign ID extraction → `search_term_view` GAQL query → offer ID extraction → variant_index join. Log row counts at each step for both `days=30` and `start_date`/`end_date` approaches.
- The `days=30` approach working (10,000 queries, 424 SKUs) is the known-good baseline — the date-range path needs to produce equivalent results for the same period

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-fix-google-ads-backfill-pipeline-search-terms-performance-metrics*
*Context gathered: 2026-02-19*
