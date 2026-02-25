# Project Research Summary

**Project:** Allied FeedOps v1.3c — Actionable Shopping Intelligence
**Domain:** Google Shopping tier optimization intelligence system
**Researched:** 2026-02-25
**Confidence:** HIGH

## Executive Summary

v1.3c transforms the existing Allied FeedOps shopping funnel from a passive campaign management interface into an active revenue optimization engine. The core problem is simple but costly: hardcoded ROAS thresholds (3.6/3.1/2.6) do not match actual performance distributions across 59 product groups, causing the Tier Movements Panel to show zero recommendations despite real misplacement opportunities. The recommended solution is a distribution-based scoring engine (`tier-scoring.ts`) that computes dynamic percentile boundaries from live data and uses z-score analysis to identify misplaced search terms — then quantifies their dollar impact to prioritize operator action.

The recommended approach is deliberately conservative about new infrastructure: one new npm package (`simple-statistics`), zero new services, and maximum reuse of existing pipelines. The scoring engine calls existing service.ts functions, writes to already-provisioned but empty tables (`query_value_scores`, `routing_recommendations`), and triggers the already-built execution pipeline (`executeTierMovementBatch()`). The critical dependency chain is: distribution engine → misplaced term detection → dollar estimates → execution wiring → everything else. The most important design decision is whether to compute distributions on-demand or via background job; background computation is strongly recommended to avoid Vercel serverless timeout risk at this data volume (~3K search terms, 177 campaign-group combinations).

The primary risks cluster around statistical rigor and automation safety. ROAS distributions in Google Shopping are right-skewed, not normal — z-scores on raw ROAS data will produce nonsense; percentile ranks or robust z-scores are required. Sparse product groups (some tiers have 2-5 terms) need a hierarchical fallback to global distributions to prevent degenerate thresholds. Automated tier movements need hard spend caps and dry-run-first enforcement before any automation executes live, or a single miscalculated scoring run can promote dozens of terms into higher-bid tiers simultaneously. An operational prerequisite must be resolved before Phase 1 begins: `funnel_snapshots_daily` appears empty in production and Cloud Scheduler is not activated — this must be fixed first or trend analysis will silently return misleading zeros.

## Key Findings

### Recommended Stack

v1.3c adds exactly one new dependency to the dashboard: `simple-statistics@^7.8.8`. It covers all statistical computation needed — percentiles, robust z-scores, chi-squared tests, t-tests, linear regression, and Bayesian smoothing — in a 30KB zero-dependency package with bundled TypeScript types. All visualization uses the already-installed Recharts 3.7 (ScatterChart with ZAxis for bubble charts; custom Bar shape for box plots). Heavy aggregation across all 2,784 SKUs uses PostgreSQL `percentile_cont()`, `stddev()`, and `width_bucket()` functions built into Supabase (PG 15). Scheduling uses existing Vercel Crons (vercel.json pattern already established) and pg_cron (available on Supabase).

**Core technologies:**
- `simple-statistics` v7.8.8 (NEW): All statistical computation — zero deps, 30KB, TypeScript types included, actively maintained; covers quantile, zScore, chiSquaredGoodnessOfFit, tTestTwoSample, linearRegression
- Recharts 3.7 (existing): All charts — ScatterChart for bubble/scatter, custom Bar shape for box plots, ComposedChart for trend bands
- PostgreSQL 15 via Supabase (existing): Heavy aggregation — `percentile_cont()`, `width_bucket()`, window functions for z-scores across all SKUs
- Vercel Crons (existing): Rule evaluation (daily 6am UTC), A/B experiment measurement (weekly Sunday 9am UTC)
- pg_cron (existing): Distribution recomputation (daily 5:30am UTC) — pure SQL, no API calls needed

**What NOT to add:** D3.js (Recharts wraps it internally), second chart library (Nivo/Victory/ApexCharts), mathjs (700KB, 23x heavier), jStat (stale since 2020), Redis/Upstash, Bull/BullMQ, node-cron, scipy Python side. The 59 product groups × ~3K terms data volume justifies none of these.

