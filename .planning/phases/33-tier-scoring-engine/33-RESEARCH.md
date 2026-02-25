# Phase 33: Tier Scoring Engine - Research

**Researched:** 2026-02-25
**Domain:** Distribution-based statistical scoring for Google Shopping tier optimization
**Confidence:** HIGH

## Summary

Phase 33 replaces hardcoded ROAS tier thresholds (3.6/3.1/2.6 in `query-intelligence.ts` line 138, `control-center.ts` lines 3-7) with a dynamically computed, distribution-based scoring engine. The core computation is straightforward: pull live tier performance data from `getLabelTierPerformance()` (177 rows = 59 product groups x 3 tiers), compute percentile distributions per tier per `custom_label_0` group, score each search term using robust z-scores (median/MAD) against its tier's distribution, and surface misplaced terms with dollar-impact estimates and confidence scores. The engine writes computed scores to the already-provisioned `query_value_scores` table (extended with `tier_fit_scores`, `recommended_tier`, `net_monthly_impact`, `scored_at` columns in Phase 32 migration 037).

The UI is a new page with a 4-level drill-down: all groups overview -> single group with tier distributions -> single tier with term scores -> individual term detail with scoring breakdown. Per CONTEXT.md decisions, the hero section leads with actionable callouts ("23 terms may be in the wrong tier -- $2.4K/mo potential impact"), statistics are always visible with plain English explanations, and every term has an always-visible confidence badge (High/Medium/Low). This phase computes and displays scores only; taking action on misplacements is Phase 34.

