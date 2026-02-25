---
phase: 29-content-performance-feedback-linkage
plan: 03
subsystem: ui, api
tags: [next.js, supabase, dashboard, content-impact, search-terms, drill-down, control-cohort, diff-in-diff]

# Dependency graph
requires:
  - phase: 29-content-performance-feedback-linkage
    provides: Content Impact landing page with row click routing, performance_impact_scores table, search_query_snapshots table
provides:
  - GET /api/content-impact/[sku] endpoint with detailed metrics, control cohort, publish history
  - GET /api/content-impact/[sku]/search-terms endpoint with gained/lost term deltas
  - /content-impact/[sku] drill-down detail page with 7 sections
affects: [30-service-ts-persistence]

# Tech tracking
tech-stack:
  added: []
  patterns: [SKU-resolved dynamic API routes using getSkuCandidates, collapsible sections for methodology transparency, search term pre/post snapshot comparison]

key-files:
  created:
    - dashboard/src/app/api/content-impact/[sku]/route.ts
    - dashboard/src/app/api/content-impact/[sku]/search-terms/route.ts
    - dashboard/src/app/(dashboard)/content-impact/[sku]/page.tsx
  modified: []

key-decisions:
  - "Search term comparison uses closest pre-publish and earliest post-publish snapshots per query term"
  - "Control cohort section defaults to collapsed to reduce visual noise; methodology is always accessible"
  - "Publish history section only renders when more than one publish event exists for the SKU+platform pair"

patterns-established:
  - "SKU detail routes: resolve URL SKU via getSkuCandidates against publish_events table"
  - "Collapsible methodology sections: ChevronDown/ChevronRight toggle with radix Collapsible"
  - "Search term split view: gained (green) left, lost (red) right, top 10 with Show All expansion"

requirements-completed: [FEED-01, FEED-03]

# Metrics
duration: 5min
completed: 2026-02-25
---

# Phase 29 Plan 03: Content Impact Detail Page Summary

**Drill-down detail page with search term gained/lost split view, DiD control cohort transparency, and publish history navigation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-25T08:53:50Z
- **Completed:** 2026-02-25T08:59:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created GET /api/content-impact/[sku] endpoint returning publish event details, baseline metrics, 7/14/30-day window aggregation, impact scores with pre/post/control values, control cohort SKU list, and full publish history
- Created GET /api/content-impact/[sku]/search-terms endpoint comparing pre/post publish search query snapshots to identify gained and lost terms with impression/click deltas and "New" badge flagging
- Built drill-down detail page with 7 sections: breadcrumb, header, impact summary card, performance windows, search terms split view, collapsible control cohort methodology, and collapsible publish history
- All edge cases handled: missing baselines, pending windows, no search data, no control cohort, single publish event (history hidden)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create SKU detail API route and search terms API route** - `db96d413` (feat)
2. **Task 2: Build drill-down detail page with search terms, control cohort, and publish history** - `683999af` (feat)

## Files Created/Modified
- `dashboard/src/app/api/content-impact/[sku]/route.ts` - GET endpoint with 6 data sections: event details, baseline, window metrics, impact scores, control skus, publish history
- `dashboard/src/app/api/content-impact/[sku]/search-terms/route.ts` - GET endpoint returning gained/lost search term deltas with is_new flag
- `dashboard/src/app/(dashboard)/content-impact/[sku]/page.tsx` - Client component with impact summary, performance windows, search term split view, collapsible control cohort, collapsible publish history

## Decisions Made
- Search term comparison uses the latest pre-publish snapshot and earliest post-publish snapshot per query term, rather than aggregating across multiple snapshots
- Control cohort section defaults to collapsed to keep the page scannable, with methodology explanation and raw DiD numbers available on expand
- Publish history section conditionally renders only when there are 2+ publish events for the same SKU+platform combination
- Terms with zero impression delta are excluded from both gained and lost lists (only meaningful changes shown)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed let to const for controlCategories**
- **Found during:** Task 1 (lint verification)
- **Issue:** `controlCategories` variable declared with `let` but never reassigned
- **Fix:** Changed to `const` to satisfy prefer-const lint rule
- **Files modified:** dashboard/src/app/api/content-impact/[sku]/route.ts
- **Verification:** `npm run lint` passes with zero errors
- **Committed in:** 683999af (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial lint fix. No scope change.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Content Impact feedback loop UI is complete (landing page + detail page)
- Phase 29 fully delivered: schema + enforcement (Plan 01), landing page (Plan 02), detail page (Plan 03)
- Ready for Phase 30 (service.ts persistence) which builds on this feedback infrastructure

---
*Phase: 29-content-performance-feedback-linkage*
*Completed: 2026-02-25*
