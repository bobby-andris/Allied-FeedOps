# Pitfalls Research

**Domain:** Actionable Shopping Intelligence -- distribution-based scoring, automated tier movements, A/B testing, and revenue leakage detection for Google Shopping campaign management
**Researched:** 2026-02-25
**Confidence:** HIGH (based on codebase analysis of existing service.ts, policy.ts, tier-movement.ts, query-intelligence.ts, control-center.ts, experiment schema, and milestone spec)

## Critical Pitfalls

### Pitfall 1: Distribution Cold Start -- Degenerate Percentiles from Sparse Tiers

**What goes wrong:**
The spec says to compute p25/p50/p75 ROAS distributions per tier per `custom_label_0` to set dynamic thresholds. With 59 product groups x 3 tiers = 177 combinations, many will have very few search terms (some product groups may have 2-5 terms in a tier). Computing percentiles on 3 data points produces unstable thresholds that flip wildly between scoring runs. A single new conversion can move the p75 ROAS from 2.0 to 8.0, causing the scoring engine to recommend mass movements.

**Why it happens:**
Developers test with aggregate data ("we have thousands of terms total") and miss that per-group-per-tier slicing reduces sample sizes dramatically. The hardcoded thresholds (ROAS 3.6/3.1/2.6) "worked" precisely because they avoided this problem -- they were wrong but stable.

**How to avoid:**
- Set a minimum sample size floor per distribution (e.g., 10 terms with 20+ clicks each). Below this, fall back to cross-group tier-level distributions (all product groups combined for that tier).
- Use hierarchical fallback: per-group-per-tier -> per-tier-global -> hardcoded defaults. Never return "no data" -- always have a fallback.
- Apply Bayesian smoothing: blend per-group distributions with global priors weighted by sample size. With 3 terms, the prior dominates; with 30 terms, the group data dominates.
- Log which fallback level was used so operators can see "this group's thresholds are based on global averages, not group-specific data."

**Warning signs:**
- Threshold values changing >20% between consecutive runs with no major campaign changes
- Product groups with <5 terms in any tier (check before launch)
- Revenue leakage estimates that swing from $500/month to $5,000/month between page loads
- "100% of terms in tier X are misplaced" -- this means the distribution is degenerate, not that everything is wrong

**Phase to address:**
Phase 1 (Adaptive Tier Scoring Engine) -- this is the foundation. If the scoring engine is unstable, every downstream feature (revenue leakage, automation rules, A/B testing) inherits the instability.

---

### Pitfall 2: Automation Without Spend Caps -- Runaway Budget Drain

**What goes wrong:**
The tier-movement pipeline (`tier-movement.ts`) writes negative keywords to live Google Ads campaigns. Automated rules that fire "if ROAS > X for Y days, auto-promote" can promote terms into higher-bid tiers en masse. If the scoring engine miscalculates (see Pitfall 1) or data is stale, automation could promote 50 terms from LOW to MEDIUM simultaneously, instantly increasing ad spend by thousands of dollars/month with no human in the loop.

**Why it happens:**
The existing `executeTierMovementBatch()` function has guardrails (`evaluateGuardrails()`) but they check spend *deltas* (40% spike) and attribution quality -- they do NOT cap the number of simultaneous movements or the total budget impact of a batch. The guardrails were designed for human-initiated movements, not autonomous scheduling.

**How to avoid:**
- Add a **max-movements-per-run** cap (e.g., 10 movements per automated evaluation). Even if the engine recommends 50, execute only the top 10 by confidence.
- Add a **max-daily-spend-impact** cap: sum the `expected_cost_change` for all recommendations in a batch, reject the batch if total exceeds a configurable threshold (e.g., $50/day incremental spend).
- Require **dry-run-first**: every automated rule must execute a dry run, persist the preview to `routing_recommendations`, and only execute after a cooling period (24h) unless operator approves sooner.
- Add a **circuit breaker**: if 3+ automated batches in a row have >50% rejection rate from operators reviewing after the fact, disable the rule and alert.
- Never auto-execute "block" or "demote" actions for terms with >$100 spend/month without operator approval -- these terms are revenue-generating and blocking them has immediate negative impact.

**Warning signs:**
- Automated rule executes 20+ movements in a single run
- No human has reviewed automated movements in 7+ days
- `policy_action_execution_log` shows exclusively automated entries (no manual approvals)
- Daily spend increases >15% without corresponding revenue increase

