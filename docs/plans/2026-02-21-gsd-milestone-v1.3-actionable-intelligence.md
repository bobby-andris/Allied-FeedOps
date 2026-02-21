# GSD Milestone v1.3: Actionable Shopping Intelligence

## Context for Claude

You are working on Allied-FeedOps, a Google Ads optimization dashboard for alliedbrass.com (luxury bathroom accessories — towel bars, soap dispensers, robe hooks, etc. in 28+ finishes). The site sells through a 3-tier Shopping campaign funnel managed via Google Sheets supplemental feed `custom_label_0` labels.

### Prerequisites

> **This milestone assumes two prior milestones have been completed:**
>
> 1. **v1.3a (Content Generation Excellence)** — Content quality must be addressed first. Optimizing tier placements for products with generic, keyword-stuffed descriptions yields limited returns. Better descriptions → higher CTR → more data → more meaningful optimization signals. See `docs/plans/2026-02-21-strategic-milestone-assessment.md` Part 3 for the full argument.
>
> 2. **v1.3b (Architecture Validation & Data Persistence)** — Data persistence gaps must be resolved before building intelligence on top. Specifically:
>    - `service.ts` funnel data is ephemeral (2-minute cache, no historical persistence) — trend analysis and before/after measurement require persisted snapshots
>    - Deferred migrations 034b/035b must be evaluated and resolved (apply, prune, or remove) — see "Deferred Migration Status" section below
>    - Content↔performance feedback linkage must be established

### Campaign Architecture

- **177 Shopping campaigns** across **59 product groups** (custom_label_0 values like "Towel Bars", "Soap Dispensers")
- Each product group has 3 campaigns: `AVD - Shopping - US - {product_group} - HIGH|MEDIUM|LOW`
  - **HIGH** = broadest match, lowest intent (discovery traffic)
  - **MEDIUM** = mid-funnel (research traffic)
  - **LOW** = most restrictive, highest intent (purchase-ready traffic)
- Tier assignment works by adding **negative keywords** to the tiers a term should NOT appear in
- 3 shared negative lists: Global Block, Competitor Terms, Branded Search Terms

### What Exists Today (the Problem)

Milestone v1.2 built substantial **infrastructure** — a working Shopping Funnel management system, optimization libraries, GA4 attribution layer, intent policy engine, and 30+ database tables. Phase 22 (Fix Integration Bugs) resolved several integration issues: `prompt_builder.py` correction_text key fix, `GMC_MERCHANT_ID` environment variable set, `keyword_bank.json` included in Docker context, and documentation gaps closed. However, the **user-facing pages** built on this infrastructure are skeleton shells that render empty tables and zero-value cards because they don't actually compute insights from the available data:

1. **Tier Movements Panel** — shows "0 recommendations" because `query-intelligence.ts` uses hardcoded ROAS/CVR thresholds instead of computing from actual tier performance distributions
2. **Intent Control Center** — shows "0 terms evaluated" because no pipeline connects the NLP decomposition in `query-intelligence.ts` to the existing funnel terms fetched by `service.ts`
3. **Search Governance** — shows empty candidates table because no pipeline connects `search_queries` / `keyword_metrics` data to campaign draft generation
4. **Experiment Lab** — registration form only, backed by empty `experiment_registry` table with no execution or measurement logic
5. **Policy engine thresholds** (ROAS 3.6/3.1, CVR 5%/3%) in `control-center.ts` are arbitrary hardcoded values with no adaptive logic

---

## What v1.2 Already Built (DO NOT REBUILD)

### Live Google Ads Integration (`service.ts`)
**File**: `dashboard/src/lib/shopping-funnel/service.ts` (~1600 lines)
**DO NOT modify this file's existing functions. EXTEND it or call its exports.**

Key exports to USE:
- `getNeedsDecisionTerms(options)` → Returns `NeedsDecisionTerm[]` — search terms not yet assigned to a tier, with per-custom_label_0 performance metrics (impressions, clicks, cost_micros, conversions, conversions_value, source_tier)
- `getExistingFunnelTerms(options)` → Returns `ExistingFunnelTerm[]` — search terms already assigned to tiers, with the same performance metrics per custom_label_0
- `getLabelTierPerformance(options)` → Returns per-tier aggregates (spend, conversionValue, conversions, clicks) grouped by custom_label_0 and tier (HIGH/MEDIUM/LOW)
- `postDecisions(decisions)` → Writes negative keywords to Google Ads to assign terms to tiers
- `updateExistingAssignments(updates)` → Moves terms between tiers by adding/removing negatives
- `getAvailableCustomLabels()` → Lists all 59 product group labels
- `getFunnelCampaignList()` → Lists all shopping campaign names with parsed tier info
- `getShoppingFunnelDataLineage()` → Returns metadata about data freshness and query counts

