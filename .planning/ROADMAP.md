# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** — API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** — Phases 05-08 (shipped 2026-02-13)
- ✅ **v1.1 Dashboard UX & Quality** — Phases 9-16 (shipped 2026-02-21)
- ✅ **v1.2 Impact Debug & Fix** — Phases 17-22 (shipped 2026-02-21)
- ✅ **v1.3a Content Generation Excellence** — Phases 23-27 (shipped 2026-02-25)
- ✅ **v1.3b Architecture Validation & Data Persistence** — Phases 28-31 (shipped 2026-02-25)
- 🚧 **v1.3c Actionable Shopping Intelligence** — Phases 32-37 (in progress)

## Phases

<details>
<summary>Phase 0 Discovery — SHIPPED 2026-02-13</summary>

- [x] Phase 01: API Capability Validation (2/2 plans) — 2026-02-12
- [x] Phase 02: Comprehensive Data Discovery (4/4 plans) — 2026-02-12
- [x] Phase 03: Sample Testing & Analysis (3/3 plans) — 2026-02-13
- [x] Phase 04: Documentation & Decision (2/2 plans) — 2026-02-13

</details>

<details>
<summary>v1.0 Historical Data Backfill — SHIPPED 2026-02-13</summary>

- [x] Phase 05: Job Infrastructure & Foundation (4/4 plans) — 2026-02-13
- [x] Phase 06: Data Collection Pipeline (3/3 plans) — 2026-02-13
- [x] Phase 07: Data Quality & Validation (4/4 plans) — 2026-02-13
- [x] Phase 08: Monitoring & Automation (5/5 plans) — 2026-02-13

</details>

<details>
<summary>v1.1 Dashboard UX & Quality — SHIPPED 2026-02-21</summary>

- [x] Phase 9: SKU Review Revamp (3/3 plans) — 2026-02-18
- [x] Phase 10: Image Workflow Improvements (3/3 plans) — 2026-02-19
- [x] Phase 11: Performance Page Enhancements (3/3 plans) — 2026-02-19
- [x] Phase 12: Dashboard Audit & Cleanup (3/3 plans) — 2026-02-19
- [x] Phase 13: Fix Google Ads Data Sourcing (3/3 plans) — 2026-02-19
- [x] Phase 14: Complete 180-day Backfill & Monitoring Fixes (3/3 plans) — 2026-02-19
- [x] Phase 15: Google Ads Data Backfill & Monitoring Verification (3/3 plans, partial) — 2026-02-20
- [x] Phase 16: Fix Google Ads Backfill Pipeline (3/3 plans) — 2026-02-20

</details>

<details>
<summary>v1.2 Impact Debug & Fix — SHIPPED 2026-02-21</summary>

- [x] Phase 17: Google Shopping Intelligence & Model Research (3/3 plans) — 2026-02-21
- [x] Phase 18: Diagnosis — Establish Ground Truth (3/3 plans) — 2026-02-21
- [x] Phase 19: Measurement Infrastructure (4/4 plans) — 2026-02-21
- [x] Phase 20: Targeted Fixes & Intelligence Application (4/4 plans) — 2026-02-21
- [x] Phase 21: Apply Database Migrations & Update Schema Docs (1/1 plan) — 2026-02-21
- [x] Phase 22: Fix Integration Bugs & Close Documentation Gaps (2/2 plans) — 2026-02-21

</details>

<details>
<summary>v1.3a Content Generation Excellence — SHIPPED 2026-02-25</summary>

- [x] Phase 23: Foundation (2/2 plans) — 2026-02-21
- [x] Phase 24: Prompt Architecture (2/2 plans) — 2026-02-21
- [x] Phase 25: Evaluate & Iterate (5/7 plans, 2 superseded) — 2026-02-23
- [x] Phase 25.1: Prompt Architecture Research (3/3 plans) — 2026-02-24
- [x] Phase 25.2: Per-Platform Generation Architecture (2/3 plans, 1 superseded) — 2026-02-24
- [x] Phase 25.3: Prompt Rewrite from Human Feedback (3/4 plans, 1 deferred) — 2026-02-24
- [x] Phase 25.4: Production Impact Audit (1/1 plan) — 2026-02-24
- [x] Phase 26: Human Evaluation & Test Batch (2/3 plans) — 2026-02-24
- Phase 27: Prompt Optimization (empty)

**Known gaps:** EVAL-03, EVAL-05, EVAL-06 accepted as tech debt.

