# Action Queue Terminology & UI Fix — Continuation State

**Date:** 2026-02-26
**Status:** Research complete, needs execution
**Context usage:** Session ended at 83%

## What Quick-3 Fixed (commit c7c9b993)

determineAction() now uses ROAS percentiles instead of statistical best-fit:
- ROAS < currentTier p25 → constrain (move UP toward HIGH)
- ROAS > currentTier p75 → promote (move DOWN toward LOW)
- Returns {action, targetTier} tuple — impact and verdict use correct target

This fixes the core scoring bug. But terminology and UI are still wrong.

## What's STILL Wrong (5 issues)

### Issue 1: "constrain" should be "demote" everywhere

The authoritative domain doc (`docs/domain/waterfall-shopping-structure.md`) and the older intent system (`policy.ts`, `TierMovementsPanel.tsx`) both use **"Demote"** — meaning "pull UP the funnel" toward HIGH to choke bidding.

The tier-scoring system uses "constrain" which is a made-up term not in the domain vocabulary.

**Files to change:**
- `dashboard/src/lib/optimization/tier-scoring.types.ts` — `RecommendedAction` type: `'constrain'` → `'demote'`
- `dashboard/src/lib/optimization/tier-scoring.ts` — `determineAction()` returns, verdict text
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` — button label "Constrain" → "Demote", handler name
- `dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx` — button label "Constrain" → "Demote"
- `dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts` — test assertions
- `dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts` — if it references 'constrain'
- `dashboard/src/lib/optimization/control-center.ts` — if it references 'constrain'
- `dashboard/src/lib/optimization/query-intelligence.ts` — if it references 'constrain'

### Issue 2: TierMovementArrow shows wrong tier

`ActionQueueRow.tsx` line 81:
```tsx
<TierMovementArrow current={term.currentTier} recommended={term.recommendedTier} />
```

`recommendedTier` is the STATISTICAL best-fit tier (often LOW for underperformers). But when action is 'demote', the arrow should show movement toward HIGH, not toward LOW.

**Fix:** The `targetTier` from `determineAction()` needs to be available on the TermScore type and used in the UI. Currently it's computed inside `scoreTerm()` but not stored on the returned TermScore.

**Files to change:**
- `dashboard/src/lib/optimization/tier-scoring.types.ts` — add `targetTier?: FunnelTier` to TermScore
- `dashboard/src/lib/optimization/tier-scoring.ts` — return `targetTier` in TermScore
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` — use `term.targetTier ?? term.recommendedTier`
- `dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx` — same
- `dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts` — persist targetTier in model_inputs

### Issue 3: Non-wasted terms only get Approve/Reject buttons

`ActionQueueRow.tsx` lines 112-133: For non-wasted-spend terms (misplaced), the buttons are generic "Approve" and "Reject". But these terms have a specific directional action (promote or demote). The buttons should say:

- For `recommendedAction === 'promote'`: "Promote to {targetTier}" button (green)
- For `recommendedAction === 'demote'`: "Demote to {targetTier}" button (amber)
- "Reject" stays as-is

**Files to change:**
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` — add promote/demote button variants

### Issue 4: Verdict text says "Constrain" not "Demote"

`tier-scoring.ts` lines 270-274:
```typescript
case 'constrain':
  actionReason = `Constrain to HIGH — spent $X with zero conversions`
  // or
  actionReason = `Constrain — underperforming in ${currentTier}, move to ${targetTier} for restricted bidding`
```

Should say "Demote" in both cases.

### Issue 5: Button label mismatch in LeakageTermRow

`LeakageTermRow.tsx` line 175: Button text says "Constrain" but the handler is named `handleDemote` (line 82) which is correct. The button label should match: "Demote".

## Execution Plan

Single quick task with 2 sub-tasks:

**Task 1: Rename constrain → demote across codebase**
- Update RecommendedAction type
- Update tier-scoring.ts (determineAction, verdicts)
- Update all tests
- Update ActionQueueRow and LeakageTermRow button labels

**Task 2: Add targetTier to TermScore and fix UI**
- Add targetTier to TermScore type
- Return targetTier from scoreTerm()
- Update TierMovementArrow to use targetTier
- Add Promote/Demote buttons for non-wasted misplaced terms
- Persist targetTier in API route

## How to Verify

Open https://allied-feed-ops.vercel.app/tier-scoring:
1. Action Queue should show a MIX of Promote/Demote/Block actions (not all "Promote")
2. Wasted spend → Block + Demote buttons (not "Constrain")
3. High performer in HIGH → "Promote to MEDIUM/LOW" button
4. Low performer in LOW → "Demote to MEDIUM/HIGH" button
5. Tier movement arrows should show correct direction (not always → LOW)
6. Verdict text says "Demote" not "Constrain"

## Key Reference

Domain doc: `docs/domain/waterfall-shopping-structure.md`
- Section 3A: "Promote" = push DOWN funnel (add negative keyword to current tier)
- Section 3A: "Demote" = pull UP funnel (remove negative from upper tiers)
- Section 3B: "Demote to HIGH" = push wasted spend to constrained tier
