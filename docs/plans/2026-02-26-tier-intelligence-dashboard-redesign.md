# Tier Intelligence Dashboard Redesign

**Date:** 2026-02-26
**Status:** Approved design, ready for implementation
**Context:** Phase 34.2 is complete. The scoring engine and intent-based logic are correct (77 tests pass). This redesign improves how results are **presented** to the user. The scoring engine (`tier-scoring.ts`) must NOT be modified.

**Required reading before implementing:** This document is self-contained. You do NOT need to read other docs. Everything you need is here.

---

## DOMAIN KNOWLEDGE: The Waterfall Shopping Paradox

**You MUST understand this before touching any code.**

Allied Brass uses a "Waterfall" Google Shopping structure with 3 campaign tiers. ALL search queries enter the HIGH tier first. Negative keywords push terms DOWN the funnel.

| Tier       | Funnel Position      | tROAS Setting                  | Bidding Behavior                     | Expected Actual ROAS |
| ---------- | -------------------- | ------------------------------ | ------------------------------------ | -------------------- |
| **HIGH**   | Top (entry point)    | **Highest** (most restrictive) | Conservative — Google bids low       | **Lowest**           |
| **MEDIUM** | Middle               | Moderate                       | Moderate bidding                     | Moderate             |
| **LOW**    | Bottom (high-intent) | **Lowest** (most aggressive)   | Aggressive — Google bids high to win | **Highest**          |

**THE PARADOX:** Target ROAS setting is INVERSE to Actual ROAS. High tROAS = low actual ROAS (restricts bidding on broad traffic). Low tROAS = high actual ROAS (aggressive bidding on converting traffic).

**Actions:**
- **"Promote" = push DOWN the funnel** (e.g., MEDIUM → LOW). Adds negative keyword in current tier so term falls to a lower tier with more aggressive bidding. Used for high-intent terms that deserve more spend.
- **"Demote" = push UP the funnel** (e.g., LOW → HIGH). Removes negative keywords so term gets caught by a higher tier with restrictive bidding. Used for low-intent terms wasting budget.
- **"Block"** = account-level negative keyword. Completely stops bidding on irrelevant terms.

**Tier descriptions for UI tooltips:**
- **HIGH:** "Top-of-funnel tier. Catches generic, broad searches (e.g., 'grab bar'). Highest Target ROAS setting restricts bidding. Expected: lowest ROAS, lowest CVR."
- **MEDIUM:** "Mid-funnel tier. Catches category + 1 attribute queries (e.g., 'polished nickel grab bar'). Moderate Target ROAS. Expected: moderate ROAS and CVR."
- **LOW:** "Bottom-of-funnel tier. Catches specific, high-intent searches with 2+ attributes (e.g., 'polished nickel grab bar 18in'). Lowest Target ROAS allows aggressive bidding. Expected: highest ROAS and CVR."

---

## Problem Statement

1. **Action Queue is a wall of noise** — Every row has 4-5 badges (confidence, reason, intent, trigger), a verdict line, tier arrow, impact badge, AND action buttons. No information hierarchy.
2. **Term detail page lacks narrative clarity** — Shows scores and metrics but doesn't answer "what is the current state, what would change in my Google Ads account, and why?"
3. **Multi-label keywords are invisible** — A keyword can appear in multiple custom_label_0 funnels at different tiers, but scoring only uses `funnels[0]`.

---

## Change 1: Action Queue — Group by Action Type

### Current State (what exists now)

File: `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx`

Currently renders a flat list of ALL actionable terms sorted by impact. Each `ActionQueueRow` shows:
- Rank number, term name, ConfidenceBadge, ReasonBadge, Intent score badge, "Intent-Proven"/"Conversion-Proven" badges
- `actionReason` text line
- TierMovementArrow (current → target)
- ImpactBadge
- Action buttons (Block/Demote for wasted_spend, Approve/Reject for others)

This creates visual overload — 60+ rows each with 4-5 colored badges.

### Proposed Change

Replace the flat list with **three collapsible groups** sorted by urgency:

**Group 1: "Stop Wasting Money"** (red accent — `border-l-red-500`)
- Contains: terms where `trigger === 'wasted_spend'`
- Actions per row: **Block** button + **Restrict to HIGH** button (if not already in HIGH)
- These are actively draining budget with zero return — show first

**Group 2: "Restrict Bidding"** (amber accent — `border-l-amber-500`)
- Contains: terms where `trigger === 'demote_underperform'`
- Action per row: **Move to [targetTier]** (single approve button)
- Generic terms in tiers with aggressive bidding — restrict them

