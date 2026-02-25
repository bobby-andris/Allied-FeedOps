# Architecture Patterns

**Domain:** Actionable Shopping Intelligence (v1.3c)
**Researched:** 2026-02-25
**Confidence:** HIGH (based on full source code audit of existing pipeline)

## Current Pipeline Architecture

The existing data flow is a 4-stage pipeline that runs entirely server-side in Next.js API routes:

```
Stage 1: DATA ACQUISITION
  service.ts (6 parallel GAQL queries, 2-min memory cache)
    getNeedsDecisionTerms() -> NeedsDecisionTerm[]
    getExistingFunnelTerms() -> ExistingFunnelTerm[]
    getLabelTierPerformance() -> LabelTierPerformance[]

Stage 2: INTELLIGENCE (scoring + classification)
  query-intelligence.ts
    decomposeSearchTerm() -> NLP features (product_object, modifiers, branded, competitor)
    enrichNeedsDecisionTerm() -> adds intent_features, recommendation, value_score
  intent/taxonomy.ts
    classifyIntent() -> IntentClassification (8 intent classes)

Stage 3: AGGREGATION + RECOMMENDATIONS
  control-center.ts
    buildOpportunityClusters() -> grouped by product_object
    buildRecommendationQueue() -> sorted by impact_score
    buildRoasRecommendations() -> ROAS target adjustments per label/tier

Stage 4: EXECUTION
  intent/policy.ts
    routeIntentDecision() -> branded/competitor/funnel routing
    evaluatePromotionDemotion() -> promote/demote/negative/hold
    evaluateGuardrails() -> go/hold/blocked status
    recommendBidPolicy() -> ROAS/CPA target adjustments
  intent/tier-movement.ts
    executeTierMovement() -> Supabase logging + negative keyword management
    updateSupplementalFeedTiers() -> Google Sheets custom_label_0 column update
```

## Recommended Architecture: New Components in the Pipeline

The new features insert into this pipeline at specific, well-defined points. No existing files need wholesale replacement -- only `enrichNeedsDecisionTerm()` in query-intelligence.ts gets its scoring logic delegated to the new tier-scoring.ts.

### Integration Diagram

```
Google Ads API (live, 2-min cache)
    |
    v
service.ts [UNCHANGED - DO NOT MODIFY]
  getNeedsDecisionTerms()
  getExistingFunnelTerms()
  getLabelTierPerformance()
    |
    +---> tier-scoring.ts [NEW - Phase 1]
    |       computeTierDistributions(labelTierPerf) -> TierDistributions
    |       scoreTerm(term, distributions) -> AdaptiveScore
    |       detectMisplacement(term, distributions) -> MisplacementResult
    |       estimateImpact(misplacement, distributions) -> DollarImpact
    |       |
    |       +---> Persists to query_value_scores (existing table, migration 033)
    |       +---> Persists to routing_recommendations (existing table, migration 033)
    |
    +---> query-intelligence.ts [MODIFIED - Phase 1]
    |       decomposeSearchTerm() [KEEP as-is]
    |       enrichNeedsDecisionTerm() [MODIFIED: delegates scoring to tier-scoring.ts]
    |
    +---> revenue-leakage.ts [NEW - Phase 1]
    |       computeRevenueLeakage(existingTerms, distributions) -> LeakageReport
    |       computeWastedSpend(existingTerms, distributions) -> WastedSpendAlert[]
    |       computeUnderInvested(existingTerms, keywordMetrics) -> UnderInvestedWinner[]
    |
    +---> demand-gaps.ts [NEW - Phase 2]
    |       computeImpressionShareGaps(searchQueries, keywordMetrics) -> ImpressionGap[]
    |       computeCpcOpportunities(existingTerms, keywordMetrics) -> CpcOpportunity[]
    |       computeSeasonalPatterns(keywordMetrics) -> SeasonalPattern[]
    |
    +---> competitive-intel.ts [NEW - Phase 2]
    |       computeBrandNonBrandSplit(terms) -> BrandSplit
    |       computeCompetitorMentions(terms) -> CompetitorAnalysis[]
    |       computeLongTailAnalysis(terms) -> TailAnalysis
    |
    +---> product-matrix.ts [NEW - Phase 2]
    |       computeBcgMatrix(labelTierPerf) -> BcgQuadrant[]
    |
    +---> automation-rules.ts [NEW - Phase 3]
    |       evaluateRules(rules, existingTerms, distributions) -> RuleEvaluation[]
    |       |
    |       +---> calls policy.ts evaluatePromotionDemotion() [UNCHANGED]
    |       +---> calls tier-movement.ts executeTierMovementBatch() [UNCHANGED]
    |
    +---> experiment-engine.ts [NEW - Phase 3]
    |       registerExperiment(config) -> writes experiment_registry
    |       assignTerms(experimentId, terms) -> writes experiment_assignments
    |       measureOutcomes(experimentId) -> writes experiment_outcomes
    |       |
    |       +---> calls tier-movement.ts for treatment group [UNCHANGED]
    |
    +---> impact-tracker.ts [NEW - Phase 4]
            computeImpact(executionLog, snapshots) -> ImpactReport
            computeWeeklyDigest(allSources) -> WeeklyDigest
```