</details>

<details>
<summary>v1.3b Architecture Validation & Data Persistence — SHIPPED 2026-02-25</summary>

- [x] Phase 28: Architecture Audit & Migration Triage (3/3 plans) — 2026-02-25
- [x] Phase 29: Content-Performance Feedback Linkage (3/3 plans) — 2026-02-25
- [x] Phase 30: Historical Funnel Persistence (3/3 plans) — 2026-02-25
- [x] Phase 30.1: Funnel Snapshot Backfill (1/1 plan) — 2026-02-25
- [x] Phase 31: Schema Cleanup & End-to-End Validation (3/3 plans) — 2026-02-25

**Tech debt:** 12 items (Cloud Scheduler activation, funnel re-backfill, DiD compute pipeline, prompt_hash backfill)

</details>

### v1.3c Actionable Shopping Intelligence (In Progress)

**Milestone Goal:** Transform the shopping funnel from passive reporting into an active revenue optimization engine with distribution-based scoring, dollar-value leakage detection, market intelligence, and semi-automated tier optimization with measurement.

- [x] **Phase 32: Operational Prerequisites** - Activate Cloud Scheduler, backfill funnel data, extend schemas for adaptive scoring and experiments (completed 2026-02-25)
- [x] **Phase 33: Tier Scoring Engine** - Distribution-based scoring with hierarchical fallback replacing hardcoded ROAS thresholds (completed 2026-02-25)
- [x] **Phase 33.1: Scoring Calibration** - Fix $0 impact bug, calibrate 95% misplaced rate down to actionable 10-20% (completed 2026-02-25)
- [x] **Phase 33.2: UI Redesign** - Redesign Tier Intelligence from statistical exploration to action-oriented decision-making (completed 2026-02-25)
- [x] **Phase 34: Revenue Leakage and Execution** - Dollar-value leakage dashboard with one-click tier movement execution and undo (completed 2026-02-26)
- [ ] **Phase 34.1: Fix Decision Logic** - Core scoring fixes, under-invested detection, label blocking (completed 2026-02-26)
- [ ] **Phase 34.2: Zero-Conversion Intent Scoring** - Dual-domain intent scoring (feed alignment + behavioral), terminology fix, execution wiring
- [ ] **Phase 35: Market Intelligence** - Demand gap analysis, competitive intel, product group BCG matrix, seasonal patterns
- [ ] **Phase 36: Automation and Experiments** - Rule-based tier rebalancing with safety guardrails and A/B testing framework
- [ ] **Phase 37: Reporting and Benchmarks** - Optimization impact tracker, weekly digest, competitive benchmarks, budget recommendations

## Phase Details

### Phase 32: Operational Prerequisites
**Goal**: All data infrastructure gaps from v1.3b tech debt are resolved so scoring and trend analysis operate on real data, not silent zeros
**Depends on**: Phase 31
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):
  1. Cloud Scheduler is running and `funnel_snapshots_daily` has rows from the last 7 days (verified via SQL count query)
  2. `query_value_scores` table has `tier_fit_scores`, `recommended_tier`, `net_monthly_impact`, and `scored_at` columns available
  3. `experiment_outcomes` table has `p_value`, `confidence_interval`, and `minimum_sample_size` columns available
**Plans**: TBD

### Phase 33: Tier Scoring Engine COMPLETE 2026-02-25
**Goal**: Users can see dynamically computed tier boundaries and per-term scoring that adapts to actual performance distributions instead of hardcoded thresholds
**Depends on**: Phase 32
**Requirements**: TIER-01, TIER-02, TIER-03, TIER-04, TIER-05, TIER-06
**Success Criteria** (what must be TRUE):
  1. User sees tier performance distributions (p25/p50/p75 for ROAS, CVR, CPC, CTR per tier) that update when underlying data changes, not static 3.6/3.1/2.6 values
  2. User sees per-term placement scores using robust z-scores (median/MAD) with hierarchical fallback displayed when per-group data is sparse
  3. User sees "Insufficient data" degraded state for any tier with fewer than 5 terms with non-zero metrics
  4. User sees confidence scores per term that combine data volume, consistency, statistical significance, and NLP intent alignment into a single 0-1 value
  5. Tier boundary thresholds auto-adjust based on actual MEDIUM tier percentiles without manual configuration
