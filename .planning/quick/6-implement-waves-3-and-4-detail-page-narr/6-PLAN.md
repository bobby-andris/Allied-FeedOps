---
phase: quick-6
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - dashboard/src/lib/optimization/tier-scoring.types.ts
  - dashboard/src/lib/optimization/tier-scoring.ts
  - dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
autonomous: true
requirements: [WAVE-3, WAVE-4]

must_haves:
  truths:
    - "Detail page shows a Narrative Briefing card with Current State, Proposed Change, and Why paragraphs"
    - "Detail page shows a Raw Google Ads Data card with 9 stat boxes in a 3-column grid"
    - "Scoring Factors and Tier Fit sections have Info icon tooltips explaining each metric"
    - "TermScore carries totalClicks, totalConversionsValue, totalAverageCpcMicros, totalAllConversions from the scoring engine"
  artifacts:
    - path: "dashboard/src/lib/optimization/tier-scoring.types.ts"
      provides: "4 new optional fields on TermScore interface"
      contains: "totalClicks"
    - path: "dashboard/src/lib/optimization/tier-scoring.ts"
      provides: "Population of 4 new fields in scoreTerm return"
      contains: "totalClicks: term.total_clicks"
    - path: "dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx"
      provides: "NarrativeBriefing, RawGoogleAdsData sections + tooltips on scoring factors and tier fit"
  key_links:
    - from: "tier-scoring.ts"
      to: "tier-scoring.types.ts"
      via: "TermScore interface"
      pattern: "totalClicks.*totalConversionsValue"
    - from: "TermScorecard.tsx"
      to: "@/components/ui/tooltip"
      via: "Tooltip import"
      pattern: "TooltipProvider.*TooltipContent"
---

<objective>
Implement Waves 3 and 4 from the tier intelligence dashboard redesign: add Narrative Briefing card, Raw Google Ads Data card, and Info tooltips to the TermScorecard detail page.

Purpose: The detail page currently shows scores and metrics but lacks narrative clarity ("what is happening, what would change, and why") and raw data transparency. These additions make the detail page a self-contained briefing document.

Output: Enhanced TermScorecard.tsx with 2 new sections at top + tooltips on existing sections. 4 new fields on TermScore populated from ExistingFunnelTerm.
</objective>

<execution_context>
@/Users/bobby/.claude/get-shit-done/workflows/execute-plan.md
@/Users/bobby/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/plans/2026-02-26-tier-intelligence-dashboard-redesign.md (THE design doc — Waves 3 and 4 sections)
@dashboard/src/lib/optimization/tier-scoring.types.ts (TermScore interface)
@dashboard/src/lib/optimization/tier-scoring.ts (scoreTerm function)
@dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx (current component)
@dashboard/src/components/ui/tooltip.tsx (existing shadcn Tooltip)

<interfaces>
<!-- From tier-scoring.types.ts — TermScore interface (lines 106-130) -->
```typescript
export interface TermScore {
  searchTerm: string
  customLabel0: string
  currentTier: FunnelTier
  recommendedTier: FunnelTier
  targetTier?: FunnelTier
  isMisplaced: boolean
  tierFitScores: Record<FunnelTier, number>
  fitScoreDelta: number
  dataConfirmed: boolean
  confidence: ConfidenceResult
  impact: ImpactRange | null
  fallbackLevel: FallbackLevel
  totalConversions: number
  totalCostMicros: number
  actualRoas: number
  verdict: string
  peerContext: string
  recommendedAction?: RecommendedAction
  actionReason?: string
  targetTier?: FunnelTier
  totalImpressions?: number
  behavioralSignals?: BehavioralSignals
  intentScore?: IntentScoreBreakdown
  trigger?: string
}
```

<!-- From ExistingFunnelTerm (shopping-funnel/types.ts) — fields to pass through: -->
```typescript
total_clicks: number
total_conversions_value: number
total_average_cpc?: number       // weighted average CPC in micros
total_all_conversions?: number   // includes micro-conversions
```