**Group 3: "Bid More Aggressively"** (green accent — `border-l-green-500`)
- Contains: terms where `trigger === 'promote_conversion' || 'promote_intent' || 'under_invested'`
- Action per row: **Move to [targetTier]** (single approve button)
- High-intent terms stuck in restrictive tiers — unleash them

**Each group header shows:**
```
[Group Name]                    [N terms]    [Total: $X/mo impact]    [Approve All High-Confidence]
```
The batch button approves all terms in that group with confidence > 0.80.

**Each row within a group is simplified to:**
```
[term name]                    [MEDIUM → HIGH]    [$17/mo]    [Block] [Restrict]
Zero purchases, $17 spent — restrict bidding
```

**REMOVED from row** (now only on detail page):
- ConfidenceBadge
- ReasonBadge (redundant — the group IS the reason category)
- Intent score badge
- "Intent-Proven" / "Conversion-Proven" badges

**KEPT on row:**
- Term name (clickable → opens TermScorecard detail)
- One-line `actionReason` text (already exists on TermScore)
- TierMovementArrow (current → proposed)
- Monthly impact (from `term.impact.low` – `term.impact.high`)
- Action buttons (Block/Restrict for wasted_spend group; Approve/Reject for others)

**Sort within each group:**
- Primary: `impact.mid` descending (highest dollar impact first)
- Secondary: `confidence.score` descending
- Show top 10 per group by default; "Show all N" button expands

### Files to Modify

1. **`dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts`** — Add a `groupActionableTerms()` function:
```typescript
export type ActionGroup = 'stop_wasting' | 'restrict_bidding' | 'bid_aggressive'

export interface ActionGroupData {
  key: ActionGroup
  label: string
  terms: ClassifiedTerm[]
  totalImpact: { low: number; mid: number; high: number }
  highConfidenceCount: number
}

export function groupActionableTerms(terms: ClassifiedTerm[]): ActionGroupData[] {
  // Group by trigger → action group
  // wasted_spend → stop_wasting
  // demote_underperform → restrict_bidding
  // promote_conversion, promote_intent, under_invested → bid_aggressive
  // Sort each group by impact.mid desc, then confidence.score desc
  // Return in order: stop_wasting, restrict_bidding, bid_aggressive
}
```

2. **`dashboard/src/app/(dashboard)/tier-scoring/components/ActionGroupHeader.tsx`** — NEW component:
```typescript
interface ActionGroupHeaderProps {
  group: ActionGroupData
  accentColor: string // 'red' | 'amber' | 'green'
  isExpanded: boolean
  onToggle: () => void
  onBatchApprove: (terms: ClassifiedTerm[]) => void
}
```
Renders: group label, term count, total impact range, batch approve button, expand/collapse chevron.

3. **`dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx`** — Rewrite to use grouped layout:
- Call `groupActionableTerms()` on the terms prop
- Render an `ActionGroupHeader` + list of simplified `ActionQueueRow` per group
- Each group shows top 10, with "Show all N" expander

4. **`dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx`** — Simplify:
- Remove: ConfidenceBadge, ReasonBadge, Intent badge, trigger badges
- Keep: term name, actionReason line, TierMovementArrow, ImpactBadge, action buttons
- The row is now much cleaner — just the essential info

5. **`dashboard/src/app/(dashboard)/tier-scoring/page.tsx`** — No changes to data flow. The `actionableTerms` useMemo already filters correctly. Just pass them to the updated ActionQueueTable.

---

## Change 2: Term Detail Page — Narrative Briefing + Raw Data + Tooltips

### Current State (what exists now)

File: `dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx`

Current section order:
1. Back button + term header with badges
2. Verdict card (action reason + tier arrow)
3. Decision Reasoning card (trigger label, explanation, evidence grid, intent mapping)
4. Peer context text
5. Scoring Factors card (expandable factors with progress bars)
6. Tier Fit Comparison card (bar chart per tier)
7. Confidence Breakdown card
8. Behavioral Signals card (when available)
9. Data Source card

`TermScorecard` receives `{ term: TermScore; onBack: () => void }`.

### Current TermScore Fields Available