### Component Boundaries

| Component | Responsibility | Reads From | Writes To | Dependencies |
|-----------|---------------|------------|-----------|-------------|
| `tier-scoring.ts` | Distribution computation, z-score placement, dollar impact estimation | service.ts exports (cached) | `query_value_scores`, `routing_recommendations` | None (pure computation + persistence) |
| `revenue-leakage.ts` | Misplacement detection, wasted spend alerts, under-investment identification | tier-scoring.ts output, `keyword_metrics` table | None (returns data to API route) | tier-scoring.ts |
| `demand-gaps.ts` | Impression share gaps, CPC opportunities, seasonal patterns | `search_queries` table, `keyword_metrics` table | None | None |
| `competitive-intel.ts` | Brand/non-brand split, competitor mentions, long-tail analysis | service.ts exports | None | query-intelligence.ts `decomposeSearchTerm()` |
| `product-matrix.ts` | BCG quadrant classification per product group | service.ts `getLabelTierPerformance()` | None | None |
| `automation-rules.ts` | Rule evaluation, scheduled execution with dry-run | `automation_rules` table (new), service.ts | `policy_action_execution_log`, `routing_recommendations` | tier-scoring.ts, policy.ts, tier-movement.ts |
| `experiment-engine.ts` | Experiment lifecycle (register, assign, measure, resolve) | `experiment_registry/assignments/outcomes` | Same tables | tier-movement.ts |
| `impact-tracker.ts` | Before/after measurement, weekly digest | `policy_action_execution_log`, `performance_snapshots` | None | None |

### Data Flow: How tier-scoring.ts Sits in the Pipeline

**Question 1 answered: Where does tier-scoring.ts sit?**

tier-scoring.ts is a **pure computation module** that sits between service.ts (data acquisition) and the API routes (data delivery). It does NOT intercept or modify the service.ts pipeline. Instead:

1. API routes (e.g., `/api/shopping-funnel/revenue-leakage`) call service.ts to get raw data
2. API routes pass raw data to tier-scoring.ts for adaptive scoring
3. tier-scoring.ts returns scored results to the API route
4. API route persists scores and returns JSON to client

```typescript
// revenue-leakage/route.ts (pseudocode)
export async function POST(req: Request) {
  // 1. Get raw data from existing service.ts (uses 2-min cache)
  const existingTerms = await getExistingFunnelTerms(options)
  const labelTierPerf = await getLabelTierPerformance(options)

  // 2. Compute distributions (NEW)
  const distributions = computeTierDistributions(labelTierPerf.rows)

  // 3. Score each term against distributions (NEW)
  const scoredTerms = existingTerms.terms.map(term => ({
    ...term,
    adaptiveScore: scoreTerm(term, distributions),
    misplacement: detectMisplacement(term, distributions),
  }))

  // 4. Persist computed scores (to existing empty tables)
  await persistScores(scoredTerms)

  // 5. Return revenue leakage report
  return Response.json(computeRevenueLeakage(scoredTerms, distributions))
}
```

