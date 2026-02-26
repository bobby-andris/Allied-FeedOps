# Tier Intelligence Dashboard Redesign

**Date:** 2026-02-26
**Status:** Approved design, ready for implementation
**Context:** Phase 34.2 is complete. The scoring engine and intent-based logic are correct. This redesign improves how results are presented to the user.

## Problem Statement

The Tier Intelligence page has three UX problems:

1. **Action Queue is a wall of noise** — Every row has 4-5 badges (confidence, reason, intent, trigger type), a verdict line, tier arrow, impact badge, AND action buttons. No information hierarchy. User can't quickly identify what matters.
2. **Term detail page lacks narrative clarity** — Shows scores and metrics but doesn't answer "what is the current state, what would change, and why?" User can't verify the recommendation against their Google Ads account.
3. **Multi-label keywords are invisible** — A keyword can appear in multiple custom_label_0 waterfall funnels at different tier levels, but the system only scores against `funnels[0]`. This hides critical routing information.

## Design: Three Changes

---

### Change 1: Action Queue — Group by Action Type with Priority Ranking

**Replace** the current flat list of 60+ rows with **three collapsible groups**, sorted by urgency:

#### Group 1: "Stop Wasting Money" (red accent)
- Contains: `wasted_spend` trigger terms
- Primary actions: **Block** (account-level negative) or **Restrict** (demote to HIGH tier)
- Why first: These are actively draining budget with zero return

#### Group 2: "Restrict Bidding" (amber accent)
- Contains: `demote_underperform` trigger terms
- Primary action: **Move to [tier]** (move UP the funnel to a more restrictive tier)
- Why second: These are in tiers with aggressive bidding but their intent doesn't warrant it

#### Group 3: "Bid More Aggressively" (green accent)
- Contains: `promote_conversion` + `promote_intent` + `under_invested` trigger terms
- Primary action: **Move to [tier]** (move DOWN the funnel to a more aggressive tier)
- Why third: These are opportunities to capture more value, not bleeding money

#### Each group header shows:
- Group name + term count
- Total monthly impact (sum of all terms in group)
- "Approve All High-Confidence" batch button (confidence > 0.80)

#### Each row within a group is simplified to:
```
[term name]                    [MEDIUM → HIGH]    [$17/mo]    [Approve] [Reject]
Zero purchases, $17 spent — restrict bidding
```

**What's removed from the row** (moved to detail page only):
- Confidence badge
- Intent score badge
- Reason badge (redundant — the group IS the reason)
- "Intent-Proven" / "Conversion-Proven" badges
- Trigger type badge

**What stays on the row:**
- Term name (clickable to detail)
- One-line plain English reason (the `actionReason` text, shortened)
- Tier movement arrow (current → proposed)
- Monthly impact estimate
- Approve / Reject buttons (or Block / Restrict for wasted spend)

#### Priority ranking within each group:
- Primary sort: Impact (descending) — highest dollar impact first
- Secondary sort: Confidence (descending) — most certain recommendations first
- Show top 10 per group by default, "Show all N" expander for the rest

---

### Change 2: Term Detail Page — Narrative Briefing + Raw Data + Tooltips

**Replace** the current layout with a structured top-to-bottom flow:

#### Section 1: Narrative Briefing (NEW — top of page)

A card with three clearly labeled paragraphs:

**Current State:**
> "recessed toilet paper holder polished chrome" is in the **MEDIUM** tier for the `recessed tp holder` product group. In this tier, Google bids at a moderate Target ROAS, allowing moderate spend. Over the last 90 days: 487 impressions, 33 clicks, $17.42 spent, 0 purchases.

**Proposed Change:**
> Move to **HIGH** tier. This is the most restrictive tier — Google's bidding will be capped by the highest Target ROAS setting. Expected result: spend on this term drops significantly, saving an estimated $8–$17/mo.

**Why:**
> Zero purchases despite $17 spend exceeds the $15 wasted-spend threshold (1.5x account average CPA of $64.22). The term has strong click engagement (6.82x relative CTR) suggesting relevance, but it's not converting — restrict bidding until conversion data improves.

#### Section 2: Raw Google Ads Data (NEW)

A "Google Ads Performance" card showing the actual numbers from the API — not aggregations, the real data:

| Metric | Value |
|--------|-------|
| Impressions | 487 |
| Clicks | 33 |
| CTR | 6.78% |
| Avg CPC | $0.53 |
| Total Cost | $17.42 |
| Conversions | 0 |
| All Conversions (incl. micro) | 4.8 |
| Conversion Value | $0.00 |
| ROAS | 0.00x |

