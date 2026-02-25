---
phase: 33-tier-scoring-engine
plan: 02
subsystem: api
tags: [tier-scoring, supabase-upsert, api-route, simple-statistics, shopping-funnel]

# Dependency graph
requires:
  - phase: 32-operational-prerequisites
    provides: query_value_scores table with tier_fit_scores, recommended_tier, net_monthly_impact columns
  - phase: 33-01
    provides: tier-scoring.ts computation module (computeTierDistributions, scoreTerm, getCachedDistributions, buildHeroCallout)
provides:
  - GET /api/shopping-funnel/tier-scoring API endpoint for scoring orchestration
  - Unique index migration (038) enabling upsert on query_value_scores
  - Database persistence of scored terms via chunked upsert
affects: [33-03-PLAN, 33-04-PLAN, tier-scoring-ui, optimization-pages]

# Tech tracking
tech-stack:
  added: []
  patterns: [chunked-upsert-500, parallel-data-fetch, admin-client-for-writes]

key-files:
  created:
    - dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
    - supabase/migrations/038_query_value_scores_unique_index.sql
  modified: []

key-decisions:
  - "Used createAdminClient() for DB writes instead of cookie-based createClient() -- API routes need service role for upsert"
  - "Filter labelTierPerformance rows client-side since getLabelTierPerformance() does not accept customLabel0 param"
  - "Skip terms with Campaign Negative or Unknown tier assignments -- only score HIGH/MEDIUM/LOW"

patterns-established:
  - "Chunked upsert pattern: batch DB writes in 500-row chunks to avoid payload limits"
  - "Parallel data fetch: Promise.all for independent service calls in API routes"

requirements-completed: [TIER-01, TIER-02, TIER-03]

# Metrics
duration: 3min
completed: 2026-02-25
---

# Phase 33 Plan 02: Tier Scoring API Route Summary

**API route at /api/shopping-funnel/tier-scoring with unique index migration enabling chunked upsert persistence to query_value_scores**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-25T18:50:20Z
- **Completed:** 2026-02-25T18:53:56Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created unique index migration (038) on query_value_scores(search_term, custom_label_0) for upsert support
- Built API route that fetches tier performance and funnel terms in parallel, scores each term, and persists results
- API route returns distributions, scores, heroCallout, computedAt, and aggregate impact metrics
- maxDuration=60 configured for Vercel serverless timeout

## Task Commits

Each task was committed atomically:

1. **Task 1: Install simple-statistics and create unique index migration** - `23fb3d7a` (chore)
2. **Task 2: Build API route for tier scoring** - `8574e936` (feat)

## Files Created/Modified
- `supabase/migrations/038_query_value_scores_unique_index.sql` - Unique index for upsert conflict resolution
- `dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts` - API route orchestrating scoring, persistence, and JSON response

## Decisions Made
- Used `createAdminClient()` from `@/lib/supabase/admin` for database writes (service role needed for upsert, not cookie-based auth)
- Applied client-side filtering of labelTierPerf rows by customLabel0 since `getLabelTierPerformance()` doesn't accept that parameter
- Terms with 'Campaign Negative' or 'Unknown' tier assignments are skipped (only HIGH/MEDIUM/LOW are scored)
- Upsert errors on individual chunks are logged but don't abort the entire operation (partial persistence is acceptable)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Used createAdminClient instead of createServiceClient**
- **Found during:** Task 2 (API route implementation)
- **Issue:** Plan referenced `createServiceClient` from `@/lib/supabase/server` but that function doesn't exist. The server module exports `createClient` which is cookie-based (not suitable for API writes).
- **Fix:** Used `createAdminClient` from `@/lib/supabase/admin` which uses service role key for privileged writes.
- **Files modified:** dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
- **Verification:** Import resolves, matches pattern used in other API routes
- **Committed in:** 8574e936

**2. [Rule 3 - Blocking] Client-side customLabel0 filtering for getLabelTierPerformance**
- **Found during:** Task 2 (API route implementation)
- **Issue:** Plan assumed `getLabelTierPerformance` accepts `customLabel0` parameter but the actual function signature only takes `{ startDate, endDate }`.
- **Fix:** Fetch all rows then filter by customLabel0 in the API route when the parameter is provided.
- **Files modified:** dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
- **Verification:** Inspected service.ts function signature at line 1042
- **Committed in:** 8574e936

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- Plan 01 (tier-scoring.ts computation module) not yet completed -- API route imports from `@/lib/optimization/tier-scoring` which doesn't exist yet. This causes 1 expected TypeScript error that will resolve when Plan 01 completes. The route is structurally complete and correct.
- Migration 038 SQL file created but not yet applied to production Supabase (MCP tools not available in this execution context). Must be applied before the API route can persist data.

## User Setup Required
- Apply migration 038 to production Supabase: execute `CREATE UNIQUE INDEX IF NOT EXISTS idx_query_value_scores_term_label_unique ON query_value_scores (search_term, custom_label_0);`

## Next Phase Readiness
- API route ready to serve data once Plan 01 (computation module) is completed
- Migration must be applied to production before upsert will work
- Plans 03-04 (UI) can proceed with the API contract defined here

---
*Phase: 33-tier-scoring-engine*
*Completed: 2026-02-25*
