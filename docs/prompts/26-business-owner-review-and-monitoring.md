# Task 26: Allied Brass Business Owner — Review, Publish, and Monitor Content Performance

## Objective

You ARE the owner of Allied Brass. You have a feed optimization dashboard at https://allied-feed-ops.vercel.app that you built to optimize your Google Shopping feed content. Your goal is to use this dashboard to:

1. **Review and approve** AI-generated content for your products — ensuring every title, description, and lifestyle image you approve will drive more revenue
2. **Publish** approved content to Google Merchant Center (via Google Sheets supplemental feed) and Shopify
3. **Monitor performance** at every level — account-wide, category-level, and per-SKU — to understand if your content changes are actually working
4. **Take action** based on performance data — double down on what works, fix what doesn't, and continuously improve

You are not a passive reviewer. You are an active business owner making decisions that directly impact revenue. Every approval is a bet that the new content will outperform what's currently live. You need data to make that bet, and you need monitoring to know if you won.

## Your Business Context

- **Company**: Allied Brass — premium bathroom accessories manufacturer
- **Products**: ~1,200 master SKUs × 28 finishes = ~33,600 variants
- **Sales channels**: Shopify storefront + Google Shopping ads + Bing Shopping ads
- **Revenue model**: Direct-to-consumer via Shopify, traffic driven primarily by Google Shopping
- **Average order value**: $30-$200 per item
- **Key differentiators**: Solid brass construction, 28 finish options, Made in Virginia, Lifetime warranty

## Phase 1: Understand Your Current State

Before reviewing any content, understand where your business stands RIGHT NOW.

### 1.1 Account-Level Google Ads Health Check

These are metrics you should monitor REGARDLESS of content changes — they tell you if your ads business is healthy.

**Pull account-level metrics** using `mcp__google-ads-mcp__search`:

```
Customer ID: 6253381786

-- Account-level last 30 days
SELECT metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM customer WHERE segments.date DURING LAST_30_DAYS

-- Account-level last 7 days (recent trend)
SELECT metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM customer WHERE segments.date DURING LAST_7_DAYS

-- Campaign breakdown
SELECT campaign.name, campaign.status, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM campaign WHERE segments.date DURING LAST_30_DAYS AND campaign.status = 'ENABLED'
ORDER BY metrics.conversions_value DESC
```

**Assess**:
- **ROAS** (Return on Ad Spend): `conversions_value / (cost_micros / 1,000,000)` — Is it above your target? (3x? 5x?)
- **CPC trend**: Is cost per click rising? (competition increasing?)
- **Impression share**: Are you losing impressions to budget or rank?
- **Conversion rate**: `conversions / clicks` — Is it stable, rising, or declining?

### 1.2 Category-Level Performance

Understand which product categories are your revenue drivers vs money pits.

```
-- Product type performance (last 30 days)
SELECT segments.product_type_l1, segments.product_type_l2,
       metrics.impressions, metrics.clicks, metrics.conversions, metrics.conversions_value, metrics.cost_micros
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.conversions_value DESC
LIMIT 20
```

**Identify**:
- **Stars**: High revenue + high ROAS (protect these — careful with content changes)
- **Cash cows**: High revenue but declining (need content refresh)
- **Question marks**: High impressions, low conversion (content/price problem)
- **Dogs**: Low everything (deprioritize or test aggressively)

### 1.3 Pre-Publish Baseline Snapshot

Before approving ANY content, ensure baselines exist for those SKUs.

Use `mcp__supabase__execute_sql`:
```sql
-- Check which SKUs have baselines
SELECT master_sku, platform, avg_impressions, avg_clicks, avg_ctr, avg_conversions, avg_cvr, avg_conversion_value, created_at
FROM performance_baselines
WHERE platform = 'google'
ORDER BY avg_conversion_value DESC NULLS LAST
LIMIT 30;

-- Find SKUs with generated content but NO baseline (risky to publish without baseline)
SELECT gc.master_sku, gc.platform, gc.quality_score, pb.master_sku as has_baseline
FROM generated_content gc
LEFT JOIN performance_baselines pb ON gc.master_sku = pb.master_sku AND gc.platform = pb.platform
WHERE gc.content_type = 'title' AND gc.platform = 'google' AND gc.candidate_content IS NOT NULL
  AND pb.master_sku IS NULL
LIMIT 20;
```

**Rule**: Never publish content for a SKU without capturing a performance baseline first. You need the "before" to measure the "after."

## Phase 2: Review and Approve Content

### 2.1 Strategic SKU Selection

Don't review randomly. Prioritize SKUs by revenue impact.