Important: All service.ts functions use a **2-minute cache** (`CACHE_TTL_MS = 120000`). Data is live from Google Ads API on first call, then cached. Each call runs **6 parallel GAQL queries** to build the full funnel state.

> **⚠️ Data Persistence Gap (v1.3b prerequisite)**: All service.ts data is ephemeral — no historical funnel term data is persisted to the database. This means trend analysis (Phase 1 "compare last 7d vs previous 7d"), before/after impact measurement (Phase 4), and any time-series computation require daily snapshot persistence to be implemented in v1.3b first. Without it, this milestone's trend and impact features have no historical data to compute from.

### Query Intelligence Library (`query-intelligence.ts`)
**File**: `dashboard/src/lib/optimization/query-intelligence.ts` (~265 lines)
**REPLACE the hardcoded thresholds in this file; keep the NLP decomposition.**

What to KEEP:
- `decomposeSearchTerm(searchTerm)` → NLP decomposition returning `QueryIntentFeatures` (product_object, modifier_tokens, use_case_tokens, is_branded, is_competitor, has_mismatch_risk)
- Brand tokens list (allied brass, alliedbrass, avd)
- Competitor tokens list (16 competitors: moen, delta, kohler, etc.)
- Product object hints (16 product types: towel bar, soap dish, etc.)
- Modifier hints (chrome, nickel, bronze, etc.)

What to REPLACE:
- `estimateTierFromMetrics()` — currently uses hardcoded ROAS >= 3.6 → LOW, >= 3.1 → MEDIUM, else HIGH. Replace with distribution-based adaptive thresholds.
- `recommendActionForTerm()` — currently returns a static confidence based on click count. Replace with multi-signal scoring.
- `scoreNeedsDecisionTerm()` — the impact scoring is reasonable but doesn't use actual tier performance data for comparison. Enhance with tier-relative scoring.
- `enrichNeedsDecisionTerm()` — the composition function. Update to use the new adaptive scoring.

### Control Center Library (`control-center.ts`)
**File**: `dashboard/src/lib/optimization/control-center.ts` (~285 lines)
**ENHANCE these functions to use real tier performance data.**

Existing exports to build on:
- `buildOpportunityClusters(terms)` → Groups NeedsDecision terms by product_object, computes attractiveness score. Currently only for unassigned terms — extend to work on existing funnel terms too.
- `buildRecommendationQueue(terms, limit)` → Sorts terms by impact score. Currently only for NeedsDecision — extend to include tier movement recommendations for existing funnel terms.
- `buildQueryScoreSummary(terms)` → Aggregate stats. Keep as-is.
- `buildRoasRecommendations(rows)` → Uses `getLabelTierPerformance()` output to recommend ROAS target changes per custom_label_0/tier. The logic is sound (±10% bounded changes, confidence from click/conversion volume) but uses hardcoded baseline ROAS targets (3.6/3.1/2.6). Replace with dynamically computed baselines.

### Intent Policy Engine
**File**: `dashboard/src/lib/intent/policy.ts`
**File**: `dashboard/src/lib/intent/tier-movement.ts`
**Code exists but backing tables may be deferred.** The TypeScript code is written and tested, but several tables it references (`term_intent_state`, `policy_action_execution_log`, `negative_registry`, etc.) are part of migration 035b which was DEFERRED during v1.2. These tables may have been applied out-of-band — **verify in v1.3b before relying on them.** If applied, the tier movement pipeline can execute movements, log to `policy_action_execution_log`, update `term_intent_state`, write to `negative_registry`, and update Google Sheets.

Key functions already built:
- `evaluatePromotionDemotion(input)` → Policy decision with confidence and reason codes
- `evaluateGuardrails(input)` → Guardrail check (blocked/hold/active) based on spend/revenue thresholds
- `executeTierMovement(supabase, request, guardrailStatus, dryRun)` → Single movement execution
- `executeTierMovementBatch(supabase, batch, guardrailInput)` → Batch execution
- `updateSupplementalFeedTiers(movements)` → Updates Google Sheets custom_label_0 column

