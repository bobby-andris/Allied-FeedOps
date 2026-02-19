---
phase: 11-performance-page-enhancements
plan: "01"
subsystem: ui
tags: [next.js, react, supabase, performance, dashboard]

# Dependency graph
requires:
  - phase: 10-image-workflow-improvements
    provides: prior phase context; performance_snapshots data backfilled (44 snapshots, 36 SKUs)
provides:
  - Enhanced GET /api/performance with baselineWindow, snapshotWindow, daysSincePublish, hasSnapshot
  - Rewritten performance page with dual time selectors, delta table, trend indicators, filter toggle, sortable columns
affects:
  - 12-dashboard-audit (performance page is one of the pages to audit)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - DeltaCell sub-component pattern: shows baseline value, current value, and colored delta% in a stacked layout
    - SortableHeader as module-level component (not nested in render function) to satisfy react-hooks/static-components
    - Snapshot-window query: JS-side filtering with snapshot_date >= publishDate AND snapshot_date <= publishDate + N days

key-files:
  created: []
  modified:
    - dashboard/src/app/api/performance/route.ts
    - dashboard/src/app/(dashboard)/performance/page.tsx

key-decisions:
  - "Snapshot-only data sourcing: remove live Google Ads API call entirely — performance page reads exclusively from performance_baselines + performance_snapshots"
  - "JS-side window filtering: fetch all snapshots for published SKUs then filter by date window in JS (simpler than per-SKU SQL subqueries for this row count)"
  - "Neutral threshold ±3%: delta < 3% shows gray; >=3% green; <=-3% red — applied to both delta badges and TrendIcon"
  - "SortableHeader outside PerformanceTable: moved component to module scope to fix react-hooks/static-components ESLint error"

patterns-established:
  - "DeltaCell format: current value (bold) / baseline → delta% (small muted baseline, colored delta)"
  - "hasSnapshot false rows: bg-muted/30 background, No snapshot Badge instead of delta values"

requirements-completed: [PERF-01, PERF-02, PERF-03]

# Metrics
duration: 4min
completed: 2026-02-19
---

# Phase 11 Plan 01: Performance Page Enhancements Summary

**Performance page rewritten with dual time selectors (Baseline/Snapshot 7d/30d/60d), delta table showing baseline vs snapshot per metric, trend icons, days-since-publish column, sortable columns, and snapshot-only data sourcing (no live Google Ads API)**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-02-19T03:50:44Z
- **Completed:** 2026-02-19T03:54:40Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Removed live Google Ads API call from performance route; data now sourced exclusively from `performance_baselines` + `performance_snapshots`
- Added `baselineWindow`, `snapshotWindow` params (7d/30d/60d); each SKU record includes `daysSincePublish`, `hasSnapshot`, and window labels
- Rewritten performance page with: dual time selectors, filter toggle (With snapshot / All SKUs), sortable column headers, DeltaCell format showing baseline → current → delta%, TrendIcon per row, no-snapshot empty state

## Task Commits

Each task was committed atomically:

1. **Task 1: Enhance /api/performance to support dual time windows and return daysSincePublish** - `70d35f70` (feat)
2. **Task 2: Rewrite performance page with dual selectors, delta table, trend indicators, filter toggle, sortable columns** - `65e99980` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `dashboard/src/app/api/performance/route.ts` - Rewrote GET handler; removed Google Ads imports, added baselineWindow/snapshotWindow params, snapshot-window query, daysSincePublish, hasSnapshot, totalWithSnapshot in summary
- `dashboard/src/app/(dashboard)/performance/page.tsx` - Fully rewritten with DeltaCell, SortableHeader, TrendIcon, ChangeCard, PerformanceTable components; dual selectors, filter toggle, platform tabs, sortable columns

## Decisions Made

- **Snapshot-only sourcing**: Removed `fetchShoppingPerformance`, `isGoogleAdsConfigured`, `getDateRange`, `ProductPerformance` imports. The performance page now reads exclusively from stored snapshots, making results deterministic and consistent.
- **JS-side window filtering**: Fetched all snapshots for published SKUs and filtered by `snapshot_date >= publishDate && snapshot_date <= publishDate + snapshotWindowDays` in JS. Simpler than per-SKU SQL subqueries given the small row count (~44 snapshots).
- **Neutral threshold ±3%**: Delta badges and TrendIcon use ±3% as the neutral zone — avoids noise from rounding artifacts at near-zero deltas.
- **SortableHeader at module scope**: Moved `SortableHeader` from inside `PerformanceTable` render function to module level to fix `react-hooks/static-components` ESLint errors. Props threaded through: `col`, `sortColumn`, `sortDir`, `onSort`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `isNeutral` unused variable and `SortableHeader` component-in-render**
- **Found during:** Task 2 (lint pass)
- **Issue:** `isNeutral` variable assigned but never used (warning); `SortableHeader` defined inside `PerformanceTable` function body triggers `react-hooks/static-components` errors (5 errors)
- **Fix:** Removed `isNeutral` variable; moved `SortableHeader` to module scope and added `sortColumn`, `sortDir`, `onSort` as explicit props
- **Files modified:** `dashboard/src/app/(dashboard)/performance/page.tsx`
- **Verification:** `npm run lint` passes with 0 errors (2 pre-existing warnings in unrelated files)
- **Committed in:** `65e99980` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug/lint errors in Task 2 output)
**Impact on plan:** Fix required for zero-error lint pass. No scope change.

## Issues Encountered

None beyond the lint fixes documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Performance page ready for visual verification at `/performance`
- 44 snapshots backfilled (36 SKUs) provide real data to exercise the new delta table
- Phase 12 (dashboard audit) can include performance page in its walkthrough

---
*Phase: 11-performance-page-enhancements*
*Completed: 2026-02-19*
