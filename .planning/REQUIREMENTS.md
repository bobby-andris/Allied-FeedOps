# Requirements: Allied FeedOps v1.3c

**Defined:** 2026-02-25
**Core Value:** Transform low-performing product feeds into high-converting assets through data-driven content optimization at scale

## v1.3c Requirements

Requirements for Actionable Shopping Intelligence milestone. Each maps to roadmap phases.

### Operational Prerequisites

- [ ] **OPS-01**: Cloud Scheduler activated for funnel_snapshots_daily capture (CRON_SECRET configured, setup script run)
- [ ] **OPS-02**: funnel_snapshots_daily table re-backfilled with historical data and verified non-empty
- [ ] **OPS-03**: query_value_scores table schema extended with tier_fit_scores JSONB, recommended_tier, net_monthly_impact, scored_at columns
- [ ] **OPS-04**: experiment_outcomes table schema extended with p_value, confidence_interval, and minimum_sample_size columns

### Tier Scoring

- [x] **TIER-01**: User can view dynamically computed tier performance distributions (p25/p50/p75 ROAS/CVR/CPC/CTR per tier) replacing hardcoded 3.6/3.1/2.6 thresholds
- [x] **TIER-02**: User can see tier boundary thresholds that auto-adjust based on actual MEDIUM tier percentiles (LOW floor = MEDIUM p75, HIGH ceiling = MEDIUM p25)
- [x] **TIER-03**: User can view per-term scoring with robust z-scores (median/MAD) accounting for right-skewed ROAS distributions
- [ ] **TIER-04**: User can see hierarchical fallback scoring when per-group data is sparse (per-group → global → sensible defaults)
- [ ] **TIER-05**: User can see "Insufficient data" degraded state when a tier has fewer than 5 terms with non-zero metrics
- [ ] **TIER-06**: User can view confidence scores based on data volume, consistency, statistical significance, and NLP intent alignment

### Revenue Leakage

- [ ] **LEAK-01**: User can see total revenue leakage estimate as a hero number showing a range with confidence coloring
- [ ] **LEAK-02**: User can view misplaced terms sorted by dollar impact with revenue estimate ranges (not point values) and reason codes
- [ ] **LEAK-03**: User can view wasted spend alerts for terms with zero conversions and high spend, with Block/Demote action buttons
- [ ] **LEAK-04**: User can view under-invested winners showing impression share gap (actual vs Keyword Planner market) with potential revenue gain
- [ ] **LEAK-05**: User can view tier ROAS distribution box plots showing overlap zones between tiers
- [ ] **LEAK-06**: User can see "Last computed" timestamp on all revenue leakage data

### Execution

- [ ] **EXEC-01**: User can approve/reject individual tier movement recommendations with one click
- [ ] **EXEC-02**: User can batch-approve all high-confidence recommendations (confidence > 0.80) in one action
- [ ] **EXEC-03**: User can undo a tier movement using negative_registry audit trail and criterion IDs
- [ ] **EXEC-04**: User can view movement history from policy_action_execution_log
- [ ] **EXEC-05**: Recommendations persist to routing_recommendations table for asynchronous operator review

### Demand Intelligence

- [ ] **DEMAND-01**: User can view impression share gaps (actual impressions vs Keyword Planner avg_monthly_searches) per term
- [ ] **DEMAND-02**: User can view CPC opportunity scores showing headroom between actual CPC and Keyword Planner high_top_of_page_bid
- [ ] **DEMAND-03**: User can view seasonal demand patterns from monthly_search_volumes with terms spiking or declining >20% flagged
- [ ] **DEMAND-04**: User can view new term discovery rate (terms appearing for first time in last 7 days)
- [ ] **DEMAND-05**: User can view brand vs non-brand revenue split using NLP decomposition
- [ ] **DEMAND-06**: User can view competitor mention tracking per competitor token (moen, delta, kohler, etc.) with impressions, spend, conversions
- [ ] **DEMAND-07**: User can view long-tail vs head term analysis grouped by word count with ROAS/CVR comparison

### Product Intelligence

- [ ] **PROD-01**: User can view all 59 product groups classified into BCG quadrants (Stars/Cash Cows/Question Marks/Dogs) based on ROAS and revenue medians
- [ ] **PROD-02**: User can interact with bubble chart visualization (X: ROAS, Y: Revenue, Size: Spend, Color: Trend)
- [ ] **PROD-03**: User can click a product group bubble to drill down to term-level breakdown
- [ ] **PROD-04**: User can view tabular alternative to bubble chart with sortable columns

### Automation

- [ ] **AUTO-01**: User can define automated tier rebalancing rules with configurable conditions (ROAS threshold, days, tier, action)
- [ ] **AUTO-02**: User can preview rule effects via dry-run mode before enabling
- [ ] **AUTO-03**: Automation system enforces hard guardrails: max simultaneous movements cap, total spend impact limit per batch, 7-day cooldown per term
- [ ] **AUTO-04**: Automation system includes circuit breaker: auto-halt if ROAS drops >15% in 3 days or conversions drop >20% WoW
- [ ] **AUTO-05**: User can schedule automated rule evaluation via Cloud Scheduler endpoint

### Experiments

