---
phase: quick-3
plan: 01
subsystem: optimization
tags: [tier-scoring, roas, waterfall-shopping, determineAction]

requires:
  - phase: 34.1-fix-decision-logic
    provides: "Tier scoring engine with calibration gates and prescriptive verdicts"
provides:
  - "ROAS-based determineAction using p25/p75 percentiles instead of statistical best-fit"
  - "Correct constrain/promote direction based on term ROAS vs tier distribution"
  - "6 new tests proving ROAS-based action determination"
affects: [tier-scoring, action-queue, waterfall-dashboard]

tech-stack:
  added: []
  patterns: ["ROAS percentile comparison (p25/p75) for action direction instead of statistical tier fit"]

key-files:
  created: []
  modified:
    - dashboard/src/lib/optimization/tier-scoring.ts
    - dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts

key-decisions:
  - "determineAction returns {action, targetTier} tuple — targetTier is ROAS-derived, separate from recommendedTier (statistical fit)"
  - "HIGH tier underperformers observe (cannot constrain further up) — boundary correctly handled"
  - "recommendedTier field preserved on TermScore for display; only action/impact/verdict use targetTier"

patterns-established:
  - "ROAS-based action: underperformer (< p25) -> constrain UP, high performer (> p75) -> promote DOWN"
  - "Wasted spend path unchanged — evaluated before ROAS comparison"

requirements-completed: [QUICK-3]

duration: 3min
completed: 2026-02-26
---

# Quick Task 3: Fix determineAction ROAS-based Logic Summary

**Rewrote determineAction to use ROAS p25/p75 percentiles for promote/constrain direction, fixing bug where all underperformers got 'promote' instead of 'constrain'**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-26T04:54:19Z
- **Completed:** 2026-02-26T04:57:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Fixed core bug: underperforming terms (ROAS below tier p25) now get 'constrain' (restrict bidding) instead of 'promote' (aggressive bidding)
- High-performing terms (ROAS above tier p75) correctly get 'promote' to move down funnel for aggressive bidding
- Impact estimation and verdict text now reference correct ROAS-derived targetTier instead of statistical recommendedTier
- Added 6 targeted tests proving the ROAS-based logic works correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite determineAction to use ROAS percentiles** - `c7c9b993` (fix)
2. **Task 2: Add targeted tests for ROAS-based action determination** - `6daff12f` (test)

## Files Created/Modified
- `dashboard/src/lib/optimization/tier-scoring.ts` - Rewrote determineAction signature to accept currentTierDist and termRoas, returns {action, targetTier}; updated scoreTerm call site and verdict text to use targetTier
- `dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts` - Added 6 tests in "ROAS-based determineAction logic" describe block

## Decisions Made
- determineAction returns a `{action, targetTier}` tuple rather than just the action, so callers can use the ROAS-derived target tier for impact and verdict without re-deriving it
- Kept `recommendedTier` on TermScore unchanged (still from statistical fit) since it is used elsewhere for display purposes
- HIGH tier boundary: underperformers in HIGH cannot be constrained further (already at top), so they observe

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing test failure in "TIER-06: computeConfidence > uses intent features when provided" (branded terms return 0.2 alignment, test expects >=0.5). This is unrelated to the ROAS-based changes and was failing before the fix. Not in scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Tier scoring engine now correctly routes underperformers to constrained tiers and high performers to aggressive tiers
- Action queue UI will display correct constrain/promote recommendations
- Pre-existing branded intent test should be fixed separately (out of scope)

---
*Phase: quick-3*
*Completed: 2026-02-26*
