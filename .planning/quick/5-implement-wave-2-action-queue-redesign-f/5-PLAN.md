---
phase: quick-5
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts
  - dashboard/src/app/(dashboard)/tier-scoring/components/ActionGroupHeader.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
  - dashboard/src/app/(dashboard)/tier-scoring/page.tsx
autonomous: true
requirements: [WAVE-2]
must_haves:
  truths:
    - "Action queue groups terms into 3 collapsible sections: Stop Wasting Money (red), Restrict Bidding (amber), Bid More Aggressively (green)"
    - "Each group header shows term count, total impact range, and Approve All High-Confidence batch button"
    - "Each row is simplified: term name, actionReason text, tier arrow, impact, and action buttons only (no ConfidenceBadge, ReasonBadge, Intent badge, trigger badges)"
    - "Groups show top 10 by default with Show all N expander"
    - "Within each group, terms sort by impact.mid desc then confidence.score desc"
  artifacts:
    - path: "dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts"
      provides: "groupActionableTerms() function + ActionGroup types"
      exports: ["ActionGroup", "ActionGroupData", "groupActionableTerms"]
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/ActionGroupHeader.tsx"
      provides: "Collapsible group header with batch approve"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx"
      provides: "Grouped layout using ActionGroupHeader + ActionQueueRow"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx"
      provides: "Simplified row without badge clutter"
  key_links:
    - from: "ActionQueueTable.tsx"
      to: "reason-codes.ts"
      via: "groupActionableTerms(terms)"
      pattern: "groupActionableTerms"
    - from: "ActionQueueTable.tsx"
      to: "ActionGroupHeader.tsx"
      via: "renders per group"
      pattern: "ActionGroupHeader"
---

<objective>
Implement Wave 2 of the tier-intelligence-dashboard-redesign: replace the flat action queue with a grouped layout organized by action type (Stop Wasting Money / Restrict Bidding / Bid More Aggressively). Simplify rows by removing badge clutter. Add collapsible group headers with batch approve.

Purpose: The current action queue is a wall of noise with 4-5 badges per row. Grouping by action type creates information hierarchy — users see the most urgent actions (wasted spend) first, with clean rows showing only what matters.

Output: Redesigned Action Queue tab with 3 collapsible groups, simplified rows, and batch approve per group.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/plans/2026-02-26-tier-intelligence-dashboard-redesign.md (THE design doc — Change 1 section)

<interfaces>
<!-- Key types the executor needs -->

From dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts:
```typescript
export type ReasonCode = 'misplaced' | 'wasted_spend' | 'under_invested'
export interface ClassifiedTerm extends TermScore {
  reasonCode: ReasonCode
  reasonLabel: string
}
export function classifyAllTerms(terms: TermScore[], keywordDataMap?: Map<string, KeywordData>): ClassifiedTerm[]
```

From dashboard/src/lib/optimization/tier-scoring.types.ts (relevant TermScore fields):
```typescript
interface TermScore {
  searchTerm: string
  customLabel0: string
  currentTier: FunnelTier           // 'HIGH' | 'MEDIUM' | 'LOW'
  targetTier?: FunnelTier
  confidence: ConfidenceResult      // { score, level, factors }
  impact: ImpactRange | null        // { low, mid, high, currency, period, direction }
  verdict: string
  actionReason?: string
  trigger?: string                  // 'wasted_spend' | 'demote_underperform' | 'promote_conversion' | 'promote_intent' | 'under_invested' | 'observe'
}
```

From dashboard/src/app/(dashboard)/tier-scoring/components/LeakageTermRow.tsx:
```typescript
export interface ApproveOptions {
  recommendedAction?: 'global_block' | 'funnel'
  recommendedTier?: string
}
```

From dashboard/src/app/(dashboard)/tier-scoring/hooks/useRecommendations.ts:
```typescript
export type RecommendationStatus = { status: 'pending' | 'accepted' | 'rejected' | 'expired' }
```

From dashboard/src/lib/formatting.ts:
```typescript
export function formatDollars(amount: number): string
```

Existing components used in rows (KEEP):
- TierMovementArrow: `<TierMovementArrow current={} recommended={} targetTier={} />`
- ImpactBadge: `<ImpactBadge impact={term.impact} />`

Existing components to REMOVE from rows:
- ConfidenceBadge, ReasonBadge (imported from sibling files)
- Badge (from @/components/ui/badge) — the intent/trigger badges
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add groupActionableTerms to reason-codes.ts + Create ActionGroupHeader.tsx</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionGroupHeader.tsx
  </files>
  <action>
**reason-codes.ts** — Add these exports AFTER the existing code (do NOT modify existing functions):

