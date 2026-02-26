---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
autonomous: true
requirements: [TIER-REDESIGN-WAVE1]

must_haves:
  truths:
    - "A search term appearing in 2+ custom_label_0 funnels produces 2+ TermScore objects"
    - "Each TermScore has the correct customLabel0 matching its funnel assignment"
    - "Existing single-funnel terms still produce exactly 1 TermScore each"
    - "All 77+ existing tier-scoring tests still pass"
  artifacts:
    - path: "dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts"
      provides: "Multi-label scoring loop"
      contains: "for (const funnel of term.funnels)"
  key_links:
    - from: "route.ts scoring loop"
      to: "scoreTerm()"
      via: "shallow copy with target funnel at index 0"
      pattern: "funnels: \\[funnel"
---

<objective>
Replace the single-funnel scoring loop in tier-scoring route.ts with a multi-label loop that scores each term once per custom_label_0 funnel assignment.

Purpose: A keyword like "grab bar" can appear in multiple custom_label_0 product groups (e.g., "grab bars" and "bathroom accessories") at different tiers. Currently only funnels[0] is scored, making multi-label keywords invisible.

Output: Updated route.ts where multi-label terms produce multiple TermScore objects (one per funnel).
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/plans/2026-02-26-tier-intelligence-dashboard-redesign.md (Change 3: Multi-Label Keywords section)
@dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Replace single-funnel scoring loop with multi-label loop</name>
  <files>dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts</files>
  <action>
Replace lines 167-190 (the scoring loop) with the multi-label version from the redesign plan.

Current code (lines 168-190) iterates `existingTermsResult.terms` and only uses `term.funnels[0]`. Replace with a nested loop that iterates ALL funnels per term.

New scoring loop:
```typescript
const scores: TermScore[] = []
for (const term of existingTermsResult.terms) {
  if (!term.funnels.length) continue

  const intentFeatures = decomposeSearchTerm(term.search_term)
  const feedScore = feedAlignmentMap.get(term.search_term)

  // Score once per custom_label_0 funnel assignment
  for (const funnel of term.funnels) {
    const currentTier = mapTierToFunnelTier(funnel.tier)
    if (!currentTier) continue

    const groupKey = funnel.custom_label_0
    const groupDist = distributions.get(groupKey)
    if (!groupDist) continue

    // scoreTerm reads funnels[0] internally — shallow copy with this funnel first
    const termForThisFunnel = {
      ...term,
      funnels: [funnel, ...term.funnels.filter(f => f !== funnel)],
    }

    const scored = scoreTerm(termForThisFunnel, groupDist, globalFallbackDists, intentFeatures, DEFAULT_CALIBRATION, feedScore, AVG_CPA)
    scores.push(scored)
  }
}
```

Key points:
- `intentFeatures` and `feedScore` are computed ONCE per term (outside inner loop) since they depend on search_term, not funnel
- The shallow copy `termForThisFunnel` puts the target funnel at index 0 so `scoreTerm()` reads the correct tier and customLabel0 without any changes to the scoring engine
- The `filter(f => f !== funnel)` uses reference equality which is correct since funnels are objects from the same array
- Do NOT modify `scoreTerm()` or any other function — only the loop in route.ts
- The rest of route.ts (aggregateImpact, DB upsert with onConflict composite key, search candidates, hero callout) all work correctly with multiple TermScores per search term
  </action>
  <verify>
```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts 2>&1 | tail -5
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build 2>&1 | tail -10
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit 2>&1 | tail -5
```
  </verify>
  <done>
- The scoring loop iterates all funnels per term (not just funnels[0])
- All 77+ existing tier-scoring tests pass (scoring engine unchanged)
- npm run build passes with zero errors
- tsc --noEmit passes with zero errors
  </done>
</task>

</tasks>

<verification>
1. `cd dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` — 77+ tests pass
2. `cd dashboard && npm run build` — zero errors
3. `cd dashboard && npx tsc --noEmit` — zero errors
4. `cd dashboard && npm run lint` — no new issues
5. Grep for `funnels[0]` in route.ts — should NOT appear in the scoring loop (only in scoreTerm which is untouched)
</verification>

<success_criteria>
- route.ts scoring loop uses nested `for (const funnel of term.funnels)` pattern
- A term with N funnels produces N TermScore objects with distinct customLabel0 values
- Zero test regressions — all 77+ tier-scoring tests pass
- Build and type check pass
</success_criteria>

<output>
After completion, create `.planning/quick/4-implement-wave-1-of-tier-intelligence-da/4-SUMMARY.md`
</output>