### Expected Features

The feature landscape is anchored by one critical path: the distribution scoring engine unlocks everything downstream. Without it, all other features (revenue leakage estimates, recommendation persistence, execution wiring) either do not work or produce misleading results.

**Must have (table stakes):**
- Distribution-based tier boundaries — replaces hardcoded ROAS 3.6/3.1/2.6 constants in `query-intelligence.ts` line 138, `control-center.ts` lines 3-7, and `policy.ts` lines 20-41; THE reason Tier Movements Panel shows zero recommendations
- Misplaced term detection with percentile rank / robust z-score analysis — core value proposition; flags promotion and demotion candidates
- Dollar-value impact estimates on every recommendation — shown as ranges ("$800-$3,200/month"), not point estimates; color-coded by confidence
- Wasted spend alerts — terms with spend + zero conversions in 30 days; simple filter, immediate value
- Revenue leakage hero number — single "at least $X,XXX/month in detected opportunities" (conservative bound); quantifies system value
- One-click execution wiring — backend pipeline already exists (`executeTierMovementBatch()`); this is UI plumbing
- Movement history + undo — `negative_registry` and `policy_action_execution_log` tables exist and store criterion IDs for reversal
- Recommendation persistence — `routing_recommendations` table exists (migration 033, currently empty) with pending/accepted/rejected/expired workflow
- Multi-factor confidence scoring — four-factor model: data volume (30%), consistency/CoV (30%), statistical significance (20%), NLP alignment (20%)

**Should have (differentiators):**
- BCG product group matrix — quadrant chart for 59 groups using `getLabelTierPerformance()` output; use action-oriented quadrant labels (Scale Up / Optimize / Maintain / Review) not BCG terminology
- Competitor conquest tracking — group competitor-mentioning terms (16 tokens already in NLP) by brand; show per-competitor ROAS and spend
- Under-invested winner detection — high-CVR terms with impression share < 30% using `keyword_metrics` data (both tables populated)
- Seasonal demand pattern analysis — use `monthly_search_volumes` JSONB from `keyword_metrics` table to predict demand spikes
- Brand vs non-brand revenue split — quantifies growth headroom; simple aggregation on existing NLP output
- Automated tier rebalancing rules — configurable rule engine with three-stage rollout (dry-run → human-approved batch → auto with circuit breakers)
- A/B testing framework — uses already-provisioned `experiment_registry/assignments/outcomes` tables (confirmed in production, empty)

**Defer to v1.4:**
- Full automation without human review
- Email/Slack notifications
- ML-based prediction models
- Performance-informed content regeneration loop

### Architecture Approach

The architecture inserts new computation modules into the existing 4-stage pipeline (Data Acquisition → Intelligence → Aggregation → Execution) at well-defined points, without modifying the critical path. `service.ts` is strictly read-only (1600+ lines, live Google Ads integration used daily — do not touch). New modules consume its exports. `query-intelligence.ts` gets its hardcoded scoring logic delegated to a new `tier-scoring.ts`. All new API routes follow the existing pattern: heavy computation in `/lib/optimization/` modules, thin wrappers in `/app/api/`. Three-layer caching: service.ts 2-min memory cache → module-level distribution cache (10 min) → Supabase persisted scores (`query_value_scores`).

**Major components:**
1. `tier-scoring.ts` (Phase 1, core) — distribution computation, percentile-rank/robust-z-score placement, dollar impact estimation; writes to `query_value_scores` and `routing_recommendations`; hierarchical fallback for sparse tiers
2. `revenue-leakage.ts` (Phase 1) — misplacement detection, wasted spend alerts, under-investment identification; reads tier-scoring.ts output; returns ranges not point estimates
3. `demand-gaps.ts` / `competitive-intel.ts` / `product-matrix.ts` (Phase 2) — market intelligence modules; all independent of Phase 1 execution pipeline and can build in parallel with Phase 1 UI work
4. `automation-rules.ts` / `experiment-engine.ts` (Phase 3) — always route through existing `evaluateGuardrails()` → `executeTierMovementBatch()` pipeline; experiment engine must add lock check to `executeTierMovement()` before first experiment
5. `impact-tracker.ts` / `weekly-digest.ts` (Phase 4) — pure read-only aggregation; require Phase 1-3 execution history to exist

