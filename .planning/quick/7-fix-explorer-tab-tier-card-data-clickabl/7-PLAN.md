---
phase: quick-7
plan: 7
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/page.tsx
autonomous: true
requirements: []

must_haves:
  truths:
    - "Explorer tab tier cards show correct term counts and distribution stats (not 'Limited data') when a group has scored terms"
    - "Optimization Opportunities rows in GroupDetail are clickable and navigate to TermScorecard detail view"
    - "Multi-label terms show a Multi-Label Context card on TermScorecard when the same searchTerm appears in 2+ custom_label_0 groups"
    - "Action Queue rows show (N labels) indicator when a term has multiple label entries"
  artifacts:
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx"
      provides: "Fixed tier cards + clickable opportunity rows"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx"
      provides: "Fixed tier card term counts"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx"
      provides: "Multi-Label Context card"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/page.tsx"
      provides: "allScoresForTerm computation + onSwitchLabel wiring"
  key_links:
    - from: "page.tsx"
      to: "TermScorecard.tsx"
      via: "allScoresForTerm prop + onSwitchLabel callback"
      pattern: "allScoresForTerm.*useMemo"
    - from: "ActionQueueTable.tsx"
      to: "ActionQueueRow.tsx"
      via: "labelCount prop"
      pattern: "labelCount"
---

<objective>
Fix Explorer tab tier card data display + clickable Optimization Opportunities rows, and implement Wave 5 Multi-Label UI from the tier intelligence dashboard redesign.

Purpose: Explorer tab currently shows "Limited data (1 terms)" for all tiers despite 215 scored terms (distribution sampleSize is always 1 because it is computed from aggregated per-label-tier rows, not per-term rows). Also, Optimization Opportunities table rows are not clickable. Wave 5 adds multi-label awareness to the detail page and action queue.
Output: Fixed Explorer tab + Multi-Label Context card on TermScorecard + label count indicators on ActionQueueRow.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@dashboard/src/app/(dashboard)/tier-scoring/page.tsx
@dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
@dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
@dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
@dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
@dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
@docs/plans/2026-02-26-tier-intelligence-dashboard-redesign.md (Wave 5 section)

<interfaces>
<!-- Key interfaces the executor needs -->

From tier-scoring.types.ts:
```typescript
interface TermScore {
  searchTerm: string
  customLabel0: string
  currentTier: FunnelTier
  recommendedTier: FunnelTier
  targetTier?: FunnelTier
  isMisplaced: boolean
  tierFitScores: Record<FunnelTier, number>
  confidence: ConfidenceResult
  impact: ImpactRange | null
  totalConversions: number
  totalCostMicros: number
  totalImpressions?: number
  actualRoas: number
  verdict: string
  trigger?: string
  // ... other fields
}

interface GroupDistributions {
  customLabel0: string
  tiers: Record<FunnelTier, TierDistribution>
  boundaries: TierBoundaries
  totalTerms: number
  scoredTerms: number
  insufficientTiers: FunnelTier[]
}
```

From TermScorecard.tsx (current props):
```typescript
interface TermScorecardProps {
  term: TermScore
  onBack: () => void
}
```

From ActionQueueRow.tsx (current props):
```typescript
interface ActionQueueRowProps {
  term: ClassifiedTerm
  onViewDetails: (term: TermScore) => void
  accentClass?: string
  onUndo?: (searchTerm: string, customLabel0: string) => void
  onApprove?: (term: TermScore, options?: ApproveOptions) => void
  onReject?: (term: TermScore) => void
  reviewStatus?: 'pending' | 'accepted' | 'rejected' | 'expired'
}
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix Explorer tab tier cards + clickable Optimization Opportunities</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupDetail.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx
  </files>
  <action>
**ROOT CAUSE:** `computeTierDistributions()` receives aggregated data from `getLabelTierPerformance()` which returns exactly 1 row per (custom_label_0, tier) combo. So `tierDist.sampleSize` is always 1, and every tier ends up in `insufficientTiers` (MIN_SAMPLE_SIZE = 5). The distribution stats (ROAS p50 etc.) ARE usable since they represent the aggregate, but the term count and insufficient flag are wrong.

**Fix GroupDetail.tsx:**

1. Add `onSelectTerm` to the `GroupDetailProps` interface:
```typescript
interface GroupDetailProps {
  group: GroupDistributions
  scores: TermScore[]
  onBack: () => void
  onSelectTier: (tier: FunnelTier) => void
  onSelectTerm: (term: TermScore) => void  // NEW
}
```

2. In the tier cards section (the `TIER_ORDER.map` block around line 112), derive `termCount` from the `scores` prop instead of `tierDist?.sampleSize`:
```typescript
const tierScores = scores.filter(s => s.currentTier === tier)
const termCount = tierScores.length
const isInsufficient = termCount === 0  // Only show "Limited data" when truly no terms
```
This replaces:
```typescript
const isInsufficient = group.insufficientTiers.includes(tier)
const termCount = tierDist?.sampleSize ?? 0
```

3. Make Optimization Opportunities table rows clickable. In the `misplacedTerms.map` block (around line 241), add `onClick`, `cursor-pointer`, and `hover:bg-muted/50` to each `TableRow`:
```tsx
<TableRow
  key={`${term.searchTerm}::${term.customLabel0}`}
  className="cursor-pointer hover:bg-muted/50"
  onClick={() => onSelectTerm(term)}