**Plans**: 4 plans
- [x] 33-01-PLAN.md — Core computation module (TDD): types, distributions, scoring, confidence, impact (Complete 2026-02-25)
- [x] 33-02-PLAN.md — Infrastructure: install simple-statistics, unique index migration, API route (Complete 2026-02-25)
- [x] 33-03-PLAN.md — UI: Hero callout, Level 1 groups overview, Level 2 group detail, sidebar nav (Complete 2026-02-25)
- [x] 33-04-PLAN.md — UI: Level 3 tier detail, Level 4 term scorecard, misplaced terms section (Complete 2026-02-25)

**Outcome**: Phase 33 infrastructure verified by user. All 4 levels of drill-down working. Identified follow-up phases 33.1 (calibration investigation) and 33.2 (UI redesign) to address 95% misplaced rate and $0 impact issues.

### Phase 33.1: Scoring Calibration
**Goal**: Calibrate the tier scoring engine so it produces trustworthy, actionable results — fix $0 impact bug, reduce 95% misplaced rate to actionable 10-20%, reframe UX language for gut-assigned tiers
**Depends on**: Phase 33
**Requirements**: TIER-01, TIER-02, TIER-03 (calibration refinements)
**Success Criteria** (what must be TRUE):
  1. estimateImpact() returns non-zero dollar values for terms with meaningful performance differences between tiers
  2. Misplaced term rate is 10-25% (not 95%), filtered by minimum confidence and impact thresholds
  3. Hero callout shows a credible dollar range that reflects actual optimization opportunity
  4. Scoring accounts for context that tiers were manually assigned by business owner intuition, not historical data
**Plans**: 2 plans
- [ ] 33.1-01-PLAN.md — Fix estimateImpact (ROAS-based), calibrate isMisplaced thresholds, add CalibrationConfig (Wave 1)
- [ ] 33.1-02-PLAN.md — Reframe UX language from "misplaced" to "opportunity" across all components (Wave 2)

**Context**: Tiers were manually assigned by Robert (business owner) based on gut feeling — not historical performance data. The scoring engine correctly identifies where data disagrees with intuition, but needs calibration to surface only high-confidence, high-impact disagreements.

### Phase 33.2: Tier Intelligence UI Redesign
**Goal**: Redesign the Tier Intelligence page from statistical exploration to action-oriented decision-making — prioritized action queue, plain English, progressive disclosure
**Depends on**: Phase 33.1
**Requirements**: TIER-01, TIER-02, TIER-03, TIER-04, TIER-05, TIER-06 (presentation refinements)
**Success Criteria** (what must be TRUE):
  1. Business owner can understand the page in under 2 minutes without statistical knowledge
  2. Page shows top 10-20 highest-impact terms as a prioritized action queue (not all 4,000+)
  3. Every term verdict is in plain English ("This term earns 2x return but has premium placement") not statistical jargon
  4. Statistical details (z-scores, distributions, MAD) preserved behind progressive disclosure for operator use
  5. Page connects to execution workflow (Phase 34) with clear next-action CTAs
**Plans**: TBD
**Note**: Consider merging into Phase 34 planning if scope overlaps significantly with Revenue Leakage UI.

### Phase 34: Revenue Leakage and Execution
**Goal**: Users can identify revenue opportunities with dollar-value estimates and act on them with one-click tier movements that persist and can be undone
**Depends on**: Phase 33.1
**Requirements**: LEAK-01, LEAK-02, LEAK-03, LEAK-04, LEAK-05, LEAK-06, EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05
**Success Criteria** (what must be TRUE):
  1. User sees a hero number showing total revenue leakage as a range with confidence coloring and a "Last computed" timestamp
  2. User sees misplaced terms sorted by dollar impact with revenue estimate ranges (not point values) and reason codes explaining why each term is flagged
  3. User sees wasted spend alerts (zero conversions + high spend) with Block/Demote action buttons and under-invested winners with impression share gap
  4. User can approve, reject, or batch-approve tier movement recommendations and see them persist in routing_recommendations for later review
  5. User can undo a previously executed tier movement and see the reversal logged in policy_action_execution_log with criterion IDs
**Plans**: TBD

### Phase 34.1: Fix Decision Logic (INSERTED) — COMPLETE 2026-02-26

