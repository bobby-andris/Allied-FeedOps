---
phase: 34-revenue-leakage-execution
plan: "01"
subsystem: api, database
tags: [supabase, next.js, upsert, routing-recommendations, crud, vitest]

requires:
  - phase: 33.2-ui-redesign
    provides: action queue UI components that will consume this API
provides:
  - routing_recommendations table with upsert support via unique constraint
  - CRUD API route (approve, reject, undo, batch_approve, history, statuses)
  - Unit test suite for recommendations API (10 tests)
affects: [34-02, 34-03, 34-04]

tech-stack:
  added: []
  patterns:
    - "Supabase upsert with onConflict for idempotent approve/reject"
    - "Action-based POST handler switching on body.action field"
    - "Metadata JSONB with history array for audit trail"

key-files:
  created:
    - supabase/migrations/039_routing_recommendations_table.sql
    - dashboard/src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts
  modified:
    - dashboard/src/app/api/shopping-funnel/recommendations/route.ts

key-decisions:
  - "Upsert on (search_term, custom_label_0) unique constraint for idempotent approve/reject"
  - "Metadata JSONB stores currentTier, impact, and append-only history array for audit"
  - "recommended_action defaults to 'funnel' for tier movements, 'global_block' for wasted spend blocks"

patterns-established:
  - "Action-based POST dispatch: body.action switches between approve/reject/undo/batch_approve"
  - "Undo fetches existing metadata then appends history entry before update"

requirements-completed: [EXEC-01, EXEC-02, EXEC-03, EXEC-05]

duration: 3min
completed: 2026-02-25
---

# Phase 34 Plan 01: Database Migration + Recommendations API Summary

**routing_recommendations table with upsert unique constraint + CRUD API handling approve/reject/undo/batch_approve with metadata history tracking**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T00:42:35Z
- **Completed:** 2026-02-26T00:45:20Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Migration 039 creates routing_recommendations table idempotently with unique constraint on (search_term, custom_label_0) for upsert support
- CRUD API route with 4 POST actions (approve, reject, undo, batch_approve) and 2 GET modes (history, statuses) while preserving existing recommendation queue GET
- 10 unit tests covering all actions, edge cases, and recommended_action override for wasted spend blocks

## Task Commits

Each task was committed atomically:

1. **Task 1: Create migration 039 for routing_recommendations** - `9ecae74e` (chore)
2. **Task 2: Build CRUD API route for recommendations** - `6aeba500` (feat)
3. **Task 3: Write unit tests for recommendations API route** - `7f473fab` (test)

## Files Created/Modified
- `supabase/migrations/039_routing_recommendations_table.sql` - Table creation with check constraints, unique constraint, indexes, RLS
- `dashboard/src/app/api/shopping-funnel/recommendations/route.ts` - GET (queue, history, statuses) + POST (approve, reject, undo, batch_approve)
- `dashboard/src/app/api/shopping-funnel/recommendations/__tests__/route.test.ts` - 10 vitest cases covering all CRUD operations

## Decisions Made
- Upsert on (search_term, custom_label_0) unique constraint for idempotent approve/reject operations
- Metadata JSONB stores currentTier, impact, and append-only history array for audit trail
- recommended_action defaults to 'funnel' for standard tier movements; supports 'global_block' override for wasted spend Block actions (LEAK-03)
- Undo fetches existing metadata first to preserve and append to history array rather than overwriting

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

Migration 039 must be applied to production Supabase before the UI can persist recommendations:
```sql
-- Apply via Supabase SQL editor or MCP
-- File: supabase/migrations/039_routing_recommendations_table.sql
```

## Next Phase Readiness
- API foundation ready for 34-02 (reason codes engine) and 34-03/34-04 (UI integration)
- Table must be applied to production before UI testing

---
*Phase: 34-revenue-leakage-execution*
*Completed: 2026-02-25*