**Files NOT to modify:** `service.ts`, `policy.ts`, `tier-movement.ts`, `persistence.ts`, `taxonomy.ts`, all existing `/api/search-terms/` and `/api/ga4/` routes.

### Critical Pitfalls

1. **Distribution cold start with sparse tiers** — Per-group-per-tier slices can have 2-5 terms; percentiles on 3 data points produce unstable thresholds that flip wildly between runs. Mitigation: hierarchical fallback (per-group-per-tier → per-tier-global → hardcoded defaults); log which fallback level was used; if >50% of terms in any tier flag as misplaced, the distribution is degenerate, not the data.

2. **Z-scores on right-skewed ROAS data** — ROAS distributions are heavily right-skewed (most terms ROAS 0-2, occasional outliers at 10-50). Standard z-scores are meaningless on this data. Mitigation: use percentile ranks as primary approach; use robust z-scores `(value - median) / MAD` if z-score semantics are needed; cap ROAS at p99 before computing distribution statistics.

3. **Automation spend runaway** — `executeTierMovementBatch()` guardrails check spend deltas but do not cap simultaneous movement count or total budget impact per batch. A miscalculated scoring run can recommend 50+ promotions en masse. Mitigation: max 10 movements per automated evaluation run; max $50/day incremental spend per batch; dry-run-first with 24h cooling period; circuit breaker halts automation if 3+ consecutive batches have >50% operator rejection.

4. **Revenue estimate false precision** — Dollar estimates multiply 3 uncertain variables (CVR delta, impressions, AOV), compounding to 2-3x error range. Showing "$2,400/month" as a point estimate erodes operator trust when actual impact is $800 or -$200. Mitigation: show ranges from day 1 ("$800-$3,200/month"); color-code by confidence; use conservative bound (p25 of estimates) for hero number; use word "estimate" or "opportunity" everywhere.

5. **Funnel snapshot operational gap** — `funnel_snapshots_daily` appears empty in production and Cloud Scheduler is not activated. Building trend analysis before fixing this produces silent zero-change numbers. Mitigation: gate all Phase 1 coding behind verification that `SELECT COUNT(*) FROM funnel_snapshots_daily WHERE snapshot_date > NOW() - INTERVAL '7 days'` returns >0; add data-availability checks to every route using historical data.

6. **Experiment contamination via shared negative lists** — Shared campaign negative lists apply to both treatment and control groups. Modification to any shared list during an experiment silently contaminates both arms. Mitigation: add experiment lock check to `executeTierMovement()` that rejects movements for experiment-enrolled terms; build this lock before the first experiment runs.

7. **Statistical significance theater in A/B tests** — `experiment_outcomes` table lacks `p_value` and `confidence_interval` columns. With luxury item volumes (~10-50 clicks/term), individual term experiments need 6+ months to reach significance. Mitigation: add p_value and CI columns; enforce minimum sample size and 30-day minimum duration in `experiment_registry` schema; display confidence intervals on all lift estimates from day 1.

## Implications for Roadmap

The critical path is strict: distribution scoring engine → misplaced term detection → everything else. Phase 2 intelligence modules can build in parallel with Phase 1 UI work. Phase 3 automation requires Phase 1 execution history. Phase 4 reporting requires Phase 1-3 data. The funnel snapshot operational task must precede all coding work.

### Pre-Phase 1: Operational Prerequisites
**Rationale:** Two operational gaps block the entire milestone and cannot be resolved by writing code. Without verifying these, Phase 1 trend analysis silently returns misleading zeros and all scheduling work fails.
**Delivers:** `funnel_snapshots_daily` populated with recent data; Cloud Scheduler activated and verified running; CRON_SECRET confirmed set
**Actions:** Run `bash scripts/setup-funnel-scheduler.sh`; POST to `/api/funnel-snapshots/backfill`; verify with `SELECT COUNT(*) FROM funnel_snapshots_daily WHERE snapshot_date > NOW() - INTERVAL '7 days'`
**Avoids:** Pitfall 5 (Funnel Snapshot Gap), silent zero-change trend analysis