>
```

**Fix GroupOverview.tsx:**

In the tier grid section (the `TIER_ORDER.map` block around line 136), derive `termCount` from the `scores` prop instead of `tierDist?.sampleSize`. First compute per-group per-tier counts in a useMemo:

In the component body, before `sortedGroups`, the component already has `scores` prop. Inside the `sortedGroups.map` render (around line 136), compute tier term count from filtered scores:
```typescript
const groupScores = scores.filter(s => s.customLabel0 === group.customLabel0)
// Then inside the tier map:
const tierTermCount = groupScores.filter(s => s.currentTier === tier).length
const isInsufficient = tierTermCount === 0
```
Replace `const termCount = tierDist?.sampleSize ?? 0` with `tierTermCount` and `const isInsufficient = group.insufficientTiers.includes(tier)` with the new check.

Note: Computing `groupScores` inside the render loop is fine since it only runs on render (not a hot path). Keep it simple.
  </action>
  <verify>
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit && npm run build
  </verify>
  <done>Explorer tab tier cards show actual scored term counts (derived from scores array). "Limited data" only shows when a tier truly has 0 scored terms. Optimization Opportunities rows are clickable and navigate to TermScorecard detail view.</done>
</task>

<task type="auto">
  <name>Task 2: Wire onSelectTerm in page.tsx + implement Wave 5 Multi-Label UI</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/page.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
  </files>
  <action>
**Part A: Wire onSelectTerm into GroupDetail in page.tsx**

In the Explorer tab section of page.tsx (around line 218), pass `onSelectTerm` to `GroupDetail`:
```tsx
<GroupDetail
  group={data.distributions[selectedGroup]}
  scores={data.scores.filter(s => s.customLabel0 === selectedGroup)}
  onBack={() => {
    setSelectedGroup(null)
    setSelectedTier(null)
    setSelectedTerm(null)
  }}
  onSelectTier={(tier) => setSelectedTier(tier)}
  onSelectTerm={(term) => setSelectedTerm(term)}  // NEW
/>
```

**Part B: Compute allScoresForTerm in page.tsx**

Add a `useMemo` after the existing `actionSelectedTerm` state (around line 45):
```typescript
const allScoresForTerm = useMemo(() => {
  if (!data) return []
  const currentTerm = actionSelectedTerm || selectedTerm
  if (!currentTerm) return []
  return data.scores.filter(s => s.searchTerm === currentTerm.searchTerm)
}, [actionSelectedTerm, selectedTerm, data])
```

Pass `allScoresForTerm` and `onSwitchLabel` to both TermScorecard instances:

Action Queue tab (around line 167):
```tsx
<TermScorecard
  term={actionSelectedTerm}
  allScoresForTerm={allScoresForTerm}
  onBack={() => setActionSelectedTerm(null)}
  onSwitchLabel={(term) => setActionSelectedTerm(term)}
/>
```

Explorer tab (around line 201):
```tsx
<TermScorecard
  term={selectedTerm}
  allScoresForTerm={allScoresForTerm}
  onBack={() => setSelectedTerm(null)}
  onSwitchLabel={(term) => setSelectedTerm(term)}