### Existing API Routes (DO NOT DUPLICATE)

**Shopping Funnel Management** (all working, used daily):
- `GET /api/search-terms/needs-decision` → Unassigned terms with NLP enrichment
- `GET /api/search-terms/existing-funnel` → Assigned terms with tier info
- `POST /api/search-terms/save-decisions` → Stage decisions locally
- `GET /api/search-terms/staged-decisions` → Read staged decisions
- `POST /api/search-terms/post-staged` → Push staged decisions to Google Ads
- `POST /api/search-terms/post-decisions` → Direct push to Google Ads
- `POST /api/search-terms/update-existing` → Move terms between tiers
- `GET /api/search-terms/data-lineage` → Data freshness metadata

**Optimization API** (built but returning empty because scoring uses hardcoded thresholds):
- `GET /api/shopping-funnel/recommendations` → Recommendation queue from `buildRecommendationQueue()`
- `GET /api/shopping-funnel/scores` → Score summary from `buildQueryScoreSummary()`
- `GET /api/shopping-funnel/opportunities` → Opportunity clusters from `buildOpportunityClusters()`
- `GET /api/shopping-funnel/roas-recommendations` → ROAS target recs from `buildRoasRecommendations()`

**Tier Movement Execution** (working):
- `POST /api/shopping-funnel/tier-movement` → Execute batch tier movements with policy validation
- `GET /api/shopping-funnel/tier-movement` → Movement history from execution log

**GA4 Attribution** (working):
- `GET /api/ga4/campaign-performance` → GA4 campaign-level sessions/transactions/revenue
- `GET /api/ga4/attribution-quality` → Attribution quality score (unassigned revenue share)
- `GET /api/ga4/attribution-forensics` → Root cause analysis (source/medium, campaign pattern, landing page)
- `GET /api/ga4/attribution-trend` → Historical trend of attribution quality
- `GET /api/ga4/reconciliation` → Google Ads vs GA4 revenue reconciliation
- `POST /api/ga4/snapshot-capture` → Capture daily attribution snapshots

**Audience Intelligence** (working):
- `GET /api/audiences/watchlist` → Audience segment performance with risk scoring
- `GET /api/audiences/recommendations` → Audience optimization recommendations

### Database Tables Already Created (migrations 032-035)

**Search Term Management** (migration 032):
- `search_term_decisions` — Staged operator decisions
- `google_ads_api_errors` — Error logging for API calls

**Optimization Control Plane** (migration 033):
- `query_intent_features` — Persisted NLP decomposition results
- `query_value_scores` — Persisted impact scores
- `routing_recommendations` — Persisted tier recommendations with review workflow (pending/accepted/rejected/expired)
- `roas_target_recommendations` — ROAS target adjustment recs with approval workflow
- `opportunity_clusters` — Persisted opportunity clusters with launch status
- `ga4_campaign_daily` — Daily GA4 campaign performance snapshots
- `ga4_attribution_quality_daily` — Daily attribution quality scores
- `shopify_order_facts` — Order-level data
- `shopify_order_line_facts` — Line-item data with custom_label_0
- `shopify_customer_value_snapshots` — Customer value metrics (30/90/365d)
- `audience_watchlist_snapshots` — Audience segment performance snapshots
- `guardrail_incidents` — Guardrail violation log

**GA4 Attribution Forensics** (migration 034):
- `ga4_source_medium_daily` — Source/medium quality breakdown
- `ga4_landing_page_quality_daily` — Landing page quality breakdown
- `ga4_attribution_root_cause_daily` — Root cause aggregation
- `ga4_shopify_reconciliation_daily` — Cross-platform reconciliation

**Intent Execution System** (migration 035 — applied; **035b — DEFERRED**):

> **⚠️ Deferred Migration Status**: Migration 035 (measurement infrastructure) IS applied to live Supabase. Migration 035b (unified intent execution system — 14 tables below) is DEFERRED. The 035b migration note states tables "were applied out-of-band in a previous session" but this must be verified during v1.3b. 8 of 14 tables are prerequisites for this milestone's Phases 1-4. Migration 034b (GA4 attribution forensics — 4 tables) is also deferred and lower priority. **Resolution of 034b/035b status is a v1.3b deliverable that must complete before this milestone begins.**