**Phase to address:**
Phase 3 (Automated Tier Rebalancing Rules) -- but the caps and circuit breaker should be built into the tier-scoring engine in Phase 1 so they're available when automation is wired up.

---

### Pitfall 3: Statistical Significance Theater -- Underpowered A/B Tests on Shopping Tiers

**What goes wrong:**
The experiment framework (Phase 3.2) splits terms into treatment and control groups and measures ROAS/CVR differences. With luxury bathroom accessories (high AOV ~$50-200, low volume per term), most individual search terms get 10-50 clicks/month. An A/B test on tier assignment for a single product group might have 20 terms in treatment and 20 in control, each with 20 clicks. At p<0.05, you need ~380 conversions per group to detect a 10% CVR lift. With a 3% CVR, you'd need ~12,600 clicks per group -- roughly 6+ months of data for a single product group.

The danger: declaring a winner at p=0.15 because "we need to move fast" or because the UI shows a green arrow on the lift number without displaying the p-value.

**Why it happens:**
The `experiment_outcomes` table has `observed_lift` and `sample_size` but no `p_value` or `confidence_interval` columns. Without these stored, the UI will likely display lift without significance, and operators will act on noise. The schema also has no `min_sample_size` or `min_duration` columns to enforce experiment validity.

**How to avoid:**
- Add `p_value numeric(8,6)` and `confidence_interval_lower/upper numeric(14,6)` columns to `experiment_outcomes` (or store in `metadata` JSONB).
- Add `min_sample_size` and `min_duration_days` columns to `experiment_registry`. Enforce: experiments cannot be resolved before both thresholds are met.
- Use sequential testing (not fixed-horizon): compute a running p-value and only declare significance when it crosses 0.05 after a minimum observation window (14 days).
- For shopping tier experiments specifically, run experiments at the **product group level** (not individual terms) to aggregate enough volume. A product group with 200 terms across 3 tiers has enough volume to detect meaningful effects in 30-60 days.
- Display confidence intervals on all lift estimates in the UI. Show "Lift: +12% (95% CI: -8% to +32%)" not just "Lift: +12%".
- Default experiment duration to 30 days minimum. Allow extension but not shortening.

**Warning signs:**
- Experiments resolved (status='success'/'failure') with sample_size < 100
- Experiments resolved in <14 days
- Multiple experiments showing "significant" lifts of opposite signs on the same product group
- No experiments ever reach 'inconclusive' status (suggests the bar is too low)

**Phase to address:**
Phase 3 (A/B Testing Framework). The schema additions should be in the migration that creates `automation_rules`. The UI must show significance from day 1 -- adding it later means operators have already learned to trust raw lift numbers.

---

### Pitfall 4: Revenue Estimates That Erode Trust -- False Precision in Dollar Impact

**What goes wrong:**
The spec shows `netMonthlyImpact: number // dollars` with messages like "Moving 'brass towel bar' from HIGH to MEDIUM could generate ~$Y additional monthly revenue." These estimates use formulas like `(target_tier_avg_cvr - current_tier_avg_cvr) x current_impressions x target_tier_avg_aov`. Each variable has 20-50% uncertainty, and they multiply: if CVR estimate is 30% off, impressions 20% off, and AOV 25% off, the combined estimate can be 2-3x off in either direction.

Operators see "$2,400/month revenue leakage" as a precise number. When they execute the recommendation and revenue changes by $800 (or drops $200), they lose trust in the entire system. The "total leakage estimate" hero number is especially dangerous because it sums estimates across dozens of terms, compounding errors.

**Why it happens:**
Developers show dollar estimates because the spec says "every recommendation must show a dollar-value estimate." But without communicating uncertainty, a helpful estimate becomes a false promise.

**How to avoid:**
- Show **ranges, not point estimates**: "$800 - $3,200/month" not "$2,400/month". Use Monte Carlo simulation or propagate the coefficient of variation through the formula.
- Color-code by confidence: green (high data volume, tight range), yellow (moderate), red (low data volume, wide range). Terms with <50 clicks should always be red.
- The hero "total leakage" number should show the conservative bound: "At least $X/month in revenue opportunities detected (conservative estimate)." Use p25 of the distribution of estimates, not the sum of medians.
- Track prediction accuracy: after each executed movement, compare the predicted impact to actual outcome at 14/30 days. Store in `performance_impact_scores`. Report hit rate: "Our estimates have been within 50% of actual 72% of the time."
- Use the word "estimate" or "opportunity" everywhere, never "leakage" in isolation (which implies certainty).

