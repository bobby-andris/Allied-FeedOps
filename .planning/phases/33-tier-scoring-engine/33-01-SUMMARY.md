---
phase: 33-tier-scoring-engine
plan: 01
subsystem: optimization
tags: [statistics, simple-statistics, z-score, median, MAD, tier-scoring, TDD]

# Dependency graph
requires:
  - phase: 32-operational-prerequisites
    provides: funnel_snapshots_daily table, LabelTierPerformance type
provides:
  - Pure computation module for distribution-based tier scoring
  - TypeScript interfaces for tier scoring system
  - Robust z-score scoring using median/MAD
  - Hierarchical fallback (per_group -> global -> defaults)
  - Confidence scoring with 30/30/20/20 weighting
  - Impact estimation as ranges (low/mid/high)
affects: [33-02-api-route, 33-03-ui, 33-04-ui]

# Tech tracking
tech-stack:
  added: [simple-statistics]
  patterns: [robust-z-score, median-absolute-deviation, hierarchical-fallback, distribution-based-boundaries]

key-files:
  created:
    - dashboard/src/lib/optimization/tier-scoring.types.ts
    - dashboard/src/lib/optimization/tier-scoring.ts
    - dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts
  modified: []

key-decisions:
  - "Robust z-scores (median/MAD) over standard z-scores for right-skewed ROAS data"
  - "ROAS capped at p99 before computing distributions to limit outlier impact"
  - "Tier fit scored as weighted deviation: 50% ROAS, 20% CVR, 15% CPC, 15% CTR"
  - "Default AOV of $85 for Allied Brass impact estimation"
  - "MAD=0 returns z-score of 0 (all-identical-values edge case)"

patterns-established:
  - "Pure computation module pattern: zero side effects, stateless functions, module-level cache"
  - "Factory test fixtures: makeLabelTierPerf(), makeTermWithFunnels(), distribution generators"
  - "Hierarchical fallback: per_group -> global -> defaults based on MIN_SAMPLE_SIZE=5"

requirements-completed: [TIER-01, TIER-02, TIER-03, TIER-04, TIER-05, TIER-06]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 33 Plan 01: Tier Scoring Engine Summary

**Distribution-based tier scoring with robust z-scores (median/MAD), hierarchical fallback, and 30/30/20/20 confidence weighting using simple-statistics**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T18:50:13Z
- **Completed:** 2026-02-25T18:54:12Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- TDD cycle completed: 21 tests written RED, all passing GREEN
- Pure computation module replacing hardcoded ROAS thresholds (3.6/3.1/2.6) with dynamic distribution-based scoring
- Robust z-score scoring immune to right-skewed ROAS distributions (outlier ROAS 15-50 does not distort scoring)
- Hierarchical fallback ensures scoring works even with sparse data (<5 terms per tier)
- 15% max boundary shift cap prevents tier thresholds from changing too rapidly between computation runs

## Task Commits

Each task was committed atomically:

1. **Task 1: Define type contracts and write failing tests** - `fbb1bb7f` (test)
2. **Task 2: Implement tier-scoring.ts to pass all tests** - `709fb209` (feat)

## Files Created/Modified
- `dashboard/src/lib/optimization/tier-scoring.types.ts` - All TypeScript interfaces (TierDistribution, GroupDistributions, TermScore, ConfidenceResult, ImpactRange, ScoringResult, etc.)
- `dashboard/src/lib/optimization/tier-scoring.ts` - Pure computation module: computeTierDistributions, scoreTerm, computeConfidence, estimateImpact, computeTierBoundaries, getCachedDistributions, buildHeroCallout
- `dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts` - 21 tests covering all 6 TIER requirements with factory fixtures

## Decisions Made
- Robust z-scores (median/MAD) over standard z-scores — right-skewed ROAS data makes mean/stddev unreliable
- ROAS capped at p99 before computing distributions to limit outlier impact on percentiles
- Tier fit weighted 50% ROAS, 20% CVR, 15% CPC, 15% CTR (ROAS is primary optimization metric)
- Default AOV of $85 for Allied Brass impact estimation (can be parameterized later)
- MAD=0 edge case returns z-score of 0 rather than throwing (handles all-identical-values case)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Types and computation module ready for API route (Plan 02)
- All exports match must_haves specification
- Module-level cache with 10-minute TTL ready for API route consumption

---
*Phase: 33-tier-scoring-engine*
*Completed: 2026-02-25*
