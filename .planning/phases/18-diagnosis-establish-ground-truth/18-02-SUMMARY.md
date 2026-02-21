---
phase: 18-diagnosis-establish-ground-truth
plan: 02
subsystem: ui, api
tags: [nextjs, react, supabase, dashboard, funnel, diagnostics]

# Dependency graph
requires:
  - phase: 18-diagnosis-establish-ground-truth
    provides: Research confirming all Supabase tables (variant_index, generated_content, sku_approvals, publish_events) are queryable for funnel counts
provides:
  - /api/funnel/summary GET endpoint — 5-stage SKU coverage funnel counts
  - /api/funnel/skus GET endpoint — paginated SKU lists per funnel stage
  - CoverageFunnel React component — visual funnel on overview page with expandable SKU lists
  - Integration of CoverageFunnel into overview page (dashboard/src/app/(dashboard)/page.tsx)
affects: [18-diagnosis-establish-ground-truth, phase-19, phase-20]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - COUNT DISTINCT via JS Set dedup (Supabase JS client lacks native COUNT DISTINCT support)
    - Lazy SKU list loading — fetch on stage click, not pre-fetched
    - Spot-check results from JSON file at .planning/phases/18-diagnosis-establish-ground-truth/spot-check-results.json

key-files:
  created:
    - dashboard/src/app/api/funnel/summary/route.ts
    - dashboard/src/app/api/funnel/skus/route.ts
    - dashboard/src/components/dashboard/CoverageFunnel.tsx
  modified:
    - dashboard/src/app/(dashboard)/page.tsx

key-decisions:
  - "Separate /api/funnel/summary endpoint instead of augmenting /api/stats — avoids slowing existing stats load"
  - "COUNT DISTINCT via JS Set dedup (acceptable for 72K rows) instead of raw SQL RPC — simpler code path"
  - "Stage 5 (confirmed_sample) reads from static spot-check-results.json file — not a live Supabase query"
  - "SKU list loads on-demand per stage click (not pre-fetched) — avoids loading 2,784 SKUs on page load"
  - "Pre-existing d3 TypeScript type definition errors noted — not caused by this plan, build was already failing"

patterns-established:
  - "Funnel stage components: card-based horizontal layout with drop-off indicators between stages"
  - "Load-more pagination pattern for inline SKU lists (50 per page)"

requirements-completed: [DIAG-01]

# Metrics
duration: 4min
completed: 2026-02-21
---

# Phase 18 Plan 02: SKU Coverage Funnel API and Dashboard Component Summary

**5-stage SKU coverage funnel with exact counts, drop-off percentages, and expandable SKU lists built as a React component on the overview page backed by two new API endpoints**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-21T02:56:17Z
- **Completed:** 2026-02-21T03:00:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Two new API endpoints: `/api/funnel/summary` (5-stage counts) and `/api/funnel/skus` (paginated SKU lists per stage)
- CoverageFunnel React component with visual funnel flow — counts, drop-off percentages, color-coded severity indicators
- Click-to-expand SKU lists per stage with load-more pagination (50 SKUs per page)
- Confirmed sample stage (DIAG-04) shows "Not yet checked" until spot-check script runs (Plan 03)
- Integrated above existing stat cards on overview page — additive, non-blocking, loads asynchronously

## Task Commits

Each task was committed atomically:

1. **Task 1: Create funnel API endpoints** - `b486a494` (feat)
2. **Task 2: Build CoverageFunnel component and integrate into overview page** - `bbf54ddb` (feat)

## Files Created/Modified

- `dashboard/src/app/api/funnel/summary/route.ts` — Returns 5-stage funnel counts; reads spot-check-results.json for stage 5
- `dashboard/src/app/api/funnel/skus/route.ts` — Returns paginated SKU list per stage with stage param validation (400 for invalid)
- `dashboard/src/components/dashboard/CoverageFunnel.tsx` — 'use client' component with loading skeleton, stage cards, drop-off indicators, expandable SKU lists
- `dashboard/src/app/(dashboard)/page.tsx` — Added CoverageFunnel import and rendering above stat cards

## Decisions Made

- Separate `/api/funnel/summary` endpoint (not augmenting `/api/stats`) — keeps existing page load fast
- COUNT DISTINCT via JS Set dedup — Supabase JS client has no native COUNT DISTINCT; acceptable for sizes involved
- Stage 5 confirmed_sample is static (reads JSON file) — live Google Sheets read-back is DIAG-04's job
- SKU lists are lazy-loaded on click — prevents loading 2,784+ SKUs on initial page render
- Pre-existing d3 TypeScript build failure noted as out-of-scope pre-existing issue

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing issue (out of scope): The dashboard has a pre-existing TypeScript build failure related to d3 type definition files (`Cannot find type definition file for 'd3-array 2'`). This was confirmed to exist before this plan's changes by verifying with git stash. The JavaScript compilation succeeds; only the TypeScript type-check phase fails. This is NOT caused by this plan's files.

## Next Phase Readiness

- DIAG-01 complete: coverage funnel is live on the overview page
- Plan 03 can write `spot-check-results.json` to `.planning/phases/18-diagnosis-establish-ground-truth/` and the funnel's "Confirmed in Sheets" stage will automatically display the results
- `/api/funnel/skus` endpoint supports all four clickable stages for future use by downstream agents (Phase 19-20)

---
*Phase: 18-diagnosis-establish-ground-truth*
*Completed: 2026-02-21*
