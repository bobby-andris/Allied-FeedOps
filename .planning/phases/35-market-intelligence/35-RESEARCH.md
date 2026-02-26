# Phase 35: Market Intelligence - Research

**Researched:** 2026-02-25
**Domain:** Dashboard visualization, demand analytics, competitive intelligence, BCG matrix
**Confidence:** HIGH

## Summary

Phase 35 adds a new top-level "Market Intelligence" page with three tabs (Demand, Competitive, Products) to the existing Next.js dashboard. All required data already exists in Supabase tables (`search_queries`, `keyword_metrics`, `query_value_scores`, `funnel_snapshots_daily`). No new database tables or migrations are needed -- this is a pure frontend + API route phase.

The implementation follows established patterns from the Tier Intelligence and Shopping Funnel pages: server-side API routes query Supabase, client-side React components render with Recharts and shadcn/ui. The BCG bubble chart is the only novel visualization, requiring Recharts `ScatterChart` with custom bubble rendering.

**Primary recommendation:** Build in 3 waves -- API layer (data aggregation queries), Demand + Competitive tabs, Products tab (BCG chart + drill-down). All data queries join `search_queries` with `keyword_metrics` and `query_value_scores`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- New top-level page "Market Intelligence" in sidebar nav, separate from Waterfall/Search Insights
- 3 sub-tabs: **Demand** | **Competitive** | **Products**
- Demand tab: impression share gaps, CPC opportunity, seasonal trends, new term discovery, long-tail analysis
- Competitive tab: brand vs non-brand revenue split, competitor mention tracking
- Products tab: BCG bubble chart + table view
- Per-tab KPI summary cards at top (3-4 cards per tab, contextual to that tab's data)
- Default shows all data (all 59 product groups), user filters down by product group, tier, or custom_label_0
- BCG: Bubble chart is the primary/default view, with toggle to switch to sortable table
- BCG axes: X-axis: ROAS, Y-axis: Revenue, Bubble size: Total spend, Color: Trend direction
- BCG quadrant boundaries: Median ROAS and median Revenue across all 59 product groups (dynamic)
- Click bubble -> right-side slide-out panel with product group detail (chart dims behind it)
- Slide-out shows: quadrant label, ROAS, Revenue, Spend, Trend %, and top terms with their tiers

### Claude's Discretion
- Demand metrics visualization: Chart types for impression share gaps, CPC opportunity, seasonal patterns, new term discovery, and long-tail analysis
- Competitive intel layout: How to present brand/non-brand split, competitor token tracking
- Color scheme and styling: Consistent with existing dashboard patterns (Tailwind, shadcn/ui)
- Mobile/responsive behavior: Adapt charts for smaller screens
- Loading states and error handling: Skeleton loaders, empty states per tab
- Seasonal pattern flagging: How to highlight terms spiking/declining >20%
- New term discovery presentation: Count + list format
- Long-tail grouping: Word count buckets and comparison chart design

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEMAND-01 | Impression share gaps per term (actual vs Keyword Planner market size) | `search_queries.impressions` vs `keyword_metrics.avg_monthly_searches` -- direct join on query_text/keyword |
| DEMAND-02 | CPC opportunity scores (headroom to market benchmark) | `search_queries.cost_micros / clicks` vs `keyword_metrics.high_cpc_micros` -- compute headroom percentage |
| DEMAND-03 | Seasonal demand patterns from monthly_search_volumes with >20% spike/decline flags | `keyword_metrics.monthly_searches` JSONB contains per-month breakdown; parse and compute MoM delta |
| DEMAND-04 | New term discovery rate (terms appearing first time in last 7 days) | `search_queries.fetched_at` or `synced_at` -- terms where earliest `period_start` is within 7 days |
| DEMAND-05 | Brand vs non-brand revenue split using NLP decomposition | Existing `QueryIntentFeatures.is_branded` in tier-scoring types; apply to revenue aggregation |
| DEMAND-06 | Competitor mention tracking per competitor token | Match `query_text` against known competitor tokens (moen, delta, kohler, etc.); aggregate metrics |
| DEMAND-07 | Long-tail vs head term analysis by word count with ROAS/CVR comparison | Split `query_text` by spaces, bucket by word count (1-2, 3-4, 5+), aggregate ROAS/CVR per bucket |
| PROD-01 | BCG quadrant classification for 59 product groups | Aggregate `query_value_scores` by `custom_label_0`; ROAS vs Revenue medians define quadrant boundaries |
| PROD-02 | Bubble chart visualization (X: ROAS, Y: Revenue, Size: Spend, Color: Trend) | Recharts `ScatterChart` with `ZAxis` for bubble size and custom shape renderer |
| PROD-03 | Click bubble to drill down to term-level breakdown | React state for selected group; slide-out panel with term-level data from `query_value_scores` |
| PROD-04 | Tabular alternative to bubble chart with sortable columns | Standard shadcn Table with column sorting; same data source as bubble chart |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15.x | Page routing, API routes | Already in project |
| React | 19.x | UI components | Already in project |
| Recharts | 3.7.0 | Charts (bar, scatter/bubble, line) | Already installed, used in DistributionChart, ApprovalChart, etc. |
| shadcn/ui | latest | Card, Tabs, Table, Badge, Select, Skeleton | Already used throughout dashboard |
| Tailwind CSS | 4.x | Styling | Already configured |
| @supabase/supabase-js | 2.x | Database queries | Already configured with server/client helpers |
| simple-statistics | 7.x | Median, percentile calculations | Already installed (Phase 33) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | Icons | Already in project for sidebar nav icons |
| date-fns | latest | Date formatting/manipulation | If not already installed, use native Date or Intl |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Recharts ScatterChart | D3.js directly | D3 gives more control but Recharts already in project; ScatterChart handles bubble charts well |
| Custom slide-out panel | Radix Dialog/Sheet | shadcn Sheet component exists and handles slide-out pattern |

**Installation:**
```bash
# No new installs needed -- all libraries already in project
```

## Architecture Patterns

### Recommended Project Structure
```
dashboard/src/
├── app/(dashboard)/
│   └── market-intelligence/
│       ├── page.tsx                    # Main page with 3 tabs
│       ├── components/
│       │   ├── DemandTab.tsx           # Demand tab content
│       │   ├── CompetitiveTab.tsx      # Competitive tab content
│       │   ├── ProductsTab.tsx         # Products tab (BCG chart + table)
│       │   ├── ImpressionShareChart.tsx # DEMAND-01 visualization
│       │   ├── CpcOpportunityChart.tsx  # DEMAND-02 visualization
│       │   ├── SeasonalTrendsChart.tsx  # DEMAND-03 visualization
│       │   ├── NewTermsCard.tsx         # DEMAND-04 card
│       │   ├── LongTailAnalysis.tsx     # DEMAND-07 visualization
│       │   ├── BrandSplitChart.tsx      # DEMAND-05 visualization
│       │   ├── CompetitorTracker.tsx    # DEMAND-06 table
│       │   ├── BcgBubbleChart.tsx       # PROD-01/02 bubble chart
│       │   ├── BcgTableView.tsx         # PROD-04 sortable table
│       │   └── ProductGroupSlideOut.tsx  # PROD-03 detail panel
│       └── hooks/
│           ├── useDemandData.ts         # Demand tab data fetching
│           ├── useCompetitiveData.ts    # Competitive tab data fetching
│           └── useProductGroups.ts      # Products tab data fetching
├── app/api/market-intelligence/
│   ├── demand/route.ts                 # DEMAND-01 through DEMAND-04, DEMAND-07
│   ├── competitive/route.ts            # DEMAND-05, DEMAND-06
│   └── products/route.ts              # PROD-01 through PROD-04
```

### Pattern 1: API Route Data Aggregation
**What:** Single API route per tab that aggregates all needed data from Supabase, returns structured JSON
**When to use:** Each tab fetches once on mount, no per-component fetching

```typescript
// Example: /api/market-intelligence/demand
export async function GET(request: NextRequest) {
  const supabase = await createClient()
  const { searchParams } = new URL(request.url)
  const customLabel0 = searchParams.get('customLabel0')

  // Parallel queries for all demand metrics
  const [impressionShare, cpcOpportunity, seasonal, newTerms, longTail] = await Promise.all([
    getImpressionShareGaps(supabase, customLabel0),
    getCpcOpportunity(supabase, customLabel0),
    getSeasonalPatterns(supabase, customLabel0),
    getNewTermDiscovery(supabase, customLabel0),
    getLongTailAnalysis(supabase, customLabel0),
  ])

  return NextResponse.json({ impressionShare, cpcOpportunity, seasonal, newTerms, longTail })
}
```

### Pattern 2: BCG Bubble Chart with Recharts ScatterChart
**What:** Use Recharts ScatterChart with ZAxis for bubble size and custom dot renderer for colors
**When to use:** PROD-02 bubble chart

```typescript
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const QUADRANT_COLORS = {
  star: '#22c55e',        // green - high ROAS, high revenue
  cashCow: '#3b82f6',     // blue - high ROAS, low revenue
  questionMark: '#f59e0b', // amber - low ROAS, high revenue
  dog: '#ef4444',          // red - low ROAS, low revenue
}

<ScatterChart>
  <XAxis dataKey="roas" name="ROAS" />
  <YAxis dataKey="revenue" name="Revenue" />
  <ZAxis dataKey="spend" range={[40, 400]} name="Spend" />
  <Scatter data={productGroups}>
    {productGroups.map((group, i) => (
      <Cell key={i} fill={getQuadrantColor(group)} cursor="pointer" />
    ))}
  </Scatter>
</ScatterChart>
```

### Pattern 3: Slide-Out Panel
**What:** Right-side panel that overlays the chart when a bubble is clicked
**When to use:** PROD-03 drill-down

```typescript
// Use shadcn Sheet component for slide-out behavior
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'

// When bubble clicked, set selectedGroup state
// Chart gets opacity-50 class when panel is open
```

### Anti-Patterns to Avoid
- **Per-component data fetching:** Do NOT have each chart component fetch its own data. One API call per tab, distribute via props or context.
- **Client-side Supabase queries:** Do NOT query Supabase from client components. Use API routes (server-side) to keep service role key secure.
- **Hardcoded competitor tokens:** Store competitor list as a constant that can be extended, not scattered inline.
- **Recharts re-renders:** Memoize chart data transformations to prevent unnecessary re-renders on tab switches.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bubble chart | Custom SVG/Canvas renderer | Recharts ScatterChart + ZAxis | Handles tooltip, responsiveness, zoom out of box |
| Slide-out panel | Custom CSS overlay | shadcn Sheet component | Already handles animation, focus trap, backdrop |
| Sortable table | Custom sort logic | shadcn Table + useState for sort | Pattern already used in shopping-funnel page |
| Median/percentile | Custom math | simple-statistics.median(), percentile() | Already installed, handles edge cases |
| Skeleton loaders | Custom pulse animations | shadcn Skeleton component | Already used throughout dashboard |
| Tab component | Custom tab logic | shadcn Tabs | Already used in shopping-funnel, tier-scoring |

**Key insight:** Every visualization component needed for Phase 35 has either an existing pattern in the codebase or a direct Recharts component. No custom chart rendering needed.

## Common Pitfalls

### Pitfall 1: Monthly Search Volumes JSONB Parsing
**What goes wrong:** `keyword_metrics.monthly_searches` is JSONB but may be stored as text string
**Why it happens:** Supabase JSONB conventions in this project require explicit parsing
**How to avoid:** Use `(monthly_searches#>>'{}')::jsonb` pattern from SCHEMA.md conventions, or parse client-side after fetch
**Warning signs:** Empty/null monthly_searches values when data should exist

### Pitfall 2: Impression Share Calculation
**What goes wrong:** Comparing `search_queries.impressions` (actual for a period) with `keyword_metrics.avg_monthly_searches` (monthly average) without normalizing
**Why it happens:** Different time windows -- actual is per-period, KP is monthly average
**How to avoid:** Normalize actual impressions to monthly equivalent based on `period_start`/`period_end` date range, OR clearly label as "Share of Search Volume" not "Impression Share" (Google's impression share is a different metric)
**Warning signs:** Share percentages > 100% or nonsensically small

### Pitfall 3: Brand Detection Accuracy
**What goes wrong:** Simple token matching misclassifies terms (e.g., "delta faucet" is competitor but "delta" alone could be other things)
**Why it happens:** Single-token matching is too broad
**How to avoid:** Use existing `QueryIntentFeatures.is_branded` / `is_competitor` from `query-intelligence.ts` NLP decomposition; add specific competitor token list as fallback
**Warning signs:** "delta" matching non-competitor contexts

### Pitfall 4: BCG Quadrant Median Sensitivity
**What goes wrong:** Median ROAS/Revenue shifts when product groups are added/removed or data refreshes
**Why it happens:** Dynamic medians mean quadrant boundaries move
**How to avoid:** Show the median lines on the chart so users understand the boundary. Consider showing the median values explicitly.
**Warning signs:** Products jumping quadrants between refreshes without performance change

### Pitfall 5: Large Dataset Performance
**What goes wrong:** Loading all ~3K+ search terms with full metrics causes slow API response
**Why it happens:** Joining search_queries + keyword_metrics + query_value_scores is a heavy query
**How to avoid:** Aggregate at API level (group by custom_label_0), return summary data. Only load term-level detail on drill-down (lazy loading in slide-out panel).
**Warning signs:** API response time > 2 seconds, browser freezing on chart render

### Pitfall 6: Trend Direction Calculation
**What goes wrong:** Trend direction for BCG bubble color is undefined -- no clear source
**Why it happens:** CONTEXT.md says "Color: Trend direction" but doesn't specify which trend
**How to avoid:** Use `funnel_snapshots_daily` to compute 30-day vs prior 30-day revenue change per custom_label_0. Positive trend = green, negative = red, flat = gray.
**Warning signs:** All bubbles same color because trend data is missing

## Code Examples

### Impression Share Gap Calculation (DEMAND-01)
```sql
-- SQL for API route
SELECT
  sq.query_text,
  sq.custom_label_0,
  SUM(sq.impressions) as actual_impressions,
  km.avg_monthly_searches as market_volume,
  CASE
    WHEN km.avg_monthly_searches > 0
    THEN ROUND(SUM(sq.impressions)::numeric / km.avg_monthly_searches * 100, 1)
    ELSE NULL
  END as impression_share_pct
FROM search_queries sq
LEFT JOIN keyword_metrics km ON LOWER(sq.query_text) = LOWER(km.keyword)
WHERE sq.impressions > 0
GROUP BY sq.query_text, sq.custom_label_0, km.avg_monthly_searches
ORDER BY km.avg_monthly_searches DESC NULLS LAST
```

### CPC Opportunity Score (DEMAND-02)
```sql
SELECT
  sq.query_text,
  sq.custom_label_0,
  CASE WHEN SUM(sq.clicks) > 0
    THEN SUM(sq.cost_micros) / SUM(sq.clicks)
    ELSE 0
  END as actual_cpc_micros,
  km.high_cpc_micros as market_high_cpc,
  CASE WHEN km.high_cpc_micros > 0
    THEN ROUND((1 - (SUM(sq.cost_micros)::numeric / SUM(sq.clicks)) / km.high_cpc_micros) * 100, 1)
    ELSE NULL
  END as cpc_headroom_pct
FROM search_queries sq
LEFT JOIN keyword_metrics km ON LOWER(sq.query_text) = LOWER(km.keyword)
WHERE sq.clicks > 0
GROUP BY sq.query_text, sq.custom_label_0, km.high_cpc_micros
```

### New Term Discovery (DEMAND-04)
```sql
SELECT
  sq.query_text,
  sq.custom_label_0,
  MIN(sq.period_start) as first_seen,
  SUM(sq.impressions) as total_impressions,
  SUM(sq.clicks) as total_clicks
FROM search_queries sq
WHERE sq.period_start >= CURRENT_DATE - INTERVAL '7 days'
AND NOT EXISTS (
  SELECT 1 FROM search_queries sq2
  WHERE sq2.query_text = sq.query_text
  AND sq2.period_start < CURRENT_DATE - INTERVAL '7 days'
)
GROUP BY sq.query_text, sq.custom_label_0
ORDER BY total_impressions DESC
```

### Product Group BCG Classification (PROD-01)
```typescript
interface ProductGroup {
  customLabel0: string
  roas: number
  revenue: number
  spend: number
  trend: number // percentage change
  quadrant: 'star' | 'cashCow' | 'questionMark' | 'dog'
  termCount: number
}

function classifyQuadrant(
  group: { roas: number; revenue: number },
  medianRoas: number,
  medianRevenue: number
): string {
  if (group.roas >= medianRoas && group.revenue >= medianRevenue) return 'star'
  if (group.roas >= medianRoas && group.revenue < medianRevenue) return 'cashCow'
  if (group.roas < medianRoas && group.revenue >= medianRevenue) return 'questionMark'
  return 'dog'
}
```

### Competitor Token Tracking (DEMAND-06)
```typescript
const COMPETITOR_TOKENS = [
  'moen', 'delta', 'kohler', 'grohe', 'hansgrohe', 'pfister',
  'american standard', 'brizo', 'rohl', 'symmons', 'jacuzzi',
  'kingston brass', 'signature hardware'
] as const

function matchCompetitorTokens(queryText: string): string[] {
  const lower = queryText.toLowerCase()
  return COMPETITOR_TOKENS.filter(token => lower.includes(token))
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom D3 charts | Recharts declarative API | Project standard | Less code, consistent styling |
| Individual API calls per metric | Batched Promise.all per tab | Phase 33+ pattern | Single round-trip per tab |
| Hardcoded sort in client | Server-side ORDER BY | Phase 34 pattern | Faster for large datasets |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest (via Next.js) + React Testing Library |
| Config file | `dashboard/vitest.config.ts` (if exists) or `jest.config.js` |
| Quick run command | `cd dashboard && npx vitest run src/app/api/market-intelligence --reporter=verbose` |
| Full suite command | `cd dashboard && npx vitest run --reporter=verbose` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEMAND-01 | Impression share gap calculation | unit | `npx vitest run src/app/api/market-intelligence/__tests__/demand.test.ts -t "impression share"` | No - Wave 0 |
| DEMAND-02 | CPC opportunity score | unit | `npx vitest run src/app/api/market-intelligence/__tests__/demand.test.ts -t "cpc opportunity"` | No - Wave 0 |
| DEMAND-03 | Seasonal pattern detection (>20% flag) | unit | `npx vitest run src/app/api/market-intelligence/__tests__/demand.test.ts -t "seasonal"` | No - Wave 0 |
| DEMAND-04 | New term discovery count | unit | `npx vitest run src/app/api/market-intelligence/__tests__/demand.test.ts -t "new term"` | No - Wave 0 |
| DEMAND-05 | Brand vs non-brand revenue split | unit | `npx vitest run src/app/api/market-intelligence/__tests__/competitive.test.ts -t "brand split"` | No - Wave 0 |
| DEMAND-06 | Competitor token matching | unit | `npx vitest run src/app/api/market-intelligence/__tests__/competitive.test.ts -t "competitor"` | No - Wave 0 |
| DEMAND-07 | Long-tail word count bucketing | unit | `npx vitest run src/app/api/market-intelligence/__tests__/demand.test.ts -t "long-tail"` | No - Wave 0 |
| PROD-01 | BCG quadrant classification | unit | `npx vitest run src/lib/market-intelligence/__tests__/bcg.test.ts -t "quadrant"` | No - Wave 0 |
| PROD-02 | Bubble chart renders with data | smoke/manual | Manual - visual verification | N/A |
| PROD-03 | Click bubble opens slide-out | smoke/manual | Manual - interaction verification | N/A |
| PROD-04 | Table view shows sortable columns | smoke/manual | Manual - interaction verification | N/A |

### Sampling Rate
- **Per task commit:** `cd dashboard && npm run build` (type check + build)
- **Per wave merge:** `cd dashboard && npm run build && npm run lint`
- **Phase gate:** Full build green + manual visual verification of all 3 tabs

### Wave 0 Gaps
- [ ] `dashboard/src/app/api/market-intelligence/__tests__/demand.test.ts` -- covers DEMAND-01 through DEMAND-04, DEMAND-07
- [ ] `dashboard/src/app/api/market-intelligence/__tests__/competitive.test.ts` -- covers DEMAND-05, DEMAND-06
- [ ] `dashboard/src/lib/market-intelligence/__tests__/bcg.test.ts` -- covers PROD-01

## Open Questions

1. **Competitor token list completeness**
   - What we know: User specified moen, delta, kohler as examples
   - What's unclear: Full list of competitors Allied Brass tracks
   - Recommendation: Start with the tokens above plus common bathroom fixture brands; make the list a constant that's easy to extend

2. **Trend period for BCG bubble colors**
   - What we know: Color should represent trend direction
   - What's unclear: What time period defines "trend" (7 days? 30 days? vs prior period?)
   - Recommendation: Use 30-day vs prior 30-day from `funnel_snapshots_daily`; if insufficient data, fall back to neutral color

3. **search_queries date range for aggregation**
   - What we know: `search_queries` has `period_start`/`period_end` columns
   - What's unclear: Whether to use latest period only or aggregate across all periods
   - Recommendation: Use latest 30-day period by default; add date range filter if needed later

## Sources

### Primary (HIGH confidence)
- Codebase: `dashboard/src/lib/optimization/tier-scoring.types.ts` - existing type patterns
- Codebase: `dashboard/src/components/shared/Sidebar.tsx` - nav item structure
- Codebase: `dashboard/src/app/(dashboard)/shopping-funnel/page.tsx` - page structure pattern
- Codebase: `docs/database/SCHEMA.md` - all table schemas verified
- Codebase: `dashboard/package.json` - Recharts 3.7.0 confirmed installed

### Secondary (MEDIUM confidence)
- Recharts ScatterChart API - based on Recharts documentation patterns; ZAxis for bubble size is standard
- shadcn Sheet component - standard Radix-based slide-out pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and used in project
- Architecture: HIGH - follows exact same patterns as Phase 33/34 pages
- Pitfalls: HIGH - based on actual codebase conventions (JSONB parsing, case sensitivity)

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (stable -- no external API changes expected)