**Key design decision:** tier-scoring.ts is called on-demand by API routes, not as middleware in the service.ts pipeline. This avoids modifying the critical service.ts data path and allows the 2-min cache to work as-is for the existing shopping funnel UI.

### Data Flow: Score Persistence to query_value_scores

**Question 2 answered: How do computed scores persist?**

The `query_value_scores` table (migration 033) already exists but is empty. The new tier-scoring.ts module writes to it after computation:

```typescript
// tier-scoring.ts
export async function persistAdaptiveScores(
  supabase: SupabaseClient,
  scores: AdaptiveScore[]
): Promise<void> {
  // Upsert to query_value_scores using (search_term, custom_label_0) as natural key
  // Includes: impact_score, expected_cvr, expected_conversion_value,
  //           expected_profit_proxy, uncertainty, tier_z_scores, recommended_tier
  await supabase.from('query_value_scores').upsert(
    scores.map(s => ({
      search_term: s.searchTerm,
      custom_label_0: s.customLabel0,
      impact_score: s.impactScore,
      expected_cvr: s.expectedCvr,
      expected_conversion_value: s.expectedConversionValue,
      expected_profit_proxy: s.expectedProfitProxy,
      uncertainty: s.uncertainty,
      // New fields for adaptive scoring
      tier_fit_scores: s.tierFitScores, // JSONB: { high: z-score, medium: z-score, low: z-score }
      recommended_tier: s.recommendedTier,
      net_monthly_impact: s.netMonthlyImpact,
      scored_at: new Date().toISOString(),
    })),
    { onConflict: 'search_term,custom_label_0' }
  )
}
```

**Persistence strategy:**
- Scores are computed on-demand when the revenue leakage API is called
- Persisted scores serve as a cache for subsequent page loads (avoid recomputation)
- Scores are refreshed when the API is called again (upsert overwrites stale scores)
- The `scored_at` timestamp lets the UI show data freshness
- Recommendations are persisted to `routing_recommendations` with status 'pending' for operator review

**Caching layers (3 tiers):**
1. **service.ts memory cache** (2 min) -- raw Google Ads data
2. **Supabase persistence** (query_value_scores) -- computed scores survive server restarts
3. **Client-side SWR/React Query** -- avoid re-fetching on tab switches

### Data Flow: Automation Rules Triggering Execution

**Question 3 answered: How do automation rules trigger the existing execution pipeline?**

The automation rules engine sits as a **scheduler-triggered evaluation layer** on top of the existing policy/execution stack:

```
Cloud Scheduler (daily cron)
    |
    v
POST /api/shopping-funnel/evaluate-rules (CRON_SECRET auth)
    |
    v
automation-rules.ts
  1. loadActiveRules() from automation_rules table
  2. For each rule:
     a. getExistingFunnelTerms() from service.ts
     b. computeTierDistributions() from tier-scoring.ts
     c. Evaluate rule conditions against term data
     d. Build TierMovementRequest[] for matching terms
  3. For each batch of movements:
     a. evaluateGuardrails() from policy.ts [EXISTING - unchanged]
     b. executeTierMovementBatch(movements, guardrailInput) [EXISTING - unchanged]
        - dryRun: true for first pass (log + persist recommendations)
        - dryRun: false only for rules with auto_execute: true
  4. Persist results to policy_action_execution_log [EXISTING table]
  5. Persist pending recommendations to routing_recommendations [EXISTING table]
```

**The automation rules layer does NOT bypass the guardrail system.** Every automated movement goes through:
1. `evaluateGuardrails()` -- can block/hold all movements
2. `validateTierMovement()` -- confidence gates still apply
3. `executeTierMovement()` -- full logging to `policy_action_execution_log`

**Rule storage:**

