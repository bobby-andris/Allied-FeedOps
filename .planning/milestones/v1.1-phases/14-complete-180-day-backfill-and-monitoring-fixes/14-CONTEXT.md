# Phase 14: Complete 180-day Backfill & Monitoring Fixes - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Apply the `backfill_jobs` migration, fix the LAST_N_DAYS GAQL bug in `google_ads_search_terms.py`, re-trigger the 180-day search terms sync, run a performance metrics backfill for all 2,784 master SKUs, and fix the monitoring dashboard to show accurate coverage numbers and job status. No new features — this phase completes data infrastructure and fixes broken observability.

**Scale clarification (critical for planner):**
- 2,784 master SKUs (what the pipeline tracks)
- Each master SKU has ~28 finish variants → ~72k+ unique `gmc_offer_ids` in `variant_index`
- Google Ads operates at the variant level (gmc_offer_id), NOT master SKU level
- Almost all 2,784 master SKUs are active in Shopping or PMax campaigns
- `search_queries` stores variant-level data; `performance_baselines` stores master SKU-level data

</domain>

<decisions>
## Implementation Decisions

### Backfill sequencing

- **Claude decides sequencing** — safer to run sequentially: 14-01 sync completes and verifies before 14-02 performance backfill starts
- **Sync failure recovery:** Use the existing `/search-insights/sync` resume mechanism; 14-01 documents the job ID and how to resume manually if Cloud Run scales down mid-job
- **Verification gate for 14-01:** Dual verification required before calling 14-01 done:
  1. Zero `INVALID_ARGUMENT` errors in Cloud Run logs during 180-day sync
  2. `search_queries` rows with `synced_at IS NOT NULL` count increases from the pre-fix baseline
- **Migration smoke test:** 14-01 must include a 1-SKU smoke test of `/backfill/start` after applying `026_backfill_jobs.sql` — confirm endpoint works before 14-02 runs the full 2,784 SKU job

### Performance backfill scope

- **Target:** All 2,784 master SKUs — pass the full list to `/backfill/start`; Google Ads API returns zero rows for SKUs with no data (acceptable)
- **Re-capture existing baselines:** Yes — overwrite all 96 existing `performance_baselines` rows with fresh 180-day data; fresher data wins
- **Recovery path:** Claude decides — document job_id on start; if job fails, resume via `/backfill/resume` with the recorded job_id
- **Verification:** Claude decides — both job status = `complete` AND `performance_baselines` row count meaningfully above 96

### Coverage numbers (monitoring page)

- **search_queries coverage:** Show TWO numbers:
  - Master SKUs with any search term data / 2,784
  - Variant gmc_offer_ids with any search term data / total in variant_index (~72k)
- **performance_baselines coverage:** One number: master SKUs with baselines / 2,784
- **Layout:** Separate cards — "Search Terms Coverage" card and "Performance Baselines Coverage" card
- **Queries:** Replace current PostgREST-limited queries with SQL `COUNT(DISTINCT ...)` queries to avoid the 1000-row default limit

### Active Jobs display

- **Show active/running job first** (if any), then last N completed/failed jobs below
- **N = Claude decides** (5 is sensible default for readability)
- **Two separate sections after Phase 14 migration:**
  - "Search Term Sync Jobs" — reads from `search_query_sync_jobs` (existing table, has history)
  - "Performance Backfill Jobs" — reads from `backfill_jobs` (created in 14-01)
- **Per job row shows:** status, started_at, SKUs processed (or progress), error count

### Claude's Discretion

- Exact sequencing timing (whether 14-01 and 14-02 are separate sessions or back-to-back)
- Number of jobs to show in history list (5 recommended)
- Specific resume/retry implementation detail in the backfill plan
- Exact query structure for COUNT queries on the monitoring page

</decisions>

<specifics>
## Specific Ideas

- The 125 distinct SKUs noted in STATE.md for `search_queries` is pre-Phase 13 fix data — the post-fix re-sync should yield many more distinct master SKUs
- The `synced_at` column (migration 027 from Phase 13) is the marker distinguishing pre-fix vs post-fix search term rows — use it in verification queries
- `variant_index` has ~72k rows — any query against it must use COUNT queries, not raw fetch (PostgREST 1000-row limit will silently truncate)
- The monitoring page "Freshness heatmap" fix is part of 14-03 — accuracy means using correct COUNT-based queries for the underlying data, not a UI redesign

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-complete-180-day-backfill-and-monitoring-fixes*
*Context gathered: 2026-02-19*