This section builds trust — the user can cross-reference with their Google Ads account.

Fields to show (all available on `ExistingFunnelTerm`):
- `total_impressions`
- `total_clicks`
- CTR (computed: clicks / impressions)
- `total_average_cpc` (converted from micros to dollars)
- `total_cost_micros` (converted to dollars)
- `total_conversions`
- `total_all_conversions` (includes micro-conversions like add-to-cart)
- `total_conversions_value`
- Actual ROAS (computed: conversions_value / cost)

#### Section 3: Verdict + Tier Movement (existing, kept)

The current Verdict card with the tier arrow. No changes needed.

#### Section 4: Decision Reasoning (existing, kept)

The trigger label, explanation, supporting evidence grid, intent→tier mapping. No changes needed — this is already good.

#### Section 5: Scoring Factors with Tooltips (ENHANCED)

Keep the existing expandable scoring factors, but add **info icon tooltips** to each factor name. Tooltip content:

- **ROAS Position**: "How well this term's ROAS fits the target tier's distribution. Computed as a robust z-score (using median and MAD) — 0 means perfect median fit, negative means below median. Weight: 50% of tier fit score."
- **Consistency**: "How stable this term's performance is across its data. Score of 0.9 = all funnel assignments agree on tier, 0.3 = conflicting assignments. Weight: 30% of confidence."
- **Data Volume**: "Reliability based on click volume. Computed as min(clicks / 100, 1.0). At 100+ clicks this maxes out. Weight: 30% of confidence."
- **Intent Alignment**: "How well this term's query specificity matches the tier's expected intent profile. Generic queries score high in HIGH tier, specific queries score high in LOW tier. Weight: 20% of confidence."
- **Feed Alignment**: "How well this query's words match your product feed attributes. Computed via TF-IDF term matching (60%) and query specificity/word count (40%). From Cloud Run /score-intent endpoint. Weight: 55% of unified intent score."
- **Behavioral Intent**: "Purchase intent signals from Google Ads behavior. Combines: relative CTR (30%), CPC ceiling proximity (25%), micro-conversions (20%), cost velocity (10%). Weight: 45% of unified intent score."

Also add tooltips to the **Tier Fit Comparison** bars:
- **HIGH**: "Top-of-funnel tier. Catches generic, broad searches. Highest Target ROAS setting restricts bidding. Expected: lowest ROAS, lowest CVR."
- **MEDIUM**: "Mid-funnel tier. Catches category + 1 attribute queries. Moderate Target ROAS. Expected: moderate ROAS and CVR."
- **LOW**: "Bottom-of-funnel tier. Catches specific, high-intent searches (2+ attributes). Lowest Target ROAS allows aggressive bidding. Expected: highest ROAS and CVR."

#### Section 6: Behavioral Signals (existing, kept)
#### Section 7: Confidence Breakdown (existing, kept)
#### Section 8: Data Source (existing, kept)

#### Section ordering (top to bottom):
1. Narrative Briefing (NEW)
2. Raw Google Ads Data (NEW)
3. Verdict + Tier Movement
4. Decision Reasoning
5. Multi-Label Context (NEW — see Change 3)
6. Scoring Factors (with tooltips)
7. Tier Fit Comparison (with tooltips)
8. Confidence Breakdown
9. Behavioral Signals
10. Data Source

---

### Change 3: Multi-Label Keywords — Score Per Label

#### Data Model Change

Currently `scoreTerm()` uses `term.funnels[0]` only. Change to:

**In the API route (`/api/shopping-funnel/tier-scoring/route.ts`):**
- For each `ExistingFunnelTerm`, iterate over ALL `funnels` entries (not just `[0]`)
- Call `scoreTerm()` once per funnel assignment (per custom_label_0)
- Each call uses that label's group distribution
- This produces multiple `TermScore` objects for the same search term, differentiated by `customLabel0`

**The `TermScore` type already has `customLabel0` as a field**, and the `makeKey()` function in useRecommendations already uses `${searchTerm}::${customLabel0}` as a composite key. So the data model already supports this — it's just the scoring loop that needs to iterate.

#### UI Changes

**Action Queue:**
- Terms that appear in multiple labels show a small "(2 labels)" indicator
- Each label-specific score is a separate row (because the action is per-label — you might block in one label but promote in another)
- If the same term has the same action across labels, they could be grouped visually (future optimization, not required for v1)