```sql
-- New table: automation_rules
CREATE TABLE automation_rules (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  description TEXT,
  conditions JSONB NOT NULL,
  -- Example conditions:
  -- { "metric": "roas", "operator": ">", "value": 5.0, "duration_days": 14, "tier": "medium" }
  -- { "metric": "conversions", "operator": "=", "value": 0, "spend_floor": 20.00, "duration_days": 30 }
  action TEXT NOT NULL,       -- 'promote' | 'demote' | 'block'
  auto_execute BOOLEAN DEFAULT false, -- false = dry-run only, creates recommendation
  confidence_floor NUMERIC DEFAULT 0.75,
  enabled BOOLEAN DEFAULT true,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_evaluated_at TIMESTAMPTZ,
  last_triggered_count INTEGER DEFAULT 0
);
```

### Data Flow: Experiment Framework and Tier Movement

**Question 4 answered: How does the experiment framework interact with tier movement?**

The experiment framework uses the tier movement system for the treatment group only, while the control group remains untouched:

```
experiment-engine.ts
  |
  |-- registerExperiment(config)
  |     Writes to experiment_registry (existing KEEP'd table)
  |     Config includes: hypothesis, term_selection_criteria,
  |                      treatment_tier, control_tier, duration_days, success_metric
  |
  |-- assignTerms(experimentId, candidateTerms)
  |     1. Filter candidates by selection criteria
  |     2. Random 50/50 split (or configurable ratio)
  |     3. Write assignments to experiment_assignments (existing KEEP'd table)
  |        Each row: experiment_id, search_term, custom_label_0, group ('treatment'|'control')
  |     4. For treatment group ONLY:
  |        executeTierMovementBatch() with movements to treatment_tier
  |        This uses the EXISTING pipeline (guardrails, logging, negatives)
  |     5. Control group: NO changes -- they stay in their current tier
  |
  |-- measureOutcomes(experimentId)
  |     1. Read assignments from experiment_assignments
  |     2. For each term in treatment and control:
  |        Get current performance from getExistingFunnelTerms()
  |     3. Compute treatment vs control deltas:
  |        - ROAS delta, CVR delta, revenue delta
  |        - Statistical significance (z-test on conversion rates)
  |     4. Write results to experiment_outcomes (existing KEEP'd table)
  |
  |-- resolveExperiment(experimentId)
  |     If treatment wins (p < 0.05):
  |       Move control terms to treatment tier (via executeTierMovementBatch)
  |     If control wins:
  |       Revert treatment terms (via executeTierMovementBatch)
  |     Update experiment_registry status to 'resolved'
```

**Critical constraint:** Only ONE experiment per (search_term, custom_label_0) at a time. The assignment process must check for conflicts against active experiments.

### Caching Strategy for Distribution Computations

**Question 5 answered: Caching strategy for expensive distribution computations**

Distribution computation involves:
1. Calling `getLabelTierPerformance()` -- returns ~177 rows (59 labels x 3 tiers)
2. Calling `getExistingFunnelTerms()` -- returns potentially thousands of terms
3. Computing percentiles, z-scores, and impact estimates

**Strategy: 3-layer cache with progressive freshness**

```
Layer 1: service.ts memory cache (2 min TTL)
  Already exists. Raw GAQL results cached in-process.
  Shared across all API routes in the same server instance.

Layer 2: Computed distributions cache (10 min TTL, in-memory)
  NEW: tier-scoring.ts maintains a module-level cache:
    let distributionCache: { data: TierDistributions; computedAt: number } | null = null
    const DISTRIBUTION_CACHE_TTL_MS = 10 * 60 * 1000

  Rationale: Distributions change slowly (daily at most).
  Computing from ~177 LabelTierPerformance rows is fast (~5ms).
  This prevents recomputation on every page load.

Layer 3: Persisted scores in Supabase (query_value_scores)
  Per-term scores persisted on computation.
  API routes check: if scores exist and scored_at < 1 hour ago, return persisted.
  If stale or missing, recompute from live data.

  This handles server restarts and cold starts -- scores survive.
```

