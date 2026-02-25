# Technology Stack — v1.3c Actionable Shopping Intelligence

**Project:** Allied FeedOps v1.3c
**Researched:** 2026-02-25
**Milestone:** v1.3c (Actionable Shopping Intelligence)
**Confidence:** HIGH (all recommendations verified via official docs/GitHub)

> **Scope note:** This document covers only NET NEW tooling needed for v1.3c.
> Existing stack (Next.js 16, Python/FastAPI, Supabase Postgres 15, Cloud Run, Recharts 3.7,
> @tremor/react 3.18, google-ads-api 23.0, Vercel Crons, Cloud Scheduler, pg_cron)
> is already installed and validated through v1.3b. Do not re-install or alter those packages.

---

## Guiding Principle

v1.3c adds ONE new npm package (`simple-statistics`). Everything else uses existing infrastructure: Recharts for visualization, PostgreSQL for heavy statistical computation, Vercel Crons for scheduling, and Supabase tables for caching computed distributions.

---

## Recommended Stack Additions

### 1. Statistical Computation: `simple-statistics` (NEW)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| simple-statistics | ^7.8.8 | Percentiles, z-scores, chi-squared, t-tests, Bayesian classification, IQR, linear regression | Zero dependencies, ~30KB bundle, TypeScript types included (index.d.ts), functional API enables tree-shaking. Covers ALL v1.3c statistical needs in one package. |

