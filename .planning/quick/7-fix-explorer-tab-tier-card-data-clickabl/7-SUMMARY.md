---
phase: quick-7
plan: 7
subsystem: tier-scoring-ui
tags: [fix, feature, multi-label, explorer-tab, wave-5]
dependency_graph:
  requires: [quick-4, quick-5, quick-6]
  provides: [fixed-tier-cards, clickable-opportunities, multi-label-context]
  affects: [tier-scoring-page, term-scorecard, action-queue]
tech_stack:
  added: []
  patterns: [scores-derived-counts, cross-label-memo, label-count-indicator]
key_files:
  created: []
  modified:
    - dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/page.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
    - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
decisions:
  - "Derive termCount from scores.filter() instead of tierDist.sampleSize to fix always-1 sample size bug"
  - "Show 'Limited data' only when tier has 0 scored terms (not based on insufficientTiers array)"
  - "labelCount computed in ActionQueueTable via useMemo Map for O(n) efficiency"
metrics:
  duration: 5min
  completed: 2026-02-26
  tasks: 2
  files: 6
---

# Quick Task 7: Fix Explorer Tab Tier Card Data + Clickable Opportunities + Wave 5 Multi-Label UI

Fixed tier cards showing correct term counts and added Multi-Label Context card with cross-group label switching.

## What Changed

### Task 1: Fix Explorer Tab Tier Cards + Clickable Opportunities (f688fd0e)

**Root cause fix:** `computeTierDistributions()` receives aggregated data from `getLabelTierPerformance()` which returns exactly 1 row per (custom_label_0, tier) combo. So `tierDist.sampleSize` was always 1, causing every tier to show "Limited data (1 terms)" despite having 215 scored terms.

**Fix:** Both GroupDetail.tsx and GroupOverview.tsx now derive term counts from `scores.filter(s => s.currentTier === tier).length` instead of `tierDist?.sampleSize`. "Limited data" only shows when a tier truly has 0 scored terms.

**Clickable rows:** Optimization Opportunities table rows in GroupDetail now have `cursor-pointer`, `hover:bg-muted/50`, and `onClick` to navigate to TermScorecard detail view.

### Task 2: Wave 5 Multi-Label UI (06538449)

- **allScoresForTerm** computed via `useMemo` in page.tsx -- filters all scores matching the currently-viewed term's searchTerm across all custom_label_0 groups
- **Multi-Label Context card** on TermScorecard -- shows when a term appears in 2+ product groups with tier movement indicators and "View this label" click-to-switch
- **Label count indicator** on ActionQueueRow -- shows "(N labels)" badge when a term has entries in multiple groups
- **labelCounts** computed in ActionQueueTable via `useMemo` with a `Map<string, number>` for O(n) efficiency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Wired onSelectTerm in page.tsx during Task 1**
- **Found during:** Task 1 verification
- **Issue:** Task 1 added `onSelectTerm` to GroupDetailProps but page.tsx didn't pass it yet (that was planned for Task 2), causing TypeScript build failure
- **Fix:** Added `onSelectTerm={(term) => setSelectedTerm(term)}` to GroupDetail in page.tsx as part of Task 1
- **Files modified:** page.tsx
- **Commit:** f688fd0e

## Verification

- TypeScript: zero errors (`npx tsc --noEmit`)
- Build: passes (`npm run build`)
- Tests: all 77 tier-scoring tests pass (`npx vitest run`)
- Lint: no new errors (8 pre-existing errors in market-intelligence files)

## Self-Check: PASSED

All 6 modified files exist. Both commits (f688fd0e, 06538449) verified in git log.
