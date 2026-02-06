# Task: Search Insights & Performance Data Lifecycle

## Overview

This prompt covers the complete data lifecycle from search queries and performance metrics through to content generation and review. The goal is to create a closed-loop system where:

1. **Search data** informs what keywords to include in content
2. **Performance data** measures how well content performs after publishing
3. **Review page** surfaces both to help reviewers make informed decisions
4. **Content generation** automatically incorporates high-value keywords

---

## Mode & Skills

**Recommended Mode:** Plan Mode (`/plan`)

**Required Skills (invoke in order):**
1. `superpowers:brainstorming` - Before designing the implementation approach
2. `superpowers:systematic-debugging` - When investigating existing data flow issues
3. `frontend-design` - When implementing the Review page UI components
4. `superpowers:test-driven-development` - Before implementing each phase
5. `superpowers:verification-before-completion` - Before claiming any phase complete

**MCP Servers to Use:**
- `mcp__supabase__execute_sql` - Query/inspect Supabase tables directly
- `mcp__supabase__list_tables` - Verify schema exists
- `mcp__google-ads-mcp__search` - Test Google Ads API queries
- `mcp__vercel__get_runtime_logs` - Debug API issues in production
- `mcp__plugin_playwright_playwright__*` - Visual verification of dashboard pages

**Agents to Consider:**
- `Explore` agent - For thorough codebase investigation
- `Plan` agent - For architectural decisions

---

## The Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SEARCH INSIGHTS FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Google Ads API                                                             │
│  (search_term_view)                                                         │
│        │                                                                    │
│        ▼                                                                    │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐       │
│  │ search_queries  │────▶│ keyword_metrics │────▶│ Evidence Table  │       │
│  │ (raw terms)     │     │ (volume, CPC)   │     │ Builder         │       │
│  └─────────────────┘     └─────────────────┘     └────────┬────────┘       │
│                                                           │                 │
│        ┌──────────────────────────────────────────────────┤                 │
│        │                                                  │                 │
│        ▼                                                  ▼                 │
│  ┌─────────────────┐                            ┌─────────────────┐        │
│  │ Review Page     │                            │ LLM Prompt      │        │
│  │ SearchInsights  │                            │ "Include these  │        │
│  │ Card            │                            │  keywords..."   │        │
│  └─────────────────┘                            └─────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PERFORMANCE DATA FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BEFORE PUBLISH                              AFTER PUBLISH                  │
│  ┌─────────────────┐                        ┌─────────────────┐            │
│  │ Capture 30-day  │                        │ Capture weekly  │            │
│  │ baseline        │                        │ snapshots       │            │
│  └────────┬────────┘                        └────────┬────────┘            │
│           │                                          │                      │
│           ▼                                          ▼                      │
│  ┌─────────────────┐                        ┌─────────────────┐            │
│  │ performance_    │                        │ performance_    │            │
│  │ baselines       │                        │ snapshots       │            │
│  └────────┬────────┘                        └────────┬────────┘            │
│           │                                          │                      │
│           └──────────────────┬───────────────────────┘                      │
│                              │                                              │
│                              ▼                                              │
│                    ┌─────────────────┐                                     │
│                    │ Review Page     │                                     │
│                    │ Performance     │                                     │
│                    │ Card            │                                     │
│                    └────────┬────────┘                                     │
│                             │                                              │
│              ┌──────────────┴──────────────┐                               │
│              ▼                              ▼                               │
│     ┌─────────────────┐           ┌─────────────────┐                      │
│     │ /generate page  │           │ Lift metrics    │                      │
│     │ SKU priority    │           │ Before/After    │                      │
│     └─────────────────┘           └─────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 0: Verify Search Insights Sync Works

**Before starting implementation, verify the Search Insights sync is operational.**

The CI/CD pipeline and all Google Ads secrets are already configured. If sync fails, use `superpowers:systematic-debugging` to investigate.

### Verification Steps

1. Navigate to https://allied-feed-ops.vercel.app/search-insights
2. Click "Sync Data" button
3. Verify sync starts (shows progress indicator)

**If sync fails:**
- Check Cloud Run logs: `gcloud builds list --project=bobbys-project-346400 --limit=5`
- Check Vercel logs for API errors
- Verify all 8 GCP secrets exist and are bound to runtime SA (see CLAUDE.md)

