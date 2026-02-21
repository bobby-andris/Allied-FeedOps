---
phase: 14-complete-180-day-backfill-and-monitoring-fixes
plan: "01"
subsystem: google-ads-search-terms
tags: [search-terms, gaql, last-n-days, between, migration, backfill-jobs]
dependency_graph:
  requires: []
  provides:
    - last-n-days-bug-fixed-in-google-ads-search-terms
    - backfill-jobs-table-in-production
    - search-insights-sync-accepts-180-days
  affects:
    - google_ads_search_terms.py
    - search_insights.py
    - supabase production schema
tech_stack:
  added: []
  patterns:
    - explicit-between-date-ranges-in-gaql
    - supabase-migration-renaming-for-conflict-resolution
key_files:
  modified:
    - src/feedops/integrations/google_ads_search_terms.py
    - src/feedops/api/search_insights.py
  created:
    - supabase/migrations/031_backfill_jobs.sql
decisions:
  - "026_backfill_jobs.sql renamed to 031_backfill_jobs.sql to avoid naming conflict with two existing 026_*.sql files"
  - "LAST_N_DAYS syntax removed from all 3 GAQL query sites in google_ads_search_terms.py (not 2 as the plan estimated)"
  - "Task 2 (trigger 180-day sync) and Task 3 (human verification) deferred to Phase 15-01 — sync execution moved to Phase 15 scope"
metrics:
  completed: 2026-02-19
  tasks: 1
  files: 3
commits:
  - "a1cb4bdd — fix(14-01): replace LAST_N_DAYS with BETWEEN date ranges in google_ads_search_terms.py + raise sync limit to 180d"
  - "8b0d46ff — chore(14-01): add 031_backfill_jobs.sql migration (re-numbered from 026 to resolve naming conflict)"
---

# Phase 14 Plan 01: Migration + LAST_N_DAYS Fix Summary

Apply `031_backfill_jobs.sql` migration, fix the `LAST_N_DAYS` GAQL syntax bug in `google_ads_search_terms.py`, and raise the search-insights sync day limit to 180. The actual 180-day sync trigger was deferred to Phase 15-01.

## What Was Built

### Task 1: Fix LAST_N_DAYS + apply migration + raise sync limit

**Problem**: All GAQL queries in `google_ads_search_terms.py` used `WHERE segments.date DURING LAST_{days}_DAYS`, which causes `INVALID_ARGUMENT` errors from the Google Ads API for values > 30. Additionally, the `backfill_jobs` and `backfill_job_errors` tables were missing from production (Phase 5-8 migrations were never applied).

**Fix — LAST_N_DAYS → BETWEEN (3 query sites)**:

Each GAQL method now computes explicit date strings before building the query:
```python
end_date = date.today().strftime("%Y-%m-%d")
start_date = (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")
# ...
WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
```

Methods updated:
- `_fetch_campaign_products` (line ~476)
- `fetch_search_terms` (line ~492)
- `_fetch_search_volume` (line ~810) — a third site not noted in the original plan

**Fix — Migration**:
`supabase/migrations/031_backfill_jobs.sql` creates:
- `backfill_jobs` table — async job tracking (job_id, job_type, status, progress, etc.)
- `backfill_job_errors` table — per-item error logging
- `increment_backfill_failures` RPC — atomic failure counter

Renamed from `026_backfill_jobs.sql` to `031_backfill_jobs.sql` to avoid conflict with two pre-existing `026_*.sql` files.

**Fix — Sync day limit**:
`SyncSearchTermsRequest.days` field changed from `le=90` to `le=180`, allowing the `/search-insights/sync` endpoint to accept `days=180` without validation errors.

## Deviations from Plan

- **3 GAQL sites fixed, not 2**: The plan identified `_fetch_campaign_products` and `fetch_search_terms`. A third site (`_fetch_search_volume`) also used `LAST_N_DAYS` and was fixed in the same commit.
- **Migration renumbered**: Plan referenced `026_backfill_jobs.sql`; file created as `031_backfill_jobs.sql` to avoid naming conflict.
- **Tasks 2 & 3 deferred**: The 180-day sync trigger and human verification gate were not executed in this plan — moved to Phase 15-01 scope.

## Self-Check: PASSED

**Verification**:
- `grep -n "LAST_.*_DAYS" src/feedops/integrations/google_ads_search_terms.py` → 0 matches
- `grep -n "BETWEEN" src/feedops/integrations/google_ads_search_terms.py` → 3 matches (one per method)
- `grep -n "le=180" src/feedops/api/search_insights.py` → 1 match
- Migration file `031_backfill_jobs.sql` exists in `supabase/migrations/`
