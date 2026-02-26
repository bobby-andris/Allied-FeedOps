---
phase: quick-6
plan: 1
subsystem: tier-intelligence
tags: [dashboard, ui, detail-page, narrative, tooltips]
dependency_graph:
  requires: [quick-5]
  provides: [wave-3-narrative-briefing, wave-4-raw-data-tooltips]
  affects: [tier-scoring-detail-page]
tech_stack:
  added: []
  patterns: [tooltip-provider, narrative-builder-functions]
key_files:
  created: []
  modified:
    - dashboard/src/lib/optimization/tier-scoring.types.ts
    - dashboard/src/lib/optimization/tier-scoring.ts
    - dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
decisions:
  - Narrative builder functions extracted as pure helpers outside component for reuse
  - TIER_DESCRIPTIONS separate from TIER_TOOLTIPS (briefing vs tooltip contexts)
  - Wasted spend threshold text says "wasted-spend threshold" (not hardcoded dollar amount since it is dynamic)
metrics:
  duration: 203s
  completed: "2026-02-26T18:55:18Z"
---

# Quick Task 6: Waves 3 & 4 -- Detail Page Narrative Briefing + Raw Data + Tooltips Summary

Trigger-specific narrative briefing, 9-box raw Google Ads data grid, and Info tooltips on all scoring factors and tier fit rows in TermScorecard detail page.

## What Was Done

### Task 1: Add 4 raw data fields to TermScore + populate in scoreTerm
**Commit:** e5e73fc5

Added 4 optional fields to TermScore interface (`totalClicks`, `totalConversionsValue`, `totalAverageCpcMicros`, `totalAllConversions`) and populated them from ExistingFunnelTerm in the scoreTerm return object. All 77 existing tests pass.

### Task 2: Narrative Briefing, Raw Google Ads Data, Tooltips
**Commit:** b8617170

1. **Narrative Briefing card** -- first card after term header. Three bold-labeled paragraphs (Current State, Proposed Change, Why) that generate trigger-specific prose from TermScore data. Covers all 6 triggers (wasted_spend, demote_underperform, promote_conversion, promote_intent, under_invested, observe) with contextual details like rCTR, intent scores, and word count.

2. **Raw Google Ads Data card** -- 9 stat boxes in a 3-column grid (2 on mobile): Impressions, Clicks, CTR, Avg CPC, Total Cost, ROAS, Conversions, All Conv., Conv. Value. All values formatted with toLocaleString, formatDollars, or percentage as appropriate. Division-by-zero guarded.

3. **Scoring Factor tooltips** -- Info icon next to each of the 6 factor names (ROAS Position, Consistency, Data Volume, Intent Alignment, Feed Alignment, Behavioral Intent) with detailed explanations of what each metric measures and its weight.

4. **Tier Fit tooltips** -- Info icon next to each tier name (HIGH, MEDIUM, LOW) in the Tier Fit Comparison card explaining the waterfall structure and expected performance.

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- 77/77 tier-scoring tests pass
- Dashboard build passes with zero errors
- No new lint warnings in modified files
