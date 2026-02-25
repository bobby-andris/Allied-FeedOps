---
phase: 30-historical-funnel-persistence
plan: 02
subsystem: ui
tags: [trends, funnel-snapshots, dashboard, cards, next-api]

# Dependency graph
requires:
  - phase: 30-01
    provides: "funnel_snapshots_daily table with daily capture endpoint"
provides:
  - "GET /api/funnel-snapshots/trends endpoint returning 7d vs prev-7d aggregated metrics"
  - "FunnelTrendCards component with 6 trend summary cards above Shopping Funnel tabs"
affects: [30-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-contained client component pattern: fetch own data, manage own state, render null when no data"
    - "TrendArrow sub-component with 5% threshold and invertColor for cost metrics"

key-files:
  created:
    - "dashboard/src/app/api/funnel-snapshots/trends/route.ts"
    - "dashboard/src/app/(dashboard)/shopping-funnel/FunnelTrendCards.tsx"
  modified:
    - "dashboard/src/app/(dashboard)/shopping-funnel/page.tsx"

key-decisions:
  - "Flat indicator shows 'Flat' text instead of percentage to clearly distinguish from up/down trends"
  - "ROAS format trims trailing zeros (75.5x not 75.50x) for cleaner display"

patterns-established:
  - "Self-contained trend card component: fetches data, handles loading/empty/error states internally"

requirements-completed: [HIST-03]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 30 Plan 02: Trend Cards Summary

**7-day trend summary cards with TrendArrow indicators powered by funnel_snapshots_daily aggregation API, rendering Impressions/Clicks/CTR/Ad Spend/Conversions/ROAS above Shopping Funnel tabs**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T10:57:54Z
- **Completed:** 2026-02-25T11:01:36Z
- **Tasks:** 3
- **Files created:** 2
- **Files modified:** 1

## Accomplishments
- Trends API aggregates funnel_snapshots_daily into 7d vs prev-7d periods with CTR/ROAS derived metrics
- FunnelTrendCards renders 6 cards with green/red/flat trend arrows based on 5% threshold
- Shopping Funnel page wired with only 2 additive lines (import + render)
- All 14 tests pass (6 trends API + 8 FunnelTrendCards)
- Full build passes, lint clean

## Task Commits

Each task was committed atomically:

1. **Task 1: Create trends API route** - `a3a7f4a4` (feat)
2. **Task 2: Create FunnelTrendCards component** - `8332f6a6` (feat)
3. **Task 3: Wire FunnelTrendCards into Shopping Funnel page** - `f5c781e5` (feat)

## Files Created/Modified
- `dashboard/src/app/api/funnel-snapshots/trends/route.ts` - GET endpoint: 15-day query window, current/previous period split, CTR/ROAS computation with division-by-zero guards, Cache-Control: s-maxage=3600
- `dashboard/src/app/(dashboard)/shopping-funnel/FunnelTrendCards.tsx` - Self-contained client component: 6 metric cards in 3-column grid, TrendArrow with 5% threshold, skeleton loading state, null render when no data
- `dashboard/src/app/(dashboard)/shopping-funnel/page.tsx` - Added import + render of FunnelTrendCards above Tabs (2 lines only)
- `dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx` - Fixed 2 test assertions (getByText -> getAllByText for duplicate percentage matches)

## Decisions Made
- Flat indicator shows "Flat" label (no percentage) to clearly differentiate from directional trends
- ROAS format trims trailing zeros for cleaner display (75.5x not 75.50x)
- Ad Spend uses inverted color logic (up=red, down=green) since higher spend is typically undesirable

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed test scaffolds using getByText for non-unique text matches**
- **Found during:** Task 2 (FunnelTrendCards component)
- **Issue:** Test scaffolds from 30-00 used `getByText(/+25.0%/)` and `getByText(/-40.0%/)` which fail when multiple cards show the same percentage (e.g., Impressions and Clicks both at +25%)
- **Fix:** Changed to `getAllByText` with `toBeGreaterThanOrEqual(1)` assertion
- **Files modified:** `dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx`
- **Verification:** All 8 FunnelTrendCards tests pass
- **Committed in:** 8332f6a6 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary fix to test scaffolds that had duplicate-match bug. No scope creep.

## Issues Encountered
None beyond the test scaffold fix.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Trend cards ready for production (will show data once Cloud Scheduler populates funnel_snapshots_daily)
- Cards gracefully handle empty state (hidden entirely) and insufficient history ("No prior data")
- Ready for Plan 03 (service.ts write-behind caching)

---
*Phase: 30-historical-funnel-persistence*
*Completed: 2026-02-25*

## Self-Check: PASSED

- FOUND: trends/route.ts (138 lines, min 30)
- FOUND: FunnelTrendCards.tsx (218 lines, min 60)
- FOUND: commit a3a7f4a4
- FOUND: commit 8332f6a6
- FOUND: commit f5c781e5
- All 14 tests pass (6 trends + 8 FunnelTrendCards)
- Full build passes with zero errors
- page.tsx diff shows only 2 additive lines