- [ ] **EXP-01**: User can register an experiment with hypothesis, term set, duration, and success metric
- [ ] **EXP-02**: User can split terms into treatment and control groups stored in experiment_assignments
- [ ] **EXP-03**: System executes treatment group tier movements via existing executeTierMovementBatch()
- [ ] **EXP-04**: System enforces minimum sample size based on conversion volume and detectable effect size
- [ ] **EXP-05**: System computes treatment vs control metrics with statistical significance (p-value, confidence interval)
- [ ] **EXP-06**: System locks experiment terms from other movements during active experiments

### Budget & Benchmarks

- [ ] **BUDGET-01**: User can view budget allocation recommendations showing spend shifts from Dogs to Cash Cows with monthly revenue estimates
- [ ] **BUDGET-02**: User can view total addressable market per product group using Keyword Planner avg_monthly_searches

### Reporting

- [ ] **RPT-01**: User can view optimization impact tracker with before/after performance for each tier movement and cumulative ROI timeline
- [ ] **RPT-02**: User can view weekly digest with top/bottom 5 performers, new terms, actions taken, and recommended next actions
- [ ] **RPT-03**: User can view competitive benchmark comparing actual CPC vs market benchmark per product category
- [ ] **RPT-04**: User can identify categories with competitive advantage (below-market CPC + above-market CVR) vs overpaying categories

## Future Requirements

Deferred to v1.4+.

### Closed-Loop Optimization
- **LOOP-01**: Performance-informed content regeneration based on CTR/CVR outcomes
- **LOOP-02**: Cross-system learning (what prompt changes drove CTR improvement?)
- **LOOP-03**: Automated optimization cycles (daily/weekly/monthly content refresh)

### Advanced Analytics
- **ADV-01**: DiD (difference-in-differences) compute pipeline for performance_impact_scores
- **ADV-02**: Attribution confidence scoring per term
- **ADV-03**: Order-line-level margin analysis (requires sku_margin_daily table)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time streaming data | Batch collection + 2-min cache sufficient for operator workflows |
| Multi-account Google Ads | Single account (6253381786) — no multi-tenant needed |
| Mobile app | Web dashboard sufficient for operator use case |
| Merchant API migration | Content API works until Aug 2026 |
| Direct Keyword Planner API calls from dashboard | Use cached keyword_metrics table (30-day TTL) instead |
| Custom ML models for scoring | simple-statistics percentile/z-score approach sufficient; ML adds complexity without clear ROI |
| Real-time automation (sub-hour) | Daily/weekly rule evaluation sufficient; sub-hour creates risk without proportional benefit |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| OPS-01 | Phase 32 | Pending |
| OPS-02 | Phase 32 | Pending |
| OPS-03 | Phase 32 | Pending |
| OPS-04 | Phase 32 | Pending |
| TIER-01 | Phase 33 | Complete |
| TIER-02 | Phase 33 | Complete |
| TIER-03 | Phase 33 | Complete |
| TIER-04 | Phase 33 | Pending |
| TIER-05 | Phase 33 | Pending |
| TIER-06 | Phase 33 | Pending |
| LEAK-01 | Phase 34 | Pending |
| LEAK-02 | Phase 34 | Pending |
| LEAK-03 | Phase 34 | Pending |
| LEAK-04 | Phase 34 | Pending |
| LEAK-05 | Phase 34 | Pending |
| LEAK-06 | Phase 34 | Pending |
| EXEC-01 | Phase 34 | Pending |
| EXEC-02 | Phase 34 | Pending |
| EXEC-03 | Phase 34 | Pending |
| EXEC-04 | Phase 34 | Pending |
| EXEC-05 | Phase 34 | Pending |
| DEMAND-01 | Phase 35 | Pending |
| DEMAND-02 | Phase 35 | Pending |
| DEMAND-03 | Phase 35 | Pending |
| DEMAND-04 | Phase 35 | Pending |
| DEMAND-05 | Phase 35 | Pending |
| DEMAND-06 | Phase 35 | Pending |
| DEMAND-07 | Phase 35 | Pending |
| PROD-01 | Phase 35 | Pending |
| PROD-02 | Phase 35 | Pending |
| PROD-03 | Phase 35 | Pending |
| PROD-04 | Phase 35 | Pending |
| AUTO-01 | Phase 36 | Pending |
| AUTO-02 | Phase 36 | Pending |
| AUTO-03 | Phase 36 | Pending |
| AUTO-04 | Phase 36 | Pending |
| AUTO-05 | Phase 36 | Pending |
| EXP-01 | Phase 36 | Pending |
| EXP-02 | Phase 36 | Pending |
| EXP-03 | Phase 36 | Pending |
| EXP-04 | Phase 36 | Pending |
| EXP-05 | Phase 36 | Pending |
| EXP-06 | Phase 36 | Pending |
| BUDGET-01 | Phase 37 | Pending |
| BUDGET-02 | Phase 37 | Pending |
| RPT-01 | Phase 37 | Pending |
| RPT-02 | Phase 37 | Pending |
| RPT-03 | Phase 37 | Pending |
| RPT-04 | Phase 37 | Pending |

**Coverage:**
- v1.3c requirements: 49 total
- Mapped to phases: 49
- Unmapped: 0

---
*Requirements defined: 2026-02-25*
*Last updated: 2026-02-25 after roadmap creation*