- `intent_taxonomy_versions` — Policy version management
- `term_intent_state` — Current intent classification per term
- `policy_decision_log` — Every policy evaluation logged
- `policy_action_execution_log` — Every execution action logged
- `policy_snapshots` — Point-in-time snapshots
- `sku_margin_daily` — Margin data for ROAS calculations
- `order_line_returns_daily` — Return data for true profitability
- `attribution_confidence_daily` — Attribution confidence tracking
- `experiment_registry` — Experiment definitions
- `experiment_assignments` — Term-to-experiment assignments
- `experiment_outcomes` — Experiment results
- `negative_registry` — All negative keywords with audit trail
- `search_buildout_recommendations` — Campaign expansion suggestions
- `operator_review_audit` — Operator action audit trail

**Pre-existing tables** (from earlier milestones):
- `search_queries` — Variant-level search term data enriched with Keyword Planner (avg_monthly_searches, competition_index, CPC estimates)
- `keyword_metrics` — Keyword Planner historical data with monthly breakdown
- `performance_baselines` / `performance_snapshots` — Pre/post-publish performance metrics
- `product_catalog` — All product variants with full product data
- `variant_index` — master_sku ↔ gmc_offer_id mapping

### GA4 Client Library
**File**: `dashboard/src/lib/ga4/client.ts`
- `runGa4Report(options)` → Generic GA4 Data API report runner
- `computeAttributionQuality(rows)` → Attribution quality scoring
- Campaign-level, audience-level, and source/medium reporting

**File**: `dashboard/src/lib/ga4/forensics.ts`
- Source/medium quality analysis
- Landing page quality analysis
- Campaign pattern classification
- Attribution root cause detection
- Attribution trend analysis

**File**: `dashboard/src/lib/ga4/audience-watchlist.ts`
- Audience segment performance scoring
- Risk-level classification
- Recommendation generation (observe/exclude/target/review)

---

## Goal

Transform the skeleton pages into a **revenue-generating intelligence system** by connecting the existing v1.2 infrastructure to **real data-driven computation**. The core issue is NOT missing infrastructure — it's that the scoring/recommendation logic uses hardcoded values instead of computing from actual performance distributions.

Every recommendation must:
1. Be computed from **actual Google Ads performance data** (not hardcoded thresholds)
2. Show the **expected impact in dollars** (not abstract scores)
3. Include a **confidence level** based on data volume
4. Be **executable with one click** through the existing tier movement pipeline

The system should help us:
1. **Increase revenue** by identifying high-converting terms stuck in wrong tiers
2. **Reduce wasted spend** by finding underperforming terms that should be demoted or blocked
3. **Gain market share** by discovering untapped search demand we're not capturing
4. **Optimize ROI** by dynamically adjusting tier thresholds based on actual performance, not guesses

---

## Phase 1: Revenue Leakage Detection & Tier Optimization

**Goal**: Surface the highest-impact tier movements with dollar-value estimates so operators can immediately improve ROAS.

### What to Build

#### 1.1 Adaptive Tier Scoring Engine

**Modify**: `dashboard/src/lib/optimization/query-intelligence.ts`
**New file**: `dashboard/src/lib/optimization/tier-scoring.ts` (or extend existing)

Replace the hardcoded thresholds with a **distribution-based scoring model**:

1. **Compute tier performance baselines** from live data:
   - Call `getLabelTierPerformance()` from `service.ts` to get actual spend/revenue/conversions/clicks per custom_label_0 per tier
   - Call `getExistingFunnelTerms()` to get per-term performance within each tier
   - For each tier (HIGH/MEDIUM/LOW), compute the **actual distribution** of term-level ROAS, CVR, CPC, CTR
   - Compute percentiles: p25, p50 (median), p75 for each metric within each tier

2. **Dynamic tier boundary computation**:
   - LOW tier floor = MEDIUM tier p75 ROAS (terms performing above 75th percentile of MEDIUM should be in LOW)
   - HIGH tier ceiling = MEDIUM tier p25 ROAS (terms performing below 25th percentile of MEDIUM should be in HIGH)
   - These thresholds auto-adjust as performance changes — no more hardcoded 3.6/3.1

3. **For each (search_term, custom_label_0) pair currently in the funnel**, compute:
   - **ROAS** = conversion_value / cost (from `ExistingFunnelTerm.custom_label_0s[].conversions_value / cost_micros`)
   - **CPA** = cost / conversions (with Bayesian smoothing for low-volume: add 0.5 pseudo-conversions)
   - **CTR relative to tier average** — this term's CTR ÷ average CTR of all terms in this tier
   - **CVR relative to tier average** — same
   - **Cost share** — this term's cost ÷ total tier cost
   - **Revenue share** — this term's revenue ÷ total tier revenue
   - **Trend** — compare metrics from `service.ts` with two different date windows (last 7d vs previous 7d) using `defaultDateWindow()`

