---
phase: 34-revenue-leakage-execution
plan: "02"
subsystem: ui
tags: [react-hooks, classification, optimistic-updates, tier-scoring, revenue-leakage]

requires:
  - phase: 34-revenue-leakage-execution
    provides: recommendations API route (34-01)
  - phase: 33-tier-scoring
    provides: TermScore interface, tier-scoring engine
provides:
  - useRecommendations hook with approve/reject/undo/batchApprove and optimistic updates
  - Reason code classification module (misplaced, wasted_spend, under_invested)
  - TermScore enriched with totalConversions and totalCostMicros fields
affects: [34-03, 34-04, revenue-leakage-tab]

tech-stack:
  added: []
  patterns: [optimistic-update-with-revert, reason-code-classification, composite-key-state-map]

key-files:
  created:
    - dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts
    - dashboard/src/app/(dashboard)/tier-scoring/hooks/useRecommendations.ts
    - dashboard/src/app/(dashboard)/tier-scoring/__tests__/reason-codes.test.ts
  modified:
    - dashboard/src/lib/optimization/tier-scoring.types.ts
    - dashboard/src/lib/optimization/tier-scoring.ts
    - dashboard/src/app/(dashboard)/tier-scoring/__tests__/plain-verdict.test.ts

key-decisions:
  - "Wasted spend threshold set at $5 (5M micros) — below this is noise, not actionable waste"
  - "Priority order: wasted_spend > under_invested > misplaced ensures most urgent classification wins"
  - "Hook uses searchTerm::customLabel0 composite key for status lookup — matches API's unique constraint"

patterns-established:
  - "Optimistic update pattern: save previous state, update immediately, revert on API error"
  - "Reason code classification: pure function accepts TermScore + optional KeywordData, returns category"

requirements-completed: [LEAK-02, LEAK-03, LEAK-04, EXEC-01, EXEC-02, EXEC-03, EXEC-04]

duration: 4min
completed: 2026-02-26
---

# Phase 34 Plan 02: useRecommendations Hook + Reason Code Classification Summary

**Client-side data layer with optimistic-update recommendation hook and 3-category leakage reason code classifier (misplaced/wasted$/under-invested)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-26T00:42:13Z
- **Completed:** 2026-02-26T00:46:12Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- Extended TermScore with totalConversions and totalCostMicros for wasted spend detection (LEAK-03)
- Built reason code classifier with priority-based categorization: wasted_spend > under_invested > misplaced
- Created useRecommendations hook with full optimistic update/revert pattern for approve, reject, undo, batchApprove
- 14 unit tests covering all classification categories, edge cases, and sorting behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Create reason code classification module** - `3845460a` (feat)
2. **Task 2: Create useRecommendations hook** - `6da572f1` (feat)
3. **Task 3: Write unit tests for reason codes** - `dc83cdd8` (test)

## Files Created/Modified
- `dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts` - Reason code classification with classifyLeakageReason, classifyAllTerms, labels, colors
- `dashboard/src/app/(dashboard)/tier-scoring/hooks/useRecommendations.ts` - Hook managing recommendation statuses with optimistic updates
- `dashboard/src/app/(dashboard)/tier-scoring/__tests__/reason-codes.test.ts` - 14 unit tests for classification logic
- `dashboard/src/lib/optimization/tier-scoring.types.ts` - Added totalConversions and totalCostMicros to TermScore
- `dashboard/src/lib/optimization/tier-scoring.ts` - Populated new TermScore fields from ExistingFunnelTerm
- `dashboard/src/app/(dashboard)/tier-scoring/__tests__/plain-verdict.test.ts` - Updated mock to include new fields

## Decisions Made
- Wasted spend threshold set at $5 (5M micros) — below this is noise, not actionable waste
- Priority order: wasted_spend > under_invested > misplaced ensures most urgent classification wins
- Hook uses searchTerm::customLabel0 composite key for status lookup — matches API's unique constraint
- Under-invested detection requires upward direction + keyword data — downward terms are demotion candidates, not under-invested

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated plain-verdict test mock for new TermScore fields**
- **Found during:** Task 1 (reason code classification module)
- **Issue:** Existing plain-verdict.test.ts mock factory was missing new totalConversions and totalCostMicros fields, would cause TypeScript error
- **Fix:** Added default values to makeTermScore helper
- **Files modified:** dashboard/src/app/(dashboard)/tier-scoring/__tests__/plain-verdict.test.ts
- **Verification:** Plain verdict tests still pass (10/10)
- **Committed in:** 3845460a (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Required to maintain existing test compatibility after type change. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Reason codes and hook ready for consumption by wave 2-3 UI components (34-03, 34-04)
- classifyAllTerms provides sorted, labeled data ready for Revenue Leakage tab rendering
- useRecommendations hook provides full CRUD with optimistic updates for action queue

---
*Phase: 34-revenue-leakage-execution*
*Completed: 2026-02-26*
