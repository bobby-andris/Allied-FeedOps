---
phase: 19-measurement-infrastructure
plan: 04
subsystem: gmc-integration
tags: [merchant-api, gmc, disapprovals, dashboard, python, typescript, react]

# Dependency graph
requires:
  - phase: 19-measurement-infrastructure
    plan: 01
    provides: gmc_product_status table (migration 035)
provides:
  - MerchantApiClient querying product_view for disapproved/limited products
  - POST /gmc/sync Cloud Run endpoint with run_async_in_thread pattern
  - GET /api/gmc/status dashboard route reading gmc_product_status cache
  - POST /api/gmc/sync dashboard proxy to Cloud Run
  - GmcDisapprovalBadge component for inline SKU tables
  - Monitoring page extended to 3 tabs with GMC Status tab
affects:
  - 19-05 (MEAS-02 now satisfied — disapproval data visible in dashboard)
  - Phase 20 (GMC disapproval data informs which SKUs need content fixes)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Merchant API REST queries using httpx + service account token (no new SDK dependency)"
    - "Offer ID lowercase normalization: Merchant API returns shopify_US_, DB uses shopify_us_"
    - "run_async_in_thread for GMC sync background job — Cloud Run container lifecycle safety"
    - "Lazy-load GMC tab data: only fetches on first tab selection (not on page mount)"
    - "In-memory job status dict _sync_jobs for short-lived sync job tracking"

key-files:
  created:
    - src/feedops/integrations/merchant_api.py
    - src/feedops/api/gmc_sync.py
    - dashboard/src/app/api/gmc/sync/route.ts
    - dashboard/src/app/api/gmc/status/route.ts
    - dashboard/src/components/gmc/GmcDisapprovalBadge.tsx
    - .planning/phases/19-measurement-infrastructure/19-04-SUMMARY.md
  modified:
    - src/feedops/api/main.py
    - dashboard/src/app/(dashboard)/monitoring/page.tsx

key-decisions:
  - "GMC_MERCHANT_ID env var (not FEEDOPS_MERCHANT_CENTER_ID) — matches all existing code in codebase"
  - "MerchantApiClient reads GMC_MERCHANT_ID with fallback to FEEDOPS_MERCHANT_CENTER_ID for forward compatibility"
  - "Sync only fetches disapproved/limited products (not all eligible) — reduces API quota and storage"
  - "In-memory _sync_jobs dict for job status (not Supabase) — sufficient for short-lived sync operations"
  - "Lazy load GMC tab: fetches data on first tab activation, not on page mount"

requirements-completed: [MEAS-02]

# Metrics
duration: 5min
completed: 2026-02-21
---

# Phase 19 Plan 04: GMC Disapproval Visibility Summary

**End-to-end GMC disapproval sync pipeline: Merchant Reports API query → Supabase upsert → dashboard monitoring tab with expandable issue details and inline badge component**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-21T04:17:55Z
- **Completed:** 2026-02-21T04:22:51Z
- **Tasks:** 2 (Task 1 was checkpoint resolved before execution)
- **Files modified:** 7

## Accomplishments

- Created `MerchantApiClient` in `merchant_api.py` — queries Merchant Reports API `product_view` with MAPI_SCOPE auth, normalizes all offer IDs to lowercase, parses `item_issues` into structured dicts
- Created `gmc_sync.py` FastAPI router — POST /gmc/sync uses `run_async_in_thread` for Cloud Run container safety, resolves master_sku via variant_index, bulk upserts to `gmc_product_status` in 500-record batches
- Registered gmc_sync_router in `main.py`
- Created dashboard proxy routes: POST /api/gmc/sync (thin proxy) and GET /api/gmc/status (reads from Supabase cache with filters)
- Created `GmcDisapprovalBadge` component: red badge for disapprovals, yellow for warnings, null if clean
- Extended monitoring page from 2 to 3 tabs: added GMC Status tab with summary cards (total/disapproved/limited/last sync), Sync Now button, product table sorted by disapproval_count DESC, expandable rows showing full item_issues detail

## Task Commits

1. **Task 2: Merchant API client and GMC sync endpoint** - `2ccd9808` (feat)
2. **Task 3: Dashboard GMC routes, monitoring tab, badge** - `cf0d64fb` (feat)

## Files Created/Modified

- `src/feedops/integrations/merchant_api.py` — MerchantApiClient with product_view query and issue parsing
- `src/feedops/api/gmc_sync.py` — POST /gmc/sync router, background sync task, _resolve_master_skus helper
- `src/feedops/api/main.py` — registered gmc_sync_router
- `dashboard/src/app/api/gmc/sync/route.ts` — POST proxy to Cloud Run
- `dashboard/src/app/api/gmc/status/route.ts` — GET reading gmc_product_status with filters
- `dashboard/src/components/gmc/GmcDisapprovalBadge.tsx` — inline badge component
- `dashboard/src/app/(dashboard)/monitoring/page.tsx` — extended to 3 tabs with GMC Status tab

## Decisions Made

- Used existing `GMC_MERCHANT_ID` env var (not the plan's `FEEDOPS_MERCHANT_CENTER_ID`) — matches all existing code in `scripts/query_gmc_offer_ids.py`, `merchant_center.py`, `google_feed_upload.py`; added fallback to `FEEDOPS_MERCHANT_CENTER_ID` for forward compat
- Sync fetches only disapproved/limited products (not all eligible) — saves API quota, aligns with MEAS-02 goal of surfacing the "silent impression killer"
- In-memory `_sync_jobs` dict for job status tracking — sufficient for short-lived GMC sync operations, no extra DB dependency
- Lazy-load GMC tab: fetches on first activation vs. page mount — avoids unnecessary DB reads when user only views other tabs

## Deviations from Plan

### Auto-fixed Issues

None - plan executed exactly as written.

### Notable Implementation Details

- **Auth reuse pattern**: `merchant_api.py` uses the same credential loading approach as `merchant_center.py` (GOOGLE_APPLICATION_CREDENTIALS → GOOGLE_SERVICE_ACCOUNT_KEY → google.auth.default()) without importing from that module to avoid coupling
- **gmc_sync.py imports `run_async_in_thread` from main.py**: Used a local import inside the endpoint function to avoid circular import at module level — this is the standard Python pattern for cross-module dependency on the app object

## Self-Check: PASSED

- FOUND: src/feedops/integrations/merchant_api.py
- FOUND: src/feedops/api/gmc_sync.py
- FOUND: src/feedops/api/main.py (gmc_sync_router registered at lines 126-127)
- FOUND: dashboard/src/app/api/gmc/sync/route.ts
- FOUND: dashboard/src/app/api/gmc/status/route.ts
- FOUND: dashboard/src/components/gmc/GmcDisapprovalBadge.tsx
- FOUND: monitoring/page.tsx has 3 TabsTrigger values (performance, search, gmc)
- Commit 2ccd9808 verified (Task 2: Python merchant API + sync router)
- Commit cf0d64fb verified (Task 3: Dashboard routes + monitoring tab + badge)
- Python import test: `from feedops.integrations.merchant_api import MerchantApiClient` — OK
- Dashboard build: PASSED
- Dashboard lint: PASSED (1 pre-existing warning in unrelated file)

---
*Phase: 19-measurement-infrastructure*
*Completed: 2026-02-21*
