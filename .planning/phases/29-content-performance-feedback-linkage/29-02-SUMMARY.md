---
phase: 29-content-performance-feedback-linkage
plan: 02
subsystem: ui, api
tags: [next.js, supabase, dashboard, content-impact, performance-tracking, ctr, impact-scores]

# Dependency graph
requires:
  - phase: 29-content-performance-feedback-linkage
    provides: performance_impact_scores table, cohort_type/product_category columns on performance_snapshots
provides:
  - GET /api/content-impact endpoint joining 4 performance tables with window aggregation
  - /content-impact dashboard page with scannable impact table
  - Sidebar navigation entry for Content Impact
affects: [29-03, 30-service-ts-persistence]

# Tech tracking
tech-stack:
  added: []
  patterns: [application-layer 4-table join with window aggregation, impact tier classification, re-publish grouping with is_latest_publish flag]

key-files:
  created:
    - dashboard/src/app/api/content-impact/route.ts
    - dashboard/src/app/(dashboard)/content-impact/page.tsx
  modified:
    - dashboard/src/components/shared/Sidebar.tsx

key-decisions:
  - "Impact classification uses CTR as primary score; CVR included in response but CTR drives tier label"
  - "Window aggregation excludes day 0 per research pitfall #4 — first day data is noisy"
  - "Minimum 50-impression threshold per window — below that returns null (insufficient data)"
  - "Best available window used for delta column (30d > 14d > 7d)"

patterns-established:
  - "Content impact API: fetch all 4 tables in parallel, join in application code, aggregate windows client-side"
  - "Impact score badge: tier-specific styling with tooltip on insufficient data"

requirements-completed: [FEED-01, FEED-02]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 29 Plan 02: Content Impact Landing Page Summary

**Content Impact landing page with 10-column table showing baseline vs post-publish CTR at 7/14/30-day windows, impact score tiers, and re-publish grouping**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T08:47:41Z
- **Completed:** 2026-02-25T08:52:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created GET /api/content-impact endpoint that joins publish_events, performance_baselines, performance_snapshots, and performance_impact_scores with window aggregation at 7/14/30-day intervals
- Built Content Impact landing page with 10-column table: SKU, platform, published date, baseline CTR, 7/14/30d CTR, delta, impact score, and version
- Added sidebar navigation entry between Performance and Search Insights
- Implemented all edge cases: no baseline warning badge, pending window countdown, legacy publish label, insufficient data tooltip, re-published SKU toggle

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Content Impact API route with 4-table join and window aggregation** - `de9d5a2c` (feat)
2. **Task 2: Build Content Impact landing page and add sidebar navigation** - `5aeaf52b` (feat)

## Files Created/Modified
- `dashboard/src/app/api/content-impact/route.ts` - GET endpoint with 4-table join, window aggregation, impact tier classification
- `dashboard/src/app/(dashboard)/content-impact/page.tsx` - Client component with scannable table, color-coded deltas, impact badges
- `dashboard/src/components/shared/Sidebar.tsx` - Added Content Impact navigation entry with TrendingUp icon

## Decisions Made
- Impact classification uses CTR score as the primary driver for the tier label; CVR lift is included in the response payload but does not affect badge display
- Window aggregation excludes day 0 snapshots (research pitfall #4 — first-day data is noisy from pre-existing impressions)
- Minimum 50-impression threshold per window prevents misleading CTR calculations from low-traffic SKUs
- Delta column shows the best available window (30d preferred, then 14d, then 7d) rather than always showing 30d

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PlatformBadge type mismatch**
- **Found during:** Task 2 (build verification)
- **Issue:** `row.platform` is `string` but PlatformBadge expects `'google' | 'bing' | 'shopify'` union type
- **Fix:** Cast platform to the expected union type in the JSX
- **Files modified:** dashboard/src/app/(dashboard)/content-impact/page.tsx
- **Verification:** Build passes after fix
- **Committed in:** 5aeaf52b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor type casting fix. No scope change.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Content Impact page is live and accessible from sidebar
- Row click routes to `/content-impact/[sku]?event_id=X` (detail page built in Plan 03)
- API returns all data needed for both the table view and future drill-down views

---
*Phase: 29-content-performance-feedback-linkage*
*Completed: 2026-02-25*
