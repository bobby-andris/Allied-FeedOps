# Phase 34.1 Research — Tier Intelligence Decision Logic & Expansion

**Date**: 2026-02-25
**Scope**: Decision logic gaps, custom_label_0 blocking, Shopping→Search pipeline, revenue insights, data quality

---

## 1. Decision Logic — Additional Gaps Beyond the 5 Known Bugs

### 1a. `estimateTierFromMetrics` in `query-intelligence.ts` Uses Hardcoded ROAS Thresholds

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/query-intelligence.ts`, lines 116-145

The `estimateTierFromMetrics()` function uses hardcoded thresholds (`roas >= 3.6` → LOW, `roas >= 3.1` → MEDIUM, else HIGH). These are the **old** static thresholds that the distribution-based `tier-scoring.ts` was built to replace. But `estimateTierFromMetrics` is still called by `recommendActionForTerm()` (line 191), which feeds the `NeedsDecisionTerm` recommendation pipeline (the `/api/shopping-funnel/recommendations` route).

**Impact**: Two parallel scoring systems exist — the distribution-based `scoreTerm()` in `tier-scoring.ts` and the threshold-based `estimateTierFromMetrics()` in `query-intelligence.ts`. They can produce contradictory tier recommendations for the same term. The recommendations API uses the old system; the tier-scoring API uses the new one.

**Fix**: Unify. Either deprecate `estimateTierFromMetrics` or have it delegate to the distribution-based scorer.

### 1b. `control-center.ts` BASELINE_TARGET_ROAS Is Also Hardcoded and Inverted

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/control-center.ts`, lines 3-7

```typescript
const BASELINE_TARGET_ROAS = {
  HIGH: 3.6,
  MEDIUM: 3.1,
  LOW: 2.6,
} as const
```

These values have HIGH with the *highest* target ROAS and LOW with the *lowest*. Per the waterfall domain model (see MEMORY.md), this is **correct for target ROAS settings** (HIGH priority = restrictive bidding = high tROAS setting). However, the `buildRoasRecommendations()` function (line 249) compares `observedRoas` against these targets. Since observed ROAS in HIGH is typically ~1.2 (per DEFAULT_DISTRIBUTIONS), **every HIGH tier row will trigger `direction = 'increase'`** (observed 1.2 << target 3.6 * 0.8 = 2.88). This makes the ROAS recommendation engine a no-op — it will always say "increase" for HIGH and potentially always say "decrease" for LOW.

**Impact**: The `/api/shopping-funnel/roas-recommendations` endpoint produces monotonic, non-actionable recommendations.

**Fix**: The comparison logic needs to understand that observed ROAS != target ROAS in the waterfall model. These are fundamentally different metrics. `observedRoas` is actual performance; `targetRoas` is a bid constraint. The recommendation should compare observed ROAS against the *tier's expected distribution*, not against the bid target.

### 1c. `under_invested` Detection in `reason-codes.ts` Is Broken

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/(dashboard)/tier-scoring/lib/reason-codes.ts`, lines 47-54

```typescript
if (
  term.impact.direction === 'downward' &&
  keywordData.avgMonthlySearches > UNDER_INVESTED_MULTIPLIER * (term.totalCostMicros > 0 ? 1 : 0)
)
```

The expression `UNDER_INVESTED_MULTIPLIER * (term.totalCostMicros > 0 ? 1 : 0)` evaluates to either `2 * 1 = 2` or `2 * 0 = 0`. So any term with `avgMonthlySearches > 2` qualifies as under-invested (virtually every term). The multiplier was intended to compare market volume against *actual impressions*, not against a boolean.

**Fix**: Should be `keywordData.avgMonthlySearches > UNDER_INVESTED_MULTIPLIER * term.totalImpressions` (but `totalImpressions` is not on `TermScore` — it would need to be added, or passed separately).

### 1d. Confidence Consistency Factor Is a Weak Proxy

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/tier-scoring.ts`, lines 297-303