**Goal:** Fix the scoring engine's broken decision logic so recommendations are prescriptive (what action to take) rather than descriptive (which tier's distribution you resemble), and add custom_label_0 level blocking, search promotion candidates, and label profitability summaries
**Requirements**: FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, FIX-06, FIX-07, FIX-08, FIX-09, FEAT-01, FEAT-02, FEAT-03, DOC-01
**Depends on:** Phase 34
**Plans:** 3/3 plans executed
**Success Criteria** (what must be TRUE):
  1. Wasted spend terms (0 conversions, >$5 spend) NEVER get recommended to LOW tier — always block or constrain
  2. Impact estimates for wasted spend equal cost saved (not $0)
  3. Under-invested detection compares search volume against actual impressions (not > 2 for all terms)
  4. Constrain button hidden when term already in HIGH tier
  5. User can block all terms under a product category with one click
  6. routing_recommendations and query_value_scores documented in SCHEMA.md

Plans:
- [x] 34.1-01-PLAN.md — Core scoring engine fixes (TDD): action model, impact formula, CPC inversion, prescriptive verdicts (Wave 1)
- [x] 34.1-02-PLAN.md — Downstream fixes: under_invested, Constrain guard, scoring unification, API routes (Wave 2)
- [x] 34.1-03-PLAN.md — New capabilities: label blocking, search promotion, label profitability, schema docs (Wave 2)

### Phase 34.2: Zero-Conversion Intent Scoring Engine (INSERTED)

**Goal:** Replace the brittle MPN-match promotion rule with a mathematically sound, dual-domain intent scoring engine that combines feed alignment analysis (attribute extraction + TF-IDF specificity) with behavioral Google Ads signals (rCTR, CPC ceiling pressure, micro-conversions) to confidently promote zero-conversion terms through the waterfall — plus fix all terminology (constrain to demote) and wire the tier-scoring UI to the proven Shopping Funnel execution pipeline
**Depends on:** Phase 34.1
**Requirements**: INTENT-01, INTENT-02, INTENT-03, INTENT-04, INTENT-05, INTENT-06, INTENT-07, INTENT-08
**Success Criteria** (what must be TRUE):
  1. "Constrain" is fully eradicated from codebase — replaced with "Demote" everywhere (types, logic, UI, tests)
  2. Feed alignment scoring (attribute extraction + TF-IDF) is deployed on Cloud Run and returns intent scores for any search term
  3. Behavioral intent signals (rCTR, CPC ceiling ratio, micro-conversion delta) are computed in tier-scoring pipeline from Google Ads API data
  4. Unified intent score (feed alignment + behavioral) drives the new determineAction() decision matrix including zero-conversion promotion via Trigger E
  5. UI shows Promote/Demote buttons with target tier labels, correct TierMovementArrow direction using targetTier, and intent score breakdown
  6. Action queue connects to the Shopping Funnel execution pipeline (applyTierAssignment) for actual Google Ads keyword movements
  7. Account audit completed: conversion actions cataloged, average CPA computed, CPC caps documented, historical data validated
  8. All changes pass build + lint + existing tests + new intent scoring tests
**Plans**: 6 plans

Plans:
- [ ] 34.2-01-PLAN.md — Terminology fix: eradicate "constrain", add targetTier to TermScore (Wave 1)
- [ ] 34.2-02-PLAN.md — Google Ads account audit: conversion actions, CPC caps, avg CPA (Wave 1)
- [ ] 34.2-03-PLAN.md — Feed alignment scoring: attribute extraction + TF-IDF on Cloud Run (Wave 2)
- [ ] 34.2-04-PLAN.md — Behavioral intent signals: extend GAQL query, compute rCTR/CPC/micro-conv (Wave 2)
- [ ] 34.2-05-PLAN.md — Unified scoring + 5-trigger determineAction + UI + execution wiring (Wave 3)
- [ ] 34.2-06-PLAN.md — Calibration: score 1000+ terms, validate thresholds, apply to engine (Wave 4)

### Phase 35: Market Intelligence
**Goal**: Users can understand demand patterns, competitive positioning, and product group health to make strategic decisions beyond individual term optimization
**Depends on**: Phase 33
**Requirements**: DEMAND-01, DEMAND-02, DEMAND-03, DEMAND-04, DEMAND-05, DEMAND-06, DEMAND-07, PROD-01, PROD-02, PROD-03, PROD-04
**Success Criteria** (what must be TRUE):
  1. User sees impression share gaps per term (actual vs Keyword Planner market size) and CPC opportunity scores showing headroom to market benchmark
  2. User sees seasonal demand patterns from monthly_search_volumes with terms spiking or declining >20% flagged, plus new term discovery rate for the last 7 days
  3. User sees brand vs non-brand revenue split, competitor mention tracking per competitor token (moen, delta, kohler, etc.), and long-tail vs head term ROAS/CVR comparison
  4. User sees product groups classified into BCG-style quadrants in both a bubble chart (click to drill down to term-level) and a sortable table view