---

## Phase 1: Review Page Insight Cards

**Skill:** `frontend-design`

Implement three collapsible "Insight Cards" in the Review page sidebar that surface search and performance data to reviewers.

### Design System

**Color Variables (status-driven):**
```css
--insight-positive: #10b981;   /* emerald-500 - good */
--insight-warning: #f59e0b;    /* amber-500 - needs attention */
--insight-critical: #ef4444;   /* red-500 - action required */
--insight-neutral: #6b7280;    /* gray-500 - no data */
```

**Typography:**
- Card headers: `font-medium text-sm text-gray-500 uppercase tracking-wide`
- Key metrics: `font-semibold text-lg text-gray-900`
- Secondary text: `text-sm text-gray-600`

### Component 1: SearchInsightsCard

**Location:** `dashboard/src/components/review/SearchInsightsCard.tsx`

**Collapsed State:**
```
┌────────────────────────────────────────────────────────────┐
│ 🔍 SEARCH INSIGHTS                          ● 3 gaps  [▼] │
├────────────────────────────────────────────────────────────┤
│ "brass towel bar 24"                           2.4K/mo    │
│  └─ ✓ in title                                            │
└────────────────────────────────────────────────────────────┘
```

**Expanded State:**
```
┌────────────────────────────────────────────────────────────┐
│ 🔍 SEARCH INSIGHTS                          ● 3 gaps  [▲] │
├────────────────────────────────────────────────────────────┤
│ TOP QUERIES                                               │
│ ┌──────────────────────────────────┬─────────┬──────────┐ │
│ │ brass towel bar 24 inch          │ 2.4K/mo │ ✓ title  │ │
│ │ wall mount towel holder          │ 1.8K/mo │ ⚠ desc   │ │
│ │ bathroom towel bar brass         │ 1.2K/mo │ ✓ title  │ │
│ │ polished brass accessories       │   950   │ ✗ missing│ │
│ └──────────────────────────────────┴─────────┴──────────┘ │
│                                                           │
│ KEYWORD GAPS (high volume, not in content)                │
│ ┌─────────────────────────────────────────────────────┐   │
│ │ ⚠ "wall mount" — 1,800/mo — Add to title           │   │
│ │ ⚠ "bathroom" — 950/mo — Consider for description   │   │
│ │ ⚠ "24 inch" — 720/mo — Dimension missing           │   │
│ └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

**Status Indicator Logic:**
- 🟢 Green dot: All top 5 queries have keywords in title
- 🟡 Yellow dot + count: 1-3 keyword gaps found
- 🔴 Red dot + count: 4+ keyword gaps OR top query keyword not in title

**Data Source:**
- `search_queries_by_master_sku` table
- `keyword_metrics` table for volume data

### Component 2: PerformanceCard

**Location:** `dashboard/src/components/review/PerformanceCard.tsx`

**Collapsed State:**
```
┌────────────────────────────────────────────────────────────┐
│ 📊 PERFORMANCE (30d)                      ● below avg [▼] │
├────────────────────────────────────────────────────────────┤
│ 45.2K impressions   3.2% CTR   $2,847 revenue             │
│                     ▼ 0.9% vs category                    │
└────────────────────────────────────────────────────────────┘
```

**Expanded State (with baseline):**
```
┌────────────────────────────────────────────────────────────┐
│ 📊 PERFORMANCE (30d)                      ● below avg [▲] │
├────────────────────────────────────────────────────────────┤
│              CURRENT        BASELINE        CHANGE        │
│ Impressions  45,200         42,100          +7.4%  ↑      │
│ Clicks       1,446          1,263           +14.5% ↑      │
│ CTR          3.2%           3.0%            +0.2%  ↑      │
│ Conversions  89             71              +25.4% ↑      │
│ Revenue      $2,847         $2,201          +29.3% ↑      │
├────────────────────────────────────────────────────────────┤
│ ⚠ CTR 3.2% is below category average (4.1%)              │
│   Recommend: Improve title keyword match                  │
└────────────────────────────────────────────────────────────┘
```

**No Baseline State:**
```
┌────────────────────────────────────────────────────────────┐
│ 📊 PERFORMANCE (30d)                          ● no data   │
├────────────────────────────────────────────────────────────┤
│ 45.2K impressions   3.2% CTR   $2,847 revenue             │
│ Baseline will be captured when content is published.      │
└────────────────────────────────────────────────────────────┘
```

**Status Indicator Logic:**
- 🟢 Green: CTR ≥ category average AND improving
- 🟡 Yellow: CTR below average OR declining
- 🔴 Red: CTR significantly below average (>20% under)
- ⚪ Gray: No performance data available

**Data Source:**
- `performance_baselines` table (pre-publish metrics)
- `performance_snapshots` table (post-publish metrics)
- Live Google Ads API for current metrics

### Component 3: ContentQualityCard

**Location:** `dashboard/src/components/review/ContentQualityCard.tsx`

**Collapsed State:**
```
┌────────────────────────────────────────────────────────────┐
│ ✅ CONTENT QUALITY                              82%   [▼] │
├────────────────────────────────────────────────────────────┤
│ Ready to publish • Keyword Inclusion: 7/10                │
└────────────────────────────────────────────────────────────┘
```

**Expanded State:**
```
┌────────────────────────────────────────────────────────────┐
│ ✅ CONTENT QUALITY                              82%   [▲] │
├────────────────────────────────────────────────────────────┤
│ Specificity        ████████░░  8/10  Concrete claims      │
│ Benefit Coverage   ████████░░  8/10  Benefits in hook     │
│ Keyword Inclusion  ███████░░░  7/10  Missing "wall mount" │
│ Format Adherence   █████████░  9/10  Within limits        │
│ Brand Voice        ████████░░  8/10  Premium tone         │
│ Factual Accuracy   █████████░  9/10  All claims verified  │
├────────────────────────────────────────────────────────────┤
│ 💡 Add "wall mount" to title for +1 keyword score         │
└────────────────────────────────────────────────────────────┘
```

**Status Indicator Logic (from AGENTS.md):**
- 🟢 ≥80%: "Ready to publish"
- 🟡 70-79%: "Minor revisions needed"
- 🔴 <70%: "Major revision required"

**Data Source:**
- Quality scoring from `dashboard/src/lib/quality-scoring.ts`
- Scoring dimensions defined in `AGENTS.md`

### Review Page Layout Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ ← Back to Queue                                    [Approve] [Request Edit] │
├───────────────────────────────────────────┬─────────────────────────────────┤
│                                           │                                 │
│  PRODUCT HERO IMAGE                       │  INSIGHT CARDS (sidebar)        │
│  ┌─────────────────────────────────┐      │                                 │
│  │         [Product Image]         │      │  ┌─────────────────────────┐   │
│  └─────────────────────────────────┘      │  │ 🔍 Search Insights      │   │
│                                           │  │ "brass towel bar" 2.4K  │   │
│  CONTENT COMPARISON                       │  │ ● 3 gaps            [▼] │   │
│  ┌─────────────────────────────────┐      │  └─────────────────────────┘   │
│  │ CURRENT          │ CANDIDATE    │      │                                 │
│  │ (Shopify live)   │ (Generated)  │      │  ┌─────────────────────────┐   │
│  │ Title...         │ Title...     │      │  │ 📊 Performance          │   │
│  │ Description...   │ Description..│      │  │ 45K imp • 3.2% CTR      │   │
│  └─────────────────────────────────┘      │  │ ● below avg         [▼] │   │
│                                           │  └─────────────────────────┘   │
│  VARIANT TABS                             │                                 │
│  [Google] [Bing] [Shopify]                │  ┌─────────────────────────┐   │
│                                           │  │ ✅ Quality: 82%         │   │
│                                           │  │ Ready to publish    [▼] │   │
│                                           │  └─────────────────────────┘   │
│                                           │                                 │
└───────────────────────────────────────────┴─────────────────────────────────┘
```