The `consistency` factor checks if a term appears in multiple funnel assignments and whether they all agree on the tier. But in the waterfall model, a term typically appears in ONE tier (the highest-priority one that doesn't have it as a negative). Multiple funnel assignments would be an anomaly, not a sign of consistency. So this factor is always 0.5 (the neutral default) for normal terms, making it dead weight at 30% of the confidence score.

**Impact**: 30% of confidence is always 0.5 * 0.3 = 0.15, reducing the effective range of the confidence score.

**Fix**: Replace with a time-consistency proxy — e.g., how stable is this term's performance across weeks? Or use the ratio of clicks-to-impressions variance.

### 1e. Peer Context Rank Uses Distribution Points, Not Raw Data

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/tier-scoring.ts`, lines 575-596

`buildPeerContext()` estimates percentile rank using p25/p50/p75 distribution points (max 9 synthetic values) rather than actual term ROAS values. This makes the percentile ranking coarse and unreliable — a term can only rank against 9 fixed points, not against actual peers.

**Impact**: "Ranks in top 15% of Towel Bar terms" may be inaccurate because it's comparing against 9 points, not the actual N terms in that group.

### 1f. CPC Z-Score Direction Not Inverted

**File**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/lib/optimization/tier-scoring.ts`, lines 216-224

The fit score uses `Math.abs(zCpc)` — treating CPC the same as ROAS/CVR/CTR. But CPC is an *inverse* metric: lower is better (within a tier). A term with CPC much lower than the tier median should be a *better* fit, not a worse one. The absolute value treatment means a term paying $0.20 CPC in a tier with $0.80 median gets the same penalty as one paying $1.40.

**Impact**: CPC contributes 15% to fit scoring but doesn't account for its inverse relationship to desirability. This biases recommendations — a cheap, high-converting term might be flagged as misplaced because its CPC is "far from the tier median."

**Fix**: For CPC, use `zCpc` (signed, where negative = cheaper = better fit for any tier) instead of `Math.abs(zCpc)`, or weight it differently.

### 1g. The "Misplaced" Concept Should Be Reframed

The current model asks "which tier does this term statistically fit?" But that's the wrong question for a waterfall. The right question is: "Is this term getting the right *bidding treatment* for its performance?" A high-ROAS term in HIGH isn't "misplaced to LOW" — it's "under-invested and should be promoted to LOW for aggressive bidding." A zero-conversion term in LOW isn't "a better fit for HIGH" — it's "wasting aggressive bids and should be blocked or constrained."

The reframe: Replace `isMisplaced` / `recommendedTier` with `actionNeeded` / `recommendedAction`:
- `promote` — high performer in a constrained tier, push down funnel
- `constrain` — poor performer in aggressive tier, push up funnel
- `block` — irrelevant/zero-conversion, add as negative everywhere
- `observe` — correctly placed, no action needed

This aligns with the user's actual workflow (managing negative keyword lists) rather than abstract tier fitting.

---

## 2. Custom Label 0 Level Actions — Design

### 2a. Current Usage of `custom_label_0`

`custom_label_0` is the product category segment (e.g., "towel bar", "grab bar", "basket"). It appears in:

| Table | Column | Notes |
|-------|--------|-------|
| `label_tier_daily_snapshot` | `custom_label_0` | Daily performance by label+tier (unique on `snapshot_date, custom_label_0, tier`) |
| `term_intent_state` (035b KEEP) | `custom_label_0` | Intent classification per term per label |
| `policy_decision_log` (035b KEEP) | `custom_label_0` | Decision audit trail |
| `policy_action_execution_log` (035b KEEP) | `custom_label_0` | Action execution log |
| `search_buildout_recommendations` (035b KEEP) | `custom_label_0` | Search campaign recommendations |
| `query_value_scores` | `custom_label_0` | Scored terms (unique on `search_term, custom_label_0`) |
| `publish_events` | `segment_key` | Normalized custom_label_0 (migration 034) |

In the Google Ads campaign structure, `custom_label_0` maps to campaign names: `AVD - Shopping - US - {custom_label_0} - {TIER}`. See `service.ts` line 36: `CAMPAIGN_NAME_PATTERN = /^AVD - Shopping - US - (.+?) - (HIGH|MEDIUM|LOW)$/i`.

### 2b. What "Block Custom Label 0" Means

Blocking a `custom_label_0` means: pause or remove ALL 3 campaigns for that label (HIGH/MEDIUM/LOW). This is a **campaign-level** action, not a negative-keyword action. The mechanism would be:

1. **Pause campaigns**: Set campaign status to PAUSED for all 3 tiers of that label
2. **OR add account-level negatives**: Add all terms under that label as negatives (but this is impractical for dynamic queries)
3. **Recommended approach**: Campaign pause via Google Ads API

### 2c. Proposed `routing_recommendations` Extension

The `routing_recommendations` table doesn't exist in SCHEMA.md (it's used by the recommendations API but likely created ad-hoc or is part of an unapplied migration). The current POST handler already supports `recommended_action` values including `'funnel'`, `'global_block'`, `'competitor'`, `'branded'`.