/>
```

**Part C: Add Multi-Label Context card to TermScorecard.tsx**

1. Update the `TermScorecardProps` interface:
```typescript
interface TermScorecardProps {
  term: TermScore
  allScoresForTerm?: TermScore[]
  onBack: () => void
  onSwitchLabel?: (term: TermScore) => void
}
```

2. Update the component signature to destructure the new props:
```typescript
export function TermScorecard({ term, allScoresForTerm, onBack, onSwitchLabel }: TermScorecardProps)
```

3. Add a Multi-Label Context card between the Decision Reasoning card and the Peer Context section (after the closing of the Decision Reasoning Card around line 534, before the peer context `{term.peerContext && ...}` block).

Only render when `allScoresForTerm` has more than 1 entry:
```tsx
{allScoresForTerm && allScoresForTerm.length > 1 && (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-base">Multi-Label Context</CardTitle>
    </CardHeader>
    <CardContent className="space-y-2">
      <p className="text-sm text-muted-foreground">
        This term appears in {allScoresForTerm.length} product groups:
      </p>
      <div className="space-y-2">
        {allScoresForTerm.map(score => {
          const isCurrentView = score.customLabel0 === term.customLabel0
          const destination = score.targetTier ?? score.recommendedTier
          const hasMovement = destination !== score.currentTier
          return (
            <div
              key={score.customLabel0}
              className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-sm ${
                isCurrentView ? 'border-primary bg-primary/5' : 'hover:bg-muted/50 cursor-pointer'
              }`}
              onClick={() => {
                if (!isCurrentView && onSwitchLabel) onSwitchLabel(score)
              }}
            >
              <span className="font-medium min-w-[120px]">{score.customLabel0}</span>
              {hasMovement ? (
                <span className="flex items-center gap-1.5 text-xs">
                  <span className={tierTextColor[score.currentTier]}>{score.currentTier}</span>
                  <span className="text-muted-foreground">&rarr;</span>
                  <span className={tierTextColor[destination]}>{destination}</span>
                </span>
              ) : (
                <span className="text-xs text-green-700">Aligned in {score.currentTier}</span>
              )}
              {score.trigger && score.trigger !== 'observe' && (
                <span className="text-xs text-muted-foreground">
                  ({score.trigger === 'wasted_spend' ? 'Wasted Spend' :
                    score.trigger === 'demote_underperform' ? 'Demote' :
                    score.trigger === 'promote_conversion' ? 'Conversion-Proven' :
                    score.trigger === 'promote_intent' ? 'Intent-Proven' :
                    score.trigger === 'under_invested' ? 'Under-Invested' : score.trigger})
                </span>
              )}
              <span className="ml-auto text-xs">
                {isCurrentView ? (
                  <span className="text-primary font-medium">Currently viewing</span>
                ) : (
                  <span className="text-primary hover:underline">View this label</span>
                )}
              </span>
            </div>
          )
        })}
      </div>
    </CardContent>
  </Card>
)}
```

Note: `tierTextColor` is already defined in TermScorecard.tsx (line 37-41).

**Part D: Add (N labels) indicator to ActionQueueRow.tsx**

1. Add `labelCount` to `ActionQueueRowProps`:
```typescript
interface ActionQueueRowProps {
  term: ClassifiedTerm
  onViewDetails: (term: TermScore) => void
  accentClass?: string
  labelCount?: number  // NEW
  onUndo?: (searchTerm: string, customLabel0: string) => void
  onApprove?: (term: TermScore, options?: ApproveOptions) => void
  onReject?: (term: TermScore) => void
  reviewStatus?: 'pending' | 'accepted' | 'rejected' | 'expired'
}
```

2. Destructure `labelCount` in the component and add indicator after the term name (around line 68, after `{term.searchTerm}` span):
```tsx
<span className="font-medium truncate">{term.searchTerm}</span>
{labelCount && labelCount > 1 && (
  <span className="text-xs text-muted-foreground shrink-0">({labelCount} labels)</span>
)}
```

**Part E: Compute labelCount in ActionQueueTable.tsx**

In ActionQueueTable.tsx, add a `useMemo` to compute label counts per searchTerm:
```typescript
const labelCounts = useMemo(() => {
  const counts = new Map<string, number>()
  for (const term of terms) {
    counts.set(term.searchTerm, (counts.get(term.searchTerm) ?? 0) + 1)
  }
  return counts
}, [terms])
```

Then pass `labelCount` to each `ActionQueueRow` (around line 127):
```tsx
<ActionQueueRow
  key={key}
  term={term}
  accentClass={ACCENT_CLASSES[group.key]}
  labelCount={labelCounts.get(term.searchTerm) ?? 1}
  onViewDetails={onSelectTerm}
  onUndo={onUndo}
  onApprove={onApprove}
  onReject={onReject}
  reviewStatus={status?.status ?? 'pending'}
/>
```
  </action>
  <verify>
cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit && npm run build && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts
  </verify>
  <done>
- page.tsx passes onSelectTerm to GroupDetail (Explorer tab clickable opportunities work end-to-end)
- allScoresForTerm computed and passed to TermScorecard in both Action Queue and Explorer tabs
- Multi-Label Context card renders between Decision Reasoning and Peer Context when term has 2+ label entries; clicking "View this label" switches the active score
- ActionQueueRow shows "(N labels)" indicator when labelCount > 1
- All 77+ existing tests pass, build succeeds
  </done>
</task>

</tasks>

<verification>
1. `cd dashboard && npm run build` -- MUST pass with zero errors
2. `cd dashboard && npx tsc --noEmit` -- zero type errors
3. `cd dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` -- all 77+ tests pass
4. `cd dashboard && npm run lint` -- fix any lint issues
</verification>

<success_criteria>
- Explorer tab: clicking into a group shows correct term counts per tier (not "Limited data" when terms exist)
- Explorer tab: Optimization Opportunities rows are clickable and navigate to TermScorecard
- TermScorecard: Multi-Label Context card appears for terms with 2+ label entries
- TermScorecard: "View this label" switches to that label's score
- Action Queue: rows show "(N labels)" for multi-label terms
- Build passes, all existing tests pass
</success_criteria>

<output>
After completion, create `.planning/quick/7-fix-explorer-tab-tier-card-data-clickabl/7-SUMMARY.md`
</output>