4. **Tier placement scoring**: For each term, score how well it fits in each tier:
   - Compute z-score of term's ROAS relative to each tier's ROAS distribution
   - Term belongs in the tier where its z-score is closest to 0 (best fit)
   - If current tier z-score is > 1.5 (way above average) → candidate for promotion
   - If current tier z-score is < -1.5 (way below average) → candidate for demotion

5. **Impact estimation** using actual tier averages (NOT hardcoded):
   - `expected_revenue_change` = (target_tier_avg_cvr - current_tier_avg_cvr) × current_impressions × target_tier_avg_aov
   - `expected_cost_change` = (target_tier_avg_cpc - current_tier_avg_cpc) × current_clicks
   - `net_monthly_impact` = expected_revenue_change - expected_cost_change
   - Show as: "Moving '{term}' from HIGH to MEDIUM could generate ~$Y additional monthly revenue"

6. **Confidence scoring** (replace the current click-count-only confidence):
   - Data volume factor: min(clicks / 100, 1) × 0.3
   - Consistency factor: (1 - coefficient_of_variation_of_daily_ROAS) × 0.3
   - Statistical significance: use chi-squared test for conversion rate difference × 0.2
   - NLP intent alignment: does the term's intent features match the target tier? × 0.2

#### 1.2 Revenue Leakage Dashboard

**New API route**: `POST /api/shopping-funnel/revenue-leakage`

This route should:
1. Call `getExistingFunnelTerms()` and `getLabelTierPerformance()` from `service.ts`
2. Run the adaptive scoring engine from 1.1
3. Return:

```typescript
{
  tierPerformanceSummary: {
    HIGH: { totalSpend, totalRevenue, roas, avgCpc, avgCvr, termCount, roasDistribution: number[] },
    MEDIUM: { ... },
    LOW: { ... }
  },
  misplacedTerms: Array<{
    searchTerm: string
    customLabel0: string
    currentTier: 'HIGH' | 'MEDIUM' | 'LOW'
    recommendedTier: 'HIGH' | 'MEDIUM' | 'LOW'
    currentRoas: number
    tierAvgRoas: number
    netMonthlyImpact: number  // dollars
    confidence: number
    reasonCodes: string[]
  }>,
  wastedSpendAlerts: Array<{
    searchTerm: string
    customLabel0: string
    tier: string
    spend30d: number
    conversions30d: number
    suggestedAction: 'block' | 'demote'
  }>,
  underInvestedWinners: Array<{
    searchTerm: string
    customLabel0: string
    cvr: number
    tierAvgCvr: number
    impressionShare: number  // actual impressions / keyword_metrics.avg_monthly_searches
    potentialRevenueGain: number
  }>,
  totalLeakageEstimate: number  // sum of all net_monthly_impact for recommended movements
}
```

**UI**: Enhanced Tier Movements panel on Shopping Funnel page showing:
- Total revenue leakage estimate as a hero number ("~$X,XXX/month in revenue leakage detected")
- Top 10 misplaced terms sorted by dollar impact, with approve/reject buttons
- Wasted spend alerts with "Block" and "Demote" action buttons
- Under-invested winners with impression share gap visualization
- Tier ROAS distribution box plots showing overlap zones

#### 1.3 One-Click Tier Movement Execution

**USE the existing pipeline** — `POST /api/shopping-funnel/tier-movement` already works.

The UI just needs to:
- Wire "Approve" buttons to call the existing tier-movement API with the recommendation data
- Wire "Approve All High-Confidence" to batch-submit all recommendations with confidence > 0.80
- Show movement history from `GET /api/shopping-funnel/tier-movement`
- Add **Undo** capability using `negative_registry` table (the existing pipeline stores criterion IDs)
- Persist recommendations to `routing_recommendations` table (already exists in migration 033) so operators can review them asynchronously

---

## Phase 2: Market Intelligence & Demand Gap Analysis

**Goal**: Identify untapped search demand alliedbrass.com is NOT capturing but could profitably target.

### What to Build

#### 2.1 Search Demand Analysis

**Data sources**: `search_queries` + `keyword_metrics` tables (already populated by Python pipeline)