**Performance budget:**
- Distribution computation: ~5ms (177 rows, percentile calc)
- Per-term scoring: ~0.1ms x 1000 terms = ~100ms
- Supabase upsert: ~200ms for 1000 rows (batched)
- Total revenue-leakage API response: <3 seconds (target met)

**What NOT to cache:** Revenue leakage dollar estimates should be recomputed from fresh distributions, not cached independently. The dollar estimates are derived values and stale estimates are worse than slightly stale scores.

## Patterns to Follow

### Pattern 1: Computation Module + API Route Separation

**What:** All heavy computation lives in `/lib/optimization/` modules. API routes in `/app/api/` are thin wrappers that call computation modules, handle auth, and return JSON.

**When:** Every new feature.

**Example:**
```typescript
// lib/optimization/tier-scoring.ts -- COMPUTATION (testable, no HTTP concerns)
export function computeTierDistributions(rows: LabelTierPerformance[]): TierDistributions {
  // Pure function, no side effects, easily unit-testable
}

// app/api/shopping-funnel/revenue-leakage/route.ts -- THIN WRAPPER
export async function POST(req: Request) {
  const data = await getExistingFunnelTerms(options)
  const distributions = computeTierDistributions(labelTierPerf.rows)
  const leakage = computeRevenueLeakage(data, distributions)
  return Response.json(leakage)
}
```

**Why:** Matches existing pattern (query-intelligence.ts + control-center.ts are pure computation; API routes call them). Keeps heavy logic testable without HTTP mocking.

### Pattern 2: Existing Persistence Helper for New Tables

**What:** Use `insertRowsSafe()` from `intent/persistence.ts` for all new database writes. It handles missing table errors gracefully.

**When:** Writing to any table that might not exist in a given environment.

**Example:**
```typescript
import { insertRowsSafe } from '@/lib/intent/persistence'

const result = await insertRowsSafe(supabase, 'automation_rules', [ruleRow])
if (result.warning) {
  console.warn(result.warning) // Table missing, but don't crash
}
```

### Pattern 3: Guardrail-Gated Execution

**What:** Every automated action goes through the guardrail evaluation before execution.

**When:** Any code path that modifies Google Ads or Google Sheets data.

**Example:**
```typescript
// ALWAYS evaluate guardrails before batch execution
const guardrailDecision = evaluateGuardrails(guardrailInput)
if (guardrailDecision.status === 'blocked') {
  return { blocked: true, reason: guardrailDecision.incidents }
}
// Then proceed with executeTierMovementBatch()
```

### Pattern 4: service.ts as Read-Only Data Source

**What:** Never modify service.ts. Call its exports and process the results downstream.

**When:** Always.

**Why:** service.ts is the most critical file in the dashboard -- it's the live Google Ads integration used daily. Any modification risks breaking the working shopping funnel management system. All new computation modules consume its exports.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Modifying service.ts Data Path

**What:** Adding new computation logic inside service.ts functions.
**Why bad:** service.ts is 1600+ lines, handles 6 parallel GAQL queries with retry logic and caching. Modifying it risks breaking the live shopping funnel management that operators use daily.
**Instead:** Create new modules that consume service.ts exports.

### Anti-Pattern 2: Client-Side Distribution Computation

**What:** Sending raw term data to the browser and computing distributions in React components.
**Why bad:** ExistingFunnelTerms can contain thousands of terms. Distribution computation involves sorting, percentile calculation, and z-score math. This belongs server-side.
**Instead:** Compute in API routes, return pre-computed scores and recommendations to the client.

### Anti-Pattern 3: Bypassing Guardrails for Automation

**What:** Having automation rules call `postDecisions()` or `updateExistingAssignments()` directly, skipping the guardrail evaluation.
**Why bad:** Automated execution without guardrails can cause runaway spend. The guardrail system exists specifically to prevent this.
**Instead:** Always route through `evaluateGuardrails()` -> `executeTierMovementBatch()`.