```typescript
interface TermScore {
  searchTerm: string
  customLabel0: string
  currentTier: FunnelTier           // 'HIGH' | 'MEDIUM' | 'LOW'
  recommendedTier: FunnelTier       // statistical best-fit tier
  targetTier?: FunnelTier           // trigger-based target (preferred over recommendedTier)
  isMisplaced: boolean
  tierFitScores: Record<FunnelTier, number>
  fitScoreDelta: number
  dataConfirmed: boolean
  confidence: ConfidenceResult      // { score, level, factors: { dataVolume, consistency, significance, intentAlignment } }
  impact: ImpactRange | null        // { low, mid, high, currency, period, direction }
  fallbackLevel: FallbackLevel
  totalConversions: number          // raw
  totalCostMicros: number           // raw (in micros — divide by 1,000,000 for dollars)
  totalImpressions?: number         // raw
  actualRoas: number                // computed: conversions_value / cost
  verdict: string
  peerContext: string
  recommendedAction?: 'promote' | 'demote' | 'block' | 'observe'
  actionReason?: string
  behavioralSignals?: BehavioralSignals  // { rCTR, cpcCeilingRatio, microConversionDelta, composite, ... }
  intentScore?: IntentScoreBreakdown     // { feedAlignmentScore, behavioralScore, unifiedScore }
  trigger?: string                       // 'wasted_spend' | 'demote_underperform' | 'promote_conversion' | 'promote_intent' | 'under_invested' | 'observe'
}
```

### Fields MISSING from TermScore (need to add for raw data card)

These exist on `ExistingFunnelTerm` but are NOT currently passed through to `TermScore`:
- `total_clicks` — needed for raw data display
- `total_conversions_value` — needed for raw data display
- `total_average_cpc` — needed for raw data display (in micros)
- `total_all_conversions` — needed for raw data display (includes micro-conversions)

**Action:** Add these 4 fields to the `TermScore` interface in `tier-scoring.types.ts` and populate them in the `scoreTerm()` function in `tier-scoring.ts`. All 4 values are available on the `term: ExistingFunnelTerm` parameter.

```typescript
// Add to TermScore interface:
totalClicks?: number
totalConversionsValue?: number
totalAverageCpcMicros?: number
totalAllConversions?: number
```

**Populate in `scoreTerm()` return object:**
```typescript
totalClicks: term.total_clicks,
totalConversionsValue: term.total_conversions_value,
totalAverageCpcMicros: term.total_average_cpc,
totalAllConversions: term.total_all_conversions,
```

### Proposed Section Order

1. **Narrative Briefing** (NEW — most important, goes first)
2. **Raw Google Ads Data** (NEW — trust-building)
3. Verdict + Tier Movement (existing)
4. Decision Reasoning (existing)
5. Multi-Label Context (NEW — Wave 5, see Change 3)
6. Scoring Factors with tooltips (enhanced)
7. Tier Fit Comparison with tooltips (enhanced)
8. Confidence Breakdown (existing)
9. Behavioral Signals (existing)
10. Data Source (existing)

### Section 1: Narrative Briefing Card

NEW card at the top. Three paragraphs with bold labels:

**Current State:** Generate from TermScore data:
- `"{term.searchTerm}" is in the **{term.currentTier}** tier for the `{term.customLabel0}` product group.`
- Tier description from domain knowledge (HIGH = restrictive, MEDIUM = moderate, LOW = aggressive)
- `"Over the last 90 days: {totalImpressions} impressions, {totalClicks} clicks, ${totalCostMicros/1M} spent, {totalConversions} purchases."`

**Proposed Change:** Generate from trigger + targetTier:
- `"Move to **{targetTier}** tier."` + tier description
- For wasted_spend + block: `"Add as account-level negative keyword — completely stop bidding on this term."`
- For wasted_spend + demote: `"Move to HIGH tier to restrict bidding via highest tROAS cap."`
- For demote_underperform: `"Move to {targetTier} to restrict bidding — this query is too generic for aggressive spend."`
- For promote_conversion: `"Move to {targetTier} for more aggressive bidding — this term has proven conversions."`
- For promote_intent: `"Move to {targetTier} for more aggressive bidding — intent signals are strong despite zero conversions so far."`
- Impact estimate: `"Expected savings/gain: ${impact.low}–${impact.high}/mo"`

**Why:** Generate from trigger:
- For wasted_spend: `"Zero purchases despite ${cost} spend exceeds the $15 wasted-spend threshold. {rCTR context if available}."`
- For demote_underperform: `"Query intent score of {unifiedScore} maps to {expectedTier} tier, but currently in {currentTier}. {word count or specificity context}."`
- For promote_conversion: `"{totalConversions} conversions confirm purchase intent. Intent score {unifiedScore} maps to {expectedTier}. More aggressive bidding would capture more volume."`
- For promote_intent: `"Intent score {unifiedScore} exceeds the 0.65 threshold. {rCTR or word count context}. Worth promoting despite zero conversions."`

### Section 2: Raw Google Ads Data Card

A grid (3 columns on desktop, 2 on mobile) of stat boxes:

