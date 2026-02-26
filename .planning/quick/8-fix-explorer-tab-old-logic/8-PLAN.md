---
phase: quick-8
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/TierDetail.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/LabelProfitabilitySummary.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/lib/plain-verdict.ts
  - dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
autonomous: true
requirements: [QUICK-8]
must_haves:
  truths:
    - "Explorer tab GroupDetail Optimization Opportunities table shows same terms and actions as Action Queue for that group"
    - "GroupOverview opportunity counts per group match Action Queue counts per group"
    - "TierDetail status column uses trigger-based targetTier, not old recommendedTier"
    - "HeroCallout totalMisplaced count is trigger-only (no legacy isMisplaced padding)"
    - "LabelProfitabilitySummary opportunity counts are trigger-based"
  artifacts:
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx"
      provides: "Trigger-based opportunity filtering and targetTier display"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/TierDetail.tsx"
      provides: "Trigger-based misplaced filtering and sorting"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx"
      provides: "Trigger-based opportunity counts per group card"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/LabelProfitabilitySummary.tsx"
      provides: "Trigger-based opportunity counting"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/lib/plain-verdict.ts"
      provides: "Trigger-aware verdict text generation"
    - path: "dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts"
      provides: "Trigger-only totalMisplaced count"
  key_links:
    - from: "GroupDetail.tsx"
      to: "reason-codes.ts"
      via: "import classifyAllTerms"
      pattern: "classifyAllTerms\\(scores\\)"
    - from: "GroupOverview.tsx"
      to: "reason-codes.ts"
      via: "import classifyAllTerms"
      pattern: "classifyAllTerms\\(groupScores\\)"
---

<objective>
Replace all Phase 33 legacy `isMisplaced` + `recommendedTier` logic in Explorer tab components with the Phase 34.2 trigger system (`trigger`, `targetTier`, `classifyAllTerms`). The Action Queue tab already uses the correct logic; the Explorer tab still shows old statistical best-fit recommendations that contradict the Action Queue.

Purpose: Explorer tab currently shows 26 terms all recommended HIGH->LOW (old statistical logic), while Action Queue correctly shows the same terms as wasted spend needing demotion to HIGH. This confuses the user.

Output: All Explorer tab components use the same trigger-based classification as the Action Queue.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts
@dashboard/src/app/(dashboard)/tier-scoring/page.tsx
@.planning/quick/7-fix-explorer-tab-tier-card-data-clickabl/.continue-here.md

<interfaces>
<!-- Key types and contracts the executor needs -->

From reason-codes.ts:
```typescript
export function classifyAllTerms(terms: TermScore[], keywordDataMap?: Map<string, KeywordData>): ClassifiedTerm[]
// Returns terms that are isMisplaced OR have actionable trigger. Sorted by impact desc.
// ClassifiedTerm extends TermScore with { reasonCode, reasonLabel }
```

From tier-scoring.types.ts (relevant fields on TermScore):
```typescript
isMisplaced: boolean          // OLD: statistical best-fit says different tier
recommendedTier: FunnelTier   // OLD: statistical best-fit tier
trigger?: string              // NEW: 'wasted_spend' | 'demote_underperform' | 'promote_conversion' | 'promote_intent' | 'under_invested' | 'observe'
targetTier?: FunnelTier       // NEW: the tier determineAction wants to move to
recommendedAction?: RecommendedAction  // NEW: 'block' | 'promote' | 'demote' | 'observe'
```

The correct pattern is already in page.tsx:
```typescript
const classifiedTerms = classifyAllTerms(data.scores)
const actionableTerms = classifiedTerms.filter(t => t.trigger && t.trigger !== 'observe')
```

Trigger display mapping:
- wasted_spend -> "Block" or "Demote" (red)
- demote_underperform -> "Demote" (amber)
- promote_conversion -> "Promote" (green)
- promote_intent -> "Promote" (blue)
- under_invested -> "Increase Budget" (blue)
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix GroupDetail, GroupOverview, and LabelProfitabilitySummary to use trigger system</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/LabelProfitabilitySummary.tsx
  </files>
  <action>
**GroupDetail.tsx:**
1. Import `classifyAllTerms` from `'../lib/reason-codes'`
2. Replace line 45-47 `scores.filter(s => s.isMisplaced)` with:
   ```typescript
   const actionableTerms = useMemo(() => {
     const classified = classifyAllTerms(scores)
     return classified.filter(t => t.trigger && t.trigger !== 'observe')
   }, [scores])
   ```
