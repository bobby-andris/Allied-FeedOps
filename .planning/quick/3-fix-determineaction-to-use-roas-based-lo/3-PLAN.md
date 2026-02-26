---
phase: quick-3
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/lib/optimization/tier-scoring.ts
  - dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts
autonomous: true
requirements: [QUICK-3]

must_haves:
  truths:
    - "Underperforming terms (ROAS below current tier p25) get 'constrain' action, not 'promote'"
    - "High-performing terms (ROAS above current tier p75) get 'promote' action"
    - "estimateImpact uses the correct target tier matching the action direction"
    - "Verdict text references the correct target tier, not recommendedTier"
    - "Existing wasted spend logic unchanged (block for HIGH, constrain for MEDIUM/LOW)"
  artifacts:
    - path: "dashboard/src/lib/optimization/tier-scoring.ts"
      provides: "Fixed determineAction with ROAS-based logic"
    - path: "dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts"
      provides: "Tests proving ROAS-based action determination"
  key_links:
    - from: "determineAction()"
      to: "scoreTerm()"
      via: "returns {action, targetTier} used for impact and verdict"
      pattern: "determineAction.*currentTierDist"
---

<objective>
Fix three interconnected bugs in determineAction() where the scoring engine uses statistical best-fit tier (recommendedTier) instead of ROAS-based logic to decide promote vs constrain. This causes ALL underperforming terms to get 'promote' (move to aggressive bidding) instead of 'constrain' (restrict bidding), because low-ROAS terms statistically fit LOW tier's distribution.

Purpose: Correct the action recommendation so underperformers get constrained and high-performers get promoted.
Output: Updated tier-scoring.ts with ROAS-based determineAction, updated tests.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@dashboard/src/lib/optimization/tier-scoring.ts
@dashboard/src/lib/optimization/tier-scoring.types.ts
@dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts
@.planning/phases/34.1-fix-decision-logic/34.1-RESEARCH.md

<interfaces>
From tier-scoring.types.ts:
```typescript
export type RecommendedAction = 'promote' | 'constrain' | 'block' | 'observe'

export interface TierDistribution {
  tier: FunnelTier
  metrics: {
    roas: MetricDistribution  // has p25, p50, p75
    cvr: MetricDistribution
    cpc: MetricDistribution
    ctr: MetricDistribution
  }
  sampleSize: number
  fallbackLevel: FallbackLevel
}
```