### Anti-Pattern 4: Separate Caching Infrastructure

**What:** Building a Redis/separate caching layer for computed distribution scores.
**Why bad:** Over-engineering. The existing 2-min memory cache in service.ts + Supabase persistence for computed scores is sufficient for this use case (single operator, internal dashboard).
**Instead:** Use the 3-layer cache strategy described above (service.ts cache -> module-level distribution cache -> Supabase persisted scores).

### Anti-Pattern 5: Direct Google Ads Writes from New Modules

**What:** New modules calling the Google Ads API directly to add negatives or modify campaigns.
**Why bad:** The entire audit trail, negative registry, and sheet update logic is in tier-movement.ts. Bypassing it creates orphaned state.
**Instead:** Always use `executeTierMovement()` or `executeTierMovementBatch()` for any Google Ads mutations.

## Build Order (Minimizing Dependencies)

**Question 6 answered: Build order that minimizes dependencies**

```
Phase 1: Revenue Leakage Detection & Tier Optimization
  Step 1.1: tier-scoring.ts [NO dependencies on other new code]
    - computeTierDistributions()
    - scoreTerm()
    - detectMisplacement()
    - estimateImpact()
    - persistAdaptiveScores()

  Step 1.2: Modify enrichNeedsDecisionTerm() in query-intelligence.ts
    [DEPENDS ON: 1.1 tier-scoring.ts]
    - Replace hardcoded thresholds with calls to tier-scoring.ts
    - Keep decomposeSearchTerm() unchanged

  Step 1.3: revenue-leakage.ts + API route
    [DEPENDS ON: 1.1 tier-scoring.ts]
    - computeRevenueLeakage()
    - POST /api/shopping-funnel/revenue-leakage

  Step 1.4: Revenue Leakage UI + one-click execution wiring
    [DEPENDS ON: 1.3 API route, existing tier-movement API]

Phase 2: Market Intelligence (independent of Phase 1 execution pipeline)
  Step 2.1: demand-gaps.ts + API route [NO dependencies on Phase 1]
    - Reads from search_queries + keyword_metrics tables only

  Step 2.2: competitive-intel.ts + API route [NO dependencies on Phase 1]
    - Uses decomposeSearchTerm() from query-intelligence.ts (unchanged part)

  Step 2.3: product-matrix.ts + API route [NO dependencies on Phase 1]
    - Uses getLabelTierPerformance() from service.ts directly

  Step 2.4: Market Intelligence UI
    [DEPENDS ON: 2.1, 2.2, 2.3 API routes]

Phase 3: Automation & Experiments
  Step 3.1: automation_rules table migration [NO code dependencies]

  Step 3.2: automation-rules.ts + API route
    [DEPENDS ON: 1.1 tier-scoring.ts, existing policy.ts + tier-movement.ts]

  Step 3.3: experiment-engine.ts + API routes
    [DEPENDS ON: existing tier-movement.ts, experiment_* tables (already KEEP'd)]

  Step 3.4: Automation + Experiment UI
    [DEPENDS ON: 3.2, 3.3 API routes]

Phase 4: Executive Reporting (pure read-only, depends on data from Phases 1-3)
  Step 4.1: impact-tracker.ts + API route
    [DEPENDS ON: policy_action_execution_log having data from Phase 1/3 executions]

  Step 4.2: Weekly digest API route
    [DEPENDS ON: All prior API routes for data aggregation]

  Step 4.3: Executive scorecard UI
    [DEPENDS ON: 4.1, 4.2 API routes]
```

**Phase 2 can run in parallel with Phase 1** (steps 2.1-2.3 have zero dependency on tier-scoring.ts). Phase 3 requires Phase 1 completion. Phase 4 requires Phases 1+3 to have generated data.

## File Organization

### New Files to Create