**Tier 1 — High Revenue SKUs** (review first, most careful):
```sql
-- Top revenue SKUs with pending content
SELECT gc.master_sku, gc.quality_score, pb.avg_conversion_value, pb.avg_impressions, pb.avg_clicks
FROM generated_content gc
JOIN performance_baselines pb ON gc.master_sku = pb.master_sku AND gc.platform = pb.platform
JOIN sku_approvals sa ON gc.master_sku = sa.master_sku
WHERE gc.platform = 'google' AND gc.content_type = 'title'
  AND sa.approval_status = 'pending'
ORDER BY pb.avg_conversion_value DESC
LIMIT 10;
```

**Tier 2 — High Impression, Low CTR** (biggest opportunity):
```sql
-- SKUs people see but don't click — title is the problem
SELECT gc.master_sku, gc.quality_score, pb.avg_impressions, pb.avg_clicks, pb.avg_ctr
FROM generated_content gc
JOIN performance_baselines pb ON gc.master_sku = pb.master_sku AND gc.platform = pb.platform
JOIN sku_approvals sa ON gc.master_sku = sa.master_sku
WHERE gc.platform = 'google' AND gc.content_type = 'title'
  AND sa.approval_status = 'pending'
  AND pb.avg_impressions > 50
ORDER BY pb.avg_ctr ASC
LIMIT 10;
```

**Tier 3 — Zero Performance Data** (new products or low volume):
- Lower risk to experiment with
- Good for testing new content approaches

### 2.2 Review Checklist (Per SKU)

Navigate to `https://allied-feed-ops.vercel.app/review/{sku}` using Chrome browser automation (`mcp__claude-in-chrome__*`).

For each SKU, evaluate:

**Title Review**:
1. Does the title front-load the product type and key spec? (first 30 chars = mobile visibility)
2. Does the title include keywords from the top search queries for this SKU?
3. Is the title differentiated from competitors? (check Google Shopping for similar products)
4. Does the title include the collection name? (brand recognition)
5. Is it the right length? (50-150 chars for Google, no brand/finish for Shopify)

**Description Review**:
1. Does the opening hook address the buyer's actual need? (not generic filler)
2. Are ALL key dimensions included? (L × H × W, projection, weight)
3. Is the finish sentence natural and adds value?
4. Does it mention installation details? (buyers need to know)
5. Does it include trust signals? (warranty, solid brass, Made in Virginia)
6. Is it the right length? (600-800 chars Google, 600-1000 chars Shopify)

**Cross-Platform Check**:
- Google title ≠ Shopify title (different goals)
- Google description focuses on Shopping ad conversion
- Shopify description focuses on on-site purchase conversion
- Bing can mirror Google but watch for length differences

**Search Query Alignment**:
- Check the Search Insights card on the review page
- Are the top search queries reflected in the title/description?
- Missing high-volume keywords = missed traffic opportunity

**Quality Score Interpretation**:
- 90+ = Excellent, approve with confidence
- 80-89 = Good, review for specific improvements
- 70-79 = Acceptable, consider regenerating with feedback
- Below 70 = Regenerate with specific instructions

### 2.3 Approval Actions

- **Approve**: Content meets all criteria above. Click Approve.
- **Reject with feedback**: Content is close but needs specific fixes. Click Reject, provide detailed notes (e.g., "Missing mounting type in title" or "Description doesn't mention 28 finish options"). This triggers regeneration with your feedback.
- **Regenerate**: Content needs a full rewrite. Use the Regenerate button with specific instructions.

### 2.4 Lifestyle Image Review

For SKUs with lifestyle images:
- Are images showing the product in a realistic bathroom setting?
- Does the selected finish match the variant?
- Is the AI recommendation reasonable? (check scores)
- Approve images before publishing — they go to the `lifestyle_image_link` column in the Google Sheets feed

## Phase 3: Publish

### 3.1 Batch Strategy

Don't publish everything at once. Stagger for measurement.

**Recommended approach**:
1. **Wave 1**: 5-10 high-confidence SKUs (quality score 85+, strong baseline data)
2. **Wait 7 days**: Monitor performance snapshots
3. **Wave 2**: Next 10-20 SKUs if Wave 1 shows positive signals
4. **Wave 3+**: Scale up based on results

### 3.2 Publishing Steps

1. Navigate to Batches page (`/batches`)
2. Create a new batch
3. Add approved SKUs to the batch
4. Select platforms (Google, Bing, Shopify — or individual)
5. Publish — this writes to Google Sheets supplemental feed + Shopify product pages
6. Verify: Check Google Sheets to confirm rows updated correctly

### 3.3 Post-Publish Verification

After each publish:
```sql
-- Verify publish events recorded
SELECT master_sku, platform, action, status, published_at
FROM publish_events
WHERE status = 'success' AND action = 'publish'
ORDER BY published_at DESC LIMIT 20;

-- Verify content snapshots stored (for rollback)
SELECT master_sku, platform, content_type, published_at
FROM publish_events
WHERE action = 'publish' AND status = 'success'
ORDER BY published_at DESC LIMIT 10;
```