**Warning signs:**
- Revenue estimates that are >50% of total campaign spend (mathematically implausible)
- Operator approval rate dropping below 50% (they've stopped trusting recommendations)
- No feedback loop tracking predicted vs actual impact
- Single-term estimates exceeding $500/month for terms with <20 clicks

**Phase to address:**
Phase 1 (Revenue Leakage Dashboard). The range display and confidence coloring must be in the first implementation. Adding "accuracy tracking" is Phase 4 (Impact Tracker) but the UI language must be right from the start.

---

### Pitfall 5: Cache Staleness Cascade -- 2-Minute Cache Meets Heavy Computation

**What goes wrong:**
`service.ts` has a 2-minute cache (`CACHE_TTL_MS = 120000`). The revenue leakage API route will call `getExistingFunnelTerms()` and `getLabelTierPerformance()`, run distribution computation, z-score calculation, impact estimation, and return results. If the computation takes 15-30 seconds (177 campaigns x thousands of terms x percentile calculations), and two requests arrive 2 minutes apart, the second triggers a fresh Google Ads API call (6 parallel GAQL queries) PLUS the full computation, easily timing out the Vercel serverless function (default 10s for hobby, 60s for pro).

Worse: if the scoring engine persists results to `query_value_scores` and `routing_recommendations` tables, a partial write during a timeout leaves the database in an inconsistent state where some terms have new scores and others have stale scores.

**Why it happens:**
The existing cache works for the Shopping Funnel page because it returns raw data quickly. Adding heavy computation on top of the cached data path changes the performance profile without changing the caching strategy.

**How to avoid:**
- **Separate computation from serving**: Run the scoring engine as a background job (Cloud Scheduler or on-demand trigger) that writes results to `query_value_scores` and `routing_recommendations` tables. The API route reads from these tables (fast) instead of computing on-demand.
- **Compute-and-cache pattern**: The first request triggers computation and stores results with a timestamp. Subsequent requests serve the stored results until they're stale (e.g., 1 hour). Show "Last computed: 47 minutes ago" in the UI.
- If computing on-demand, add a computation lock: if another request is already computing, return the last cached result with a "refreshing" indicator.
- Set API route timeout to 60s (Vercel Pro) and add `export const maxDuration = 60` to the route.
- Use database transactions for persisting scores: all-or-nothing writes prevent partial updates.

**Warning signs:**
- Revenue leakage page takes >5 seconds to load (spec says <3 seconds)
- Vercel function logs showing 504 Gateway Timeout on scoring routes
- `query_value_scores` table has mixed timestamps (some rows from 10am, others from 2pm, in the same scoring run)
- Google Ads API quota utilization increasing >5% (currently at 1.2%)

**Phase to address:**
Phase 1 (Revenue Leakage Dashboard). The architecture decision (compute-on-demand vs background job) must be made before building the API route. Background job is strongly recommended given the data volume.

---

### Pitfall 6: Funnel Snapshot Gap -- Trend Analysis on Empty History

**What goes wrong:**
`funnel_snapshots_daily` was created and backfilled with 4,093 rows, but the production table "appears empty" (per PROJECT.md tech debt). Cloud Scheduler is not yet activated. If Phase 1 builds trend analysis ("ROAS trending up 12% this week") without first confirming historical data exists, operators see misleading "0% change" or errors. Worse, if the backfill endpoint is re-run but the scheduler isn't activated, you get a one-time snapshot with no ongoing data, making "7d vs prev-7d" comparisons impossible after the first week.

**Why it happens:**
The infrastructure was built in v1.3b but the operational activation (scheduler + backfill) is a manual step that's easy to forget. The code works, the tables exist, the endpoints exist -- the gap is operational, not technical.

**How to avoid:**
- **Gate Phase 1 on funnel data activation**: Before any Phase 1 code is written, run the backfill endpoint and activate the Cloud Scheduler. Verify data exists with a SQL count.
- Add a **data availability check** to every API route that uses historical data. If `funnel_snapshots_daily` has <14 rows for the queried group, return a degraded response with "Insufficient historical data -- trends will be available after [date]" instead of misleading zero-change numbers.
- Use `service.ts` live data for current-state analysis and ONLY use `funnel_snapshots_daily` for trend comparisons. Don't block the scoring engine on historical data availability.
- Set up a monitoring alert: if `funnel_snapshots_daily` hasn't received new rows in 48 hours, alert (means scheduler died or endpoint is failing silently).

**Warning signs:**
- `SELECT COUNT(*) FROM funnel_snapshots_daily` returns 0 (still empty)
- Trend cards showing "0% change" across all product groups (not realistic)
- `7d vs prev-7d` comparison using the same 7 days for both windows (no new data flowing in)
- Cloud Scheduler script exists but CRON_SECRET is not set

**Phase to address:**
Pre-Phase 1 prerequisite. This is an operational task, not a coding task. Run `bash scripts/setup-funnel-scheduler.sh` and POST to `/api/funnel-snapshots/backfill` before starting Phase 1 development.

---

### Pitfall 7: Experiment Contamination -- Shared Negative Lists Leak Between Treatment and Control

**What goes wrong:**
The 3-tier Shopping funnel uses shared negative keyword lists (`AVD - Global Block`, `AVD - Competitor Terms`, `AVD - BRANDED_SEARCH_TERMS - US`). When running an A/B test that moves treatment terms to a different tier (by adding/removing campaign-level negatives), the shared lists still apply to both treatment and control. If a term in the treatment group gets added to the Global Block list during the experiment (by another process or manual action), it's removed from both treatment and control, contaminating the experiment.

More subtly: tier movements work by adding negative keywords to the tiers a term should NOT appear in. If the experiment moves term "brass towel bar" from LOW to MEDIUM by removing its MEDIUM campaign negative, but another automated process (or Phase 3 automation rules) simultaneously adds it back, the experiment is silently sabotaged.

**Why it happens:**
The experiment framework (`experiment_registry`, `experiment_assignments`) tracks which terms are in treatment/control, but there's no mechanism to LOCK those terms from modification by other processes during the experiment. The `negative_registry` table logs changes but doesn't prevent conflicting changes.

**How to avoid:**
- Add an **experiment lock** check to `executeTierMovement()`: before executing any movement, check if the term is assigned to an active experiment. If yes, reject the movement with reason code `experiment_locked`.
- Add `locked_by_experiment text NULL` column to `negative_registry` or create a `experiment_term_locks` table. Active experiments register their terms, and all movement paths check the lock.
- Automation rules (Phase 3.1) must respect experiment locks: the `evaluate-rules` endpoint must filter out experiment-enrolled terms.
- Log experiment integrity violations: if a shared list modification affects experiment terms, log it to `experiment_outcomes.metadata` so the analysis can account for contamination.
- Consider using only **product group level** experiments (all terms in a product group are treatment or control) to reduce cross-contamination risk.

**Warning signs:**
- `negative_registry` rows created during an active experiment that affect experiment-enrolled terms
- Treatment and control groups having different term counts at experiment end vs start
- Experiment results showing identical performance for treatment and control (terms were moved back)
- `experiment_outcomes` with `observed_lift = 0` for all metrics (likely contamination, not no effect)

**Phase to address:**
Phase 3 (A/B Testing Framework). The lock mechanism must be built before the first experiment runs. Retroactively adding locks after experiments have been contaminated is useless.

---

### Pitfall 8: Z-Score Misuse -- Normal Distribution Assumption on Skewed ROAS Data

**What goes wrong:**
The spec proposes using z-scores to determine tier placement: "Compute z-score of term's ROAS relative to each tier's ROAS distribution. Term belongs in the tier where its z-score is closest to 0." Z-scores assume normally distributed data. ROAS distributions in Google Shopping are heavily right-skewed: most terms have ROAS 0-2 (lots of impressions, few conversions), with occasional outliers at ROAS 10-50 (one conversion on low spend). The mean is dragged up by outliers, making the z-score meaningless for the majority of terms.

**Why it happens:**
Z-scores are the textbook approach for "how far from average." Developers use them without checking the underlying distribution shape. With ROAS data, the median is typically 50-70% of the mean, and the standard deviation can exceed the mean.

**How to avoid:**
- Use **percentile ranks** instead of z-scores: "this term's ROAS is at the 85th percentile of its tier" is meaningful regardless of distribution shape.
- If z-scores are needed for the scoring formula, use **robust z-scores**: `(value - median) / MAD` where MAD = median absolute deviation. This is resistant to outliers.
- Alternatively, log-transform ROAS before computing z-scores: `log(ROAS + 0.01)` is closer to normal for most Shopping data.
- Cap outlier ROAS at p99 before computing any distribution statistics. A single term with ROAS = 47 (one $200 sale on $4.25 spend) should not dominate the tier's average.
- Validate the approach: before launch, compute z-scores for all existing funnel terms and check if the "misplaced" recommendations make intuitive sense. If >50% of terms are flagged as misplaced, the model is wrong.

**Warning signs:**
- Standard deviation of tier ROAS > 2x the mean (the distribution is too skewed for z-scores)
- >40% of terms flagged as misplaced (the model is fitting outliers, not the majority)
- Recommendations dominated by terms with very low spend (these have extreme ROAS ratios from small denominators)
- ROAS tier boundaries that are negative (mathematically possible with z-scores on skewed data, nonsensical in practice)

**Phase to address:**
Phase 1 (Adaptive Tier Scoring Engine). This is a modeling decision that must be validated before the scoring engine ships. Use percentile ranks as the primary approach; add z-scores only if there's a specific need.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Compute scores on-demand instead of background job | Simpler architecture, no scheduler needed | API timeouts, inconsistent data, high API quota usage | Only during development/testing with <100 terms |
| Skip confidence intervals on revenue estimates | Faster UI development, simpler display | Operator trust erosion, bad decisions on noise | Never -- show ranges from day 1 |
| Use global distributions instead of per-group | Avoids cold start, always has data | Misses group-specific patterns (towel bars vs mirrors have very different ROAS profiles) | Acceptable as fallback, not as default for groups with sufficient data |
| Store experiment p-values in metadata JSONB instead of typed columns | Avoids migration, flexible schema | No DB-level constraints on validity, harder to query/aggregate | Acceptable for MVP if a typed migration follows within 2 sprints |
| Hardcode max-movements-per-run in code instead of configurable | Ship automation faster | Operators can't tune safety margins | Never -- hardcoded safety limits inevitably need adjustment |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Google Ads API (negative keywords) | Executing 50+ keyword mutations in a single API call, hitting operations-per-minute rate limit | Batch mutations in groups of 10-20 with 1-second delays between batches. The existing `service.ts` retry logic handles transient errors but not rate limit backpressure. |
| Google Ads API (GAQL queries) | Running additional GAQL queries for trend data (7d vs prev-7d) on top of the 6 existing parallel queries in `service.ts`, doubling API load | Use `funnel_snapshots_daily` table for historical comparisons. Only use live GAQL for current state. |
| Supabase (query_value_scores writes) | Upserting thousands of score rows one-by-one in a loop | Use Supabase bulk upsert with `onConflict` on the composite key. Batch in groups of 500. |
| Vercel serverless (computation timeouts) | Assuming default 10s timeout is sufficient for scoring computation | Set `export const maxDuration = 60` on computation routes. For background scoring, use Cloud Run instead of Vercel. |
| Google Sheets (supplemental feed updates) | Updating `custom_label_0` values for promoted/demoted terms without checking if the row already has the correct value | Read the current sheet state first. Only update changed rows. The existing `updateSupplementalFeedTiers()` in `tier-movement.ts` handles this correctly -- don't duplicate the logic. |
| `service.ts` cache | Calling `getExistingFunnelTerms()` from multiple API routes within the same 2-minute window and expecting identical data | The cache is module-level in `service.ts` and works correctly. But if a route calls it, mutates Google Ads (tier movement), and calls it again within 2 minutes, the cache returns stale pre-mutation data. Clear cache or wait for TTL expiry after mutations. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Computing percentiles on every page load | Revenue leakage page takes 10+ seconds, increasing linearly with term count | Pre-compute and cache. Recompute on schedule (every 1-6 hours) or on-demand with a "Refresh" button | >500 terms in funnel (likely already there) |
| N+1 queries joining `search_queries` with `keyword_metrics` for demand gap analysis | Demand gaps page takes 30+ seconds; Supabase connection pool exhaustion | Single JOIN query with indexes on `keyword` column. Precompute impression share gaps in a cached table | >2,000 keyword_metrics rows (currently ~2,784 SKUs x multiple terms) |
| Client-side sorting/filtering of 10,000+ recommendation rows | Browser freezes when opening revenue leakage page | Server-side pagination with `LIMIT/OFFSET`. Return top 50 with total count. Add filters (product group, tier, min confidence) | >1,000 recommendations |
| Bubble chart rendering with 59 product groups | Chart renders slowly, overlapping bubbles are unreadable | Use virtualized charting library. Limit to top 20 groups by spend with "Other" aggregate. Provide table view as default, chart as optional | Always -- 59 bubbles with overlapping labels is inherently messy |
| `getLabelTierPerformance()` returning 177 rows (59 groups x 3 tiers) and computing distributions for each | Scoring engine takes 20+ seconds for full computation | Compute distributions in parallel using `Promise.all()` per tier. Cache intermediate results. | >100 product groups |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Automation rules executing without operator authentication check | Unauthorized tier movements burning ad spend | All automated execution routes must verify caller identity -- Cloud Scheduler calls should use a CRON_SECRET header, operator-initiated calls should require session auth |
| Storing Google Ads API credentials in automation rule metadata | Credential exposure through `automation_rules` table reads | Never store credentials in rule definitions. Rules reference the credential source (env var name), not the credential itself |
| Revenue leakage data exposed without role-based access | Competitive intelligence data (dollar estimates, search terms, tier assignments) visible to unauthorized users | Ensure all `/api/shopping-funnel/*` routes check authentication. The existing routes do -- verify new routes follow the same pattern |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing "0 recommendations" when scoring engine is initializing or data is insufficient | Operators think system is broken (same as current hardcoded threshold problem) | Show "Computing recommendations..." with a progress indicator, or "Insufficient data for this product group -- need N more days of data" |
| Revenue leakage hero number updating on every page load with slightly different values | Operators lose trust in precision of estimates | Compute once per hour, show "as of [time]". Use consistent rounding ($2.4K not $2,387.42) |
| Automation rules executing silently with no notification | Operators discover changes days later, can't correlate spend changes to automated actions | Push notification or dashboard alert after every automated execution batch. Show "3 terms moved automatically today" banner |
| Experiment results page showing lift without context | "12% ROAS lift" sounds great but could mean $0.50/month | Always show absolute dollar impact alongside percentage lift |
| BCG matrix quadrant names (Stars/Dogs/Cash Cows) for product groups | Operators managing "Towel Bars" don't think in BCG terms | Use action-oriented labels: "Scale Up" (Stars), "Optimize" (Question Marks), "Maintain" (Cash Cows), "Review" (Dogs) |

## "Looks Done But Isn't" Checklist

- [ ] **Adaptive scoring engine**: Often missing the fallback hierarchy for sparse data -- verify scoring works for a product group with only 2 terms in LOW tier
- [ ] **Revenue leakage estimates**: Often missing uncertainty communication -- verify dollar estimates show ranges not point values
- [ ] **A/B testing framework**: Often missing minimum sample size enforcement -- verify an experiment cannot be resolved with <100 sample size
- [ ] **A/B testing framework**: Often missing experiment locking -- verify `executeTierMovement()` rejects movements for experiment-enrolled terms
- [ ] **Automation rules**: Often missing daily spend impact caps -- verify a rule evaluation run cannot recommend >$50/day incremental spend
- [ ] **Automation rules**: Often missing dry-run-first enforcement -- verify automated rules cannot execute without a dry-run preview persisted to `routing_recommendations`
- [ ] **Weekly digest**: Often missing "no data" states -- verify digest handles product groups with zero activity gracefully
- [ ] **Impact tracker**: Often missing predicted-vs-actual comparison -- verify executed movements have before/after performance stored
- [ ] **Product matrix**: Often missing pagination -- verify the page loads in <3s with all 59 product groups
- [ ] **Funnel data**: Often missing operational activation -- verify Cloud Scheduler is running and `funnel_snapshots_daily` has recent data before claiming trends are available

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Degenerate distributions causing mass movements | MEDIUM | 1. Pause automation rules immediately. 2. Review `policy_action_execution_log` for recent automated movements. 3. Use `negative_registry` rollback_tokens to reverse movements. 4. Add minimum sample size checks. 5. Re-run scoring with fallback to global distributions. |
| Runaway automated spend | HIGH | 1. Pause all automation rules. 2. Use `negative_registry` to identify and reverse recent automated movements. 3. Check Google Ads spend reports for impact. 4. Review and lower max-movements-per-run cap. 5. Require manual approval for 1 week while investigating. |
| Underpowered experiment declared significant | LOW | 1. Mark experiment as 'inconclusive' in `experiment_registry`. 2. Reverse treatment movements using `negative_registry`. 3. Extend experiment duration. 4. Add p-value requirement. |
| Trust erosion from bad revenue estimates | MEDIUM | 1. Switch all estimates to ranges. 2. Add "prediction accuracy" tracking. 3. Reduce hero number to conservative bound. 4. Rebuild operator trust over 2-4 weeks of accurate predictions. |
| Cache staleness causing stale scoring | LOW | 1. Switch to background computation model. 2. Add `Last computed: X minutes ago` to UI. 3. Add manual "Refresh" button for operators who need fresh data. |
| Experiment contamination from shared negatives | HIGH | 1. Mark affected experiments as contaminated. 2. Exclude contaminated data from analysis. 3. Add experiment locks before re-running. 4. Consider product-group-level experiments to reduce contamination surface. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Distribution cold start (degenerate percentiles) | Phase 1 -- Scoring Engine | Run scoring on all 59 groups; verify no group produces >50% misplaced terms |
| Automation spend caps | Phase 1 (caps) + Phase 3 (enforcement) | Simulate 100 terms recommended for movement; verify batch is capped at 10 |
| Underpowered A/B tests | Phase 3 -- A/B Testing | Create an experiment with sample_size=50; verify it cannot be resolved |
| Revenue estimate false precision | Phase 1 -- Revenue Leakage Dashboard | Verify UI shows ranges, not point estimates; verify confidence color coding |
| Cache staleness cascade | Phase 1 -- API route architecture | Load test: 5 concurrent requests to revenue leakage API; verify <3s response |
| Funnel snapshot gap | Pre-Phase 1 prerequisite | `SELECT COUNT(*) FROM funnel_snapshots_daily WHERE snapshot_date > NOW() - INTERVAL '7 days'` returns >0 |
| Experiment contamination | Phase 3 -- A/B Testing | Create experiment; attempt tier movement on enrolled term; verify rejection |
| Z-score on skewed data | Phase 1 -- Scoring Engine | Compute ROAS skewness for each tier; verify percentile ranks used instead of z-scores |

## Sources

- Codebase analysis: `service.ts` (2-min cache, 6 GAQL queries), `query-intelligence.ts` (hardcoded ROAS 3.6/3.1 thresholds), `control-center.ts` (BASELINE_TARGET_ROAS), `policy.ts` (PROMOTION_THRESHOLDS, evaluateGuardrails), `tier-movement.ts` (executeTierMovementBatch, CONFIDENCE_GATES)
- Schema: `experiment_registry` (no p_value column), `experiment_outcomes` (no confidence_interval), `funnel_snapshots_daily` (empty production table), `negative_registry` (rollback_token for undo)
- Milestone spec: `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md` (data volume: 177 campaigns x 59 product groups x 3 tiers)
- PROJECT.md tech debt: Cloud Scheduler not activated, funnel data needs re-backfill
- [Google Ads API Limits and Quotas](https://developers.google.com/google-ads/api/docs/best-practices/quotas) -- 10,000 operations per mutate request, token bucket rate limiting
- [Google Ads Statistical Methodology for Experiments](https://support.google.com/google-ads/answer/9232676?hl=en) -- 95% confidence, two-tailed testing
- [Shopping Campaign Priority Structures](https://savvyrevenue.com/blog/google-shopping-campaign-structure/) -- tier management patterns and priority-based funnel architecture
- [Google Ads Negative Keyword Automation Guide](https://www.negator.io/post/google-ads-api-scripts-negative-keyword-automation-developer-guide) -- batch mutation patterns, rate limit considerations
- [Google Ads Rate Limits](https://developers.google.com/google-ads/api/docs/productionize/rate-limits) -- token bucket algorithm, QPS per CID

---
*Pitfalls research for: Allied FeedOps v1.3c -- Actionable Shopping Intelligence*
*Researched: 2026-02-25*
