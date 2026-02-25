---
phase: 30-historical-funnel-persistence
plan: 00
subsystem: testing
tags: [vitest, tdd, funnel-snapshots, trend-cards, google-ads]

# Dependency graph
requires: []
provides:
  - "Failing test scaffolds for capture endpoint (auth, upsert, retention)"
  - "Failing test scaffolds for trends endpoint (aggregation, CTR/ROAS, edge cases)"
  - "Failing test scaffolds for FunnelTrendCards component (rendering, arrows, formatting)"
affects: [30-01, 30-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "vi.hoisted() for Supabase chain mocking in API route tests"
    - "Dynamic import pattern for testing Next.js route handlers"
    - "vi.waitFor() for async React component rendering tests"

key-files:
  created:
    - "dashboard/src/app/api/funnel-snapshots/__tests__/capture.test.ts"
    - "dashboard/src/app/api/funnel-snapshots/__tests__/trends.test.ts"
    - "dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx"
  modified: []

key-decisions:
  - "Used vi.hoisted() + vi.mock() pattern consistent with existing snapshot-capture.route.test.ts"
  - "Dynamic imports for route handlers to allow per-test mock reconfiguration"
  - "Supabase mock uses chainable from().upsert()/delete().lt() matching real API shape"

patterns-established:
  - "Funnel snapshot test mocking: vi.hoisted Supabase chain with from/upsert/delete/lt"
  - "Trends API test helper: stubSupabaseRows() for configurable row sets"

requirements-completed: [HIST-01, HIST-02, HIST-03]

# Metrics
duration: 2min
completed: 2026-02-25
---

# Phase 30 Plan 00: Test Scaffolds Summary

**21 failing test cases across 3 files covering capture auth/upsert/retention, trends aggregation/CTR/ROAS, and FunnelTrendCards rendering/arrows/formatting**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-25T10:45:44Z
- **Completed:** 2026-02-25T10:47:53Z
- **Tasks:** 1
- **Files created:** 3

## Accomplishments
- capture.test.ts: 7 tests covering auth rejection (401), upsert behavior, retention cleanup (90-day DELETE), error handling (500)
- trends.test.ts: 6 tests covering 7d vs prev-7d aggregation, CTR/ROAS division-by-zero guards, has_data/has_previous edge cases, Cache-Control
- FunnelTrendCards.test.tsx: 8 tests covering render-nothing on no data, 6 metric card names, "No prior data" text, green/red trend arrows, 5% flat threshold, inverted Ad Spend colors, number formatting

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffolds for capture, trends, and FunnelTrendCards** - `6d7a425d` (test)

## Files Created/Modified
- `dashboard/src/app/api/funnel-snapshots/__tests__/capture.test.ts` - Capture endpoint tests (auth, upsert, retention, errors)
- `dashboard/src/app/api/funnel-snapshots/__tests__/trends.test.ts` - Trends endpoint tests (aggregation, derived metrics, edge cases)
- `dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx` - UI component tests (rendering, arrows, formatting)

## Decisions Made
- Used vi.hoisted() + vi.mock() pattern matching existing project convention (snapshot-capture.route.test.ts)
- Used dynamic imports for route handlers so mocks can be reconfigured per test
- Supabase mock chain mirrors real API shape (from -> upsert/delete -> lt -> select)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All behavioral contracts defined for Plans 01 and 02
- Tests will pass as production code is implemented in subsequent plans
- Capture endpoint tests expect: POST handler, Bearer auth, getLabelTierPerformance call, Supabase upsert, 90-day retention DELETE
- Trends endpoint tests expect: GET handler, Supabase query with date range, CTR/ROAS computation, has_data/has_previous flags
- FunnelTrendCards tests expect: React component fetching /api/funnel-snapshots/trends, 6 metric cards, trend arrows with 5% threshold

## Self-Check: PASSED

- FOUND: capture.test.ts (199 lines, min 40)
- FOUND: trends.test.ts (176 lines, min 40)
- FOUND: FunnelTrendCards.test.tsx (324 lines, min 40)
- FOUND: commit 6d7a425d

---
*Phase: 30-historical-funnel-persistence*
*Completed: 2026-02-25*
