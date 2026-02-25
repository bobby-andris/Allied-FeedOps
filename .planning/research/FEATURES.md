# Feature Landscape: v1.3c Actionable Shopping Intelligence

**Domain:** Google Shopping tier optimization intelligence system
**Researched:** 2026-02-25
**Confidence:** HIGH -- based on existing spec review, codebase analysis, and ecosystem research

---

## Context: What Already Exists (DO NOT REBUILD)

Before categorizing new features, here is the infrastructure this milestone builds on:

| Existing Asset | Location | Status |
|---|---|---|
| 3-tier Shopping funnel (HIGH/MEDIUM/LOW) | 177 campaigns, 59 product groups | Working, used daily |
| Live Google Ads integration | `service.ts` (6 parallel GAQL queries, 2-min cache) | Working |
| NLP search term decomposition | `query-intelligence.ts` (brand/competitor/product detection) | Working -- KEEP the NLP, REPLACE the scoring |
| Hardcoded tier scoring | `query-intelligence.ts` line 138 (ROAS 3.6/3.1/2.6, CVR 5%/3%) | Working but produces zero useful recommendations |
| ROAS recommendations | `control-center.ts` (bounded +/-10% changes, confidence from volume) | Working but uses hardcoded baselines |
| Opportunity clustering | `control-center.ts` (`buildOpportunityClusters()`) | Working for unassigned terms only |
| Tier movement execution pipeline | `policy.ts` + `tier-movement.ts` (with dry-run support) | Working, logs to `policy_action_execution_log` |
| Guardrail evaluation | `policy.ts` (`evaluateGuardrails()`) | Working but uses hardcoded thresholds |
| Intent policy engine | `policy.ts` (`evaluatePromotionDemotion()`) | Working but hardcoded thresholds (line 20-41) |
| Experiment tables | `experiment_registry`, `experiment_assignments`, `experiment_outcomes` | KEEP'd, empty, ready |
| Optimization control plane tables | `routing_recommendations`, `query_value_scores`, `opportunity_clusters` | Exist, empty |
| Funnel snapshots | `funnel_snapshots_daily` with capture/trends/backfill endpoints | Schema ready, needs re-backfill + scheduler activation |
| Content Impact dashboard | `/content-impact` landing + detail pages | Working |
| All 10 KEEP'd 035b tables | `term_intent_state`, `policy_decision_log`, etc. | Confirmed in production, empty |

---

## Table Stakes