For label-level blocking, add a new action type:

```sql
-- New row type in routing_recommendations
INSERT INTO routing_recommendations (
  search_term,           -- NULL for label-level actions
  custom_label_0,        -- The label being blocked
  recommended_action,    -- 'label_block'
  recommended_tier,      -- NULL
  confidence,
  review_status,         -- 'pending' → 'accepted'
  metadata               -- { reason: "Consistently unprofitable", total_spend: X, total_roas: Y }
)
```

**Key design decisions**:
- `search_term = NULL` distinguishes label-level from term-level actions
- Add `action_scope` column: `'term'` (default) or `'label'` to make queries explicit
- The UI would show a "Block Label" button on the GroupOverview component (`/Users/bobby/Documents/GitHub/Allied-FeedOps/dashboard/src/app/(dashboard)/tier-scoring/components/GroupOverview.tsx`)

### 2d. Interaction with Per-Term Flow

When a label is blocked:
1. All pending per-term recommendations for that label should be auto-resolved (status → 'superseded')
2. New scoring runs should skip terms under blocked labels
3. The label block should appear in history view as a single high-impact action
4. Unblocking should be possible (resume campaigns)

---

## 3. Shopping → Search Promotion Pipeline

### 3a. Existing Code

The `search_buildout_recommendations` table (035b, KEEP status) already exists in the schema with the right shape:

```
search_term | custom_label_0 | recommended_search_tier ('broad'|'phrase'|'exact') | status | confidence | metadata | approved_by | approved_at
```

The `route_action` check constraint on `term_intent_state` already includes `'search_discovery'` and `'search_exact_candidate'` as valid values — these were designed for exactly this Shopping→Search pipeline.

**However**: These are 035b tables. Per CLAUDE.md, they exist in production but are currently empty with no active data pipeline. The TypeScript code that references them handles empty results gracefully.

### 3b. No Active "Search Promoter" Code

There is no existing code that populates `search_buildout_recommendations` or uses `route_action = 'search_discovery'`. The infrastructure was designed but never activated.

### 3c. Data Flow for Shopping → Search

The `search_queries` table contains Google Ads search terms with performance data. The flow would be:

1. **Discovery**: Score terms via tier-scoring engine → identify high-ROAS, high-volume terms
2. **Classification**: Terms with `actualRoas > LOW tier p75` AND `totalConversions >= 5` AND `confidence.score >= 0.7` are "search promotion candidates"
3. **Match type recommendation**: Based on query specificity (from `decomposeSearchTerm()`):
   - Generic ("grab bar") → `broad` match in Search
   - Category+attribute ("polished nickel grab bar") → `phrase` match
   - SKU-specific ("allied brass 920D-6") → `exact` match