**Files to Modify:**
- `dashboard/src/components/review/SkuReviewClient.tsx` - Add sidebar with cards
- `dashboard/src/components/review/SearchInsightsCard.tsx` - Create new
- `dashboard/src/components/review/PerformanceCard.tsx` - Create new
- `dashboard/src/components/review/ContentQualityCard.tsx` - Create new

---

## Phase 2: Evidence Table Integration

**Skill:** `superpowers:test-driven-development`

Ensure the evidence table builder includes search query data in LLM prompts.

### Current State

The evidence table builder exists at `dashboard/src/lib/evidence/search-queries.ts`. Verify it:
1. Queries `search_queries_by_master_sku` for the SKU being regenerated
2. Formats top queries with volume data
3. Identifies keyword gaps (high-volume terms not in current title/description)

### Expected LLM Prompt Section

```markdown
## Search Query Evidence

**Top queries for this product (last 30 days):**
- "brass towel bar 24 inch" - 2,400 monthly searches ✓ in title
- "wall mount towel holder" - 1,800 monthly searches ⚠ in description only
- "bathroom towel bar brass" - 1,200 monthly searches ✓ in title

**Keyword gaps (high volume, not in content):**
- "wall mount" (1,800/mo) — PRIORITIZE including in title
- "bathroom" (950/mo) — Consider for description hook
- "24 inch" (720/mo) — Dimension should be explicit

**Recommendation:** Ensure "wall mount" appears in title for better query matching.
```