### Phase 1: Revenue Leakage Detection and Tier Optimization
**Rationale:** The distribution scoring engine is the single dependency that unlocks every other feature. Nothing downstream is useful until misplaced terms can be detected with statistical rigor and dollar-value estimates with communicated uncertainty. This phase transforms the dashboard from "reports that nothing is actionable" to "actionable prioritized recommendations with confidence ranges." Must be built and validated before automation (Phase 3) can be safely calibrated.
**Delivers:** `tier-scoring.ts` with hierarchical fallback distributions; revenue leakage API and UI (hero number with conservative bound, range estimates, confidence coloring); one-click execution wiring to existing pipeline; movement history + undo; recommendation persistence to `routing_recommendations`
**Addresses:** All 9 table-stakes features
**Key decisions required:** Use percentile ranks as primary approach (not raw z-scores on skewed ROAS); background computation architecture preferred over on-demand to avoid Vercel timeout; show estimate ranges not point values from day 1; set `export const maxDuration = 60` on all scoring routes
**Avoids:** Pitfall 1 (sparse tiers — hierarchical fallback), Pitfall 2 (skewed ROAS — percentile ranks), Pitfall 4 (false precision — ranges), Pitfall 5 (cache staleness — background computation)
**Research flag:** Standard patterns — computation module + thin API route wrapper already established in codebase. No external research needed.

### Phase 2: Market Intelligence and Demand Gap Analysis
**Rationale:** Three Phase 2 modules (`demand-gaps.ts`, `competitive-intel.ts`, `product-matrix.ts`) have zero dependency on Phase 1's execution pipeline — they only need service.ts exports and existing Supabase tables. They can begin in parallel with Phase 1's UI work once Phase 1's computation modules are validated. BCG matrix and competitive intel deliver strategic value operators can act on immediately, independent of tier movement recommendations.
**Delivers:** BCG product group matrix with drill-down; competitor conquest tracking and brand/non-brand split; under-invested winner detection + CPC opportunity scoring; seasonal demand pattern analysis; long-tail vs head term analysis; competitive benchmark overlay
**Uses:** Recharts ScatterChart + ZAxis for bubble chart (official example exists); `keyword_metrics.monthly_search_volumes` JSONB for seasonal patterns; `decomposeSearchTerm()` NLP output already computing brand/competitor flags
**Key decisions required:** BCG matrix must limit to top 20 groups by spend with "Other" aggregate — 59 simultaneous bubbles with overlapping labels is unreadable; use action-oriented quadrant labels, not BCG terminology
**Avoids:** Performance trap of N+1 queries joining `search_queries` with `keyword_metrics` (use single JOIN with indexes)
**Research flag:** Standard patterns — all data sources verified populated. Recharts bubble chart has official example. No research needed.

### Phase 3: Intelligent Automation and A/B Testing
**Rationale:** Automation and experiments both require Phase 1 execution history to validate safety. Rules calibrated on empty `policy_action_execution_log` during Phase 3 have no signal to calibrate against. The experiment lock mechanism must be built before the first experiment runs, not retrofitted after contamination occurs.
**Delivers:** Automation rules engine with three-stage rollout (dry-run → human-approved batch → auto with circuit breakers); A/B testing framework with statistical rigor enforced in schema; `automation_rules` table migration; experiment lock mechanism in `executeTierMovement()`
**Key decisions required:** Always route automation through existing `evaluateGuardrails()` → `executeTierMovementBatch()` — no bypasses; add p_value + confidence_interval columns to `experiment_outcomes` in the same migration that creates `automation_rules`; minimum 30-day experiment duration enforced in code, not just documented
**Avoids:** Pitfall 3 (automation spend runaway — caps and circuit breakers), Pitfall 6 (experiment contamination — lock mechanism before first experiment), Pitfall 7 (underpowered tests — schema enforcement)
**Research flag:** Automation guardrail patterns well-documented in industry (Optmyzr, SearchEngineLand). A/B testing statistics are standard. No additional research needed.