4. **Review queue**: Insert into `search_buildout_recommendations` with status `'candidate'`
5. **Approval**: Operator reviews → status `'approved'`
6. **Application**: Create keywords in Google Ads Search campaigns (requires separate Search campaign structure)

### 3d. What's Missing

1. **Search campaign structure**: The waterfall is Shopping-only. No Search campaigns exist in the naming convention (`AVD - Shopping - US - {label} - {tier}`). The user would need to create Search campaigns first.
2. **Keyword creation API**: `service.ts` can manage negative keywords and shared lists, but has no `addKeywordToCampaign()` for positive keywords in Search campaigns.
3. **Budget allocation**: Promoting a term to Search means bidding on it in TWO campaign types. The system has no way to reason about cross-campaign budget impact.
4. **Feedback loop**: After promotion, the system needs to track Search campaign performance separately and compare it to Shopping performance for the same term.

### 3e. Recommended MVP

Phase 34.1 scope should be **candidate identification only** — populate `search_buildout_recommendations` with high-confidence candidates. Do NOT attempt automated keyword creation. The table already exists and has the right schema.

Add a new tab to the tier-scoring page: "Search Candidates" showing terms that meet promotion criteria, with approve/reject workflow reusing the existing `routing_recommendations` POST pattern.

---

## 4. Revenue Optimization Opportunities

### 4a. Label-Level Profitability Dashboard

The `label_tier_daily_snapshot` table has daily `custom_label_0 + tier` performance. This enables:

- **Profitable vs unprofitable labels**: Aggregate ROAS by label across all tiers. Labels with aggregate ROAS < 1.0 are losing money.
- **Tier efficiency per label**: Which labels have the biggest gap between HIGH and LOW tier ROAS? A large gap means the waterfall is working well for that label. A small gap means negative keywords aren't differentiating traffic effectively.
- **Spend concentration**: Which labels consume the most budget? Cross-reference with ROAS to find "high spend, low return" labels (block candidates).

This data is already queryable — it just needs a UI component in the GroupOverview or a new "Label Health" view.

### 4b. Cross-Term Pattern Detection

The `buildOpportunityClusters()` function in `control-center.ts` (line 93) already clusters terms by product object. Extend this to detect:

- **Systemic promotion opportunities**: If >60% of terms in a cluster score as "promote to LOW", the entire label's negative keyword strategy needs review, not individual terms.
- **Finish-level patterns**: `decomposeSearchTerm()` already extracts modifier tokens including finish names ("polished", "nickel", "bronze", "chrome"). Aggregate performance by finish modifier to answer: "Do 'polished nickel' terms convert better than 'oil rubbed bronze' terms?"
- **Dimension patterns**: Track whether dimension-specific queries ("18 inch towel bar") convert better than generic ("towel bar"). This informs both tier routing AND content generation title strategy.

### 4c. Seasonal Pattern Detection

The `label_tier_daily_snapshot` table has `snapshot_date`. With sufficient history (90+ days), detect:
- Week-over-week ROAS trends per label
- Labels that spike seasonally (gift-giving periods, home renovation seasons)
- CPC inflation patterns (competitors bidding more during peak)

### 4d. Wasted Spend Recovery Calculator

For terms classified as `wasted_spend` (zero conversions, >$5 spend), calculate:
- Total monthly wasted spend across all labels
- Which labels contribute most to waste
- Projected savings from blocking top waste terms
- This is partially implemented via the hero callout but needs a dedicated breakdown view.

---

## 5. Data Flow & Quality Assessment

### 5a. Data Flow

```
Google Ads API (live)
  └─→ service.ts (getNeedsDecisionTerms, getExistingFunnelTerms, getLabelTierPerformance)
       ├─→ /api/shopping-funnel/tier-scoring/route.ts
       │     ├─→ computeTierDistributions() + scoreTerm() [tier-scoring.ts]
       │     ├─→ decomposeSearchTerm() [query-intelligence.ts]
       │     ├─→ Persists scores to query_value_scores table
       │     └─→ Returns scores + distributions to UI
       ├─→ /api/shopping-funnel/recommendations/route.ts
       │     ├─→ buildRecommendationQueue() [control-center.ts] — uses OLD thresholds
       │     └─→ POST: approve/reject/undo → routing_recommendations table
       └─→ /api/shopping-funnel/roas-recommendations/route.ts
             └─→ buildRoasRecommendations() [control-center.ts] — broken (see 1b)
```