**Primary recommendation:** Build `tier-scoring.ts` as a pure computation module in `dashboard/src/lib/optimization/` that consumes `service.ts` exports, uses `simple-statistics` for all math, and persists to `query_value_scores`. Serve via a new API route with `maxDuration = 60` and 10-minute module-level cache on distributions. Build the UI as a new `/tier-scoring` page using the 4-level drill-down architecture with Recharts for distributions and shadcn/ui for tables and scorecards.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Page Entry Point & Hero**: Lead with actionable callouts, not raw statistics: "23 terms may be in the wrong tier -- $2.4K/mo potential impact". Hero section communicates what needs attention and quantifies the revenue opportunity (increased sales + reduced wasted ad spend). The overarching goal is optimizing ad spend to drive more sales -- every insight should connect back to revenue impact.
- **Information Hierarchy (Drill-Down)**: Level 1: All custom_label_0 groups overview -- show all four metrics (ROAS, CVR, CPC, CTR) per group in compact format, with all three tiers visible per group. Level 2: Drill into one custom_label_0 group -- see tier-level distributions and misplaced terms within that group. Level 3: Drill into one tier within a group -- see individual term scores and placements. Level 4: Individual term detail -- full scoring breakdown with verdict + scorecard. At each drill-down level, guide the business user on where to look next and why. Groups sorted by attention needed: prioritize groups where action could increase sales or reduce wasted ad spend.
- **Statistics & Language**: Statistics are always visible (not hidden behind toggles) -- transparency builds decision-making confidence. Every statistical measure must be explained in plain English tied to the data being shown. No jargon without explanation -- the audience includes data scientists AND business stakeholders.
- **Scoring Transparency (Per-Term)**: Combined approach: lead with a plain English verdict ("This term is a strong fit for HIGH tier because..."), then show a visual scorecard with individual factors (ROAS position, CVR position, consistency, data volume). Each factor clickable/expandable to reveal underlying math. Show peer context: "This term's 5.2x ROAS ranks in the top 15% of Towel Bar terms."
- **Confidence Scores**: Always-visible confidence badge on every term (High/Medium/Low confidence), color-coded. Confidence combines: data volume, metric consistency, statistical significance, NLP intent alignment. Badge is always present -- not just when confidence is low.
- **Misplaced Term Flagging**: Inline arrow indicators on every term list view showing current -> recommended tier with potential impact. PLUS a dedicated "Misplaced Terms" section that aggregates all mismatch terms as an action queue sorted by dollar impact. Both views coexist.
- **Degraded States & Sparse Data**: Always show which fallback level is being used for scoring (per-group data, category-wide averages, or global defaults) -- full transparency on data source. Groups with zero scored terms: show with "No data yet" state (don't hide).
- **Boundary Auto-Adjustment**: Cap maximum boundary shift per recalculation to prevent wild swings from data anomalies -- show warning if uncapped shift would have been larger. Manual override allowed on ANY boundary or scoring decision -- transparent tracking shows "Manual override active -- data suggests 3.8x but pinned at 4.0x". Philosophy: the system recommends, the user decides.

### Claude's Discretion
- Visualization approach for distributions (not box plots or stat cards -- something accessible that becomes more granular on demand)
- Guided drill-down pattern (inline callouts, sidebar, or hybrid)
- Sparse tier visual treatment and new-term scoring threshold
- Recalculation frequency and boundary change display pattern
- Exact layout and component structure

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TIER-01 | User can view dynamically computed tier performance distributions (p25/p50/p75 ROAS/CVR/CPC/CTR per tier) replacing hardcoded 3.6/3.1/2.6 thresholds | `computeTierDistributions()` in new `tier-scoring.ts` using `simple-statistics` quantile/quantileSorted; reads `getLabelTierPerformance()` from existing `service.ts`; replaces constants at `query-intelligence.ts:138`, `control-center.ts:3-7` |
| TIER-02 | User can see tier boundary thresholds that auto-adjust based on actual MEDIUM tier percentiles (LOW floor = MEDIUM p75, HIGH ceiling = MEDIUM p25) | Dynamic boundary computation in `tier-scoring.ts`; boundary shift capped per recalculation to prevent wild swings; manual override support with tracking |
| TIER-03 | User can view per-term scoring with robust z-scores (median/MAD) accounting for right-skewed ROAS distributions | `simple-statistics` zScore function applied as `(value - median) / MAD`; robust z-scores handle right-skewed ROAS without log transform; ROAS capped at p99 before distribution computation |
| TIER-04 | User can see hierarchical fallback scoring when per-group data is sparse (per-group -> global -> sensible defaults) | Three-level fallback: per-group-per-tier (>=5 terms with non-zero metrics) -> per-tier-global (all groups combined) -> hardcoded last-resort defaults; UI shows which fallback level is active per group |
| TIER-05 | User can see "Insufficient data" degraded state when a tier has fewer than 5 terms with non-zero metrics | Minimum sample threshold of 5 terms with non-zero metrics; below threshold, tier shows degraded state with "Insufficient data" indicator and falls back to higher-level distribution |
| TIER-06 | User can view confidence scores based on data volume, consistency, statistical significance, and NLP intent alignment | Four-factor model: data volume (30%, `min(clicks/100, 1)`), consistency (30%, `1 - CoV` of daily ROAS), statistical significance (20%, chi-squared p-value), NLP alignment (20%, intent features match tier semantics); combined into 0-1 score; displayed as High/Medium/Low badge |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| simple-statistics | ^7.8.8 | Percentiles, robust z-scores, IQR, chi-squared | Zero-dep, 30KB, TypeScript types included, functional API for tree-shaking. Already selected in v1.3c research. |
| recharts | ^3.7.0 (installed) | Distribution visualizations, scatter plots | Already installed and used in 3 components. Handles all chart needs. |
| @radix-ui (via shadcn/ui) | installed | Collapsible, Tooltip, Dialog for drill-down | Already installed. Collapsible for expandable scorecard factors. |
| lucide-react | ^0.563.0 (installed) | Icons (ArrowUp, ArrowDown, AlertCircle, etc.) | Already installed and used across all dashboard pages. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PostgreSQL 15 (Supabase) | existing | `percentile_cont()` for heavy aggregation | When computing distributions across all ~3K terms (background/API route) |
| Vercel Crons | existing | Optional scheduled recomputation | If on-demand computation exceeds 60s timeout; daily 5:30am UTC |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| simple-statistics | mathjs | 23x larger (700KB), general-purpose math lib; overkill for this use case |
| simple-statistics | jStat | Stale (last major update 2020), 7x larger, community @types only |
| Recharts custom distribution | D3.js directly | Already wrapped by Recharts; adding D3 direct creates two charting systems |

**Installation:**
```bash
cd dashboard && npm install simple-statistics
```

## Architecture Patterns

### Recommended Project Structure
```
dashboard/src/lib/optimization/
  tier-scoring.ts          # Pure computation: distributions, z-scores, confidence, impact
  tier-scoring.types.ts    # TypeScript interfaces for all tier-scoring data

dashboard/src/app/api/shopping-funnel/
  tier-scoring/route.ts    # API route: thin wrapper, calls tier-scoring.ts, persists to DB

dashboard/src/app/(dashboard)/tier-scoring/
  page.tsx                 # Client page: 4-level drill-down, all state management
  components/
    HeroCallout.tsx        # Actionable hero: "23 terms may be in the wrong tier"
    GroupOverview.tsx       # Level 1: All groups with compact 4-metric + 3-tier grid
    GroupDetail.tsx         # Level 2: Single group with distributions + misplaced terms
    TierDetail.tsx          # Level 3: Single tier with individual term scores
    TermScorecard.tsx       # Level 4: Individual term scoring breakdown
    DistributionChart.tsx   # Reusable distribution visualization (Recharts)
    ConfidenceBadge.tsx     # Reusable High/Medium/Low badge with color
    FallbackIndicator.tsx   # Shows which data source level is active
    MisplacedTermRow.tsx    # Inline arrow indicator with impact estimate
```

### Pattern 1: Computation Module + API Route Separation
**What:** All statistical computation in `/lib/optimization/tier-scoring.ts`. API route in `/app/api/` is a thin wrapper that fetches data, calls computation, persists results, returns JSON.
**When to use:** Always for this phase. Matches existing pattern (`query-intelligence.ts` + `control-center.ts` are pure computation).
**Example:**
```typescript
// tier-scoring.ts — pure computation, no HTTP concerns
export function computeTierDistributions(
  rows: LabelTierPerformance[],
  options?: { fallbackToGlobal?: boolean }
): Map<string, GroupDistributions> {
  // Group by custom_label_0
  // For each group, compute per-tier distributions
  // If tier has <5 terms with non-zero metrics, fall back
  const grouped = groupBy(rows, 'custom_label_0')
  // ...
}

export function scoreTerm(
  term: ExistingFunnelTerm,
  distributions: GroupDistributions,
  globalFallback: TierDistribution
): TermScore {
  // Robust z-score: (value - median) / MAD
  // Confidence: 4-factor model
  // Returns: score, confidence, recommended tier, impact estimate
}

// API route — thin wrapper
export async function GET(req: Request) {
  const labelTierPerf = await getLabelTierPerformance(options)
  const existingTerms = await getExistingFunnelTerms(options)
  const distributions = computeTierDistributions(labelTierPerf.rows)
  const scored = existingTerms.terms.map(t => scoreTerm(t, ...))
  await persistScores(scored) // upsert to query_value_scores
  return Response.json({ distributions, scored, computedAt: new Date() })
}
```

### Pattern 2: Hierarchical Fallback for Sparse Data
**What:** Three-level data source hierarchy: per-group-per-tier -> per-tier-global -> hardcoded defaults. Every computation result tags which level was used.
**When to use:** Any time computing distributions or scoring terms.
**Example:**
```typescript
type FallbackLevel = 'per_group' | 'global' | 'defaults'

interface TierDistribution {
  p25: number; p50: number; p75: number
  mean: number; mad: number
  sampleSize: number
  fallbackLevel: FallbackLevel
}

function getDistribution(
  groupRows: LabelTierPerformance[],
  globalRows: LabelTierPerformance[],
  tier: FunnelTier
): TierDistribution {
  const groupTierRows = groupRows.filter(r => r.tier === tier)
  if (groupTierRows.length >= 5) {
    return computeDistribution(groupTierRows, 'per_group')
  }
  const globalTierRows = globalRows.filter(r => r.tier === tier)
  if (globalTierRows.length >= 5) {
    return computeDistribution(globalTierRows, 'global')
  }
  return DEFAULT_DISTRIBUTIONS[tier] // hardcoded last resort
}
```

### Pattern 3: Module-Level Distribution Cache
**What:** Cache computed distributions in a module-level variable with 10-minute TTL. Distributions change slowly (at most daily), while per-term scoring happens on every page load.
**When to use:** In tier-scoring.ts to avoid recomputing distributions on every API call.
**Example:**
```typescript
let distributionCache: {
  data: Map<string, GroupDistributions>
  computedAt: number
} | null = null
const DISTRIBUTION_CACHE_TTL_MS = 10 * 60 * 1000 // 10 minutes

export function getCachedDistributions(
  rows: LabelTierPerformance[]
): Map<string, GroupDistributions> {
  const now = Date.now()
  if (distributionCache && (now - distributionCache.computedAt) < DISTRIBUTION_CACHE_TTL_MS) {
    return distributionCache.data
  }
  const data = computeTierDistributions(rows)
  distributionCache = { data, computedAt: now }
  return data
}
```

### Pattern 4: Boundary Shift Capping
**What:** Cap maximum tier boundary change per recalculation to prevent wild swings. Track and display when the uncapped shift would have been larger.
**When to use:** Every time tier boundaries are recomputed.
**Example:**
```typescript
const MAX_BOUNDARY_SHIFT_PERCENT = 0.15 // 15% max shift per recalculation

function capBoundaryShift(
  newBoundary: number,
  previousBoundary: number | null
): { value: number; capped: boolean; uncappedValue: number } {
  if (!previousBoundary) return { value: newBoundary, capped: false, uncappedValue: newBoundary }
  const shift = (newBoundary - previousBoundary) / previousBoundary
  if (Math.abs(shift) <= MAX_BOUNDARY_SHIFT_PERCENT) {
    return { value: newBoundary, capped: false, uncappedValue: newBoundary }
  }
  const cappedValue = previousBoundary * (1 + Math.sign(shift) * MAX_BOUNDARY_SHIFT_PERCENT)
  return { value: cappedValue, capped: true, uncappedValue: newBoundary }
}
```

### Anti-Patterns to Avoid
- **Modifying service.ts:** service.ts is 1600+ lines of live Google Ads integration. Never modify it. Consume its exports.
- **Client-side distribution computation:** ExistingFunnelTerms can have thousands of terms. Compute server-side, return pre-computed scores.
- **Standard z-scores on raw ROAS:** ROAS is right-skewed. Use robust z-scores (median/MAD) or percentile ranks. Cap outliers at p99.
- **Point estimate dollar values:** Always show ranges. "$800-$3,200/month" not "$2,400/month". Use conservative bound for hero number.
- **Computing on every page load without caching:** Use module-level distribution cache (10 min TTL) + persisted scores in `query_value_scores` table.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Percentile computation | Custom sort + index math | `simple-statistics quantile()` | Edge cases with ties, interpolation modes, empty arrays |
| Robust z-score (MAD) | Manual median absolute deviation | `simple-statistics medianAbsoluteDeviation()` + manual z-score | MAD computation has subtleties around zero-MAD (all identical values) |
| IQR / whisker bounds | Custom Q1/Q3 math | `simple-statistics interquartileRange()` | Consistent with quantile interpolation |
| Chi-squared test | Manual chi-squared formula | `simple-statistics chiSquaredGoodnessOfFit()` | Degrees of freedom, critical value lookup, edge cases |
| Data grouping | Manual reduce loops | Lodash-style `groupBy` utility or Array.reduce pattern | Already common in codebase; keep consistent |
| Distribution charts | D3.js from scratch | Recharts BarChart with computed bin data | Recharts is already installed; D3 adds second charting system |

**Key insight:** simple-statistics covers every statistical function needed for Phase 33. Its functional API means individual functions are tree-shakeable. Do not import mathjs or jStat for any reason.

## Common Pitfalls

### Pitfall 1: Degenerate Percentiles from Sparse Tiers
**What goes wrong:** 59 product groups x 3 tiers = 177 combinations. Many will have 2-5 terms in a tier. Computing percentiles on 3 data points produces unstable thresholds that flip wildly between scoring runs.
**Why it happens:** Developers test with aggregate data ("3K terms total") and miss per-group-per-tier sample size reduction.
**How to avoid:** Minimum sample size of 5 terms with non-zero metrics per tier. Below this, fall back to global tier distributions. Log which fallback level is used. If >50% of terms flag as misplaced, the distribution is degenerate, not the data.
**Warning signs:** Threshold values changing >20% between runs; "100% of terms in tier X are misplaced"; revenue leakage estimate swinging wildly between page loads.

### Pitfall 2: Z-Scores on Right-Skewed ROAS Data
**What goes wrong:** ROAS distributions in Google Shopping are heavily right-skewed (most terms ROAS 0-2, occasional outliers at 10-50). Standard z-scores using mean/stddev are meaningless.
**Why it happens:** Z-scores are the textbook approach, but assume normal distribution.
**How to avoid:** Use robust z-scores: `(value - median) / MAD`. Cap ROAS at p99 before computing distributions. Validate: compute skewness of actual ROAS data -- if skewness > 1.0, robust z-scores are mandatory.
**Warning signs:** Standard deviation > 2x the mean; >40% of terms flagged as misplaced; negative tier boundaries.

### Pitfall 3: Revenue Estimate False Precision
**What goes wrong:** Dollar impact estimates multiply 3 uncertain variables (CVR delta x impressions x AOV). Combined error can be 2-3x in either direction. Showing "$2,400/month" erodes trust when actual impact is $800 or -$200.
**Why it happens:** Spec says "show dollar impact." Developers display point estimates because it's simpler.
**How to avoid:** Show ranges from day 1: "$800-$3,200/month". Use conservative bound (p25 of estimates) for hero number. Color-code by confidence. Always say "estimate" or "opportunity," never "leakage" alone.
**Warning signs:** Estimates >50% of total campaign spend; operator approval rate dropping.

### Pitfall 4: Vercel Serverless Timeout
**What goes wrong:** Computing distributions for 177 groups + scoring thousands of terms + persisting to Supabase can exceed Vercel's default 10s timeout (60s on Pro).
**Why it happens:** Adding heavy computation on top of cached data path without adjusting timeout.
**How to avoid:** Set `export const maxDuration = 60` on scoring API route. Use module-level distribution cache (10 min) to avoid recomputing on every request. Use persisted `query_value_scores` as fast-path for subsequent loads. Consider background computation if timing is tight.
**Warning signs:** 504 Gateway Timeout on scoring routes; page load >5 seconds.

### Pitfall 5: Boundary Shift Instability
**What goes wrong:** When data changes significantly (new product launch, seasonal shift, content optimization), boundaries can shift dramatically between recalculations, causing mass reclassification of terms.
**Why it happens:** Dynamic boundaries without shift caps react immediately to data changes.
**How to avoid:** Cap maximum boundary shift at 15% per recalculation (per CONTEXT.md decision). Display warning when uncapped shift would have been larger. Allow manual override with transparent tracking.
**Warning signs:** >20 terms changing recommended tier in a single recalculation; boundary values jumping by >20%.

## Code Examples

### Robust Z-Score Computation
```typescript
import { median, medianAbsoluteDeviation, quantile } from 'simple-statistics'

function computeRobustZScore(value: number, values: number[]): number {
  const med = median(values)
  const mad = medianAbsoluteDeviation(values)
  if (mad === 0) return 0 // All values identical
  return (value - med) / mad
}

// Cap outliers at p99 before distribution computation
function capOutliers(values: number[]): number[] {
  const p99 = quantile(values, 0.99)
  return values.map(v => Math.min(v, p99))
}
```

### Four-Factor Confidence Score
```typescript
function computeConfidence(
  term: { clicks: number; conversions: number; dailyRoas: number[] },
  intentFeatures: QueryIntentFeatures,
  tierSemantics: TierSemantics
): { score: number; level: 'High' | 'Medium' | 'Low'; factors: ConfidenceFactors } {
  // Factor 1: Data volume (30%)
  const volumeScore = Math.min(term.clicks / 100, 1) * 0.30

  // Factor 2: Consistency (30%) — coefficient of variation of daily ROAS
  const cov = term.dailyRoas.length > 1
    ? standardDeviation(term.dailyRoas) / (mean(term.dailyRoas) || 1)
    : 1
  const consistencyScore = Math.max(0, Math.min(1, 1 - cov)) * 0.30

  // Factor 3: Statistical significance (20%)
  // Higher conversion count = more statistically reliable
  const sigScore = Math.min(term.conversions / 10, 1) * 0.20

  // Factor 4: NLP intent alignment (20%)
  // Does the term's intent profile match expected tier behavior?
  const alignmentScore = computeIntentAlignment(intentFeatures, tierSemantics) * 0.20

  const score = volumeScore + consistencyScore + sigScore + alignmentScore
  const level = score >= 0.70 ? 'High' : score >= 0.40 ? 'Medium' : 'Low'

  return {
    score,
    level,
    factors: { volumeScore, consistencyScore, sigScore, alignmentScore }
  }
}
```

### Dollar Impact Range Estimation
```typescript
interface ImpactRange {
  low: number    // conservative (p25 scenario)
  mid: number    // expected (p50 scenario)
  high: number   // optimistic (p75 scenario)
}

function estimateImpact(
  term: ScoredTerm,
  currentTier: TierDistribution,
  targetTier: TierDistribution
): ImpactRange {
  // Monthly impressions from current data
  const monthlyImpressions = term.impressions * (30 / 30) // already 30-day window

  // CVR improvement range
  const cvrDeltaLow = (targetTier.p25Cvr - currentTier.p50Cvr) // conservative
  const cvrDeltaMid = (targetTier.p50Cvr - currentTier.p50Cvr) // expected
  const cvrDeltaHigh = (targetTier.p75Cvr - currentTier.p50Cvr) // optimistic

  // Average order value (use tier median)
  const avgAov = targetTier.p50Aov || 85 // $85 default for Allied Brass

  return {
    low: Math.max(0, monthlyImpressions * cvrDeltaLow * avgAov),
    mid: Math.max(0, monthlyImpressions * cvrDeltaMid * avgAov),
    high: Math.max(0, monthlyImpressions * cvrDeltaHigh * avgAov),
  }
}
```

### Persisting Scores to query_value_scores
```typescript
import { createServiceClient } from '@/lib/supabase/server'

async function persistScores(scores: TermScore[]): Promise<void> {
  const supabase = createServiceClient()

  // Batch in chunks of 500
  for (let i = 0; i < scores.length; i += 500) {
    const chunk = scores.slice(i, i + 500)
    await supabase.from('query_value_scores').upsert(
      chunk.map(s => ({
        search_term: s.searchTerm,
        custom_label_0: s.customLabel0,
        score_version: 'v2',
        expected_clicks: s.expectedClicks,
        expected_cvr: s.expectedCvr,
        expected_conversion_value: s.expectedConversionValue,
        expected_profit_proxy: s.expectedProfitProxy,
        uncertainty: s.uncertainty,
        impact_score: s.impactScore,
        model_inputs: s.modelInputs,
        // Phase 32 extension columns:
        tier_fit_scores: s.tierFitScores,  // { high: z, medium: z, low: z }
        recommended_tier: s.recommendedTier,
        net_monthly_impact: s.netMonthlyImpact,
        scored_at: new Date().toISOString(),
      })),
      { onConflict: 'search_term,custom_label_0' }
    )
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded ROAS thresholds (3.6/3.1/2.6) | Distribution-based dynamic boundaries | Phase 33 (this phase) | Thresholds adapt to actual data; no manual tuning |
| Standard z-scores (mean/stddev) | Robust z-scores (median/MAD) | v1.3c research decision | Handles right-skewed ROAS correctly |
| Point estimate dollar impact | Range estimates with confidence coloring | v1.3c research decision | Builds trust by communicating uncertainty |
| Single-level scoring | Hierarchical fallback (per-group -> global -> defaults) | v1.3c research decision | Handles sparse data gracefully |

**Deprecated/outdated:**
- Hardcoded `BASELINE_TARGET_ROAS` in `control-center.ts` lines 3-7: replaced by dynamic distributions
- Hardcoded thresholds in `estimateTierFromMetrics()` at `query-intelligence.ts` line 138: replaced by distribution-based scoring
- `scoreNeedsDecisionTerm()` confidence formula (`clicks/50`): replaced by four-factor model

## Existing Data Sources & Infrastructure

### Tables Already Provisioned (confirmed in production)

| Table | Status | Phase 33 Usage |
|-------|--------|----------------|
| `query_value_scores` | Exists, empty, extended in migration 037 | Write: tier_fit_scores, recommended_tier, net_monthly_impact, scored_at |
| `routing_recommendations` | Exists, empty (migration 033b) | NOT written by Phase 33 (scoring only, no action). Phase 34 writes here. |
| `funnel_snapshots_daily` | Backfilled (~4,093 rows), scheduler active (Phase 32) | Read: trend comparison for boundary changes |
| `term_intent_state` | Exists, has NLP classifications | Read: intent_class for NLP alignment factor in confidence |

### Existing Functions to Consume (DO NOT MODIFY)

| Function | Location | Returns |
|----------|----------|---------|
| `getLabelTierPerformance()` | `service.ts` | 177 rows: per-group-per-tier aggregates (impressions, clicks, cost_micros, conversions, conversions_value, roas) |
| `getExistingFunnelTerms()` | `service.ts` | Per-term metrics with tier assignments |
| `decomposeSearchTerm()` | `query-intelligence.ts` | NLP features (product_object, modifiers, branded, competitor) |

### UI Components Available (installed)

| Component | Source | Phase 33 Usage |
|-----------|--------|----------------|
| Card, CardContent, CardHeader, CardTitle | shadcn/ui | Group overview cards, scorecard layout |
| Badge | shadcn/ui | Confidence badges (High/Medium/Low) |
| Collapsible | shadcn/ui (installed) | Expandable scoring factors |
| Tooltip | shadcn/ui (installed) | Hover explanations for statistics |
| Table | shadcn/ui | Term list tables at Levels 2-3 |
| Progress | shadcn/ui | Visual bars for metric percentile positions |
| Tabs | shadcn/ui | Group/tier navigation |
| BarChart, ScatterChart | recharts 3.7 | Distribution visualizations |
| ResponsiveContainer | recharts 3.7 | Chart wrapper |

## Discretion Recommendations

### Distribution Visualization (Claude's Discretion)
**Recommendation: Horizontal stacked bar with percentile markers**

Instead of box plots (stat-heavy) or stat cards (too abstract), use horizontal stacked bars that show the ROAS distribution in three color zones (LOW/MEDIUM/HIGH tier ranges). Overlay percentile markers (p25/p50/p75) as labeled tick marks. On hover/click, expand to show actual term dots positioned along the bar. This starts accessible ("green zone means high performers") and becomes granular on demand ("15 of your 42 terms are in the blue zone").

**Why:** Box plots require statistical literacy. Stat cards don't show shape. Stacked bars are universally understood (progress bars) and the color zones directly communicate "where should this term be?" The click-to-expand pattern matches the drill-down hierarchy.

### Guided Drill-Down Pattern (Claude's Discretion)
**Recommendation: Inline callouts at each level**

At each drill-down level, display a callout bar above the main content: "Towel Bars has the most misplaced terms (7) -- expanding would give you the most bang for your buck" or "HIGH tier has 3 terms that may belong in MEDIUM -- look at terms with ROAS below 2.8x." This guides without being prescriptive. The callout uses data from the scoring engine (sort groups by attention-needed metric, highlight the most impactful finding per level).

**Why:** Sidebar guidance feels disconnected from the data. A hybrid approach adds cognitive load (two things to track). Inline callouts are contextual and scannable -- they appear exactly where the user is looking.

### Sparse Tier Visual Treatment (Claude's Discretion)
**Recommendation: Semi-transparent overlay with "Limited data" label, scoring threshold at 5 terms**

Show sparse tiers (1-4 terms with non-zero metrics) with reduced opacity (50%) and a "Limited data" label. Still show the data that exists but make it visually clear the statistics are unreliable. The fallback indicator (see TIER-04) appears inline: "Scored using category-wide averages (only 3 Towel Bar terms in HIGH tier)."

For new terms with zero metrics: show with "Needs more data" badge and no score. Do NOT score them with low confidence -- absence of data is not low confidence, it's no confidence.

### Recalculation Frequency (Claude's Discretion)
**Recommendation: On-demand with smart caching, display boundary change log**

Distributions recompute when the scoring API is called and the distribution cache is stale (>10 minutes). This is effectively on-demand since operators visit the page a few times per day. No scheduled background job needed for Phase 33 (Phase 34+ may add scheduled scoring).

For boundary changes: show a simple "Before -> After" diff table when boundaries change. "ROAS boundary for Towel Bars HIGH tier: 3.2x -> 3.4x (data shifted up 6%)." Keep a log of the last 5 boundary computations in component state for the current session. Persistent boundary history is Phase 34+ scope.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | vitest ^3.2.4 |
| Config file | `dashboard/vitest.config.ts` |
| Quick run command | `cd dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts` |
| Full suite command | `cd dashboard && npx vitest run` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TIER-01 | computeTierDistributions returns p25/p50/p75 per tier per group | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "distributions"` | Wave 0 |
| TIER-02 | Boundaries auto-adjust from MEDIUM percentiles; shift is capped | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "boundaries"` | Wave 0 |
| TIER-03 | scoreTerm uses robust z-scores (median/MAD), not mean/stddev | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "robust z-score"` | Wave 0 |
| TIER-04 | Hierarchical fallback: per-group -> global -> defaults when sparse | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "fallback"` | Wave 0 |
| TIER-05 | Returns "insufficient_data" degraded state when tier has <5 terms | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "insufficient"` | Wave 0 |
| TIER-06 | Confidence score combines 4 factors into 0-1 value with level | unit | `npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts -t "confidence"` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd dashboard && npx vitest run src/lib/optimization/__tests__/tier-scoring.test.ts`
- **Per wave merge:** `cd dashboard && npx vitest run && npm run build`
- **Phase gate:** Full suite green + build passes before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `dashboard/src/lib/optimization/__tests__/tier-scoring.test.ts` -- covers TIER-01 through TIER-06
- [ ] Test fixtures: sample `LabelTierPerformance[]` data with sparse, normal, and outlier-heavy distributions
- [ ] `simple-statistics` package install: `cd dashboard && npm install simple-statistics`

## Open Questions

1. **query_value_scores upsert conflict key**
   - What we know: Migration 033b creates the table with index on `(search_term, custom_label_0, created_at DESC)` but no UNIQUE constraint on `(search_term, custom_label_0)`.
   - What's unclear: Supabase upsert with `onConflict: 'search_term,custom_label_0'` requires a unique index/constraint.
   - Recommendation: Add a unique index `CREATE UNIQUE INDEX IF NOT EXISTS idx_query_value_scores_term_label ON query_value_scores (search_term, custom_label_0)` in a new migration before Phase 33 implementation begins. Alternatively, use delete+insert pattern.

2. **Daily ROAS data for consistency factor (TIER-06)**
   - What we know: `getExistingFunnelTerms()` returns aggregate metrics over the date window, not per-day breakdown. `funnel_snapshots_daily` has daily data but at the tier-group level, not per-term.
   - What's unclear: Where to get per-term daily ROAS for coefficient of variation calculation.
   - Recommendation: Use `funnel_snapshots_daily` for tier-level consistency (if ROAS in the tier varies wildly day-to-day, all terms in that tier get lower consistency). For per-term consistency, use the aggregate CV of the term's metrics across the date window dimensions available (clicks, conversions, cost variance). If only aggregate is available, weight the consistency factor toward tier-level consistency.

3. **Navigation placement for new page**
   - What we know: Sidebar has 15 navigation items. "Shopping Funnel" exists at `/shopping-funnel`.
   - What's unclear: Should Tier Scoring be a sub-page of Shopping Funnel or a standalone sidebar entry?
   - Recommendation: Add as standalone sidebar entry "Tier Intelligence" at `/tier-scoring` between "Shopping Funnel" and "Optimization Control". This phase is the beginning of a multi-phase intelligence system that grows beyond the funnel.

## Sources

### Primary (HIGH confidence)
- Source code audit: `dashboard/src/lib/optimization/query-intelligence.ts` -- hardcoded thresholds at lines 116-145
- Source code audit: `dashboard/src/lib/optimization/control-center.ts` -- BASELINE_TARGET_ROAS at lines 3-7
- Source code audit: `dashboard/src/lib/shopping-funnel/types.ts` -- LabelTierPerformance, ExistingFunnelTerm interfaces
- Source code audit: `dashboard/src/lib/intent/tier-movement.ts` -- execution pipeline architecture
- Source code audit: `dashboard/src/lib/shopping-funnel/service.ts` -- data acquisition pipeline, cache behavior
- Migration SQL: `supabase/migrations/037_extend_scoring_and_experiment_columns.sql` -- query_value_scores extensions
- Migration SQL: `supabase/migrations/033b_DEFERRED_optimization_control_plane.sql` -- routing_recommendations schema
- v1.3c research: `.planning/research/ARCHITECTURE.md`, `FEATURES.md`, `PITFALLS.md`, `STACK.md`, `SUMMARY.md`

### Secondary (MEDIUM confidence)
- simple-statistics API docs (function coverage confirmed in STACK.md research)
- Recharts ScatterChart/BarChart APIs (usage confirmed in existing codebase components)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- simple-statistics selected and verified in prior milestone research; recharts already installed and in use
- Architecture: HIGH -- computation module + API route pattern already established in codebase (query-intelligence.ts, control-center.ts); data sources verified and populated
- Pitfalls: HIGH -- derived from actual code inspection (hardcoded values, schema gaps, ROAS distribution characteristics)

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable domain, no fast-moving dependencies)