**Confidence: HIGH** — verified via [official docs](https://simple-statistics.github.io/docs/) and [GitHub](https://github.com/simple-statistics/simple-statistics).

**Functions mapped to v1.3c features:**

| v1.3c Feature | simple-statistics Function | Usage |
|----------------|---------------------------|-------|
| Adaptive tier scoring | `quantile()`, `quantileSorted()` | Compute dynamic percentile boundaries from actual ROAS/CVR distributions |
| Outlier detection | `zScore()`, `standardDeviation()`, `mean()` | Flag SKUs performing >2 SD above/below tier mean |
| Box plot rendering | `interquartileRange()`, `quantile([0.25, 0.5, 0.75])` | Compute Q1/median/Q3/whiskers for tier distribution charts |
| A/B test significance | `chiSquaredGoodnessOfFit()` | Test conversion rate differences between experiment cohorts |
| ROAS comparison | `tTestTwoSample()` | Compare mean ROAS between control/treatment tier assignments |
| Revenue trend analysis | `linearRegression()`, `linearRegressionLine()` | Compute trend slopes for time-series revenue/CTR data |
| Low-data smoothing | `bayesian()` / manual Bayesian avg | Smooth noisy metrics for SKUs with <30 clicks |
| Permutation testing | `permutationTest()` | Non-parametric significance testing when distributions are non-normal |

**Why NOT alternatives:**

| Criterion | simple-statistics | jStat | mathjs |
|-----------|-------------------|-------|--------|
| Bundle size | ~30KB (zero deps) | ~200KB | ~700KB |
| TypeScript types | Included (index.d.ts) | @types/jstat (community) | Included |
| All needed functions | Yes (see table above) | Yes | Missing chi-squared, t-test, z-score |
| API style | Functional (tree-shakeable) | Object-oriented (all-or-nothing) | Object-oriented |
| Maintenance | Active (7.8.8, updated 2025) | Stale (last major update 2020) | Active but 23x larger |
| Decision | **USE THIS** | Too heavy, stale | Overkill — general math lib |

---

### 2. Visualization: Recharts (EXISTING — no additions)

| Technology | Version | Status | Why No New Library |
|------------|---------|--------|-----|
| recharts | ^3.7.0 (installed) | 3 components already using it | Handles all v1.3c chart types natively or with minimal custom components |
| @tremor/react | ^3.18.7 (installed) | Used for metric cards | Keep for KPI scorecards and executive summary cards |

**Confidence: HIGH** — verified via [Recharts ScatterChart API](https://recharts.github.io/en-US/api/ScatterChart/) and [Bubble Chart Example](https://recharts.github.io/en-US/examples/BubbleChart/).

**v1.3c chart requirements mapped to Recharts:**

| Chart Type | v1.3c Usage | Recharts Implementation | Complexity |
|------------|-------------|------------------------|------------|
| **Bubble chart** | BCG matrix (market share vs growth vs revenue) | `<ScatterChart>` + `<Scatter>` + `<ZAxis range={[50,400]}>` for bubble sizing. Official example exists. | Low — native support |
| **Scatter plot** | ROAS vs CVR by tier, revenue leakage scatter | `<ScatterChart>` + `<Scatter>` with color-coded data series per tier | Low — native support |
| **Distribution histogram** | Tier ROAS/CVR distributions | `<BarChart>` with computed bin data via `width_bucket()` SQL. Already using this pattern in `QualityDistribution.tsx`. | Low — existing pattern |
| **Box plot** | Tier performance distributions (Q1/median/Q3/whiskers) | `<BarChart>` with `shape` prop on `<Bar>` rendering custom SVG. ~50 lines of custom component. | Medium — custom shape |
| **Line chart with bands** | Time-series trends with confidence intervals | `<ComposedChart>` + `<Area>` (band) + `<Line>` (mean). Native Recharts composition. | Low — native support |
| **Stacked bar** | Revenue breakdown by tier/product group | `<BarChart>` + multiple `<Bar stackId="a">`. Native support. | Low — native support |

**What NOT to add and why:**

| Library | Why NOT |
|---------|---------|
| @nivo/boxplot | Adds ~200KB for one chart type. Different theming system than Recharts. Inconsistent UX. |
| ApexCharts / react-apexcharts | Duplicate of Recharts functionality. React wrapper less maintained. Would create two chart rendering paradigms. |
| AG Charts | Commercial license required for advanced features. Enterprise-oriented. Overkill. |
| D3.js directly | Recharts already wraps D3 internally. Adding raw D3 doubles the rendering paradigm. Custom SVG shapes within Recharts achieve the same result. |
| Chart.js / react-chartjs-2 | Canvas-based (not SVG). Harder to customize, no React composition model. Bundle overlap with Recharts. |

---

### 3. Heavy Distribution Computation: PostgreSQL (EXISTING — no additions)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 15+ (Supabase) | Percentile boundaries, z-scores, distribution bins across all 2,784 SKUs | `percentile_cont()`, `stddev()`, `width_bucket()`, window functions are standard SQL. No extensions needed. |

**Confidence: HIGH** — PostgreSQL ordered-set aggregate functions have been stable since v9.4. [Source: PostgreSQL docs](https://www.postgresql.org/docs/current/functions-aggregate.html).

**Computation split — PostgreSQL vs TypeScript:**

| Computation | Where | Why |
|-------------|-------|-----|
| Tier percentile boundaries (p10/p25/p50/p75/p90) | **PostgreSQL** | `percentile_cont(ARRAY[0.1,0.25,0.5,0.75,0.9]) WITHIN GROUP (ORDER BY roas)` — single query across all 2,784 SKUs. No data transfer overhead. |
| Z-scores for outlier flagging | **PostgreSQL** | `(value - AVG(value) OVER(PARTITION BY tier)) / NULLIF(STDDEV(value) OVER(PARTITION BY tier), 0)` — computed as window function inline. |
| Distribution histogram bins | **PostgreSQL** | `width_bucket(roas, min_roas, max_roas, 20)` + `COUNT(*) GROUP BY` — server computes bins, client renders. |
| Revenue leakage estimates | **PostgreSQL** | Dollar-value computations join `performance_snapshots`, `search_queries`, and tier data. Aggregate server-side, return summaries. |
| Chi-squared A/B test | **TypeScript** | `chiSquaredGoodnessOfFit()` on small cohorts (~100-500 SKUs per experiment). Fast in browser, no round-trip needed. |
| T-test for ROAS comparison | **TypeScript** | `tTestTwoSample()` on pre-aggregated metrics. Small datasets, instant computation. |
| Box plot quartiles for rendering | **TypeScript** | Data already fetched for chart. `quantile()` on in-memory array is instant. Avoids extra DB call. |
| Time-series trend slopes | **TypeScript** | `linearRegression()` on 30-90 data points from `funnel_snapshots_daily`. Trivial in-browser. |
| Bayesian smoothing for low-data SKUs | **TypeScript** | Iterative computation on individual SKU metrics. Needs programmatic control flow. |

**Rule of thumb:** Aggregate across ALL SKUs/tiers in PostgreSQL. Compute on subsets already fetched for rendering in TypeScript.

---

### 4. Scheduling: Vercel Crons + Cloud Scheduler (EXISTING — no additions)

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Vercel Crons | N/A (vercel.json config) | Dashboard API route scheduling | Already configured (1 job: GA4 snapshots) |
| GCP Cloud Scheduler | N/A (existing) | Python pipeline scheduling (funnel snapshots) | Script ready, needs activation |
| pg_cron | Supabase built-in | DB-internal scheduled computation | Available, used for feedback computation |

**Confidence: HIGH** — Vercel Crons verified in existing `vercel.json`. Cloud Scheduler scripted. pg_cron documented from v1.3b research.

**v1.3c scheduling plan:**

| Task | Scheduler | Schedule | Why This Scheduler |
|------|-----------|----------|-------------------|
| Distribution recomputation | pg_cron | Daily 5:30am UTC | Pure SQL computation on existing tables. No API calls needed. |
| Automated rule evaluation | Vercel Cron | Daily 6:00am UTC | Needs TypeScript logic (rule engine), writes recommendations to Supabase. |
| A/B experiment measurement | Vercel Cron | Weekly Sunday 9:00am UTC | Needs TypeScript (simple-statistics significance testing), updates experiment_outcomes. |
| GA4 snapshot capture | Vercel Cron | Daily 8:15am UTC | Already configured. Keep as-is. |
| Funnel snapshot capture | Cloud Scheduler | Daily 8:00am UTC | Already scripted. Needs activation (CRON_SECRET + setup-funnel-scheduler.sh). |

**Vercel Cron configuration** (updated `vercel.json`):
```json
{
  "crons": [
    { "path": "/api/ga4/snapshot-capture", "schedule": "15 8 * * *" },
    { "path": "/api/scoring/recompute-distributions", "schedule": "0 6 * * *" },
    { "path": "/api/rules/evaluate", "schedule": "30 6 * * *" },
    { "path": "/api/experiments/measure", "schedule": "0 9 * * 0" }
  ]
}
```

**Important consideration:** Vercel Hobby plan supports 2 cron jobs; Pro plan supports 40. The project deploys to Vercel (auto-deploy on push). Verify the plan supports 4+ cron entries. If on Hobby, consolidate into a single `/api/daily-jobs` endpoint that runs distribution recomputation + rule evaluation sequentially.

**pg_cron for distribution computation:**
```sql
-- Recompute tier scoring distributions daily at 5:30 AM UTC
SELECT cron.schedule(
  'recompute-tier-distributions',
  '30 5 * * *',
  $$SELECT recompute_tier_scoring_distributions()$$
);
```

---

## What NOT to Add

| Temptation | Why Avoid | What to Do Instead |
|------------|-----------|-------------------|
| **D3.js** | Recharts wraps D3 internally. Adding raw D3 = two rendering paradigms, double bundle. | Custom SVG shapes within Recharts `<Bar shape={...}>` for box plots. |
| **Nivo / Victory / ApexCharts** | Second charting library = inconsistent styling, doubled bundle, maintenance burden. | Recharts covers all chart types needed. |
| **mathjs** | 700KB general math library. 23x heavier than simple-statistics. Missing key statistical tests. | simple-statistics at 30KB covers all needs. |
| **jStat** | Last significant update 2020. Community-maintained TypeScript types. | simple-statistics is actively maintained with included types. |
| **node-cron** | Server-side scheduler for always-on processes. Vercel is serverless. | Vercel Crons for API routes, pg_cron for DB-internal jobs. |
| **Bull / BullMQ** | Job queue requiring Redis. Massive infrastructure addition for simple scheduled tasks. | Vercel Crons + pg_cron handle all scheduling. |
| **Redis / Upstash** | Adding a cache layer when Supabase tables serve as persistent cache. Over-engineering. | Write computed distributions to `tier_scoring_cache` table. Read with freshness check. |
| **scipy (Python side)** | All consumers are TypeScript dashboard components. Cross-language boundary adds latency and complexity. | simple-statistics in TypeScript, PostgreSQL for heavy aggregation. |
| **Cube.js / Metabase** | Embedded analytics platforms. Adds another service to deploy/maintain. Dashboard already has custom charts. | Custom Recharts components with Supabase data. |
| **TensorFlow.js** | Machine learning is not needed for v1.3c. Statistical methods (percentiles, z-scores, regression) are sufficient. | simple-statistics covers all analysis needs. |

---

## Integration Patterns

### simple-statistics: Adaptive Tier Scoring

```typescript
// dashboard/src/lib/scoring/adaptive-scorer.ts
import {
  quantile, zScore, standardDeviation, mean,
  interquartileRange, linearRegression, linearRegressionLine
} from 'simple-statistics';

// Compute dynamic tier boundaries from actual data
function computeTierBoundaries(roasValues: number[]) {
  const sorted = roasValues.slice().sort((a, b) => a - b);
  return {
    low_ceiling: quantile(sorted, 0.33),
    medium_ceiling: quantile(sorted, 0.67),
    p10: quantile(sorted, 0.10),
    p25: quantile(sorted, 0.25),
    median: quantile(sorted, 0.50),
    p75: quantile(sorted, 0.75),
    p90: quantile(sorted, 0.90),
    iqr: interquartileRange(sorted),
    mean: mean(sorted),
    sd: standardDeviation(sorted),
  };
}

// Flag outlier SKUs for review
function flagOutliers(values: number[], threshold = 2.0) {
  const m = mean(values);
  const sd = standardDeviation(values);
  return values
    .map((v, i) => ({ index: i, value: v, z: zScore(v, m, sd) }))
    .filter(item => Math.abs(item.z) > threshold);
}

// Time-series trend for executive reporting
function computeTrend(dataPoints: [number, number][]) {
  const regression = linearRegression(dataPoints);
  return {
    slope: regression.m,
    intercept: regression.b,
    trendLine: linearRegressionLine(regression),
    direction: regression.m > 0 ? 'improving' : 'declining',
  };
}
```

### simple-statistics: A/B Testing Significance

```typescript
// dashboard/src/lib/experiments/significance.ts
import {
  chiSquaredGoodnessOfFit,
  tTestTwoSample,
  permutationTest
} from 'simple-statistics';

interface ExperimentResult {
  significant: boolean;
  pValue: number;
  method: string;
  recommendation: 'adopt' | 'reject' | 'continue';
}

// Chi-squared test for conversion rate differences
function testConversionSignificance(
  controlConversions: number,
  controlTotal: number,
  treatmentConversions: number,
  treatmentTotal: number,
  alpha = 0.05
): ExperimentResult {
  const totalConversions = controlConversions + treatmentConversions;
  const totalSamples = controlTotal + treatmentTotal;
  const expectedRate = totalConversions / totalSamples;

  const observed = [controlConversions, controlTotal - controlConversions];
  const expectedFn = (i: number) =>
    i === 0 ? expectedRate * controlTotal : (1 - expectedRate) * controlTotal;

  const pValue = chiSquaredGoodnessOfFit(observed, expectedFn, 1);
  return {
    significant: pValue < alpha,
    pValue,
    method: 'chi-squared',
    recommendation: pValue < alpha
      ? (treatmentConversions / treatmentTotal > controlConversions / controlTotal ? 'adopt' : 'reject')
      : 'continue',
  };
}

// T-test for ROAS comparison between experiment arms
function testRoasSignificance(
  controlRoas: number[],
  treatmentRoas: number[],
  alpha = 0.05
): ExperimentResult {
  const pValue = tTestTwoSample(controlRoas, treatmentRoas);
  return {
    significant: pValue !== null && pValue < alpha,
    pValue: pValue ?? 1,
    method: 't-test',
    recommendation: pValue !== null && pValue < alpha ? 'adopt' : 'continue',
  };
}
```

### PostgreSQL: Distribution Computation (daily pg_cron)

```sql
-- Function: Recompute tier scoring distributions
-- Called by pg_cron daily. Results cached in tier_scoring_distributions table.
CREATE OR REPLACE FUNCTION recompute_tier_scoring_distributions()
RETURNS void AS $$
BEGIN
  -- Clear and recompute (atomic within transaction)
  TRUNCATE tier_scoring_distributions;

  INSERT INTO tier_scoring_distributions (
    custom_label_0, tier, term_count,
    roas_mean, roas_stddev, roas_p10, roas_p25, roas_p50, roas_p75, roas_p90,
    cvr_mean, cvr_stddev, cvr_p10, cvr_p25, cvr_p50, cvr_p75, cvr_p90,
    computed_at
  )
  SELECT
    custom_label_0,
    tier,
    COUNT(*) as term_count,
    AVG(roas) as roas_mean,
    STDDEV(roas) as roas_stddev,
    (percentile_cont(0.10) WITHIN GROUP (ORDER BY roas)),
    (percentile_cont(0.25) WITHIN GROUP (ORDER BY roas)),
    (percentile_cont(0.50) WITHIN GROUP (ORDER BY roas)),
    (percentile_cont(0.75) WITHIN GROUP (ORDER BY roas)),
    (percentile_cont(0.90) WITHIN GROUP (ORDER BY roas)),
    AVG(cvr) as cvr_mean,
    STDDEV(cvr) as cvr_stddev,
    (percentile_cont(0.10) WITHIN GROUP (ORDER BY cvr)),
    (percentile_cont(0.25) WITHIN GROUP (ORDER BY cvr)),
    (percentile_cont(0.50) WITHIN GROUP (ORDER BY cvr)),
    (percentile_cont(0.75) WITHIN GROUP (ORDER BY cvr)),
    (percentile_cont(0.90) WITHIN GROUP (ORDER BY cvr)),
    NOW()
  FROM tier_performance_materialized  -- or a view joining relevant tables
  GROUP BY custom_label_0, tier;
END;
$$ LANGUAGE plpgsql;
```

### Recharts: Bubble Chart (BCG Matrix)

```typescript
// Product group BCG matrix
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis,
  Tooltip, CartesianGrid, ResponsiveContainer, Cell
} from 'recharts';

const QUADRANT_COLORS = {
  star: '#22c55e',      // high growth, high share
  question: '#f59e0b',  // high growth, low share
  cashCow: '#3b82f6',   // low growth, high share
  dog: '#ef4444',        // low growth, low share
};

<ResponsiveContainer width="100%" height={400}>
  <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="marketShare" name="Relative Market Share" unit="%" />
    <YAxis dataKey="growthRate" name="Revenue Growth" unit="%" />
    <ZAxis dataKey="revenue" range={[50, 400]} name="Revenue" unit="$" />
    <Tooltip cursor={{ strokeDasharray: '3 3' }} />
    <Scatter name="Product Groups" data={productGroups}>
      {productGroups.map((entry, index) => (
        <Cell key={index} fill={QUADRANT_COLORS[entry.quadrant]} />
      ))}
    </Scatter>
  </ScatterChart>
</ResponsiveContainer>
```

### Recharts: Custom Box Plot Component

```typescript
// dashboard/src/components/charts/BoxPlot.tsx
// ~50 lines of custom SVG shape for use with Recharts BarChart

interface BoxPlotData {
  name: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
}

const BoxPlotShape = (props: any) => {
  const { x, y, width, payload, yAxisScale } = props;
  const { min, q1, median, q3, max } = payload;

  const yMin = yAxisScale(min);
  const yQ1 = yAxisScale(q1);
  const yMedian = yAxisScale(median);
  const yQ3 = yAxisScale(q3);
  const yMax = yAxisScale(max);
  const cx = x + width / 2;

  return (
    <g>
      {/* Box (Q1 to Q3) */}
      <rect x={x} y={yQ3} width={width} height={yQ1 - yQ3}
            fill="#8884d8" fillOpacity={0.6} stroke="#8884d8" />
      {/* Median line */}
      <line x1={x} x2={x + width} y1={yMedian} y2={yMedian}
            stroke="#333" strokeWidth={2} />
      {/* Upper whisker */}
      <line x1={cx} x2={cx} y1={yMax} y2={yQ3} stroke="#333" />
      <line x1={x + 4} x2={x + width - 4} y1={yMax} y2={yMax} stroke="#333" />
      {/* Lower whisker */}
      <line x1={cx} x2={cx} y1={yQ1} y2={yMin} stroke="#333" />
      <line x1={x + 4} x2={x + width - 4} y1={yMin} y2={yMin} stroke="#333" />
    </g>
  );
};
```

---

## Installation

```bash
# From dashboard directory — single new dependency
cd dashboard && npm install simple-statistics

# That's it. No other packages needed.
# recharts 3.7.0 — already installed
# @tremor/react 3.18.7 — already installed
# Supabase (PostgreSQL) — already available
# Vercel Crons — config-only (vercel.json)
# pg_cron — already available on Supabase
```

---

## Confidence Assessment

| Component | Confidence | Rationale |
|-----------|------------|-----------|
| simple-statistics for all stats | HIGH | Official docs confirm quantile, zScore, chiSquaredGoodnessOfFit, tTestTwoSample, permutationTest, linearRegression. TypeScript types included. Zero deps. |
| Recharts for all visualization | HIGH | ScatterChart + ZAxis = bubble charts (official example). Custom Bar shape = box plots (documented pattern). Already 3 components using Recharts in codebase. |
| PostgreSQL for heavy computation | HIGH | percentile_cont, stddev, width_bucket are standard SQL since PG 9.4. Supabase runs PG 15. |
| Vercel Crons for scheduling | HIGH | Already configured in vercel.json (1 existing job). Pattern established. |
| No second charting library needed | HIGH | Mapped all 6 chart types to Recharts. Only box plot needs custom shape (~50 LOC). |
| No Redis/Bull/separate analytics DB | HIGH | 2,784 SKUs, ~1M rows/year. Supabase tables as computed cache is sufficient. |

---

## Sources

- [simple-statistics GitHub](https://github.com/simple-statistics/simple-statistics) — v7.8.8, ISC license, TypeScript types included — HIGH confidence
- [simple-statistics API docs](https://simple-statistics.github.io/docs/) — Full function reference confirming all needed methods — HIGH confidence
- [Recharts ScatterChart API](https://recharts.github.io/en-US/api/ScatterChart/) — ZAxis support for bubble charts — HIGH confidence
- [Recharts Bubble Chart Example](https://recharts.github.io/en-US/examples/BubbleChart/) — Official bubble chart pattern — HIGH confidence
- [PostgreSQL Aggregate Functions](https://www.postgresql.org/docs/current/functions-aggregate.html) — percentile_cont, stddev — HIGH confidence
- [PostgreSQL percentile_cont tutorial](https://www.tigerdata.com/learn/understanding-percentile_cont-and-percentile_disc) — Usage patterns — MEDIUM confidence
- [Vercel Cron Jobs docs](https://vercel.com/docs/cron-jobs/manage-cron-jobs) — Configuration and plan limits — HIGH confidence
- [jStat docs](https://jstat.github.io/all.html) — Alternative considered (too heavy, stale) — HIGH confidence
- Existing project: `dashboard/package.json` — current dependency inventory
- Existing project: `dashboard/vercel.json` — current cron configuration
- Existing project: `dashboard/src/components/dashboard/QualityDistribution.tsx` — existing Recharts histogram pattern
