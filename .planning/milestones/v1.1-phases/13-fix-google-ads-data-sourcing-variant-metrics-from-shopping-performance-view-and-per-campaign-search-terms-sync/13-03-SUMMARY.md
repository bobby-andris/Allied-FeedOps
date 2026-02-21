---
phase: 13-fix-google-ads-data-sourcing-variant-metrics-from-shopping-performance-view-and-per-campaign-search-terms-sync
plan: 03
subsystem: infra
tags: [google-ads, search-terms, supabase, cloud-run, backfill]

requires:
  - phase: 13-02
    provides: Fixed fetch_search_terms() with variant fan-out + synced_at migration

provides:
  - synced_at column live in production search_queries table
  - Fixed Python code deployed to Cloud Run
  - Re-sync job running (all search terms re-fetched with corrected attribution)

affects: [search-insights, performance, monitoring]

key-files:
  created: []
  modified:
    - supabase/migrations/027_add_synced_at_to_search_queries.sql (applied to prod)

key-decisions:
  - "Used /search-insights/sync endpoint (not /backfill/start) — backfill_jobs table does not exist in production; search_query_sync_jobs does"
  - "90-day lookback, limit 5000 terms, no keyword planner enrichment (faster re-sync)"

patterns-established:
  - "search-insights/sync is the correct endpoint for re-syncing all search terms in production"
  - "backfill infrastructure (phases 5-8) was not deployed to production Supabase — do not use those endpoints"

requirements-completed:
  - phase-13-goal

duration: ~8min (tasks 1-2; task 3 is async human verification)
completed: 2026-02-19
---

# Phase 13-03: Deploy + Re-sync Summary

**Migration applied, code deployed to Cloud Run, and search_terms re-sync job triggered (job ID: 88fb3cbc-e3d8-4894-b0b3-9bb5a99672ff)**

## Performance

- **Duration:** ~8 min (tasks 1-2 complete; task 3 pending human verification)
- **Completed:** 2026-02-19

## Accomplishments

- Applied migration 027 — `synced_at` column now live in production `search_queries` table
- Dashboard build passed (npm run build)
- All 9 Phase 13 commits pushed to master — Cloud Build SUCCESS
- Cloud Run health confirmed: `{"status": "healthy", "supabase_connected": true}`
- Re-sync job triggered: job_id `88fb3cbc-e3d8-4894-b0b3-9bb5a99672ff`, status "running" at last check

## Task Notes

**Task 1 — Migration + Deploy:**
- Migration 027 applied via Supabase MCP: `synced_at timestamp with time zone` + index
- Build verified: `npm run build` passed
- Push: `5b568ddf..2c4a1b3d` — 9 commits ahead, all Phase 13 fixes deployed
- Cloud Build job `97bea788` → SUCCESS
- Health endpoint: healthy, supabase_connected: true

**Task 2 — Re-sync Trigger:**
- `backfill_jobs` table does NOT exist in production Supabase (Phase 5-8 migrations never applied)
- Used `/search-insights/sync` endpoint instead — uses `search_query_sync_jobs` table (exists)
- Job triggered: 90 days lookback, 5000 term limit, no keyword planner enrichment
- Job ID: `88fb3cbc-e3d8-4894-b0b3-9bb5a99672ff`

**Task 3 — Human Verification Checkpoint (PENDING)**

## Human Verification Required

The re-sync job is running. Once it completes, verify with:

**SQL check 1 — How many rows have synced_at populated?**
```sql
SELECT
  COUNT(*) FILTER (WHERE synced_at IS NOT NULL) AS corrected_rows,
  COUNT(*) FILTER (WHERE synced_at IS NULL) AS legacy_rows,
  COUNT(DISTINCT master_sku) FILTER (WHERE synced_at IS NOT NULL) AS corrected_skus
FROM search_queries;
```

**SQL check 2 — Variant attribution improved?**
```sql
SELECT
  master_sku,
  COUNT(DISTINCT gmc_offer_id) AS distinct_offer_ids,
  COUNT(DISTINCT query_text) AS unique_queries
FROM search_queries
WHERE synced_at IS NOT NULL
AND master_sku IN (
  SELECT DISTINCT master_sku FROM publish_events
  WHERE platform = 'google' LIMIT 5
)
GROUP BY master_sku
ORDER BY distinct_offer_ids DESC;
```
Expected: multiple distinct gmc_offer_ids per master_sku (previously was 1-3 of 28).

**Job status check:**
```bash
curl -s https://feedops-pipeline-623866089882.us-east1.run.app/search-insights/sync/88fb3cbc-e3d8-4894-b0b3-9bb5a99672ff
```

**Dashboard:**
- Search Insights page: check a published SKU shows richer variant-level query breakdown
- Monitoring page: job should show completed

## Deviations from Plan

**1. Backfill endpoint not available — switched to search-insights/sync**
- `/backfill/start` returns 500: `backfill_jobs` table missing from production (Phases 5-8 infra never deployed to Supabase)
- Fix: Used `/search-insights/sync` which uses `search_query_sync_jobs` (exists in production)
- Impact: Same data collected via different endpoint. The sync endpoint calls the same fixed `fetch_search_terms()` code.
- Note: limit is on total terms (5000), not SKUs. All SKUs are processed in the campaign-join pass.

## Issues Encountered

- Internal tool errors caused subagent failures for this plan — executed in orchestrator context directly
- `backfill_jobs` table absent from production database (discovery during this plan)

## Next Phase Readiness

- Phase 13 code complete, deployed, and re-sync running
- Human verification of corrected data is the final gate
- After verification: Phase 13 COMPLETE → run `/gsd:verify-work 13` or confirm "approved"

---
*Phase: 13-fix-google-ads-data-sourcing*
*Completed: 2026-02-19*
