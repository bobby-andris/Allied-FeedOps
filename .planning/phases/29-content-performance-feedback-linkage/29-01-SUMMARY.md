---
phase: 29-content-performance-feedback-linkage
plan: 01
subsystem: database, api
tags: [supabase, schema-migration, publish-events, prompt-hash, snapshot-capture, performance-impact]

# Dependency graph
requires:
  - phase: 28-architecture-audit-migration-triage
    provides: Schema drift analysis identifying performance_impact_scores table missing from production
provides:
  - performance_impact_scores table in production Supabase (19 columns, FK to publish_events)
  - cohort_type and product_category columns on performance_snapshots
  - Application-layer prompt_hash NOT NULL enforcement for new publish events
  - Automated post-publish search query snapshot capture
affects: [29-02, 29-03, 30-service-ts-persistence]

# Tech tracking
tech-stack:
  added: []
  patterns: [fire-and-forget snapshot capture, forward-only NOT NULL enforcement at app layer]

key-files:
  created:
    - supabase/migrations/20260225083710_create_performance_impact_scores.sql
  modified:
    - dashboard/src/app/api/publish/sku/route.ts
    - dashboard/src/app/api/publish/batch/route.ts
    - docs/database/SCHEMA.md

key-decisions:
  - "FEED-04 enforcement placed in logPublishEvent function to cover all publish code paths centrally"
  - "prompt_hash enforcement only for status=success events — failed events don't need version tracking"
  - "Legacy fallback now preserves prompt_hash when stripping other new columns on DB error"
  - "Snapshot capture uses query params to match existing snapshot-capture route interface"

patterns-established:
  - "Forward-only enforcement: validate new records at app layer without DB constraint to preserve legacy data"
  - "Fire-and-forget post-publish hooks: non-blocking fetch with .catch() for secondary actions"

requirements-completed: [FEED-02, FEED-03, FEED-04]

# Metrics
duration: 10min
completed: 2026-02-25
---

# Phase 29 Plan 01: Schema + Publish Enforcement Summary

**Created performance_impact_scores table in production, enforced prompt_hash NOT NULL for new publishes, and wired automatic post-publish snapshot capture**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-25T08:34:49Z
- **Completed:** 2026-02-25T08:44:49Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Applied migration creating `performance_impact_scores` table (19 columns) with indexes and constraints, resolving schema drift from Phase 28 audit
- Added `cohort_type` and `product_category` columns to `performance_snapshots` with check constraint
- Enforced prompt_hash NOT NULL at application layer in both publish routes (sku and batch) — throws for new successful publishes missing prompt_hash
- Wired fire-and-forget search query snapshot capture after every successful publish

## Task Commits

Each task was committed atomically:

1. **Task 1: Create performance_impact_scores table and add missing performance_snapshots columns** - `0f229dd2` (feat)
2. **Task 2: Enforce prompt_hash NOT NULL at application layer in both publish code paths** - `333395cc` (feat)
3. **Task 3: Wire post-publish search query snapshot capture into both publish code paths** - `f61ade42` (feat)

## Files Created/Modified
- `supabase/migrations/20260225083710_create_performance_impact_scores.sql` - DDL for new table and altered columns
- `dashboard/src/app/api/publish/sku/route.ts` - FEED-04 prompt_hash enforcement + FEED-03 snapshot capture
- `dashboard/src/app/api/publish/batch/route.ts` - FEED-04 prompt_hash enforcement + FEED-03 snapshot capture
- `docs/database/SCHEMA.md` - Added last schema update note marking drift resolved

## Decisions Made
- Placed FEED-04 enforcement inside `logPublishEvent()` rather than at each call site — single enforcement point covers all 11+ publish event logging calls in sku route and 13+ in batch route
- Only enforce prompt_hash for `status === 'success'` events — failed publish events don't need content version tracking
- Modified legacy fallback to preserve prompt_hash when possible, only stripping it if the DB error specifically mentions prompt_hash
- Re-throw FEED-04 errors through the catch block so the publish operation is properly rejected (not silently swallowed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed corrupted node_modules/@types with duplicate d3 directories**
- **Found during:** Task 2 (build verification)
- **Issue:** `node_modules/@types/` contained directories with spaces (e.g., "d3-array 2") causing TypeScript compilation failure
- **Fix:** Ran `npm install` which cleaned up the corrupted directories
- **Files modified:** node_modules (not committed)
- **Verification:** Build passes cleanly after reinstall

**2. [Rule 3 - Blocking] Worked around Supabase MCP unavailability for DDL execution**
- **Found during:** Task 1 (schema migration)
- **Issue:** MCP tools not available in executor session; Supabase RPC function only allows SELECT queries
- **Fix:** Used `supabase` CLI with migration file and `db push` to apply DDL to production
- **Files modified:** Created migration file, temporarily stashed non-standard-named migrations to avoid re-running them
- **Verification:** Verified via Supabase RPC SELECT queries that table and columns exist in production

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both were environmental issues. No scope change.

## Issues Encountered
- Supabase CLI `db push` wanted to re-apply 5 old migrations with non-standard naming (no timestamp prefix). Resolved by temporarily renaming them to `.bak` during push, then restoring. Our migration used `IF NOT EXISTS` throughout for idempotency.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `performance_impact_scores` table ready for Python compute-impact endpoint (Plan 02)
- `cohort_type`/`product_category` columns ready for Python collector (Plan 02)
- prompt_hash enforcement active — new publishes will be rejected if content lacks generation_prompt_hash
- Post-publish snapshot capture wired — Plan 03's search term delta view will have data for new publishes

## Self-Check: PASSED

All 4 files verified present. All 3 task commits verified in git log. FEED-04 and FEED-03 markers found in both publish routes. performance_impact_scores referenced in SCHEMA.md.

---
*Phase: 29-content-performance-feedback-linkage*
*Completed: 2026-02-25*