3. Replace all references to `misplacedTerms` with `actionableTerms` throughout the component (callout, count, table rendering)
4. In the Optimization Opportunities table (line 260-262), change the "Recommended" column to show `term.targetTier ?? term.recommendedTier` instead of `term.recommendedTier`
5. Add a "Trigger" column to the table between "Current" and "Recommended" that shows the trigger type with color coding:
   - wasted_spend: red badge "Block" or "Demote"
   - demote_underperform: amber badge "Demote"
   - promote_conversion: green badge "Promote"
   - promote_intent: blue badge "Promote"
   - under_invested: blue badge "Budget"
   Use a small inline helper function `getTriggerBadge(trigger: string)` returning JSX.
6. Update callout text to reference trigger-based count, not old misplaced count.

**GroupOverview.tsx:**
1. Import `classifyAllTerms` from `'../lib/reason-codes'`
2. Replace line 37 `groupScores.filter(s => s.isMisplaced)` with:
   ```typescript
   const classified = classifyAllTerms(groupScores)
   const actionable = classified.filter(t => t.trigger && t.trigger !== 'observe')
   ```
3. Use `actionable.length` for `misplacedCount` and `actionable.reduce(...)` for `misplacedImpact`
4. All downstream references to `misplacedCount`/`misplacedImpact` (lines 39, 43-44, 54, 62-64, 72, 106-108, 174-175) will automatically pick up the correct values since they derive from the GroupSummary object.

**LabelProfitabilitySummary.tsx:**
1. Import `classifyAllTerms` from `'../lib/reason-codes'`
2. Replace lines 30-37 (the `for` loop using `score.isMisplaced`) with:
   ```typescript
   const opportunityCounts = useMemo(() => {
     const map = new Map<string, number>()
     const classified = classifyAllTerms(scores)
     const actionable = classified.filter(t => t.trigger && t.trigger !== 'observe')
     for (const term of actionable) {
       map.set(term.customLabel0, (map.get(term.customLabel0) ?? 0) + 1)
     }
     return map
   }, [scores])
   ```
   Note: wrap in useMemo since it was previously computed inline during render (not memoized). Import `useMemo` from react.
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit 2>&1 | head -30</verify>
  <done>GroupDetail shows trigger-based opportunities with targetTier and trigger badge column. GroupOverview cards show trigger-based opportunity counts. LabelProfitabilitySummary counts use trigger system. Zero TypeScript errors.</done>
</task>

<task type="auto">
  <name>Task 2: Fix TierDetail, plain-verdict, and API route totalMisplaced</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/TierDetail.tsx
    dashboard/src/app/(dashboard)/tier-scoring/lib/plain-verdict.ts
    dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
  </files>
  <action>
**TierDetail.tsx:**
1. Import `classifyAllTerms` from `'../lib/reason-codes'`
2. Replace line 51-53 `scores.filter(s => s.isMisplaced)` with:
   ```typescript
   const actionableTerms = useMemo(() => {
     const classified = classifyAllTerms(scores)
     return classified.filter(t => t.trigger && t.trigger !== 'observe')
   }, [scores])
   ```
3. Replace all `misplacedTerms` references with `actionableTerms`
4. Line 70: callout text — change `topTerm.recommendedTier` to `topTerm.targetTier ?? topTerm.recommendedTier`
5. Line 84 sort: change `tierFitScores[a.recommendedTier]` to use `targetTier ?? recommendedTier` as key
6. Lines 97-98 sort by status: replace `a.isMisplaced !== b.isMisplaced` with check for whether term has an actionable trigger:
   ```typescript
   const aActionable = !!(a.trigger && a.trigger !== 'observe')
   const bActionable = !!(b.trigger && b.trigger !== 'observe')
   if (aActionable !== bActionable) {
     cmp = aActionable ? 1 : -1
   }
   ```
7. Lines 235-239: status column display — change `term.isMisplaced` check and `term.recommendedTier` display:
   - Check: `term.trigger && term.trigger !== 'observe'` instead of `term.isMisplaced`
   - Show: `term.targetTier ?? term.recommendedTier` instead of `term.recommendedTier`