Features operators expect from a Shopping intelligence system. Missing = system feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|-------------|-------|
| **Distribution-based tier boundaries** | Hardcoded ROAS 3.6/3.1/2.6 and CVR 5%/3% produce zero recommendations because they don't match actual performance distributions. Every serious optimization tool computes thresholds from real data. This is THE reason the Tier Movements Panel shows "0 recommendations." | Medium | `getLabelTierPerformance()`, `getExistingFunnelTerms()` from service.ts | Replace constants in `query-intelligence.ts` (line 138), `control-center.ts` (line 3-7), and `policy.ts` (lines 20-41). New file: `tier-scoring.ts` |
| **Dollar-value impact estimates on every recommendation** | Abstract scores ("impact: 0.73") are meaningless to operators. Every recommendation must show "~$X/month" to be actionable. Industry standard for any optimization tool claiming to surface revenue. | Medium | Tier-level avg CVR, avg CPC, avg AOV from live data | Current `scoreNeedsDecisionTerm()` returns `expected_profit_proxy` but not dollar estimates for tier movements. Formula: `(target_tier_avg_cvr - current_tier_avg_cvr) * current_impressions * target_tier_avg_aov` |
| **Multi-factor confidence scoring** | Low-volume terms (5 clicks) should not get same treatment as high-volume terms (500 clicks). Current confidence is simplistic (`clicks/50` or `clicks/500 * 0.5 + conversions/20 * 0.5`). Need data volume + consistency + statistical significance + NLP alignment. | Low | Click/conversion counts already available | Four-factor model: data volume (30%), consistency via CoV (30%), statistical significance (20%), NLP intent alignment (20%) |
| **Misplaced term detection with z-scores** | Terms performing significantly above/below their tier average are the primary revenue leakage source. Z-score > 1.5 = promotion candidate, < -1.5 = demotion candidate. Standard statistical approach, transparent and auditable. | Medium | Distribution engine, term-level ROAS per tier | Core of the revenue leakage analysis. For each term: compute z-score of its ROAS relative to current tier's ROAS distribution. Term belongs in tier where z-score is closest to 0. |
| **Wasted spend alerts** | Terms with spend but zero conversions over 30 days are obvious waste. Every Google Ads optimization tool surfaces these. Simple filter, high value. | Low | Existing funnel term data | Filter: cost > $5 AND conversions = 0 AND period >= 30 days. Suggest "block" or "demote." |
| **One-click tier movement execution** | Recommendations without execution are just reports. Existing `executeTierMovementBatch()` pipeline already works -- just needs UI wiring. | Low | `POST /api/shopping-funnel/tier-movement` (exists), `routing_recommendations` table (exists) | Wire approve/reject buttons to existing API. Persist to `routing_recommendations` with accept/reject/expire workflow. Mostly UI plumbing. |
| **Movement history with undo** | Operators need to see what changed and reverse mistakes. Both `negative_registry` and `policy_action_execution_log` tables exist and store criterion IDs. | Low | KEEP'd 035b tables (confirmed in production, empty) | Tables exist. Populate on movement execution. Undo = re-add/remove the negative keyword using stored criterion ID. |
| **Dry-run mode for all automated actions** | Operators will not trust automation without previewing effects first. `executeTierMovementBatch(dryRun: true)` already supported in pipeline. | Low | Existing tier-movement pipeline | Already built. Table stakes for any automation system. Just surface in UI. |
| **Recommendation persistence across page loads** | Computed recommendations must survive page refreshes. `routing_recommendations` table exists (migration 033) with `pending/accepted/rejected/expired` status workflow. | Low | Supabase `routing_recommendations` table | Write on computation, read on page load. Include expiry (recommendations older than 7 days should auto-expire if performance data changed). |
| **Product group performance overview table** | Per-group ROAS/spend/revenue aggregation across tiers. Foundation for strategic decisions. `getLabelTierPerformance()` already returns this data. | Low | Existing service.ts function | Basic sortable table view for 59 product groups. Foundation for BCG matrix (differentiator). |

---

## Differentiators

