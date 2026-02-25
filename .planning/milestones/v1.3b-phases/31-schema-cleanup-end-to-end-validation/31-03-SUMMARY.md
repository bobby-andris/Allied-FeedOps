---
phase: 31-schema-cleanup-end-to-end-validation
plan: 03
subsystem: database
tags: [supabase, e2e-validation, seed-data, schema, production-verification]

# Dependency graph
requires:
  - phase: 31-01
    provides: "Verified schema state for all 56 production tables with SCHEMA.md"
  - phase: 31-02
    provides: "Wired orphaned components and Coming Soon states for DEFER'd pages"
provides:
  - "Seed script for KEEP'd table page validation (term_intent_state, search_buildout_recommendations, experiment_registry)"
  - "E2E validation report confirming generate->publish->baseline->snapshot loop works"
  - "Complete v1.3b data architecture validation with documented gaps"
affects: [v1.3c-optimization, v1.4-closed-loop]

# Tech tracking
tech-stack:
  added: []
  patterns: ["SEED_V31 tag pattern for test data cleanup", "PostgREST insert (not upsert) for functional unique indexes"]

key-files:
  created:
    - scripts/seed_intent_state.py
    - .planning/phases/31-schema-cleanup-end-to-end-validation/31-e2e-validation-report.md
  modified: []

key-decisions:
  - "FT-16 selected as validation SKU (richest data: 20 publish events, all platforms, baselines + snapshots)"
  - "content_performance_summary confirmed non-existent -- gap for v1.3c/v1.4 closed-loop optimization"
  - "funnel_snapshots_daily has 0 rows despite Phase 30.1 backfill report -- needs re-backfill"
  - "All 14 KEEP'd tables verified empty (expected -- awaiting data pipeline activation)"
  - "Used insert instead of upsert for term_intent_state due to functional unique index"

patterns-established:
  - "SEED_V31 tagging: all test data uses policy_version='SEED_V31' for deterministic cleanup"
  - "E2E validation pattern: query each table individually via PostgREST, document as validation report"

requirements-completed: [MIGR-01, MIGR-02, MIGR-03, MIGR-04]

# Metrics
duration: 6min
completed: 2026-02-25
---

# Phase 31 Plan 03: E2E Validation with Seed Data and Production SKU Walkthrough Summary

**Validated v1.3b data architecture end-to-end: seed script proved KEEP'd table pages render, FT-16 traced through full generate->publish->baseline->snapshot loop, 5 gaps documented for v1.3c**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-25T14:40:55Z
- **Completed:** 2026-02-25T14:46:52Z
- **Tasks:** 2
- **Files created:** 2

## Accomplishments
- Created seed script that populates term_intent_state (5 rows), search_buildout_recommendations (5 rows), and experiment_registry (1 row) with SEED_V31 tag
- Verified Search Governance and Experiment Lab pages render correctly with seed data
- Cleaned up all seed data -- zero SEED_V31 rows remain in production
- Traced FT-16 through the complete data loop: 6 generated content rows, 20 publish events, 1 baseline, 5+ snapshots
- Documented 5 actionable gaps for v1.3c/v1.4 roadmap
- Dashboard build passes cleanly with zero TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Create and run seed script for KEEP'd table pages** - `a5340de0` (feat)
2. **Task 2: E2E validation walkthrough with real production SKU** - `b4a08107` (docs)

## Files Created/Modified
- `scripts/seed_intent_state.py` - Seed/cleanup script for KEEP'd table validation with --seed/--verify/--cleanup flags
- `.planning/phases/31-schema-cleanup-end-to-end-validation/31-e2e-validation-report.md` - Complete E2E validation report with FT-16 walkthrough

## Decisions Made
- Selected FT-16 as validation SKU based on automated scoring (richest data coverage across all tables)
- Used PostgREST insert (not upsert) for term_intent_state because the table has a functional unique index (`COALESCE(custom_label_0, '__all__')`) that PostgREST cannot handle via upsert
- Mapped search_queries.master_sku to term_intent_state.custom_label_0 (search_queries has no custom_label_0 column)
- Documented content_performance_summary as NOT FOUND rather than attempting to create it (per plan instructions)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed column name: search_queries uses query_text not search_term**
- **Found during:** Task 1 (seed script execution)
- **Issue:** Plan referenced `search_queries.search_term` but actual column is `query_text` per SCHEMA.md
- **Fix:** Changed select to use `query_text` and mapped to internal `search_term` key
- **Files modified:** scripts/seed_intent_state.py
- **Committed in:** a5340de0

**2. [Rule 1 - Bug] Fixed column name: search_queries has no custom_label_0**
- **Found during:** Task 1 (seed script execution)
- **Issue:** Plan referenced `search_queries.custom_label_0` but column doesn't exist; `master_sku` is the equivalent
- **Fix:** Changed select to use `master_sku` and mapped to `custom_label_0` for term_intent_state
- **Files modified:** scripts/seed_intent_state.py
- **Committed in:** a5340de0

**3. [Rule 3 - Blocking] Changed upsert to insert for term_intent_state**
- **Found during:** Task 1 (seed script execution)
- **Issue:** PostgREST upsert requires exact column match on unique constraint, but term_intent_state uses a functional index with COALESCE
- **Fix:** Used delete-then-insert pattern with SEED_V31 cleanup before insert
- **Files modified:** scripts/seed_intent_state.py
- **Committed in:** a5340de0

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 blocking)
**Impact on plan:** All fixes were necessary for the seed script to work against production schema. No scope creep.

## Issues Encountered
- funnel_snapshots_daily has 0 rows despite Phase 30.1 reporting 4,093 backfilled rows. The table exists with correct schema but contains no data. Likely needs re-backfill via the existing `/api/funnel-snapshots/backfill` endpoint.
- prompt_hash is NULL on all publish_events for FT-16, meaning prompt lineage traceability is not yet functional.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 31 is complete -- all 3 plans executed successfully
- v1.3b milestone can be marked complete based on validation results
- Gaps documented for v1.3c/v1.4: content_performance_summary view, funnel data re-backfill, prompt_hash population, KEEP'd table data pipelines

## Self-Check: PASSED

All 2 created files verified on disk. Both task commits (a5340de0, b4a08107) verified in git log.

---
*Phase: 31-schema-cleanup-end-to-end-validation*
*Completed: 2026-02-25*