```
| Impressions    | Clicks        | CTR           |
| {totalImpressions} | {totalClicks} | {clicks/impressions as %}  |
|                |               |               |
| Avg CPC        | Total Cost    | ROAS          |
| ${avgCpc}      | ${cost}       | {actualRoas}x |
|                |               |               |
| Conversions    | All Conv.     | Conv. Value   |
| {totalConversions} | {totalAllConversions} | ${totalConversionsValue} |
```

Use the same `rounded-lg bg-muted/50 p-2.5` stat box styling already used in the Decision Reasoning evidence grid.

### Tooltips

The shadcn Tooltip component already exists at `dashboard/src/components/ui/tooltip.tsx`.

Add an info icon (`lucide-react` `Info` icon, `h-3.5 w-3.5 text-muted-foreground`) next to each factor name in the Scoring Factors card and each tier name in the Tier Fit Comparison card. Wrap with:

```tsx
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'

<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <Info className="h-3.5 w-3.5 text-muted-foreground inline ml-1 cursor-help" />
    </TooltipTrigger>
    <TooltipContent className="max-w-xs">
      <p className="text-xs">{tooltipText}</p>
    </TooltipContent>
  </Tooltip>
</TooltipProvider>
```

**Scoring Factor tooltip texts:**
- **ROAS Position**: "How well this term's ROAS fits the target tier's distribution. Computed as a robust z-score using median and MAD. 0 = perfect median fit, negative = below. Weight: 50% of tier fit score."
- **Consistency**: "Performance stability. 0.9 = all funnel assignments agree, 0.3 = conflicting. Weight: 30% of confidence."
- **Data Volume**: "Reliability from click volume. min(clicks/100, 1.0). Maxes at 100+ clicks. Weight: 30% of confidence."
- **Intent Alignment**: "Query specificity vs tier profile. Generic → HIGH, specific → LOW. Weight: 20% of confidence."
- **Feed Alignment**: "Query-to-feed attribute matching via TF-IDF (60%) + specificity (40%). From Cloud Run /score-intent. Weight: 55% of unified intent."
- **Behavioral Intent**: "Google Ads purchase signals: relative CTR (30%), CPC ceiling (25%), micro-conversions (20%), cost velocity (10%). Weight: 45% of unified intent."

**Tier Fit Comparison tooltip texts:** (see tier descriptions in Domain Knowledge section above)

---

## Change 3: Multi-Label Keywords — Score Per Label

### Current Scoring Loop (must change)

File: `dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts`, lines 167-190

```typescript
// CURRENT CODE — only uses funnels[0]:
const scores: TermScore[] = []
for (const term of existingTermsResult.terms) {
  if (!term.funnels.length) continue

  const primaryFunnel = term.funnels[0]              // BUG: only first funnel
  const currentTier = mapTierToFunnelTier(primaryFunnel.tier)
  if (!currentTier) continue

  const groupKey = primaryFunnel.custom_label_0
  const groupDist = distributions.get(groupKey)
  if (!groupDist) continue

  const intentFeatures = decomposeSearchTerm(term.search_term)
  const feedScore = feedAlignmentMap.get(term.search_term)
  const scored = scoreTerm(term, groupDist, globalFallbackDists, intentFeatures, DEFAULT_CALIBRATION, feedScore, AVG_CPA)
  scores.push(scored)
}
```

### New Scoring Loop

```typescript
// NEW CODE — iterate over ALL funnels per term:
const scores: TermScore[] = []
for (const term of existingTermsResult.terms) {
  if (!term.funnels.length) continue

  const intentFeatures = decomposeSearchTerm(term.search_term)
  const feedScore = feedAlignmentMap.get(term.search_term)

  // Score once per custom_label_0 funnel assignment
  for (const funnel of term.funnels) {
    const currentTier = mapTierToFunnelTier(funnel.tier)
    if (!currentTier) continue // Skip 'Campaign Negative' and 'Unknown'

    const groupKey = funnel.custom_label_0
    const groupDist = distributions.get(groupKey)
    if (!groupDist) continue // Skip if no distribution data

    // scoreTerm uses funnels[0] internally for tier — we need to ensure
    // it uses THIS funnel. Create a shallow copy with this funnel first.
    const termForThisFunnel = {
      ...term,
      funnels: [funnel, ...term.funnels.filter(f => f !== funnel)],
    }

    const scored = scoreTerm(termForThisFunnel, groupDist, globalFallbackDists, intentFeatures, DEFAULT_CALIBRATION, feedScore, AVG_CPA)
    scores.push(scored)
  }
}
```

**Key detail:** `scoreTerm()` internally reads `term.funnels[0]` to get `currentTier` and `customLabel0`. By creating a shallow copy with the target funnel at index 0, we don't need to modify `scoreTerm()` at all.