### Implementation Steps

1. Verify `dashboard/src/lib/evidence/search-queries.ts` builds this section
2. Verify `dashboard/src/app/api/regenerate/route.ts` includes it in prompt
3. Test regeneration and confirm LLM receives search query context
4. Verify keyword inclusion improves in generated output

---

## Phase 3: Performance Baseline Capture

**Skill:** `superpowers:test-driven-development`

Automatically capture 30-day performance baseline before publishing content.

### Implementation Steps

1. **Add baseline capture function:**
   ```typescript
   // dashboard/src/lib/google-ads.ts
   export async function captureBaseline(
     masterSku: string,
     platform: 'google' | 'bing'
   ): Promise<PerformanceBaseline>
   ```

2. **Modify batch publish flow:**
   ```typescript
   // dashboard/src/lib/publishing/batch-publish.ts
   // Before publishing, capture baseline for each SKU
   await captureBaseline(masterSku, platform)
   ```

3. **Store in Supabase:**
   ```sql
   INSERT INTO performance_baselines
   (master_sku, platform, period_start, period_end, impressions, clicks, ctr, ...)
   ```

### Database Schema

```sql
CREATE TABLE performance_baselines (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  master_sku TEXT NOT NULL,
  platform TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  ctr DECIMAL(10,6) DEFAULT 0,
  conversions DECIMAL(10,2) DEFAULT 0,
  cvr DECIMAL(10,6) DEFAULT 0,
  cost DECIMAL(10,2) DEFAULT 0,
  revenue DECIMAL(10,2) DEFAULT 0,
  roas DECIMAL(10,4),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(master_sku, platform, period_start, period_end)
);
```

---

## Phase 4: Post-Publish Snapshots

**Skill:** `superpowers:brainstorming`

Create a scheduled job to capture performance snapshots for published SKUs.

### API Endpoint

```typescript
// dashboard/src/app/api/performance/capture-snapshot/route.ts
// POST /api/performance/capture-snapshot
// Captures current performance for all SKUs with publish_events

export async function POST(request: Request) {
  // 1. Get all SKUs with successful publish_events
  // 2. Fetch current performance from Google Ads
  // 3. Store in performance_snapshots
  // 4. Return summary
}
```

### Scheduler Options

| Option | Implementation | Recommendation |
|--------|---------------|----------------|
| Vercel Cron | `vercel.json` with cron schedule | Requires Pro plan |
| GitHub Actions | `.github/workflows/snapshot.yml` | Free, git-tracked |
| Manual trigger | Dashboard button + API | Start here |

**Recommended:** Start with manual API endpoint, add automation later.

---

## Phase 5: SKU Selection Prioritization

**Skill:** `superpowers:test-driven-development`

Use performance data to prioritize which SKUs appear in `/generate` recommendations.

### Enhanced Scoring Algorithm

Current tier scoring in `dashboard/src/lib/sku-scoring.ts` uses:
- Impressions (traffic volume)
- Conversions (revenue impact)
- Already optimized flag

