---
phase: quick-8
plan: 1
subsystem: tier-scoring-explorer
tags: [trigger-system, explorer-tab, ui-consistency]
dependency_graph:
  requires: [quick-7, phase-34.2]
  provides: [trigger-consistent-explorer]
  affects: [tier-scoring-page]
tech_stack:
  patterns: [classifyAllTerms-reuse, trigger-badge-helper, useMemo-classification]
key_files:
  modified:
    - dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/LabelProfitabilitySummary.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/TierDetail.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/lib/plain-verdict.ts
    - dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
decisions:
  - "Keep isMisplaced in plain-verdict.ts and TermScorecard.tsx as fallback for terms without triggers"
  - "getTriggerBadge inline helper in GroupDetail for trigger-to-badge display mapping"
  - "API aggregateImpact still includes isMisplaced terms for total impact calculation"
metrics:
  duration: "5min"
  completed: "2026-02-26T20:18:18Z"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 6
---

# Quick Task 8: Fix Explorer Tab Old Logic Summary

Replaced all Phase 33 legacy `isMisplaced` + `recommendedTier` logic in Explorer tab components with the Phase 34.2 trigger system (`trigger`, `targetTier`, `classifyAllTerms`), making Explorer tab consistent with Action Queue tab.

## One-liner

Explorer tab now uses trigger-based classification (wasted_spend, promote, demote) matching Action Queue, replacing old statistical best-fit recommendations.

## What Changed

### GroupDetail.tsx
- Replaced `scores.filter(s => s.isMisplaced)` with `classifyAllTerms(scores).filter(t => t.trigger && t.trigger !== 'observe')`
- Added "Action" column with color-coded trigger badges (Block/Demote/Promote/Budget)
- Changed "Recommended" to "Target" column showing `targetTier ?? recommendedTier`
- Callout now summarizes trigger types instead of ROAS boundaries

### GroupOverview.tsx
- Opportunity counts per group card now use trigger-based classification
- Sorting by opportunity count reflects real actionable terms

### LabelProfitabilitySummary.tsx
- Wrapped opportunity counting in `useMemo` with `classifyAllTerms` trigger filter
- No longer counts old statistical `isMisplaced` terms

### TierDetail.tsx
- Replaced `misplacedTerms` with `actionableTerms` using trigger filter
- Sort by status uses `trigger !== 'observe'` instead of `isMisplaced`
- Fit Score sort uses `targetTier ?? recommendedTier`
- Status column shows trigger-based movement arrows with `targetTier`
- Bottom "Opportunities" section uses trigger-based list

### plain-verdict.ts
- Added trigger-aware verdict generation before legacy `isMisplaced` fallback
- `generatePlainVerdict()`: prescriptive text per trigger type (wasting money, underperforming, converting, etc.)
- `generateShortVerdict()`: compact trigger descriptions for table rows

### API route (route.ts)
- `totalMisplaced` changed from `isMisplaced || trigger` to trigger-only count

## Deviations from Plan

None - plan executed exactly as written.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | c876813b | feat(quick-8): replace isMisplaced with trigger system in GroupDetail, GroupOverview, LabelProfitabilitySummary |
| 2 | a1792068 | feat(quick-8): replace isMisplaced with trigger system in TierDetail, plain-verdict, API route |

## Verification

- TypeScript: zero errors (`npx tsc --noEmit`)
- Build: passes (`npm run build`)
- Lint: all errors pre-existing in unrelated files (market-intelligence)
- Grep: no stale `s.isMisplaced` or `score.isMisplaced` filters in tier-scoring components
- Grep: all tier destination displays use `targetTier ?? recommendedTier` pattern

## Self-Check: PASSED

- [x] GroupDetail.tsx modified with trigger system
- [x] GroupOverview.tsx modified with trigger system
- [x] LabelProfitabilitySummary.tsx modified with trigger system
- [x] TierDetail.tsx modified with trigger system
- [x] plain-verdict.ts modified with trigger-aware verdicts
- [x] route.ts totalMisplaced is trigger-only
- [x] Commits c876813b and a1792068 exist
- [x] Build passes