**Plans**: TBD

### Phase 36: Automation and Experiments
**Goal**: Users can define automated tier rebalancing rules with safety guardrails and run controlled A/B experiments on tier assignments with statistical rigor
**Depends on**: Phase 34
**Requirements**: AUTO-01, AUTO-02, AUTO-03, AUTO-04, AUTO-05, EXP-01, EXP-02, EXP-03, EXP-04, EXP-05, EXP-06
**Success Criteria** (what must be TRUE):
  1. User can create automation rules with conditions (ROAS threshold, days, tier, action) and preview effects via dry-run mode before enabling
  2. Automation enforces hard guardrails: max simultaneous movements cap, total spend impact limit per batch, 7-day cooldown per term, and circuit breaker auto-halt on ROAS drop >15% in 3 days or conversions drop >20% WoW
  3. User can register an A/B experiment with hypothesis, term set, duration, and success metric, and the system splits terms into treatment/control groups
  4. System enforces minimum sample size, locks experiment-enrolled terms from other movements, and computes treatment vs control metrics with p-value and confidence intervals
  5. Automation rule evaluation runs on schedule via Cloud Scheduler endpoint
**Plans**: TBD

### Phase 37: Reporting and Benchmarks
**Goal**: Users can track the cumulative impact of optimization actions and receive strategic recommendations grounded in competitive benchmarks
**Depends on**: Phase 34, Phase 35
**Requirements**: RPT-01, RPT-02, RPT-03, RPT-04, BUDGET-01, BUDGET-02
**Success Criteria** (what must be TRUE):
  1. User sees optimization impact tracker with before/after performance for each executed tier movement and a cumulative ROI timeline
  2. User sees weekly digest with top/bottom 5 performers, new terms discovered, actions taken, and recommended next actions
  3. User sees competitive benchmark comparing actual CPC vs market benchmark per product category, with categories identified as competitive advantage or overpaying
  4. User sees budget allocation recommendations showing spend shift from underperforming to high-performing groups with monthly revenue estimates and total addressable market per product group
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 32 -> 33 -> 33.1 -> 33.2 -> 34 -> 34.1 -> 34.2 -> 35 -> 36 -> 37
Note: Phase 35 depends only on Phase 33.1 (not Phase 34), so it can begin after 33.1 completes.
Note: Phase 33.2 may merge into Phase 34 if scope overlaps significantly.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-04 | Phase 0 | 11/11 | Complete | 2026-02-13 |
| 05-08 | v1.0 | 16/16 | Complete | 2026-02-13 |
| 09-16 | v1.1 | 24/24 | Complete | 2026-02-21 |
| 17-22 | v1.2 | 17/17 | Complete | 2026-02-21 |
| 23-27 | v1.3a | ~20/21 | Complete | 2026-02-25 |
| 28-31 | v1.3b | 13/13 | Complete | 2026-02-25 |
| 32. Operational Prerequisites | 3/3 | Complete    | 2026-02-25 | - |
| 33. Tier Scoring Engine | 4/4 | Complete    | 2026-02-25 | - |
| 33.1 Scoring Calibration | 2/2 | Complete    | 2026-02-25 | - |
| 33.2 UI Redesign | 3/3 | Complete    | 2026-02-25 | - |
| 34. Revenue Leakage and Execution | 4/4 | Complete    | 2026-02-26 | - |
| 34.1 Fix Decision Logic | 3/3 | Complete    | 2026-02-26 | - |
| 34.2 Intent Scoring Engine | 1/6 | In Progress|  | - |
| 35. Market Intelligence | 3/4 | In Progress|  | - |
| 36. Automation and Experiments | v1.3c | 0/TBD | Not started | - |
| 37. Reporting and Benchmarks | v1.3c | 0/TBD | Not started | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone completed: 2026-02-21*
*v1.2 milestone completed: 2026-02-21*
*v1.3a milestone completed: 2026-02-25*
*v1.3b milestone completed: 2026-02-25*
*v1.3c roadmap created: 2026-02-25*