### Phase 4: Executive Reporting
**Rationale:** Impact tracking and weekly digest are pure read-only aggregations on data that only exists after Phases 1-3 have been operational for at least 14 days (required measurement lag for before/after comparison). Building reporting before execution history exists produces empty dashboards and erodes trust in the system.
**Delivers:** Optimization impact tracker (predicted vs actual, tracked per executed movement); executive weekly digest (top performers, decliners, actions taken, recommended actions); competitive benchmarks scorecard
**Key decisions required:** Impact tracker must store predicted impact at time of recommendation execution and compare to actual after 14/30 days — report hit rate ("estimates within 50% of actual X% of the time") to rebuild trust if early estimates were imprecise
**Avoids:** "Looks done but isn't" — verify predicted-vs-actual comparison exists; verify digest handles product groups with zero activity gracefully
**Research flag:** Standard patterns — all data sources from Phases 1-3. No external research needed.

### Phase Ordering Rationale

- **Operational gates before code:** The funnel snapshot gap is an operational task, not a coding task. It must be verified complete (not just assumed done) before Phase 1 starts, or trend analysis returns silent zeros for weeks.
- **Scoring engine is the keystone:** Every feature references `tier-scoring.ts` output. Building anything else first creates tech debt that requires rework when the distribution model is validated against real ROAS distributions.
- **Phase 2 parallelism is safe:** The three intelligence modules are fully independent of the Phase 1 execution pipeline. They can begin as soon as Phase 1's computation modules are validated — no need to wait for Phase 1 UI completion.
- **Statistical rigor must be in Phase 1 UI from day 1:** Confidence intervals, estimate ranges, and "as of" timestamps must be present in the first implementation. Operators who learn to trust point estimates cannot be retrained easily.
- **Automation requires real operational data:** Rules calibrated during Phase 3 need 2-4 weeks of Phase 1 execution logs to have meaningful signal. Build automation infrastructure immediately after Phase 1, but do not enable auto-execution until execution history validates the scoring engine.
- **Experiment locks before experiments:** The contamination risk from shared negative lists requires the lock mechanism to exist before any experiment is registered. Retrofitting locks after contamination is useless.

### Research Flags

No phases require `/gsd:research-phase` during planning. All patterns are well-documented:

- **Phase 1:** Statistical scoring + persistence pattern already established in codebase (`query-intelligence.ts` + service.ts); PostgreSQL percentile functions standard since PG 9.4
- **Phase 2:** All data sources verified and populated; Recharts patterns documented with official examples; NLP decomposition already computing all needed flags
- **Phase 3:** Guardrail patterns in `policy.ts` are the template; experiment tables are provisioned; automation guardrail industry patterns documented from Optmyzr/SearchEngineLand
- **Phase 4:** Pure aggregation on existing data; no external dependencies

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official docs verified for all packages; existing codebase confirms recharts/supabase patterns; simple-statistics API confirms all needed functions exist with TypeScript types |
| Features | HIGH | Full source code audit of existing pipeline confirms what exists vs what needs building; critical path dependency confirmed in codebase (hardcoded thresholds at specific line numbers) |
| Architecture | HIGH | Based on complete source audit of service.ts (1600+ lines), query-intelligence.ts, policy.ts, tier-movement.ts; integration points are unambiguous; caching strategy matches existing patterns |
| Pitfalls | HIGH | Pitfalls derived from actual schema gaps (missing p_value columns in experiment_outcomes), actual empty tables (funnel_snapshots_daily), actual hardcoded values (query-intelligence.ts line 138), confirmed via codebase inspection |

**Overall confidence:** HIGH

### Gaps to Address

- **Vercel plan tier:** Vercel Crons plan limit (Hobby: 2 jobs; Pro: 40). v1.3c needs 4 cron entries. Verify during Pre-Phase 1 setup — if on Hobby plan, consolidate distribution recomputation + rule evaluation into single `/api/daily-jobs` endpoint that runs both sequentially.