### 5b. Data Quality Issues

1. **No `routing_recommendations` in SCHEMA.md**: The table is used by the recommendations API but isn't documented. It was likely created manually or by an unapplied migration. Schema should be documented.

2. **`query_value_scores` not in SCHEMA.md**: The tier-scoring route upserts to this table (line 163 of route.ts), but it's also not in the schema doc. The upsert uses `onConflict: 'search_term,custom_label_0'` suggesting a unique constraint exists.

3. **Two scoring systems persist conflicting data**: The recommendations API uses `query-intelligence.ts` (hardcoded thresholds), and the tier-scoring API uses `tier-scoring.ts` (distribution-based). Both may write to `query_value_scores` with different methodologies, and the `score_version` field (`'v2-tier-scoring'`) doesn't prevent the older system from overwriting.

4. **Cache staleness**: `tier-scoring.ts` has a 10-minute module-level cache (`CACHE_TTL_MS`). In a serverless environment (Vercel), each function instance has its own cache. This means different API calls may use different cached distributions, producing inconsistent scores within the same time window.

5. **ExistingFunnelTerm aggregation**: A term can appear in multiple campaigns (across labels). The `funnels` array captures this, but `scoreTerm()` only uses `term.funnels[0]` (line 192) for currentTier and customLabel0. If a term appears in "grab bar - HIGH" and "towel bar - MEDIUM", only the first funnel assignment is used, silently discarding the second.

6. **5000-term limit**: The tier-scoring route fetches up to 5000 existing funnel terms (line 86). If the account has more, the scoring is incomplete but this isn't surfaced to the user.

---

## 6. Recommended Scope for Phase 34.1

### Must Fix (Decision Logic Correctness)

| # | Issue | File | Effort |
|---|-------|------|--------|
| 1 | Unify scoring — deprecate `estimateTierFromMetrics` hardcoded thresholds | `query-intelligence.ts:116-145` | M |
| 2 | Fix `under_invested` detection (compare against impressions, not boolean) | `reason-codes.ts:50` | S |
| 3 | Fix ROAS recommendation engine (compare observed vs distribution, not vs bid target) | `control-center.ts:249-284` | M |
| 4 | Invert CPC in fit scoring (lower CPC = better fit) | `tier-scoring.ts:219` | S |
| 5 | Reframe `isMisplaced` → action-oriented (`promote`/`constrain`/`block`/`observe`) | `tier-scoring.ts:228-281`, `tier-scoring.types.ts` | L |

### Should Build (New Capabilities)

| # | Feature | Dependency | Effort |
|---|---------|------------|--------|
| 6 | Label-level block action (UI + `routing_recommendations` extension) | GroupOverview.tsx, recommendations route | M |
| 7 | Search promotion candidate identification (populate `search_buildout_recommendations`) | tier-scoring scores | M |
| 8 | Label profitability summary view (aggregate `label_tier_daily_snapshot`) | Existing data | S |

### Should Document

| # | Item | Notes |
|---|------|-------|
| 9 | Add `routing_recommendations` to SCHEMA.md | Table exists, undocumented |
| 10 | Add `query_value_scores` to SCHEMA.md | Table exists, undocumented |
| 11 | Document the two-system scoring divergence and deprecation plan | Prevents future confusion |

### Defer to Later Phase

- Search campaign creation automation (needs Search campaign structure first)
- Seasonal pattern detection (needs 90+ days of snapshot data)
- Cross-campaign budget modeling
- Finish-level performance analysis (needs finish token extraction in scoring pipeline)