```
dashboard/src/lib/optimization/
  tier-scoring.ts          # Phase 1 - core adaptive scoring engine
  revenue-leakage.ts       # Phase 1 - leakage computation
  demand-gaps.ts           # Phase 2 - impression share / CPC / seasonal
  competitive-intel.ts     # Phase 2 - brand split, competitor mentions
  product-matrix.ts        # Phase 2 - BCG quadrant classification

dashboard/src/lib/automation/
  automation-rules.ts      # Phase 3 - rule evaluation engine
  experiment-engine.ts     # Phase 3 - experiment lifecycle

dashboard/src/lib/reporting/
  impact-tracker.ts        # Phase 4 - before/after measurement
  weekly-digest.ts         # Phase 4 - weekly summary computation

dashboard/src/app/api/shopping-funnel/
  revenue-leakage/route.ts     # Phase 1
  demand-gaps/route.ts         # Phase 2
  competitive-intel/route.ts   # Phase 2
  product-matrix/route.ts      # Phase 2
  evaluate-rules/route.ts      # Phase 3
  experiments/route.ts         # Phase 3
  impact-tracker/route.ts      # Phase 4
  weekly-digest/route.ts       # Phase 4
```

### Files to Modify (minimal changes)

```
dashboard/src/lib/optimization/query-intelligence.ts
  - enrichNeedsDecisionTerm(): delegate scoring to tier-scoring.ts
  - Keep: decomposeSearchTerm(), all token lists, all NLP logic

dashboard/src/lib/optimization/control-center.ts
  - buildRoasRecommendations(): replace BASELINE_TARGET_ROAS constant
    with dynamically computed baselines from tier-scoring.ts
  - buildRecommendationQueue(): extend to accept ExistingFunnelTerm[]
    (currently only accepts NeedsDecisionTerm[])
```

### Files NOT to Modify

```
dashboard/src/lib/shopping-funnel/service.ts     # Critical live integration
dashboard/src/lib/intent/policy.ts               # Working policy engine
dashboard/src/lib/intent/tier-movement.ts        # Working execution pipeline
dashboard/src/lib/intent/persistence.ts          # Shared utility
dashboard/src/lib/intent/taxonomy.ts             # Working intent classifier
All existing API routes under /api/search-terms/  # Used daily
All existing API routes under /api/ga4/           # Working attribution
```

## Scalability Considerations

| Concern | Current Scale | At Full Catalog | Mitigation |
|---------|--------------|-----------------|------------|
| Term volume per API call | ~500-2000 terms | ~5000+ terms | Pagination in service.ts (limit/offset already supported) |
| Distribution computation | 177 rows (59 x 3) | Same (fixed by campaign structure) | Trivial at any scale |
| Score persistence | ~2000 upserts | ~5000 upserts | Batch upsert in chunks of 500 |
| Automation rule evaluation | 5-10 rules | 20-50 rules | Sequential is fine; each rule is O(n) on term count |
| Experiment assignments | 50-100 terms | 200-500 terms | Manageable; limited by operator willingness |
| Google Ads API rate limits | 6 queries per load | Same | 2-min cache prevents hammering |

## Sources

- Source code audit: `dashboard/src/lib/shopping-funnel/service.ts` (1600+ lines)
- Source code audit: `dashboard/src/lib/optimization/query-intelligence.ts` (267 lines)
- Source code audit: `dashboard/src/lib/optimization/control-center.ts` (285 lines)
- Source code audit: `dashboard/src/lib/intent/policy.ts` (631 lines)
- Source code audit: `dashboard/src/lib/intent/tier-movement.ts` (312 lines)
- Source code audit: `dashboard/src/lib/shopping-funnel/types.ts` (245 lines)
- Source code audit: `dashboard/src/lib/intent/types.ts` (261 lines)
- Milestone spec: `docs/plans/2026-02-21-gsd-milestone-v1.3-actionable-intelligence.md`
- Project context: `.planning/PROJECT.md`
- Migration 033 tables: `query_value_scores`, `routing_recommendations`, `opportunity_clusters` (confirmed in production, empty)
- Migration 035b tables: 10 KEEP'd including `experiment_registry/assignments/outcomes`, `policy_action_execution_log`, `negative_registry` (confirmed in production, empty)