## Phase 4: Performance Monitoring

### 4.1 Always-On Metrics (Monitor Regardless of Content Changes)

These tell you if your ads business is healthy. Check weekly minimum.

**Account Health Dashboard**:
| Metric | What It Tells You | Alert Threshold |
|--------|-------------------|-----------------|
| Total ROAS | Overall ad efficiency | Below 3x = investigate |
| Account CTR | Ad relevance | Below 1% = title/image problem |
| Account CVR | Landing page effectiveness | Below 2% = site/price problem |
| Total Spend | Budget utilization | Sudden drops = campaign issue |
| CPC Trend | Competition level | >20% increase week-over-week |
| Impression Share | Visibility | Below 50% = budget/bid issue |
| Search Term Report | Query relevance | New irrelevant terms = negative keyword needed |

**Weekly Check Query**:
```
-- Week-over-week comparison
SELECT segments.date, metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
FROM customer
WHERE segments.date DURING LAST_14_DAYS
ORDER BY segments.date
```

### 4.2 Content-Change Monitoring (Per-SKU Level)

After publishing new content, track these metrics for each affected SKU.

**Capture snapshots** — Call the snapshot endpoint regularly:
```bash
# Capture for all published SKUs
curl -X POST https://allied-feed-ops.vercel.app/api/performance/capture-snapshot

# Or for specific SKU
curl -X POST "https://allied-feed-ops.vercel.app/api/performance/capture-snapshot?master_sku=920D-6&platform=google"
```

**Monitor at intervals**:
- **Day 1-3**: Impressions — Did Google start showing the new content? (GMC processes changes in 24-48 hours)
- **Day 3-7**: CTR — Are more people clicking? (Title/image change impact)
- **Day 7-14**: CVR — Are more clickers converting? (Description/landing page impact)
- **Day 14-30**: Revenue — Net revenue impact after full attribution window

**Per-SKU Tracking Query**:
```sql
-- Performance trend since publish
SELECT ps.snapshot_date, ps.days_since_publish, ps.impressions, ps.clicks, ps.ctr, ps.conversions, ps.cvr, ps.conversion_value,
       pb.avg_impressions as baseline_impressions, pb.avg_clicks as baseline_clicks, pb.avg_ctr as baseline_ctr, pb.avg_cvr as baseline_cvr
FROM performance_snapshots ps
JOIN performance_baselines pb ON ps.master_sku = pb.master_sku AND ps.platform = pb.platform
WHERE ps.master_sku = '{sku}' AND ps.platform = 'google'
ORDER BY ps.snapshot_date;
```

### 4.3 Alert Thresholds — When to Take Action

**Positive Signals** (double down):
| Signal | Threshold | Action |
|--------|-----------|--------|
| CTR increase | >15% vs baseline after 7 days | Approve similar content patterns for other SKUs |
| CVR increase | >10% vs baseline after 14 days | Scale to more SKUs in same category |
| Revenue increase | >20% vs baseline after 30 days | Apply same prompt/approach to all pending SKUs |
| Impression increase | >25% vs baseline | Google is rewarding the content — protect it |

**Negative Signals** (investigate and fix):
| Signal | Threshold | Action |
|--------|-----------|--------|
| CTR decrease | >15% vs baseline after 7 days | Rollback title immediately, investigate |
| CVR decrease | >10% vs baseline after 14 days | Check description, check price, check landing page |
| Revenue decrease | >15% vs baseline after 30 days | Full rollback, regenerate with different approach |
| Impressions drop | >30% vs baseline | GMC may have flagged content — check for policy issues |

**Rollback Process**:
1. `publish_events` stores content snapshots
2. Can revert to previous content version
3. Regenerate with feedback: "Previous version had higher CTR, analyze what made it effective"

### 4.4 Category-Level Aggregation

Don't just track per-SKU — look for patterns across categories.

```sql
-- Category performance after content changes (aggregate published SKUs)
SELECT pc.category, COUNT(DISTINCT pe.master_sku) as published_skus,
       AVG(ps.ctr) as avg_current_ctr, AVG(pb.avg_ctr) as avg_baseline_ctr,
       AVG(ps.cvr) as avg_current_cvr, AVG(pb.avg_cvr) as avg_baseline_cvr,
       SUM(ps.conversion_value) as total_current_revenue
FROM publish_events pe
JOIN performance_snapshots ps ON pe.master_sku = ps.master_sku AND pe.platform = ps.platform
JOIN performance_baselines pb ON pe.master_sku = pb.master_sku AND pe.platform = pb.platform
JOIN product_catalog pc ON pe.master_sku = pc.master_sku
WHERE pe.status = 'success' AND pe.action = 'publish'
  AND ps.snapshot_date = (SELECT MAX(snapshot_date) FROM performance_snapshots WHERE master_sku = ps.master_sku)
GROUP BY pc.category
ORDER BY published_skus DESC;
```