<!-- From tooltip.tsx — usage pattern: -->
```typescript
import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add 4 raw data fields to TermScore + populate in scoreTerm</name>
  <files>
    dashboard/src/lib/optimization/tier-scoring.types.ts
    dashboard/src/lib/optimization/tier-scoring.ts
  </files>
  <action>
    **In tier-scoring.types.ts**, add 4 optional fields to the TermScore interface (after `totalImpressions?: number` on line 126):
    ```typescript
    totalClicks?: number
    totalConversionsValue?: number
    totalAverageCpcMicros?: number
    totalAllConversions?: number
    ```

    **In tier-scoring.ts**, add these 4 fields to the return object of `scoreTerm()` (around line 370, after `totalImpressions`):
    ```typescript
    totalClicks: term.total_clicks,
    totalConversionsValue: term.total_conversions_value,
    totalAverageCpcMicros: term.total_average_cpc,
    totalAllConversions: term.total_all_conversions,
    ```

    These fields are all available on ExistingFunnelTerm already (confirmed in shopping-funnel/types.ts). Making them optional avoids breaking the 15+ existing consumers of TermScore.
  </action>
  <verify>
    cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts --reporter=verbose 2>&1 | tail -5
  </verify>
  <done>TermScore interface has 4 new optional fields. scoreTerm populates them. All 77+ existing tests pass.</done>
</task>

<task type="auto">
  <name>Task 2: Add Narrative Briefing, Raw Google Ads Data, and Tooltips to TermScorecard</name>
  <files>
    dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx
  </files>
  <action>
    Modify TermScorecard.tsx to add 3 enhancements. The component currently has sections in this order: Back button, Term header, Verdict, Decision Reasoning, Peer context, Scoring Factors, Tier Fit, Confidence, Behavioral, Data Source.

    **New section order** (after Back button + Term header): Narrative Briefing (NEW), Raw Google Ads Data (NEW), Verdict (existing), Decision Reasoning (existing), Peer context (existing), Scoring Factors with tooltips (enhanced), Tier Fit with tooltips (enhanced), Confidence (existing), Behavioral (existing), Data Source (existing).

    **1. Add imports** at top:
    ```typescript
    import { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider } from '@/components/ui/tooltip'
    import { Info } from 'lucide-react'
    ```

    **2. Narrative Briefing Card** — Insert as first Card after Term header. Three bold-labeled paragraphs:

    **Current State:** Build from TermScore data:
    - `"{searchTerm}" is in the {currentTier} tier for the {customLabel0} product group.`
    - Add tier description: HIGH = "Top-of-funnel — highest Target ROAS setting restricts bidding on broad queries." / MEDIUM = "Mid-funnel — moderate Target ROAS for category-level queries." / LOW = "Bottom-of-funnel — lowest Target ROAS allows aggressive bidding on high-intent queries."
    - `"Over the last 90 days: {totalImpressions} impressions, {totalClicks} clicks, ${totalCostMicros/1M formatted} spent, {totalConversions} purchases."`

    **Proposed Change:** Build from trigger + targetTier:
    - For wasted_spend + block: "Add as account-level negative keyword — completely stop bidding on this term."
    - For wasted_spend + demote: "Move to HIGH tier to restrict bidding via highest tROAS cap."
    - For demote_underperform: "Move to {targetTier} to restrict bidding — this query is too generic for aggressive spend."
    - For promote_conversion: "Move to {targetTier} for more aggressive bidding — this term has proven conversions."
    - For promote_intent: "Move to {targetTier} for more aggressive bidding — intent signals are strong despite zero conversions so far."
    - For observe: "No change recommended — performing as expected in {currentTier}."
    - Add impact line if impact exists: "Expected savings/gain: ${impact.low}–${impact.high}/mo"

    **Why:** Build from trigger:
    - wasted_spend: "Zero purchases despite ${cost} spend exceeds the $15 wasted-spend threshold." + rCTR context if behavioralSignals exists.
    - demote_underperform: "Query intent score of {unifiedScore} maps to {expectedTier} tier, but currently in {currentTier}." + word count context.
    - promote_conversion: "{totalConversions} conversions confirm purchase intent. Intent score {unifiedScore} maps to {expectedTier}. More aggressive bidding would capture more volume."
    - promote_intent: "Intent score {unifiedScore} exceeds the 0.65 threshold." + rCTR or word count context.
    - under_invested: "Performing well but not getting enough impressions. Market volume suggests more demand exists."
    - observe: "This term's intent profile matches its current tier placement."

    **3. Raw Google Ads Data Card** — Insert after Narrative Briefing, before Verdict. A 3-column grid (2 on mobile) of stat boxes using the existing `rounded-lg bg-muted/50 p-2.5 space-y-0.5` style (same as Decision Reasoning evidence grid):

    ```
    | Impressions         | Clicks              | CTR                           |
    | {totalImpressions}  | {totalClicks}       | {clicks/impressions as %}     |
    | Avg CPC             | Total Cost          | ROAS                          |
    | ${avgCpc formatted} | ${cost formatted}   | {actualRoas}x                 |
    | Conversions         | All Conv.           | Conv. Value                   |
    | {totalConversions}  | {totalAllConversions}| ${totalConversionsValue}      |
    ```

    Format: impressions/clicks as integers with `.toLocaleString()`, CPC as `${(totalAverageCpcMicros / 1_000_000).toFixed(2)}`, cost as `formatDollars(totalCostMicros / 1_000_000)`, CTR as `${((totalClicks / totalImpressions) * 100).toFixed(2)}%`, conv value as `formatDollars(totalConversionsValue)`. Handle undefined/zero gracefully with `?? 0` and guard against division by zero.

    **4. Tooltips on Scoring Factors** — In the `ExpandableFactor` component, add an Info icon next to `factor.name`. Create a `FACTOR_TOOLTIPS` record mapping factor names to tooltip texts:
    - "ROAS Position": "How well this term's ROAS fits the target tier's distribution. Computed as a robust z-score using median and MAD. 0 = perfect median fit, negative = below. Weight: 50% of tier fit score."
    - "Consistency": "Performance stability. 0.9 = all funnel assignments agree, 0.3 = conflicting. Weight: 30% of confidence."
    - "Data Volume": "Reliability from click volume. min(clicks/100, 1.0). Maxes at 100+ clicks. Weight: 30% of confidence."
    - "Intent Alignment": "Query specificity vs tier profile. Generic queries fit HIGH, specific queries fit LOW. Weight: 20% of confidence."
    - "Feed Alignment": "Query-to-feed attribute matching via TF-IDF (60%) + specificity (40%). From Cloud Run /score-intent. Weight: 55% of unified intent."
    - "Behavioral Intent": "Google Ads purchase signals: relative CTR (30%), CPC ceiling (25%), micro-conversions (20%), cost velocity (10%). Weight: 45% of unified intent."

    Add the tooltip inline in the ExpandableFactor row, after the factor name span:
    ```tsx
    {FACTOR_TOOLTIPS[factor.name] && (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Info className="h-3.5 w-3.5 text-muted-foreground inline cursor-help" />
          </TooltipTrigger>
          <TooltipContent className="max-w-xs">
            <p>{FACTOR_TOOLTIPS[factor.name]}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )}
    ```

    **5. Tooltips on Tier Fit Comparison** — Add Info icon + tooltip next to each tier name in the Tier Fit Comparison card. Create `TIER_TOOLTIPS` record:
    - "HIGH": "Top-of-funnel tier. Catches generic, broad searches (e.g., 'grab bar'). Highest Target ROAS setting restricts bidding. Expected: lowest ROAS, lowest CVR."
    - "MEDIUM": "Mid-funnel tier. Catches category + 1 attribute queries (e.g., 'polished nickel grab bar'). Moderate Target ROAS. Expected: moderate ROAS and CVR."
    - "LOW": "Bottom-of-funnel tier. Catches specific, high-intent searches with 2+ attributes (e.g., 'polished nickel grab bar 18in'). Lowest Target ROAS allows aggressive bidding. Expected: highest ROAS and CVR."

    Same tooltip pattern as scoring factors, placed after the tier name span in each Tier Fit row.

    **IMPORTANT:** Do NOT modify any scoring engine logic. Only add UI presentation. Do NOT remove any existing sections — just add the 2 new sections and enhance 2 existing ones with tooltips.
  </action>
  <verify>
    cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build 2>&1 | tail -10
  </verify>
  <done>TermScorecard shows Narrative Briefing card (Current State / Proposed Change / Why), Raw Google Ads Data grid (9 stat boxes), and Info tooltips on all Scoring Factors and Tier Fit rows. Build passes with zero errors. Existing 77+ tests pass.</done>
</task>

</tasks>

<verification>
1. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` — 77+ tests pass
2. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run build` — zero errors
3. `cd /Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard && npm run lint` — no new warnings
4. Visual: TermScorecard detail page shows Narrative Briefing as first card, Raw Google Ads Data as second card, tooltips on Scoring Factors and Tier Fit sections
</verification>

<success_criteria>
- TermScore interface has 4 new optional raw data fields (totalClicks, totalConversionsValue, totalAverageCpcMicros, totalAllConversions)
- scoreTerm() populates all 4 fields from ExistingFunnelTerm
- Narrative Briefing card generates trigger-specific Current State / Proposed Change / Why paragraphs
- Raw Google Ads Data card shows 9 metric boxes in 3x3 grid
- All Scoring Factor names have Info icon tooltips with metric explanations
- All Tier Fit tier names have Info icon tooltips with tier descriptions
- Build passes, 77+ existing tests pass, lint clean
</success_criteria>

<output>
After completion, create `.planning/quick/6-implement-waves-3-and-4-detail-page-narr/6-SUMMARY.md`
</output>
