---
phase: 35-market-intelligence
plan: 01
subsystem: api
tags: [supabase, next-api-routes, bcg-matrix, demand-analysis, competitor-tracking, market-intelligence]

# Dependency graph
requires:
  - phase: 34.1-fix-decision-logic
    provides: query_value_scores with tier scoring data, funnel_snapshots_daily backfill
provides:
  - Shared types for Market Intelligence UI (DemandData, CompetitiveData, ProductsData)
  - GET /api/market-intelligence/demand (impression share, CPC, seasonal, new terms, long-tail)
  - GET /api/market-intelligence/competitive (brand split, competitor mentions)
  - GET /api/market-intelligence/products (BCG quadrant classification, group detail drill-down)
  - Pure computation functions (classifyQuadrant, buildLongTailBuckets, parseMonthlySearchVolumes)
  - Constants (competitor tokens, brand tokens, BCG colors/labels)
affects: [35-02-PLAN, 35-03-PLAN, 35-04-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - In-memory join pattern for search_queries + query_value_scores (no custom_label_0 on search_queries)
    - BCG quadrant classification using dynamic medians from simple-statistics
    - Aggregation by query_text across variant-level rows before analysis

key-files:
  created:
    - dashboard/src/lib/market-intelligence/types.ts
    - dashboard/src/lib/market-intelligence/constants.ts
    - dashboard/src/lib/market-intelligence/computations.ts
    - dashboard/src/app/api/market-intelligence/demand/route.ts
    - dashboard/src/app/api/market-intelligence/competitive/route.ts
    - dashboard/src/app/api/market-intelligence/products/route.ts
  modified: []

key-decisions:
  - "In-memory join: search_queries lacks custom_label_0, so join through query_value_scores lookup map"
  - "Keyword enrichment: merge search_queries.avg_monthly_searches with keyword_metrics for best coverage"
  - "Trend computation: 30d vs prior 30d from funnel_snapshots_daily conversions_value"
  - "Detail drill-down: approximate quadrant for single group (exact quadrant requires global medians from overview)"

patterns-established:
  - "Market Intelligence API pattern: createAdminClient + dual-table aggregation + typed response"
  - "BCG classification: dynamic medians from computeMedians(), not hardcoded thresholds"

requirements-completed: [DEMAND-01, DEMAND-02, DEMAND-03, DEMAND-04, DEMAND-05, DEMAND-06, DEMAND-07, PROD-01, PROD-02, PROD-03, PROD-04]

# Metrics
duration: 6min
completed: 2026-02-26
---

# Phase 35 Plan 01: Data Layer Summary

**3 API routes serving demand signals, competitive landscape, and BCG-classified product groups for Market Intelligence tabs**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-26T04:35:28Z
- **Completed:** 2026-02-26T04:41:01Z
- **Tasks:** 3
- **Files created:** 6

## Accomplishments
- Shared type system for all 3 Market Intelligence tabs (Demand, Competitive, Products)
- 15 competitor tokens and brand detection for automated competitive analysis
- BCG quadrant classification with dynamic median thresholds (not hardcoded)
- 5 demand signals: impression share gaps, CPC headroom, seasonal patterns, new term discovery, long-tail buckets
- Product group drill-down with top 50 terms per group including tier context

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shared types, constants, and computation functions** - `5f20666d` (feat)
2. **Task 2: Create demand and competitive API routes** - `3d790f91` (feat)
3. **Task 3: Create products API route with BCG classification** - `de027634` (feat)

## Files Created/Modified
- `dashboard/src/lib/market-intelligence/types.ts` - Shared TypeScript interfaces for all 3 tabs
- `dashboard/src/lib/market-intelligence/constants.ts` - Competitor tokens, brand tokens, BCG labels/colors, thresholds
- `dashboard/src/lib/market-intelligence/computations.ts` - Pure functions: BCG classify, medians, seasonal, long-tail, CPC
- `dashboard/src/app/api/market-intelligence/demand/route.ts` - GET route for demand signals (5 analyses + KPIs)
- `dashboard/src/app/api/market-intelligence/competitive/route.ts` - GET route for brand/competitor split + mentions
- `dashboard/src/app/api/market-intelligence/products/route.ts` - GET route for BCG overview + group detail drill-down

## Decisions Made
- In-memory join pattern: search_queries lacks custom_label_0, so we build a lookup map from query_value_scores and match by lowercased search term
- Keyword metrics enrichment: search_queries may have avg_monthly_searches from enrichment, but we also check keyword_metrics table for fuller coverage
- Trend computation uses funnel_snapshots_daily 30d vs prior 30d (not search_queries periods)
- Detail drill-down approximates quadrant locally since exact classification requires global medians from the overview endpoint

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Build lock file from concurrent process required cleanup before verification build could run
- Task 3 commit picked up previously-staged files from working tree (not caused by this plan)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 3 API routes ready for UI consumption in plans 02/03
- Types are importable by dashboard components
- Optional customLabel0 filter param supported on all routes for category-level filtering

## Self-Check: PASSED

All 6 files verified present. All 3 commit hashes verified in git log. Build passes.

---
*Phase: 35-market-intelligence*
*Completed: 2026-02-26*
