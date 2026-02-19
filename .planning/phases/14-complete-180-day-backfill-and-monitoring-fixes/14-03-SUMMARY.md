---
phase: 14-complete-180-day-backfill-and-monitoring-fixes
plan: "03"
subsystem: monitoring
tags: [monitoring, coverage, backfill, search-terms, postg-rest-pagination]
dependency_graph:
  requires: []
  provides:
    - accurate-coverage-counts-in-monitoring-endpoint
    - two-active-jobs-sections-in-backfill-page
    - search-terms-offer-id-coverage-metric
  affects:
    - backfill-monitoring-dashboard
    - cloud-run-monitoring-endpoints
tech_stack:
  added: []
  patterns:
    - paginated-range-queries-to-bypass-postg-rest-1000-row-limit
    - _paginate_all-helper-function-for-large-tables
key_files:
  modified:
    - src/feedops/api/monitoring.py
    - dashboard/src/app/(dashboard)/backfill/page.tsx
  created:
    - dashboard/src/app/api/monitoring/sync-jobs/route.ts
decisions:
  - "Paginated range queries (5000 rows/page) replace unbounded .execute() calls on variant_index (72k rows)"
  - "CoverageResponse adds search_terms_sku_coverage, search_terms_offer_coverage, total_offer_ids while keeping search_terms_coverage as backwards-compat alias"
  - "Active Jobs section split into Search Term Sync Jobs (search_query_sync_jobs) and Performance Backfill Jobs (backfill_jobs)"
  - "_paginate_all() helper centralizes pagination logic for reuse across freshness and coverage endpoints"
metrics:
  duration: 4 minutes
  completed: 2026-02-19
  tasks: 2
  files: 3
---

# Phase 14 Plan 03: Monitoring Fixes (Coverage Queries + Active Jobs) Summary

Fix monitoring.py to use paginated range queries instead of PostgREST-truncated fetches (which silently returned 1000 of ~72k variant_index rows), expand CoverageResponse with offer-ID-level search terms metrics, and split the backfill page Active Jobs section into two separate sections (Search Term Sync Jobs + Performance Backfill Jobs).

## What Was Built

### Task 1: Fix monitoring.py — paginated queries replace unbounded PostgREST fetches

**Problem**: `get_data_coverage()` and `get_data_freshness()` both called `.execute()` on `variant_index` (72,000+ rows) without any range constraint. PostgREST's default 1000-row limit silently truncated the result, producing `total_skus = 1000` instead of the true ~2784 distinct master SKUs.

**Fix**: Added `_paginate_all()` helper that fetches a table in pages of 5000 rows using `.range(offset, offset + page_size - 1)` until the result set is exhausted. All large-table fetches in `get_data_freshness` and `get_data_coverage` now use this helper.

**New fields added to `CoverageResponse`**:
| Field | Description |
|-------|-------------|
| `total_offer_ids` | Distinct gmc_offer_ids in variant_index (~72k) |
| `search_terms_sku_coverage` | Master SKUs with any row in search_queries |
| `search_terms_offer_coverage` | Distinct gmc_offer_ids in search_queries |

`search_terms_coverage` kept as backwards-compat alias pointing to `search_terms_sku_coverage`.

**Queries changed**:
- `variant_index` in `get_data_freshness`: `.execute()` → `_paginate_all(...)` (pages of 5000)
- `search_queries` in `get_data_freshness`: `.execute()` → `_paginate_all(...)` (pages of 5000)
- `variant_index` in `get_data_coverage`: `.execute()` → `_paginate_all(...)` (pages of 5000, fetches both master_sku + gmc_offer_id)
- `search_queries` in `get_data_coverage`: `.execute()` → `_paginate_all(...)` (pages of 5000, fetches master_sku + gmc_offer_id)
- `performance_baselines`: single `.range(0, 2999)` (max ~2784 rows, bounded)
- `keyword_metrics_updated_at` queries: single `.range(0, 9999)` (bounded, known small)

### Task 2: Fix backfill/page.tsx — two Active Jobs sections + updated coverage cards

**New API route**: `dashboard/src/app/api/monitoring/sync-jobs/route.ts`
- `GET /api/monitoring/sync-jobs`
- Returns `{ active: SyncJob[], history: SyncJob[] }`
- Active = status IN ('running', 'pending'), limited to 5
- History = status IN ('completed', 'failed'), last 5

**backfill/page.tsx changes**:

1. Added `SyncJob` and `SyncJobsData` interfaces matching `search_query_sync_jobs` schema
2. Updated `CoverageData` interface with `search_terms_sku_coverage`, `search_terms_offer_coverage`, `total_offer_ids`
3. Added `syncJobs` state + `fetchSyncJobs()` function
4. Added `fetchSyncJobs()` to `useEffect` initial load
5. Added auto-refresh for running sync jobs (same 5s interval pattern)
6. Replaced single "Active Jobs" card with two separate `<Card>` sections:
   - **Search Term Sync Jobs**: reads from `/api/monitoring/sync-jobs`; shows Job ID, Type, Status, Queries Fetched, Days Lookback, Started At; active jobs highlighted with `border-l-blue-500` + ACTIVE badge
   - **Performance Backfill Jobs**: reads from `/api/backfill`; retains existing columns (Job ID, Type, Status, Progress bar, Items, ETA)
7. Coverage section replaced three cards with two:
   - **Search Terms Coverage**: two sub-metrics (Master SKUs count + Variant Offer IDs count)
   - **Performance Baselines Coverage**: single metric (master SKU count / total_skus)

## Deviations from Plan

None — plan executed exactly as written. The `createClient` async pattern was noted during development (`await createClient()` required) — this is a pre-existing project convention, not a new issue.

## Self-Check: PASSED

**Files created/modified**:
- `src/feedops/api/monitoring.py` — exists, contains `_paginate_all`, `search_terms_offer_coverage`, `total_offer_ids`
- `dashboard/src/app/api/monitoring/sync-jobs/route.ts` — exists
- `dashboard/src/app/(dashboard)/backfill/page.tsx` — exists, contains `search_query_sync_jobs`, `search_terms_offer_coverage`

**Commits**:
- `41c1cebf` — fix(14-03): replace unbounded PostgREST fetches with paginated range queries in monitoring.py
- `c21703c2` — feat(14-03): split Active Jobs into two sections + update coverage cards

**Build**: `npm run build` — passed (zero TypeScript errors)
**Lint**: `npm run lint` — 0 errors (2 pre-existing warnings in unmodified files)