Features that elevate this beyond a basic optimization tool. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|-------------|-------|
| **Revenue leakage hero number** | Single number at top of dashboard: "$X,XXX/month in detected revenue leakage." Quantifies the value of the optimization system itself. Powerful for executive buy-in. | Low | Sum of all misplaced-term `net_monthly_impact` estimates | Few tools do this. Requires distribution engine to be accurate. Update on every page load from cached recommendation data. |
| **Adaptive tier boundaries that auto-update** | Boundaries recompute from live data on every API call, not set once and forgotten. After v1.3a content improvements, performance distributions will shift -- static thresholds become stale within weeks. | Medium | Distribution engine, `funnel_snapshots_daily` for trend comparison | Key differentiator: thresholds evolve with the business. Seasonal shifts, content quality changes, and market dynamics all reflected automatically. |
| **Under-invested winner detection** | High-CVR terms with low impression share = money left on table. Cross-references `search_queries.impressions` with `keyword_metrics.avg_monthly_searches` to compute impression share gap. | Medium | `search_queries` + `keyword_metrics` tables (both populated) | Impression share = actual_impressions / avg_monthly_searches. Terms with CVR > tier median but impression share < 30% are under-invested. Unique because it leverages Keyword Planner data most tools ignore. |
| **BCG product group matrix** | Quadrant chart (Stars/Cash Cows/Question Marks/Dogs) for 59 product groups. Standard portfolio analysis adapted for Shopping campaigns. | Medium | `getLabelTierPerformance()` aggregated across tiers | Bubble chart: X=ROAS, Y=Revenue, Size=Spend, Color=Trend (improving/declining). Click bubble to drill down to term-level. Quadrant boundaries at median ROAS and median revenue. |
| **Seasonal demand forecasting** | Use `keyword_metrics.monthly_search_volumes` (JSONB array of {year, month, monthly_searches}) to predict demand spikes 1-2 months ahead. Proactive bidding. | Medium | `keyword_metrics` table (populated with monthly breakdown) | Month-over-month growth rate. Flag terms with >20% change in upcoming period. "Towel bar searches typically spike 40% in May -- increase bids proactively." |
| **Competitor conquest tracking** | Group all competitor-mentioning search terms (16 competitor tokens in NLP) by competitor brand. Show per-competitor: term count, impressions, spend, revenue, ROAS. | Low | `decomposeSearchTerm().is_competitor` (exists) | "Moen-related queries: 45 terms, $230 spend, $890 revenue, 3.87 ROAS." Directly actionable for conquest bidding strategy. |
| **Brand vs non-brand revenue split** | Quantify brand dependency. If 80% of revenue is branded, non-brand optimization has massive headroom. Strategic insight for growth planning. | Low | `decomposeSearchTerm().is_branded` (exists) | Simple aggregation. brand_revenue / total_revenue = brand_share. Track over time to measure non-brand growth. |
| **Long-tail vs head term analysis** | Group terms by word count (1-2=head, 3-4=mid, 5+=long-tail). Long-tail typically converts 2-3x better. Quantify the actual difference for this catalog. | Low | Existing term data | Simple word count grouping. Per bucket: term count, spend, revenue, avg ROAS, avg CVR. Informs whether to invest more in long-tail targeting. |
| **CPC opportunity scoring** | Terms where actual CPC is well below `keyword_metrics.high_top_of_page_bid_micros`. Headroom exists to bid more aggressively while remaining profitable. | Low | `search_queries` + `keyword_metrics` tables | Score = (high_top_of_page_bid - actual_cpc) / high_top_of_page_bid. High score = room to grow. Low complexity, high actionability. |
| **Competitive benchmark overlay** | Our CPC vs market benchmark CPC (from Keyword Planner) per product category. Shows where Allied Brass has competitive advantage vs where it's overpaying. | Low | `keyword_metrics.high_top_of_page_bid_micros`, `keyword_metrics.competition_index` | Category-level comparison. "Towel Bars: our CPC $0.85 vs market $1.40 -- competitive advantage. Soap Dispensers: our CPC $1.10 vs market $0.70 -- overpaying." |
| **Automated tier rebalancing rules** | Configurable rules engine: "If ROAS > X for Y+ days in tier Z, auto-promote." Dry-run first, then human-approved batch, then fully automated with guardrails. | High | `automation_rules` table (new), Cloud Scheduler, guardrail system in policy.ts | Three-stage rollout: (1) dry-run only, (2) human-approved batch, (3) auto with circuit breakers. Requires careful guardrail design. |
| **A/B testing for tier assignments** | Split terms into treatment (move to new tier) and control (keep current). Measure impact with statistical significance after N days. | High | `experiment_registry`, `experiment_assignments`, `experiment_outcomes` (KEEP'd, empty) | Google recommends 50+ conversions per arm minimum. For Allied Brass volumes (~3K terms, moderate conversion rates), experiments need 4+ week runtimes and careful term selection for statistical power. |
| **Optimization impact tracker** | Before/after measurement of every tier movement. "Tier optimization has generated $X,XXX in additional revenue this month." Proves ROI of the system. | Medium | `policy_action_execution_log`, `performance_snapshots` | Link movements to subsequent performance. Requires 7-14 day measurement lag. Cumulative timeline chart. |
| **Executive weekly digest** | Auto-generated summary: top 5 performers, top 5 decliners, new terms discovered, actions taken, recommended actions for next week. | Medium | All scoring/recommendation APIs | Computation layer on existing APIs. Dashboard page, not email (avoid notification infrastructure overhead). |

---

## Anti-Features

Features to explicitly NOT build. Scope control is critical for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real-time streaming dashboard** | Massive infrastructure overhead. Google Ads data has 3+ hour reporting delay anyway. service.ts 2-min cache is sufficient for decision-making. | Batch computation on page load with persistence to `routing_recommendations`. Manual refresh button. |
| **Automated budget management** | Budget changes have immediate financial impact. Too risky without extensive guardrails. Google's Smart Bidding handles intra-campaign budget allocation better. | Surface budget allocation RECOMMENDATIONS only. "Consider shifting $X/day from Dogs to Cash Cows." Never auto-execute budget changes. |
| **ML-based tier prediction models** | Over-engineering for ~3K terms. Z-score against distribution is statistically sound, interpretable, and auditable. ML adds opaque complexity, needs training data (tables are empty), and provides marginal accuracy gains at this data volume. | Percentile-based distribution scoring with z-scores. Transparent, correct, and automatically adaptive. |
| **Automated negative keyword management without human review** | Adding wrong negatives can block profitable traffic permanently. Catastrophic failure mode. Even Google's own tools require review for negatives. | Always require human approval for negatives. Dry-run first. Batch approval only for high-confidence (>0.85) recommendations. |
| **Email/Slack notifications** | Infrastructure overhead for notification delivery when the dashboard is the primary (and only) interface. Premature optimization of communication channel. | Weekly digest page on dashboard. Revisit notifications in v1.4 if operators explicitly request them. |
| **Custom report builder / drag-and-drop dashboards** | Generic BI tool territory. Looker Studio, Google Sheets, or Tableau handle custom reporting better than a purpose-built optimization tool. | Fixed scorecard views optimized for the specific decisions operators need to make. Export to CSV for custom analysis. |
| **Performance Max migration analysis** | PMax has fundamentally different optimization levers (audience signals, creative assets, no manual tier control). Allied Brass's manual Shopping structure provides more control for this catalog size. | Stay on Standard Shopping with priority bidding. Monitor PMax developments but don't migrate during this milestone. |
| **Cross-account Google Ads management** | Single account (6253381786). Multi-account adds massive architecture complexity for zero current value. | Keep single-account assumption throughout. Architecture doesn't preclude future expansion if needed. |
| **Native Google Ads campaign experiments** | Only works with Performance Max campaigns. Allied Brass uses Standard Shopping with manual tier structure. Campaign-level experiments can't test individual term-level tier assignments. | Build custom experiment framework using existing 035b tables. More granular than Google's native experiments for this use case. |

---

## Feature Dependencies

```
Distribution-based scoring engine (Phase 1, core)
  |
  +--> Misplaced term detection (Phase 1)
  |      |
  |      +--> Revenue leakage hero number (Phase 1)
  |      +--> Dollar-value impact estimates (Phase 1)
  |
  +--> Wasted spend alerts (Phase 1)
  |
  +--> Under-invested winner detection (Phase 2, also needs keyword_metrics)
  |
  +--> Adaptive tier boundaries (Phase 1, also needs funnel_snapshots_daily)
  |
  +--> ROAS recommendations with dynamic baselines (Phase 1, replaces hardcoded in control-center.ts)

One-click execution wiring (Phase 1)
  |
  +--> Movement history + undo (Phase 1)
  +--> Recommendation persistence (Phase 1)

Product group performance overview (Phase 2)
  |
  +--> BCG matrix visualization (Phase 2)
  +--> Budget allocation recommendations (Phase 3)

Competitor conquest tracking (Phase 2)
  +--> Competitive benchmark overlay (Phase 4)

Brand/non-brand split (Phase 2, standalone)
Long-tail analysis (Phase 2, standalone)
CPC opportunity scoring (Phase 2, standalone)
Seasonal demand patterns (Phase 2, standalone)

Distribution engine (Phase 1) + Movement history (Phase 1)
  |
  +--> Automated tier rebalancing rules (Phase 3)
  +--> A/B testing framework (Phase 3)

All Phase 1-3 APIs
  |
  +--> Executive weekly digest (Phase 4)
  +--> Optimization impact tracker (Phase 4)
```

**Critical path:** Distribution engine --> Misplaced terms --> Dollar estimates --> Execution wiring --> Movement history

Everything else branches from the distribution engine. It is the single most important feature to build first.

---

## MVP Recommendation

**Phase 1 -- Revenue Leakage Detection and Tier Optimization (highest value, lowest risk):**
1. Distribution-based tier boundaries in new `tier-scoring.ts` -- unlocks everything else
2. Misplaced term detection with z-score analysis -- the core value proposition
3. Dollar-value impact estimates on every recommendation
4. Wasted spend alerts -- easy wins, immediate value
5. Revenue leakage hero number -- quantifies system value
6. One-click execution wiring to existing pipeline
7. Movement history + undo capability
8. Recommendation persistence to `routing_recommendations`

**Phase 2 -- Market Intelligence and Demand Gap Analysis (medium complexity, strategic value):**
9. Product group BCG matrix with drill-down
10. Competitor conquest tracking + brand/non-brand split
11. Under-invested winner detection + CPC opportunity scoring
12. Seasonal demand pattern analysis
13. Long-tail vs head term analysis
14. Competitive benchmark overlay

**Phase 3 -- Intelligent Automation (highest risk, requires Phase 1 operational data):**
15. Automated tier rebalancing rules with three-stage rollout
16. A/B testing framework with experiment lifecycle

**Phase 4 -- Executive Reporting (depends on all above):**
17. Optimization impact tracker -- proves ROI
18. Executive weekly digest
19. Competitive benchmarks scorecard

**Defer to v1.4:**
- Full automation without human review
- Email/Slack notifications
- ML-based prediction models
- Content-informed regeneration based on tier performance

---

## Scoring Approach Details

### Distribution-Based Scoring (recommended approach)

**Why percentile-based, not ML:** For approximately 3,000 search terms across 59 product groups, percentile-based scoring is the right tool. ML models need training data (which doesn't exist -- tables are empty), add interpretability problems, and provide marginal accuracy gains over statistical methods at this data volume. Z-scores against tier distributions are transparent, auditable, and automatically adaptive as performance shifts.

**How it works:**
1. Call `getLabelTierPerformance()` for tier-level aggregates (spend, revenue, conversions, clicks per tier per product group)
2. Call `getExistingFunnelTerms()` for term-level metrics within each tier
3. For each tier (HIGH/MEDIUM/LOW), compute ROAS distribution: p25, p50 (median), p75, mean, standard deviation
4. Dynamic tier boundary computation:
   - LOW tier floor = MEDIUM tier p75 ROAS (above 75th percentile of MEDIUM = belongs in LOW)
   - HIGH tier ceiling = MEDIUM tier p25 ROAS (below 25th percentile of MEDIUM = belongs in HIGH)
5. For each term, compute z-score = (term_ROAS - tier_mean_ROAS) / tier_stddev_ROAS
6. Term belongs in the tier where its z-score is closest to 0 (best fit)
7. z-score > 1.5 in current tier = strong promotion candidate
8. z-score < -1.5 in current tier = strong demotion candidate
9. Impact estimate = (target_tier_avg_cvr - current_tier_avg_cvr) x current_impressions x target_tier_avg_aov

**Bayesian smoothing for low-volume terms:**
- Add 0.5 pseudo-conversions and proportional pseudo-cost to prevent division by zero
- Formula: smoothed_cvr = (conversions + 0.5) / (clicks + (0.5 / tier_avg_cvr))
- Apply when term has < 20 clicks to stabilize estimates
- Do NOT apply for terms with 50+ clicks (sufficient real data)

### Confidence Thresholds (industry-aligned)

| Confidence Level | Criteria | Use |
|-----------------|---------|-----|
| HIGH (> 0.80) | 100+ clicks, 5+ conversions, daily ROAS CoV < 0.5 | Safe for batch auto-approval |
| MEDIUM (0.50-0.80) | 30-100 clicks, 1-5 conversions | Require individual operator review |
| LOW (< 0.50) | < 30 clicks, 0-1 conversions | Show as informational only, no action buttons |
| Auto-execution minimum | 0.70 | Threshold for automated rule execution |
| Batch auto-approve minimum | 0.85 | Threshold for "Approve All High-Confidence" button |

**Four-factor confidence model:**
- Data volume: min(clicks / 100, 1) x 0.30
- Consistency: (1 - coefficient_of_variation_of_daily_ROAS) x 0.30, clamped to [0, 1]
- Statistical significance: chi-squared test p-value for conversion rate difference x 0.20
- NLP intent alignment: does term's intent features match target tier semantics? x 0.20

### Guardrail Patterns for Automation

**Three-tier safety model (standard in automated campaign management):**

**1. Hard guardrails (never overridable):**
- Maximum daily spend change: 10% of current tier spend
- Maximum terms moved per day: 5% of tier term count
- No movements for terms with < 30 clicks (insufficient data)
- No promotions to LOW tier (highest bid) without 3+ conversions
- Mandatory 7-day cooldown after any movement before re-evaluation
- Never auto-block branded terms

**2. Soft guardrails (operator can override with confirmation):**
- Confidence threshold for auto-execution: 0.85 (configurable)
- Maximum dollar impact per single movement: $500/month estimated
- Seasonal override: disable automation during known demand spikes (configurable dates)
- Warn if moving competitor-mentioning terms between tiers

**3. Circuit breakers (automatic halt + alert):**
- If overall ROAS drops > 15% across any tier in 3 consecutive days, halt all automated movements
- If total conversions drop > 20% week-over-week, halt all automated movements
- If > 10 automated movements in a day produce negative impact (measured after 7-day lag), halt and require manual review
- Circuit breaker reset: manual operator action required, cannot auto-resume

### A/B Testing Sizing Guidance

**Google's recommendation:** 50+ conversions per arm for statistical significance (from Demand Gen experiment documentation). Their experiments use Jackknife resampling with 20 buckets per arm.

**For Allied Brass:** With moderate conversion volumes across 3K terms, experiment sizing requires:
- Select high-volume terms (50+ clicks/month) for experiments
- Minimum 4-week runtime (Google's recommendation for Shopping campaigns)
- 50/50 traffic split for maximum statistical power
- Target 95% confidence level (p < 0.05) for declaring winners
- Use cluster analysis to create balanced treatment/control groups based on historical performance

### Visualization Patterns for Revenue Leakage

**Hero metric (top of page):** Large number "$4,200/month in revenue leakage" with trend arrow vs previous computation. Green if leakage is shrinking (movements are working), red if growing. This answers "why should I care?" in 2 seconds.

**Tier ROAS distribution box plots:** Show ROAS distribution per tier as side-by-side box plots. Overlapping regions between tiers are visually the "leakage zones" where terms are misplaced. Intuitive visualization of the statistical problem.

**Waterfall chart for cumulative impact:** Start with current revenue. Add each recommended movement's estimated impact as a step. End with projected revenue if all recommendations are executed. Classic financial visualization, familiar to executives.

**Sortable recommendation table (primary interaction surface):** Columns: search term, current tier, recommended tier, dollar impact, confidence, action buttons (approve/reject/defer). Default sort by dollar impact descending. Batch approve/reject with "Select All High-Confidence" button.

**BCG bubble chart for product groups:** X=ROAS, Y=Revenue, Bubble size=Spend, Color=Trend (green=improving, red=declining). Four labeled quadrants. Click any bubble for term-level drill-down. Toggle between chart and table view for operators who prefer tabular data.

---

## Complexity Estimates

| Feature | New Code (est.) | Calendar Days | Risk Level |
|---------|----------------|---------------|------------|
| Distribution engine + scoring (`tier-scoring.ts`) | 300-400 lines | 2-3 | LOW -- math is well-understood, data sources exist |
| Revenue leakage API route + response shape | 200-300 lines | 1-2 | LOW -- computation layer on existing data |
| Revenue leakage UI (hero, table, box plots) | 400-500 lines | 2-3 | LOW -- shadcn/ui components, familiar patterns |
| One-click execution + movement history UI | 100-150 lines of changes | 1 | LOW -- backend pipeline exists, just wiring |
| Product group BCG matrix API + chart | 200 API + 300 UI | 2-3 | MEDIUM -- chart library selection, drill-down UX |
| Competitive intel + demand gaps APIs | 300 lines across 3-4 route files | 2-3 | LOW -- data and NLP decomposition exist |
| Competitive intel + demand gaps UI | 400-500 lines | 2-3 | LOW -- tables and simple visualizations |
| Automation rules engine + table + UI | 400-500 new | 3-4 | HIGH -- guardrail design is critical, three-stage rollout |
| A/B testing framework (lifecycle + UI) | 500-600 new | 4-5 | HIGH -- statistical rigor, experiment sizing, measurement lag |
| Impact tracker + weekly digest APIs | 300 lines | 2-3 | MEDIUM -- delayed measurement requires careful date math |
| Impact tracker + digest UI | 300 lines | 1-2 | LOW -- scorecard layout |

**Total estimate:** 18-25 developer days across all 4 phases.

---

## Sources

**Ecosystem research:**
- [DataFeedWatch: Priority Bidding for Shopping ROAS](https://www.datafeedwatch.com/blog/how-to-increase-google-shopping-roas) -- tiered campaign structure patterns
- [Channable: Shopping bidding strategies 2026](https://www.channable.com/blog/bidding-strategies) -- target ROAS best practices, exploration budgets
- [Store Growers: Shopping Ads Benchmarks 2026](https://www.storegrowers.com/shopping-ads-benchmarks/) -- industry ROAS/CPC/CTR benchmarks
- [Google Ads Help: Automated bidding for Shopping](https://support.google.com/google-ads/answer/6309029?hl=en) -- Google's own guardrail documentation
- [Google Ads Help: Statistical methodology behind experiments](https://support.google.com/google-ads/answer/9232676?hl=en) -- Jackknife resampling, 20 buckets
- [Google Ads Help: Demand Gen A/B experiments](https://support.google.com/google-ads/answer/13719071?hl=en) -- 50 conversion minimum per arm
- [SearchEngineLand: When Google AI bidding breaks](https://searchengineland.com/google-ai-bidding-breaks-take-control-466251) -- guardrail failure modes
- [Optmyzr: Budget automation guardrails](https://www.optmyzr.com/bfcm-google-ads-2025-budget-automation-guide/) -- circuit breaker patterns
- [Practical Ecommerce: BCG Matrix for Ecommerce](https://www.practicalecommerce.com/Using-the-BCG-Matrix-for-Ecommerce-Marketing-Decisions) -- portfolio analysis methodology
- [Scube Marketing: Google Shopping bidding 44-point guide](https://www.scubemarketing.com/blog/google-shopping-bid-strategy) -- bid management best practices

**Codebase analysis:**
- `dashboard/src/lib/optimization/query-intelligence.ts` -- current hardcoded scoring (lines 116-145, 196-265)
- `dashboard/src/lib/optimization/control-center.ts` -- current ROAS recommendations (lines 3-7, 237-284)
- `dashboard/src/lib/intent/policy.ts` -- current guardrail system (lines 20-41)
- `dashboard/src/lib/intent/tier-movement.ts` -- execution pipeline
- `dashboard/src/lib/shopping-funnel/service.ts` -- live Google Ads data
- `dashboard/src/app/(dashboard)/shopping-funnel/TierMovementsPanel.tsx` -- current UI
- `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` -- existing spec (Phase 1-4 structure)