**plain-verdict.ts:**
1. Update `generatePlainVerdict()`:
   - Before the existing `if (!term.isMisplaced)` check, add a trigger-aware path:
   ```typescript
   // Trigger-based verdicts take priority
   if (term.trigger && term.trigger !== 'observe') {
     const target = term.targetTier ?? term.recommendedTier
     const targetName = tierLabel[target]
     switch (term.trigger) {
       case 'wasted_spend':
         return `Wasting money — zero conversions with significant spend. ${target === 'HIGH' ? 'Block or restrict' : 'Demote'} to ${targetName}`
       case 'demote_underperform':
         return `Underperforming in current tier — demote to ${targetName} to restrict bidding`
       case 'promote_conversion':
         return `Converting well — promote to ${targetName} for more aggressive bidding`
       case 'promote_intent':
         return `High intent signal but no conversions yet — promote to ${targetName} to test with aggressive bidding`
       case 'under_invested':
         return `Impression gap detected — increase budget or promote to ${targetName}`
     }
   }
   ```
   - Keep the existing `isMisplaced` / `!isMisplaced` logic as fallback for terms without triggers.

2. Update `generateShortVerdict()` similarly:
   - Add trigger-aware path before the `if (!term.isMisplaced)` check:
   ```typescript
   if (term.trigger && term.trigger !== 'observe') {
     const target = term.targetTier ?? term.recommendedTier
     switch (term.trigger) {
       case 'wasted_spend': return `Wasted spend — ${target}`
       case 'demote_underperform': return `Underperforming — demote to ${target}`
       case 'promote_conversion': return `Converting — promote to ${target}`
       case 'promote_intent': return `High intent — promote to ${target}`
       case 'under_invested': return `Under-invested — ${target}`
     }
   }
   ```

**API route (route.ts line 303):**
Change `totalMisplaced` computation from:
```typescript
totalMisplaced: scores.filter(s => s.isMisplaced || (s.trigger && s.trigger !== 'observe')).length,
```
To trigger-only (no legacy `isMisplaced` inflation):
```typescript
totalMisplaced: scores.filter(s => s.trigger && s.trigger !== 'observe').length,
```
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit 2>&1 | head -30 && npm run lint -- --max-warnings=0 2>&1 | tail -10</verify>
  <done>TierDetail uses trigger-based filtering and shows targetTier. plain-verdict.ts generates trigger-aware verdicts. API route totalMisplaced is trigger-only. Zero TypeScript errors, lint passes.</done>
</task>

<task type="auto">
  <name>Task 3: Build verification and cleanup</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/TierDetail.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/LabelProfitabilitySummary.tsx
    dashboard/src/app/(dashboard)/tier-scoring/lib/plain-verdict.ts
    dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts
  </files>
  <action>
1. Run `cd dashboard && npm run build` — fix any errors.
2. Grep all 6 modified files for any remaining bare `isMisplaced` references that should have been replaced with trigger logic. Specifically:
   - `s.isMisplaced` as a filter condition (should be trigger-based)
   - `term.recommendedTier` without `targetTier ??` fallback (should use `targetTier ?? recommendedTier`)
   Note: `isMisplaced` may still appear in type definitions and the fallback path of plain-verdict.ts — those are acceptable.
3. Verify no unused imports were left behind (e.g., if `isMisplaced` was the only reason for an import).
4. Run `npm run lint` on the changed files and fix any issues.
5. Confirm `npm run build` passes clean.
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build 2>&1 | tail -5</verify>
  <done>Full build passes. No stale isMisplaced filter logic remains in Explorer tab components. All 6 files use trigger system consistently.</done>
</task>

</tasks>

<verification>
1. `cd dashboard && npm run build` passes with zero errors
2. `npx tsc --noEmit` passes with zero errors
3. `npm run lint` passes
4. Grep confirms no bare `s.isMisplaced` filters remain in GroupDetail, TierDetail, GroupOverview, LabelProfitabilitySummary
5. Grep confirms `targetTier ?? recommendedTier` pattern used everywhere tier destination is displayed
</verification>

<success_criteria>
- GroupDetail Optimization Opportunities table uses classifyAllTerms + trigger filter, shows targetTier and trigger badge
- GroupOverview group cards show trigger-based opportunity counts (not isMisplaced counts)
- TierDetail status column and sort use trigger system
- LabelProfitabilitySummary counts use trigger-based classification
- plain-verdict.ts generates trigger-aware verdict text with fallback to old logic
- API route totalMisplaced is trigger-only (no isMisplaced inflation)
- Full dashboard build passes
</success_criteria>

<output>
After completion, create `.planning/quick/8-fix-explorer-tab-old-logic/8-SUMMARY.md`
</output>