**New API route**: `GET /api/shopping-funnel/demand-gaps`

Compute:
- **Impression Share Gaps**: For each search term in `search_queries`, join with `keyword_metrics` on keyword. Compare `search_queries.impressions` (what we're getting) vs `keyword_metrics.avg_monthly_searches` (total market). Terms with high search volume but low impression share = opportunity. Calculate: `impression_share = actual_impressions / avg_monthly_searches`
- **CPC Opportunity Score**: Terms where our actual CPC (from `service.ts` data: `cost_micros / clicks / 1_000_000`) is well below `keyword_metrics.high_top_of_page_bid_micros / 1_000_000`. These terms have headroom to bid more aggressively while remaining profitable. Score = `(high_top_of_page_bid - actual_cpc) / high_top_of_page_bid`
- **Seasonal Demand Patterns**: Use `keyword_metrics.monthly_search_volumes` (JSONB array of `{year, month, monthly_searches}`) to identify:
  - Terms with demand spiking in next 1-2 months (bid up proactively)
  - Terms with declining demand (reduce bids to protect ROAS)
  - Calculate month-over-month growth rate and flag terms with >20% upcoming change

#### 2.2 Competitive Intelligence from Search Terms

**USE existing NLP decomposition** from `query-intelligence.ts`:
- `decomposeSearchTerm()` already detects `is_branded` and `is_competitor` with the 16-competitor token list
- Extend to track competitor mention frequency and revenue attribution

**New API route**: `GET /api/shopping-funnel/competitive-intel`

Compute from live `getNeedsDecisionTerms()` + `getExistingFunnelTerms()` data:
- **New Term Discovery Rate**: Compare current term set vs `search_queries` historical records. Count terms appearing for first time in last 7 days.
- **Brand vs Non-Brand Split**: Use `decomposeSearchTerm().is_branded` to categorize all terms. Show: brand_revenue, non_brand_revenue, brand_share_pct
- **Competitor Mention Tracking**: Use `decomposeSearchTerm().is_competitor` to identify competitor-mentioning queries. For each competitor token (moen, delta, kohler, etc.): count of terms, total impressions, total spend, any conversions. These represent conquest opportunities.
- **Long-tail vs Head Term Analysis**: Group terms by word count (1-2 = head, 3-4 = mid, 5+ = long-tail). For each bucket: term_count, total_spend, total_revenue, avg_roas, avg_cvr. Long-tail typically converts better — quantify the difference.

#### 2.3 Product Group Performance Matrix

**USE existing** `getLabelTierPerformance()` which already returns per-group/per-tier aggregates.

**New API route**: `GET /api/shopping-funnel/product-matrix`

For each of the 59 custom_label_0 groups, aggregate across all tiers:
- Total spend, total revenue, ROAS, total clicks, total conversions
- Trend: compare current period vs previous period (use two date window calls to service.ts)
- Classify into BCG quadrants:
  - "Stars": ROAS > median AND revenue > median
  - "Cash Cows": ROAS > median AND revenue < median (can increase spend profitably)
  - "Question Marks": ROAS < median AND revenue > median (optimize or restructure)
  - "Dogs": ROAS < median AND revenue < median (reduce spend or restructure)

**UI**: Interactive bubble chart on a new "Market Intelligence" tab or page:
- X-axis: ROAS, Y-axis: Revenue, Bubble size: Spend, Color: Trend
- Click any bubble → drill down to term-level breakdown using `getExistingFunnelTerms({ customLabel0: selectedGroup })`
- Quadrant labels and color coding
- Table view alternative for operators who prefer tabular data

---

## Phase 3: Intelligent Automation & Experiment Framework

**Goal**: Move from manual operator decisions to semi-automated optimization with measurement.

### What to Build

#### 3.1 Automated Tier Rebalancing Rules

**USE existing tables**: `policy_action_execution_log`, `guardrail_incidents`, `routing_recommendations`

Build a rule engine where operators define conditions:
- "If ROAS > X for Y+ days in tier Z, auto-promote" (X/Y/Z configurable)
- "If 0 conversions with >$Z spend in 30 days, auto-block"
- "If ROAS drops below X for Y+ days in LOW tier, auto-demote"

Implementation:
- Store rules in a new `automation_rules` table (or as JSONB in an existing config table)
- **Dry run mode**: Call `executeTierMovementBatch()` with `dryRun: true` (already supported!) to preview what would happen
- **Confidence gate**: Use the existing guardrail system in `policy.ts` — `evaluateGuardrails()` already blocks or holds based on spend/revenue thresholds
- **Execution**: Use `executeTierMovementBatch()` which already logs every action to `policy_action_execution_log`
- **Scheduled evaluation**: New API route `POST /api/shopping-funnel/evaluate-rules` that can be called by Cloud Scheduler

#### 3.2 A/B Testing for Tier Assignments

**USE existing tables**: `experiment_registry`, `experiment_assignments`, `experiment_outcomes` (all created in migration 035)

Build actual experiment lifecycle:
1. **Register**: Create experiment in `experiment_registry` with hypothesis, term set, duration, success metric
2. **Assign**: Split terms into treatment (move to new tier) and control (keep in current tier). Store in `experiment_assignments`
3. **Execute treatment**: Use `executeTierMovementBatch()` to move treatment terms
4. **Measure**: After N days, compute treatment vs control metrics:
   - Treatment ROAS vs Control ROAS
   - Revenue delta
   - Statistical significance (chi-squared or z-test on conversion rates)
5. **Resolve**: Store results in `experiment_outcomes`. If treatment wins with p < 0.05, recommend applying to all terms.

#### 3.3 Budget Allocation Recommendations

**USE existing** `buildRoasRecommendations()` from `control-center.ts` as a starting point.

Enhance to recommend budget shifts:
- Identify product groups where ROAS is high but impression share is low (profitable but under-funded)
- Identify product groups where ROAS is low and spend is high (over-funded)
- Calculate: "Moving $X/day from {dogs} to {cash_cows} could generate ~$Y additional monthly revenue"
- Use `keyword_metrics.avg_monthly_searches` to estimate total addressable market per group

---

## Phase 4: Executive Scorecard & Reporting

**Goal**: Give operators and business stakeholders a clear picture of optimization progress and ROI.

### What to Build

#### 4.1 Optimization Impact Tracker

**USE existing data**: `policy_action_execution_log` (every tier movement logged), `performance_snapshots` (post-action metrics), `performance_baselines` (pre-action metrics)

New API route: `GET /api/shopping-funnel/impact-tracker`

Compute:
- For each movement in `policy_action_execution_log`, fetch before/after performance from `performance_snapshots`
- Total estimated revenue gained from promotions (terms moved to higher-converting tiers)
- Total spend saved from demotions and blocks
- Net ROI of the optimization system
- Timeline chart showing cumulative impact over time

#### 4.2 Weekly Digest

**USE existing data sources** — this is a computation layer on top of existing APIs:

Auto-generated summary (new API route `GET /api/shopping-funnel/weekly-digest`):
- Top 5 performing search terms this week (highest ROAS from `getExistingFunnelTerms()`)
- Top 5 underperforming (biggest ROAS decline vs prior week)
- New search terms discovered (terms in current period not in `search_queries` historical)
- Actions taken this week (from `policy_action_execution_log` filtered by date)
- Recommended actions for next week (top 5 from revenue leakage analysis)

#### 4.3 Competitive Benchmark

**USE existing**: `keyword_metrics` table contains `competition_index`, `low_top_of_page_bid_micros`, `high_top_of_page_bid_micros`

Compare our actual performance against market benchmarks:
- Our avg CPC vs market benchmark CPC (from Keyword Planner) per product category
- Identify categories where we have a competitive advantage (below-market CPC + above-market CVR)
- Categories where we're overpaying relative to market (our CPC > high_top_of_page_bid)

---

## Technical Implementation Notes

### Data Flow Architecture

```
Google Ads API (live, 2-min cache)
    ↓
service.ts (getNeedsDecisionTerms, getExistingFunnelTerms, getLabelTierPerformance)
    ↓
tier-scoring.ts (NEW - adaptive distribution-based scoring)
    ↓
API routes (/api/shopping-funnel/revenue-leakage, /demand-gaps, etc.)
    ↓
UI components (enhanced Tier Movements panel, Market Intelligence page)
    ↓
Execution (existing tier-movement pipeline → Google Ads negatives + Google Sheets)
```

### Data Sources Priority
1. **Primary**: Live Google Ads API via `service.ts` exports (most current, includes campaign structure and term-level metrics)
2. **Enrichment**: `search_queries` + `keyword_metrics` tables (Keyword Planner data for market sizing, CPC benchmarks, seasonal patterns)
3. **Historical**: `performance_baselines` / `performance_snapshots` (for before/after tracking of optimization actions)
4. **Attribution**: GA4 via `ga4/client.ts` exports (revenue reconciliation, attribution quality, campaign performance)
5. **Persistence**: Write computed scores to `query_value_scores`, recommendations to `routing_recommendations`, clusters to `opportunity_clusters` (all tables exist in migration 033)

### Key Files to Modify
- `dashboard/src/lib/optimization/query-intelligence.ts` — replace hardcoded thresholds with adaptive scoring that calls `getLabelTierPerformance()`
- `dashboard/src/lib/optimization/control-center.ts` — enhance `buildRoasRecommendations()` to use dynamic baselines; extend `buildRecommendationQueue()` to include existing funnel terms

### Key Files to Create
- `dashboard/src/lib/optimization/tier-scoring.ts` — new adaptive tier scoring engine
- `dashboard/src/app/api/shopping-funnel/revenue-leakage/route.ts` — revenue leakage computation
- `dashboard/src/app/api/shopping-funnel/demand-gaps/route.ts` — demand gap analysis
- `dashboard/src/app/api/shopping-funnel/competitive-intel/route.ts` — competitive intelligence
- `dashboard/src/app/api/shopping-funnel/product-matrix/route.ts` — product group matrix
- `dashboard/src/app/api/shopping-funnel/weekly-digest/route.ts` — weekly digest
- `dashboard/src/app/api/shopping-funnel/impact-tracker/route.ts` — optimization impact tracking
- `dashboard/src/app/api/shopping-funnel/evaluate-rules/route.ts` — automation rule evaluation

### Key Files NOT to Break
- `dashboard/src/lib/shopping-funnel/service.ts` — the live Google Ads integration. EXTEND, don't replace. Call its existing exports.
- `dashboard/src/app/(dashboard)/shopping-funnel/page.tsx` — the existing Needs Decision and Existing Funnel tabs work and are used daily. Only modify the Tier Movements tab and add new visualization tabs.
- All existing API routes under `/api/search-terms/` — these power the working Shopping Funnel management system.
- All existing API routes under `/api/ga4/` — these power the attribution quality monitoring.
- `dashboard/src/lib/intent/policy.ts` and `tier-movement.ts` — the execution pipeline. Use as-is.

### Skills Catalog Cross-Reference

The following skills from the strategic assessment (Part 8) are prerequisites or enablers for specific phases:

| Skill | Prerequisite For | Notes |
|-------|-----------------|-------|
| `google-shopping-content` | v1.3a (before this milestone) | Content quality directly affects CTR/CVR signals this milestone optimizes |
| `bing-shopping-content` | v1.3a (before this milestone) | Same — platform-specific content quality |
| `product-storytelling` | v1.3a (before this milestone) | Differentiation and emotional resonance improve the signals we measure |
| `competitor-research` | Phase 2 (Competitive Intel) | Competitor research skill enriches the competitive intelligence analysis |
| `feed-optimization` | Phase 1-2 (Tier Optimization) | Feed optimization best practices inform tier scoring and demand gap analysis |

**Key dependency**: The content generation skills (`google-shopping-content`, `bing-shopping-content`, `product-storytelling`) must be created and applied during v1.3a. Without improved content, the optimization signals this milestone computes will reflect description quality as much as placement quality — making recommendations noisy and less actionable.

### Performance Considerations
- Google Ads API has rate limits. The 2-minute cache in service.ts handles interactive use. For batch scoring computations, run server-side in API routes using a single call to `getExistingFunnelTerms()` (which caches the 6-query result).
- Heavy computations (tier distributions, percentile calculations, impact estimates) MUST happen server-side in API routes, not client-side
- Persist computed scores to `query_value_scores` and recommendations to `routing_recommendations` tables to avoid recomputing on every page load
- Use `keyword_metrics` table for market data (cached with 30-day TTL) — don't call Keyword Planner API directly from the dashboard

### Success Metrics
- Operators should be able to identify $X,000/month in revenue leakage within 5 minutes of opening the dashboard
- Every recommendation must show a dollar-value estimate (not abstract scores like "impact: 0.73")
- Tier movement recommendations should have >70% operator approval rate (measured via `routing_recommendations` accept/reject tracking)
- The system should surface at least 10 actionable insights per product group per month
- Revenue leakage page should load in <3 seconds (use cached service.ts data + persisted scores)