**Detail Page — Multi-Label Context section (NEW):**
- Appears between Decision Reasoning and Scoring Factors
- Shows a card: "This term appears in N product groups"
- Tab or accordion per label showing:
  - Label name + current tier in that label
  - Recommendation for that label (may differ!)
  - Key metrics for that label's funnel

Example:
```
This term appears in 2 product groups:

[recessed tp holder]  MEDIUM → HIGH  (Wasted Spend — $17, 0 conversions)  [Viewing]
[toilet paper holder] HIGH → HIGH    (Aligned — performing as expected)
```

The user is viewing one label's detail at a time. Clicking another label switches the full scorecard context to that label's scoring.

---

## Implementation Plan

### Wave 1: Multi-Label Scoring (backend, no UI change)
**Files:** `dashboard/src/app/api/shopping-funnel/tier-scoring/route.ts`
**Task:** Change the scoring loop to iterate over all funnels per term, not just `funnels[0]`. Each produces a separate TermScore. Verify with tests that a term with 2 funnels produces 2 scored entries.
**Risk:** Low — the data model already supports composite keys.
**Tests:** Add test case for multi-funnel term scoring.

### Wave 2: Action Queue Redesign (UI only)
**Files:**
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueTable.tsx` — Replace with grouped layout
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` — Simplify row
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionGroupHeader.tsx` — NEW: group header with count + impact + batch approve
- `dashboard/src/app/(dashboard)/tier-scoring/page.tsx` — Wire up grouping logic
- `dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts` — Add grouping function

**Task:** Group classified terms into three buckets (Stop Wasting Money, Restrict Bidding, Bid More Aggressively). Simplify rows. Add group headers with aggregate stats. Show top 10 per group with expander.

### Wave 3: Detail Page Narrative + Raw Data
**Files:**
- `dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx` — Add narrative briefing, raw data section, reorder sections
**Task:** Build the "Current State / Proposed Change / Why" narrative card. Build the raw Google Ads data card. Both use data already available on TermScore + the original ExistingFunnelTerm (may need to pass raw term data through).

**Data threading concern:** TermScorecard currently receives `TermScore` which has computed metrics but not all raw fields. Need to either:
- (a) Add raw fields to TermScore (total_impressions is already there, need total_clicks, total_average_cpc, total_all_conversions), OR
- (b) Pass the original ExistingFunnelTerm alongside TermScore

Recommend (a) — add the missing raw fields to TermScore type and populate in scoreTerm().

### Wave 4: Tooltips
**Files:**
- `dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx` — Add Tooltip components to scoring factors and tier fit comparison
- May need `@radix-ui/react-tooltip` or use existing shadcn Tooltip component

**Task:** Add info icon + tooltip to each scoring factor name and each tier label in the Tier Fit Comparison. Tooltip text is defined in this design doc above.

### Wave 5: Multi-Label UI
**Files:**
- `dashboard/src/app/(dashboard)/tier-scoring/components/TermScorecard.tsx` — Add multi-label context section
- `dashboard/src/app/(dashboard)/tier-scoring/components/ActionQueueRow.tsx` — Add "(N labels)" indicator
- `dashboard/src/app/(dashboard)/tier-scoring/page.tsx` — Handle label switching on detail page

**Task:** Show multi-label context on the detail page. Allow switching between labels to see different recommendations.

---

## Key Domain Rules (for implementer reference)

### Waterfall Paradox
- HIGH priority = top of funnel, HIGHEST tROAS setting, LOWEST actual ROAS
- LOW priority = bottom of funnel, LOWEST tROAS setting, HIGHEST actual ROAS
- "Promote" = push DOWN the funnel (toward LOW, more aggressive bidding)
- "Demote" = push UP the funnel (toward HIGH, more restricted bidding)

### Trigger Priority (from determineAction)
- A: Wasted Spend — zero conversions + >$15 spend → block or demote to HIGH
- B: Demote — intent says term is too generic for current tier → move UP
- C: Promote (Conversion-Proven) — intent + conversions confirm high intent → move DOWN
- D: Promote (Intent-Proven) — intent signals strong but zero conversions yet → move DOWN with evidence gate
- E: Under-Invested — high performer not getting volume → move DOWN

### Intent Score Thresholds
- < 0.30 → HIGH (generic)
- 0.30–0.60 → MEDIUM (mid-specificity)
- > 0.60 → LOW (specific, high-intent)

### Files That Must Not Change (scoring engine is correct)
- `dashboard/src/lib/optimization/tier-scoring.ts` — Core scoring logic
- `dashboard/src/lib/optimization/tier-scoring.types.ts` — Types (extend only, don't modify existing)
- `dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts` — 77 passing tests