- **ROAS distribution shape validation:** Research recommends percentile ranks over z-scores due to expected right-skew, but the actual distribution shape for Allied Brass's 177 campaign-group combinations is unverified. First task of Phase 1 scoring engine: compute actual ROAS skewness and validate the modeling assumption before building on it. If skewness < 1.0, standard z-scores may be acceptable.

- **Funnel snapshot production state:** PROJECT.md notes the table "appears empty." Exact row count and whether Cloud Scheduler setup script is ready to run without modification must be verified before committing to the Pre-Phase 1 timeline. Run the verification query before estimating Phase 1 start date.

- **`query_value_scores` schema compatibility:** The existing migration 033 schema may not include `tier_fit_scores`, `recommended_tier`, or `net_monthly_impact` columns needed for adaptive scoring. Verify column list and add a migration if needed before Phase 1 persists adaptive scores.

## Sources

### Primary (HIGH confidence)
- Source code audit: `dashboard/src/lib/shopping-funnel/service.ts` (1600+ lines) — data acquisition pipeline, 2-min cache behavior
- Source code audit: `dashboard/src/lib/optimization/query-intelligence.ts` — hardcoded ROAS 3.6/3.1 thresholds at lines 116-145
- Source code audit: `dashboard/src/lib/optimization/control-center.ts` — BASELINE_TARGET_ROAS constant at lines 3-7
- Source code audit: `dashboard/src/lib/intent/policy.ts` — PROMOTION_THRESHOLDS at lines 20-41, evaluateGuardrails behavior
- Source code audit: `dashboard/src/lib/intent/tier-movement.ts` — executeTierMovementBatch, CONFIDENCE_GATES
- [simple-statistics GitHub](https://github.com/simple-statistics/simple-statistics) — v7.8.8, ISC license, TypeScript types included
- [simple-statistics API docs](https://simple-statistics.github.io/docs/) — full function reference confirming all needed methods
- [Recharts ScatterChart API](https://recharts.github.io/en-US/api/ScatterChart/) — ZAxis support for bubble charts
- [Recharts Bubble Chart Example](https://recharts.github.io/en-US/examples/BubbleChart/) — official bubble chart pattern
- [PostgreSQL Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) — percentile_cont, stddev, width_bucket
- [Vercel Cron Jobs docs](https://vercel.com/docs/cron-jobs/manage-cron-jobs) — plan limits (Hobby: 2, Pro: 40)
- [Google Ads Statistical Methodology for Experiments](https://support.google.com/google-ads/answer/9232676?hl=en) — 95% confidence, two-tailed testing
- [Google Ads Help: Demand Gen A/B experiments](https://support.google.com/google-ads/answer/13719071?hl=en) — 50 conversion minimum per arm

### Secondary (MEDIUM confidence)
- [DataFeedWatch: Priority Bidding for Shopping ROAS](https://www.datafeedwatch.com/blog/how-to-increase-google-shopping-roas) — tiered campaign structure patterns
- [Optmyzr: Budget automation guardrails](https://www.optmyzr.com/bfcm-google-ads-2025-budget-automation-guide/) — circuit breaker patterns
- [SearchEngineLand: When Google AI bidding breaks](https://searchengineland.com/google-ai-bidding-breaks-take-control-466251) — guardrail failure modes
- [Practical Ecommerce: BCG Matrix for Ecommerce](https://www.practicalecommerce.com/Using-the-BCG-Matrix-for-Ecommerce-Marketing-Decisions) — portfolio analysis methodology
- [Google Ads API Negative Keyword Automation](https://www.negator.io/post/google-ads-api-scripts-negative-keyword-automation-developer-guide) — batch mutation patterns, rate limit considerations
- [Google Ads Rate Limits](https://developers.google.com/google-ads/api/docs/productionize/rate-limits) — token bucket algorithm, QPS per CID

### Tertiary (LOW confidence)
- Milestone spec: `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` — Phase 1-4 structure (plan, not validated implementation)

---
*Research completed: 2026-02-25*
*Ready for roadmap: yes*