From tier-scoring.ts (current determineAction signature, line 484):
```typescript
function determineAction(
  currentTier: FunnelTier,
  recommendedTier: FunnelTier,
  totalConversions: number,
  totalCostMicros: number,
  isMisplaced: boolean
): RecommendedAction
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Rewrite determineAction to use ROAS percentiles and update scoreTerm to use returned targetTier</name>
  <files>dashboard/src/lib/optimization/tier-scoring.ts</files>
  <action>
Three changes to tier-scoring.ts:

**1. Rewrite determineAction() (line 484-510):**

Change signature to accept currentTierDist and termRoas, return `{ action: RecommendedAction, targetTier: FunnelTier }`:

```typescript
function determineAction(
  currentTier: FunnelTier,
  currentTierDist: TierDistribution,
  termRoas: number,
  totalConversions: number,
  totalCostMicros: number,
  isMisplaced: boolean
): { action: RecommendedAction; targetTier: FunnelTier } {
  const costDollars = totalCostMicros / 1_000_000
  const TIER_UP: Record<FunnelTier, FunnelTier> = { HIGH: 'HIGH', MEDIUM: 'HIGH', LOW: 'MEDIUM' }
  const TIER_DOWN: Record<FunnelTier, FunnelTier> = { HIGH: 'MEDIUM', MEDIUM: 'LOW', LOW: 'LOW' }

  // 1. Wasted spend: zero conversions + meaningful spend (unchanged)
  if (totalConversions === 0 && costDollars > 5) {
    if (currentTier === 'HIGH') return { action: 'block', targetTier: 'HIGH' }
    return { action: 'constrain', targetTier: 'HIGH' }
  }

  // 2. Not flagged as misplaced by calibration gates — observe
  if (!isMisplaced) return { action: 'observe', targetTier: currentTier }

  // 3. ROAS-based action: compare term ROAS against current tier's distribution
  const p25 = currentTierDist.metrics.roas.p25
  const p75 = currentTierDist.metrics.roas.p75

  // Underperformer: ROAS below current tier's p25 — constrain (move UP toward HIGH)
  if (termRoas < p25 && currentTier !== 'HIGH') {
    return { action: 'constrain', targetTier: TIER_UP[currentTier] }
  }

  // High performer: ROAS above current tier's p75 — promote (move DOWN toward LOW)
  if (termRoas > p75 && currentTier !== 'LOW') {
    return { action: 'promote', targetTier: TIER_DOWN[currentTier] }
  }

  // Within IQR or at boundary tier — observe
  return { action: 'observe', targetTier: currentTier }
}
```

**2. Update scoreTerm() call site (around line 252):**

Change the call to pass currentTierDist and termRoas:
```typescript
const currentTierDist = chooseDist(currentTier)
const { action: recommendedAction, targetTier } = determineAction(
  currentTier, currentTierDist, termRoas, term.total_conversions, term.total_cost_micros, isMisplaced
)
```

**3. Update estimateImpact call (line 258) and verdict text (lines 263-281):**

Use `targetTier` instead of `recommendedTier` for both:

For impact:
```typescript
if (isMisplaced || isWastedSpend) {
  impact = estimateImpact(term, chooseDist(currentTier), chooseDist(targetTier), config)
}
```

For verdict text, replace `recommendedTier` references with `targetTier`:
- Line 271: `move to ${targetTier}` instead of `move to ${recommendedTier}`
- Line 275: `Promote to ${targetTier}` instead of `Promote to ${recommendedTier}`

Keep the `recommendedTier` field on the returned TermScore as-is (it still comes from statistical fit and is used elsewhere for display). The key change is that `recommendedAction`, impact, and verdict now use `targetTier` from ROAS-based logic instead of `recommendedTier` from statistical fit.
  </action>
  <verify>
    <automated>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts --reporter=verbose 2>&1 | tail -30</automated>
  </verify>
  <done>determineAction uses ROAS percentiles (p25/p75) to decide promote vs constrain. estimateImpact and verdict text reference the correct targetTier from the action, not recommendedTier from statistical fit. All existing tests still pass.</done>
</task>

<task type="auto">
  <name>Task 2: Add targeted tests for ROAS-based action determination</name>
  <files>dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts</files>
  <action>
Add a new describe block `'ROAS-based determineAction logic'` to tier-scoring.test.ts with these tests:

**Test 1: "underperformer in MEDIUM gets constrain, not promote"**
- Create a term in MEDIUM tier with ROAS well below MEDIUM's p25 (e.g., ROAS 0.5 when MEDIUM p25 is ~2.5)
- Use `makeNormalDistribution()` for distributions
- Set sufficient impressions/clicks/conversions for isMisplaced to trigger
- Assert `score.recommendedAction === 'constrain'`
- Assert verdict contains "Constrain" (not "Promote")

**Test 2: "high performer in HIGH gets promote, not observe"**
- Create a term in HIGH tier with ROAS well above HIGH's p75 (e.g., ROAS 12.0 when HIGH p75 is ~7.0)
- Use sufficient data for isMisplaced gates to pass
- Assert `score.recommendedAction === 'promote'`

**Test 3: "underperformer in LOW gets constrain toward MEDIUM"**
- Term in LOW with ROAS below LOW's p25
- Assert `score.recommendedAction === 'constrain'`
- Assert verdict references MEDIUM (the target), not LOW

**Test 4: "term within IQR gets observe even if recommendedTier differs"**
- Term in MEDIUM with ROAS between MEDIUM p25 and p75 (e.g., 3.0)
- Even if fit score says HIGH is a better statistical match, action should be 'observe' because ROAS is within the healthy range
- Assert `score.recommendedAction === 'observe'`

**Test 5: "impact uses correct target tier for constrain action"**
- Underperforming MEDIUM term that gets 'constrain' action
- Verify `score.impact` is computed using HIGH tier distribution (the target), not the recommendedTier from statistical fit
- The impact direction should be 'upward' (moving toward HIGH)

**Test 6: "wasted spend logic unchanged by ROAS-based refactor"**
- Verify existing wasted spend tests still describe correct behavior: block for HIGH, constrain for MEDIUM/LOW
- This test documents that the wasted spend path is untouched by the ROAS-based changes

Use the existing `makeNormalDistribution()` and `makeTermWithFunnels()` fixtures. Reference the distribution values from the fixture:
- HIGH ROAS: [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 8.0] — p25~4.625, p75~6.625
- MEDIUM ROAS: [2.0, 2.5, 2.8, 3.0, 3.2, 3.5, 3.8, 4.0] — p25~2.575, p75~3.575
- LOW ROAS: [0.5, 0.8, 1.0, 1.2, 1.5, 1.7, 1.8, 2.0] — p25~0.85, p75~1.775
  </action>
  <verify>
    <automated>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts --reporter=verbose 2>&1 | tail -40</automated>
  </verify>
  <done>New test block "ROAS-based determineAction logic" passes with 6 tests proving: underperformers get constrain (not promote), high performers get promote, within-IQR terms get observe, impact uses correct target tier, and wasted spend path is unchanged.</done>
</task>

</tasks>

<verification>
```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts --reporter=verbose
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit 2>&1 | head -20
```
All existing + new tests pass. TypeScript compiles with zero errors.
</verification>

<success_criteria>
- determineAction() uses currentTierDist.metrics.roas.p25/p75 to decide promote vs constrain
- Underperforming terms (ROAS < p25) get 'constrain', not 'promote'
- High-performing terms (ROAS > p75) get 'promote'
- estimateImpact() receives the correct target tier from the action, not recommendedTier
- Verdict text references the correct target tier
- All existing tests pass (no regressions)
- 6 new tests prove the ROAS-based logic
</success_criteria>

<output>
After completion, create `.planning/quick/3-fix-determineaction-to-use-roas-based-lo/3-SUMMARY.md`
</output>