```typescript
export type ActionGroup = 'stop_wasting' | 'restrict_bidding' | 'bid_aggressive'

export interface ActionGroupData {
  key: ActionGroup
  label: string
  terms: ClassifiedTerm[]
  totalImpact: { low: number; mid: number; high: number }
  highConfidenceCount: number
}

const TRIGGER_TO_GROUP: Record<string, ActionGroup> = {
  wasted_spend: 'stop_wasting',
  demote_underperform: 'restrict_bidding',
  promote_conversion: 'bid_aggressive',
  promote_intent: 'bid_aggressive',
  under_invested: 'bid_aggressive',
}

const GROUP_ORDER: ActionGroup[] = ['stop_wasting', 'restrict_bidding', 'bid_aggressive']

const GROUP_LABELS: Record<ActionGroup, string> = {
  stop_wasting: 'Stop Wasting Money',
  restrict_bidding: 'Restrict Bidding',
  bid_aggressive: 'Bid More Aggressively',
}

export function groupActionableTerms(terms: ClassifiedTerm[]): ActionGroupData[] {
  const grouped = new Map<ActionGroup, ClassifiedTerm[]>()
  for (const g of GROUP_ORDER) grouped.set(g, [])

  for (const term of terms) {
    const group = TRIGGER_TO_GROUP[term.trigger ?? '']
    if (group) grouped.get(group)!.push(term)
  }

  return GROUP_ORDER.map(key => {
    const groupTerms = grouped.get(key)!
    // Sort: impact.mid desc, then confidence.score desc
    groupTerms.sort((a, b) => {
      const impactDiff = (b.impact?.mid ?? 0) - (a.impact?.mid ?? 0)
      if (impactDiff !== 0) return impactDiff
      return b.confidence.score - a.confidence.score
    })

    const totalImpact = groupTerms.reduce(
      (acc, t) => ({
        low: acc.low + (t.impact?.low ?? 0),
        mid: acc.mid + (t.impact?.mid ?? 0),
        high: acc.high + (t.impact?.high ?? 0),
      }),
      { low: 0, mid: 0, high: 0 }
    )

    return {
      key,
      label: GROUP_LABELS[key],
      terms: groupTerms,
      totalImpact,
      highConfidenceCount: groupTerms.filter(t => t.confidence.score > 0.80).length,
    }
  }).filter(g => g.terms.length > 0)
}
```

**ActionGroupHeader.tsx** — NEW file. A collapsible group header with:
- `'use client'` directive
- Left side: colored left border (red/amber/green via accentColor prop mapping: `stop_wasting` -> `border-l-red-500`, `restrict_bidding` -> `border-l-amber-500`, `bid_aggressive` -> `border-l-green-500`), group label (font-semibold text-sm), term count badge (`text-xs text-muted-foreground`), total impact range using `formatDollars` from `@/lib/formatting` showing `$low - $high/mo`
- Right side: "Approve All High-Confidence" button (variant="outline", size="sm", only shown when `highConfidenceCount > 0`, shows count in button text), ChevronDown/ChevronUp icon for expand/collapse toggle
- Import `ChevronDown, ChevronUp` from `lucide-react`, `Button` from `@/components/ui/button`, `formatDollars` from `@/lib/formatting`
- Props interface:
```typescript
interface ActionGroupHeaderProps {
  group: ActionGroupData
  groupKey: ActionGroup
  isExpanded: boolean
  onToggle: () => void
  onBatchApprove: (terms: ClassifiedTerm[]) => void
}
```
- The entire header is clickable to toggle expand/collapse (cursor-pointer, hover:bg-muted/30)
- Batch approve button onClick: `(e) => { e.stopPropagation(); onBatchApprove(group.terms.filter(t => t.confidence.score > 0.80)) }`
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx tsc --noEmit --pretty 2>&1 | head -30</verify>
  <done>reason-codes.ts exports ActionGroup, ActionGroupData, groupActionableTerms. ActionGroupHeader.tsx exists and renders collapsible header with batch approve. TypeScript compiles with no errors.</done>
</task>

<task type="auto">
  <name>Task 2: Rewrite ActionQueueTable + Simplify ActionQueueRow</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
    dashboard/src/app/(dashboard)/tier-scoring/page.tsx
  </files>
  <action>
**ActionQueueRow.tsx** — Simplify the row:
1. REMOVE imports: `ConfidenceBadge`, `ReasonBadge`, `Badge` (from @/components/ui/badge), and the intent score Badge + trigger Badges
2. REMOVE from the JSX: the ConfidenceBadge component, the ReasonBadge component, the intent score Badge, the "Intent-Proven" Badge, the "Conversion-Proven" Badge
3. REMOVE the `rank` prop from the interface and JSX (no more rank number display — the group provides context)
4. KEEP: term name (clickable), actionReason text line, TierMovementArrow, ImpactBadge, all action buttons (Block/Demote for wasted_spend, Approve/Reject for others), approved/rejected status with undo
5. The row's outer div should keep its current styling but with the colored left border coming from a new `accentClass` prop (optional string, e.g., `'border-l-2 border-l-red-500'`). If not provided, fall back to plain border.
6. Update the interface: remove `rank: number`, add `accentClass?: string`
7. Clean up unused imports after removing badges — remove `Badge` from `@/components/ui/badge` import, remove `ConfidenceBadge` and `ReasonBadge` imports entirely