**Add performance-based boosting:**
```typescript
// Boost priority for high-traffic, low-CTR products
if (impressions > 10000 && ctr < categoryAverageCtr * 0.8) {
  priorityScore *= 1.5  // These need optimization most
}

// Boost for products with declining performance
if (ctrTrend < -0.1) {  // 10% decline
  priorityScore *= 1.3
}
```

---

## Investigation Checklist

Before implementing, verify current state with MCP:

```sql
-- 1. Check if performance tables exist and have data
SELECT COUNT(*) as baseline_count FROM performance_baselines;
SELECT COUNT(*) as snapshot_count FROM performance_snapshots;
SELECT COUNT(*) as published_count FROM publish_events WHERE status = 'success';

-- 2. Check search query data
SELECT COUNT(*) as query_count FROM search_queries;
SELECT COUNT(*) as agg_count FROM search_queries_by_master_sku;

-- 3. Sample data to understand current state
SELECT master_sku, query_count, total_impressions
FROM search_queries_by_master_sku
ORDER BY total_impressions DESC LIMIT 10;
```

---

## Success Criteria

### Phase 1 (Review Page)
- [ ] SearchInsightsCard shows top queries with volume
- [ ] SearchInsightsCard highlights keyword gaps
- [ ] PerformanceCard shows current metrics
- [ ] PerformanceCard shows baseline comparison (when available)
- [ ] ContentQualityCard shows 6-dimension scoring
- [ ] Cards are collapsible with summary visible

### Phase 2 (Evidence Table)
- [ ] LLM prompt includes search query section
- [ ] Keyword gaps are explicitly called out
- [ ] Generated content shows improved keyword inclusion

### Phase 3 (Baseline Capture)
- [ ] Baseline captured automatically before publish
- [ ] Data stored in performance_baselines table
- [ ] No duplicate baselines for same SKU/platform/period

### Phase 4 (Snapshots)
- [ ] API endpoint captures snapshots on demand
- [ ] Snapshots stored in performance_snapshots table
- [ ] PerformanceCard can show before/after comparison

### Phase 5 (SKU Prioritization)
- [ ] High-traffic low-CTR products prioritized
- [ ] Declining products flagged for optimization
- [ ] Generate page shows performance context

---

## Files to Examine

### Existing Components
- `dashboard/src/components/review/SkuReviewClient.tsx` - Main review page
- `dashboard/src/components/review/SearchInsightsSummary.tsx` - May already exist

### Evidence & Scoring
- `dashboard/src/lib/evidence/search-queries.ts` - Search query evidence builder
- `dashboard/src/lib/quality-scoring.ts` - Content quality scoring (if exists)
- `dashboard/src/lib/sku-scoring.ts` - SKU selection scoring

### APIs
- `dashboard/src/app/api/regenerate/route.ts` - Content regeneration
- `dashboard/src/app/api/sku-selection/route.ts` - SKU recommendations
- `dashboard/src/app/api/performance/route.ts` - Performance data (if exists)

### Google Ads
- `dashboard/src/lib/google-ads.ts` - Google Ads API client

---

## Related Documentation

- `AGENTS.md` - Content scoring rubric (6 dimensions)
- `CLAUDE.md` - Project configuration and table schemas
- `docs/prompts/14-search-query-insights.md` - Search insights implementation
- `docs/prompts/17-description-quality-analyzer.md` - Quality scoring

---

## Plan Mode Execution Checklist

### Before Starting
- [ ] Enter plan mode: `/plan`
- [ ] Read all files in "Files to Examine" section
- [ ] Run investigation queries with MCP

### Phase 1: Review Page UI
- [ ] Invoke `frontend-design` skill
- [ ] Create SearchInsightsCard component
- [ ] Create PerformanceCard component
- [ ] Create ContentQualityCard component
- [ ] Integrate into SkuReviewClient sidebar
- [ ] Visual verification with Playwright

### Phase 2: Evidence Integration
- [ ] Verify search query evidence in prompts
- [ ] Test regeneration with search context
- [ ] Verify keyword inclusion improves

### Phase 3-5: Performance Data
- [ ] Implement baseline capture
- [ ] Implement snapshot endpoint
- [ ] Update SKU scoring algorithm

### Final Verification
- [ ] All success criteria met
- [ ] No regressions in existing functionality
- [ ] Update CLAUDE.md with new patterns