### Impact on Existing Code

- `aggregateImpact()` in route.ts — Already uses composite key logic. Same term with 2 labels = 2 separate TermScore objects with different `customLabel0`. Works correctly.
- `makeKey()` in useRecommendations.ts — Already uses `${searchTerm}::${customLabel0}`. Works correctly.
- `classifyAllTerms()` in reason-codes.ts — Works on TermScore[], doesn't assume unique search terms. Works correctly.
- DB upsert in route.ts — Uses `onConflict: 'search_term,custom_label_0'` composite key. Works correctly.

### Multi-Label UI (Wave 5)

**On the detail page (TermScorecard.tsx):**

Add a "Multi-Label Context" card between Decision Reasoning and Scoring Factors. Only render when the same `searchTerm` appears with multiple `customLabel0` values in the scores array.

To enable this, the page.tsx needs to pass all scores for the current term (not just the selected one). Add a prop:

```typescript
interface TermScorecardProps {
  term: TermScore
  allScoresForTerm?: TermScore[]  // all label-specific scores for this searchTerm
  onBack: () => void
  onSwitchLabel?: (term: TermScore) => void  // switch to viewing a different label's score
}
```

In page.tsx, compute `allScoresForTerm` when a term is selected:
```typescript
const allScoresForTerm = useMemo(() => {
  if (!actionSelectedTerm || !data) return []
  return data.scores.filter(s => s.searchTerm === actionSelectedTerm.searchTerm)
}, [actionSelectedTerm, data])
```

The Multi-Label Context card renders:
```
This term appears in N product groups:

[label1]  MEDIUM → HIGH  (Wasted Spend)  [Currently viewing]
[label2]  HIGH → HIGH    (Aligned)       [View this label]
```

Clicking "View this label" calls `onSwitchLabel(otherTermScore)` which updates `actionSelectedTerm` in page.tsx.

**On the Action Queue row (ActionQueueRow.tsx):**

If the same searchTerm has multiple entries in the actionableTerms list, show a small `(N labels)` text after the term name:
```tsx
{labelCount > 1 && (
  <span className="text-xs text-muted-foreground">({labelCount} labels)</span>
)}
```
Pass `labelCount` as a prop computed in ActionQueueTable by counting entries with the same searchTerm.

---

## Implementation Waves

### Wave 1: Multi-Label Scoring Backend
**Files:** `route.ts` only
**Scope:** Replace the scoring loop (see exact code above). No UI changes.
**Test:** Verify a term with 2 funnels produces 2 TermScore objects with different customLabel0.
**Build verification:** `npm run build` must pass.

### Wave 2: Action Queue Redesign
**Files:** `reason-codes.ts`, `ActionGroupHeader.tsx` (new), `ActionQueueTable.tsx`, `ActionQueueRow.tsx`, `page.tsx`
**Scope:** Group terms into 3 categories. Simplify rows. Add group headers.
**Build verification:** `npm run build` must pass.

### Wave 3: Detail Page — Narrative + Raw Data + New Fields
**Files:** `tier-scoring.types.ts` (add 4 fields), `tier-scoring.ts` (populate 4 fields in scoreTerm return), `TermScorecard.tsx` (add 2 new sections, reorder)
**Scope:** Add Narrative Briefing card, Raw Google Ads Data card. Add missing raw fields to TermScore.
**Build verification:** `npm run build` must pass. Existing 77 tests must still pass.

### Wave 4: Tooltips
**Files:** `TermScorecard.tsx` only
**Scope:** Add Info icon + Tooltip to scoring factors and tier fit comparison. Use existing shadcn Tooltip from `@/components/ui/tooltip`.
**Build verification:** `npm run build` must pass.

### Wave 5: Multi-Label UI
**Files:** `TermScorecard.tsx`, `ActionQueueRow.tsx`, `ActionQueueTable.tsx`, `page.tsx`
**Scope:** Add Multi-Label Context section to detail page. Add label count indicator to rows. Requires Wave 1 (multi-label data) and Wave 3 (TermScorecard structure) to be done first.
**Build verification:** `npm run build` must pass.

---

## Pre-Deploy Gates (MANDATORY for every wave)

1. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build` — MUST pass
2. `npx tsc --noEmit` — zero errors
3. `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` — 77+ tests pass
4. `npm run lint` — fix all issues
5. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run dev` — Launch local dev server
6. Use agent-browser skill to launch browser and visually and manually ensure that dashboard has no errors and functionality is implemented correctly
7. Only THEN: `git push origin master` (auto-deploys to Vercel + Cloud Run)