**ActionQueueTable.tsx** — Rewrite to grouped layout:
1. Replace flat list with grouped layout using `groupActionableTerms` from `../lib/reason-codes`
2. Import `ActionGroupHeader` from `./ActionGroupHeader`, `groupActionableTerms` and types from `../lib/reason-codes`
3. State: `expandedGroups` as `Set<ActionGroup>` — default all expanded. `showAllMap` as `Record<ActionGroup, boolean>` for "show all" toggle per group.
4. For each group returned by `groupActionableTerms(terms)`:
   - Render `ActionGroupHeader` with expand/collapse and batch approve
   - If expanded, render the group's terms as `ActionQueueRow` components
   - Show top 10 terms per group by default; if group has >10 terms, show a "Show all N" button at the bottom of the group (only when not showing all)
5. Batch approve: filter group terms by `confidence.score > 0.80`, call `onApprove` for each
6. Pass `accentClass` to each row based on group key: stop_wasting -> `'border-l-2 border-l-red-500'`, restrict_bidding -> `'border-l-2 border-l-amber-500'`, bid_aggressive -> `'border-l-2 border-l-green-500'`
7. Keep the accepted-first sorting within each group: partition by recommendationStatuses, accepted first then others
8. Keep the `makeKey` helper for status lookups
9. Keep the empty state (all terms well-placed message)
10. Remove the flat pagination (PAGE_SIZE / showCount). Each group has its own "Show all" toggle.
11. Wrap all groups in a single Card. Each group is a section within CardContent.

**page.tsx** — Minimal change:
- No changes needed to data flow. The `actionableTerms` useMemo already filters correctly. ActionQueueTable receives the same `terms` prop.
- Verify that imports are still correct after the ActionQueueTable rewrite.

ACCENT_CLASSES constant (define in ActionQueueTable.tsx):
```typescript
const ACCENT_CLASSES: Record<ActionGroup, string> = {
  stop_wasting: 'border-l-2 border-l-red-500',
  restrict_bidding: 'border-l-2 border-l-amber-500',
  bid_aggressive: 'border-l-2 border-l-green-500',
}
```
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build 2>&1 | tail -20</verify>
  <done>Action queue renders 3 collapsible groups sorted by urgency. Rows are simplified (no badge clutter). Each group has batch approve and show-all toggle. Build passes with zero errors.</done>
</task>

<task type="auto">
  <name>Task 3: Lint + Test + Visual verification</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx
    dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx
  </files>
  <action>
1. Run `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run lint` and fix any lint errors. Pay special attention to:
   - Unused imports in ActionQueueRow.tsx after removing badges
   - Any missing imports in the new/rewritten files
   - ESLint: underscore prefix does NOT suppress no-unused-vars in this project — use `// eslint-disable-next-line` or remove the variable entirely
2. Run `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` — all 77+ existing tests must pass (we did not modify the scoring engine)
3. Run `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build` — final build verification
4. Grep for any remaining references to removed imports: `grep -rn 'ConfidenceBadge\|ReasonBadge' dashboard/src/app/\(dashboard\)/tier-scoring/components/ActionQueueRow.tsx` should return nothing
5. If all passes, commit with message: `feat(quick-5): action queue grouped layout (Wave 2 dashboard redesign)`
  </action>
  <verify>cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build && npm run lint && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts 2>&1 | tail -10</verify>
  <done>Build passes, lint clean, 77+ tests pass, no unused imports. Commit created on master.</done>
</task>

</tasks>

<verification>
1. `cd dashboard && npm run build` passes with zero errors
2. `cd dashboard && npm run lint` clean
3. `cd dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` — 77+ tests pass
4. No references to ConfidenceBadge or ReasonBadge in ActionQueueRow.tsx
5. groupActionableTerms correctly maps triggers to 3 groups
</verification>

<success_criteria>
- Action Queue tab shows 3 collapsible groups: "Stop Wasting Money" (red), "Restrict Bidding" (amber), "Bid More Aggressively" (green)
- Each group header shows: label, term count, total impact range, batch approve button
- Rows simplified to: term name, actionReason text, tier arrow, impact badge, action buttons
- Removed from rows: ConfidenceBadge, ReasonBadge, Intent badge, trigger badges
- Top 10 per group with "Show all N" expander
- Build + lint + tests all pass
</success_criteria>

<output>
After completion, create `.planning/quick/5-implement-wave-2-action-queue-redesign-f/5-SUMMARY.md`
</output>