**Category-level questions**:
- Are towel bars responding better to content changes than soap dishes?
- Which categories have the highest CTR lift? (Replicate that approach)
- Which categories show CVR decline despite CTR increase? (Traffic quality issue)

### 4.5 Search Query Evolution

Monitor how search queries change after content updates.

```sql
-- Compare search queries before and after publish
SELECT sqs.query_text, sqs.impressions, sqs.clicks, sqs.snapshot_date, sqs.days_since_publish
FROM search_query_snapshots sqs
WHERE sqs.master_sku = '{sku}'
ORDER BY sqs.snapshot_date, sqs.impressions DESC;
```

**Watch for**:
- New queries appearing (content change attracted different searches)
- High-value queries gaining impressions (keyword optimization working)
- Irrelevant queries appearing (content may be too broad — add negative keywords)

## Phase 5: Continuous Improvement Loop

### The Feedback Cycle

```
Monitor Performance → Identify Patterns → Update Generation → Review & Approve → Publish → Monitor...
```

1. **Weekly**: Review account health metrics, capture snapshots
2. **Bi-weekly**: Compare published SKU performance vs baselines
3. **Monthly**: Category-level analysis, identify content patterns that work
4. **Quarterly**: Update generation prompt and scoring based on performance data

### What To Do With This Information

**Revenue is up for a category**:
- Document what content patterns drove the improvement
- Update prompt examples (gold standards) with winning content
- Prioritize remaining SKUs in that category for the same treatment
- Consider increasing ad budget for high-performing categories

**Revenue is flat or down**:
- Compare content changes side-by-side with baseline content
- Check if the issue is CTR (title/image problem) or CVR (description/price/site problem)
- Check competitor landscape — did new competitors enter?
- Check search query changes — are you matching different (worse) queries?
- Rollback if clearly negative, iterate if ambiguous

**New opportunity discovered**:
- High-volume keyword not in any titles → Update prompt to prioritize this keyword
- Competitor weakness identified → Lean into that differentiator
- Seasonal trend emerging → Adjust content timing
- New finish popularity → Prioritize that finish for lifestyle images

## MCP Tools & Skills

**Use all available tools freely:**

**MCP Servers**:
- `mcp__google-ads-mcp__search` — All Google Ads queries (performance, keywords, search terms)
- `mcp__supabase__execute_sql` — Database queries (ALWAYS check `docs/database/SCHEMA.md` first)
- `mcp__merchant-api-devdocs__*` — GMC product status, price competitiveness
- `mcp__Apify__*` — Competitor analysis, SERP scraping
- `mcp__claude-in-chrome__*` — Dashboard interaction, live site review, Google Shopping browsing
- `mcp__analytics-mcp__*` — Google Analytics data (site behavior, conversion funnels)
- `mcp__vercel__*` — Dashboard deployment status
- `mcp__gcloud__*` — Cloud Run pipeline status

**Skills**:
- `superpowers:brainstorming` — Before making content strategy decisions
- `superpowers:systematic-debugging` — When investigating performance drops
- `marketing-skills:paid-ads` — Google Shopping optimization strategies
- `marketing-skills:analytics-tracking` — Setting up new tracking
- `marketing-skills:page-cro` — On-site conversion optimization
- `marketing-skills:copywriting` — Content quality evaluation
- `marketing-skills:content-strategy` — Content approach decisions
- `marketing-skills:ab-test-setup` — Designing content experiments
- `marketing-skills:competitor-alternatives` — Competitive positioning
- `marketing-skills:seo-audit` — Organic search impact of content changes

**Agent Teams**: Consider using `superpowers:dispatching-parallel-agents` for:
- Simultaneous Google Ads data pull + Supabase performance query + Competitor scraping
- Parallel review of multiple SKUs across platforms
- Concurrent monitoring of different metric categories

## Critical Context

- **Database schema**: ALWAYS read `docs/database/SCHEMA.md` before writing SQL queries
- **Google Ads customer ID**: `6253381786`
- **Dashboard URL**: `https://allied-feed-ops.vercel.app`
- **Pipeline URL**: current canonical `FEEDOPS_PIPELINE_URL`
- **Offer ID format**: Database = lowercase `shopify_us_`, GMC = uppercase `shopify_US_`
- **Multi-SKU products**: Multiple master_skus share same product_id (Google Ads aggregates at product_id)
- **Baseline requirement**: NEVER publish without a performance baseline — you need the "before" to measure the "after"
- **Snapshot endpoint**: `POST /api/performance/capture-snapshot` — call after publish and at regular intervals
- **Content is reversible**: `publish_events` stores snapshots for rollback — don't be afraid to publish, but monitor closely
