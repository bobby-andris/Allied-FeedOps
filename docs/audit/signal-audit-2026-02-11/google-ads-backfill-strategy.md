# Google Ads Historical Backfill Strategy

## Executive Summary

Currently only **84 master SKUs** have search query data (2,147 rows across 714 unique queries). The goal is to backfill data for all **2,784 master SKUs / 72,023 variants** across **1,514 unique Shopify products**. This document covers the full strategy for search terms, performance data, and keyword metrics.

---

## 1. Current State Analysis

### What Exists Today

| Table | Rows | Unique SKUs | Coverage |
|-------|------|-------------|----------|
| search_queries | 2,147 | 84 | 3.0% of 2,784 |
| search_queries_by_master_sku | 894 | 84 | 3.0% |
| keyword_metrics | 714 | - (keyword-level) | N/A |
| performance_baselines | 168 | 76 | 2.7% |

### How Data Is Currently Fetched

The existing sync pipeline (`SearchTermsClient.fetch_search_terms()`) works as follows:

1. **Step 1**: Query `shopping_performance_view` for products with impressions in the last N days, grouped by campaign (`_fetch_campaign_products()`)
2. **Step 2**: Query `search_term_view` for search terms from Shopping campaigns, limited by `LIMIT {limit}` (default 1000)
3. **Step 3**: Join search terms to products via campaign_id (approximate association)
4. **Step 4**: Look up variant info from `variant_index` table
5. **Step 5**: Save to `search_queries` table, aggregate to `search_queries_by_master_sku`
6. **Step 6**: Optionally enrich with Keyword Planner metrics

**Key limitation**: The current approach fetches the top-1000 search terms across ALL Shopping campaigns globally. It does NOT fetch per-product search terms. This means high-impression products dominate, and low-traffic SKUs never appear.

### Google Ads API Resources Used

| Resource | Current Use | Notes |
|----------|-------------|-------|
| `search_term_view` | Yes (global top-1000) | Search terms that triggered Shopping ads |
| `shopping_performance_view` | Yes (product-campaign mapping) | Product-level metrics |
| `campaign` | Yes (Shopping campaign discovery) | Campaign filtering |
| Keyword Planner | Yes (enrichment) | Search volume, competition, CPC |

---

## 2. Google Ads API Constraints

### Data Retention
- **search_term_view**: Available for the **last 180 days** (6 months) from the Google Ads API. Older data is not accessible.
- **shopping_performance_view**: Available for approximately **2 years** of historical data.
- **Keyword Planner**: Returns 12-month average metrics (no date range limitation, but data updates monthly).

### Rate Limits & Quotas
- **Basic access (Standard)**: 15,000 operations/day, ~1,500 requests/day depending on query complexity
- **search_stream**: Each call counts as 1 operation regardless of result size
- **LIMIT clause**: Google Ads API supports up to ~100,000 rows per query via streaming
- **Keyword Planner**: More restrictive; ~100 keywords per GenerateKeywordHistoricalMetrics request, ~10 requests/minute
- **Concurrency**: Recommended max 10 concurrent requests per customer ID

### Key API Behavior
- `search_term_view` does NOT support filtering by `segments.product_item_id` alongside `search_term_view.search_term` (API limitation noted in code)
- `shopping_performance_view` DOES support filtering by `segments.product_item_id`
- Both support `segments.date` for date-range filtering
- `DURING LAST_N_DAYS` is a convenience; `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'` gives precise control

---

## 3. Backfill Strategy

### 3.1 Search Terms Backfill

#### The Core Problem

The current approach only captures 1,000 search terms globally. To get per-product data, we need a fundamentally different query strategy.

#### Recommended Approach: Campaign-Product-SearchTerm Join

Instead of querying `search_term_view` globally, we should:

1. **Get all products with impressions** from `shopping_performance_view` (we can get ALL products, not just top 1000)
2. **Get search terms per campaign + ad_group** from `search_term_view` (broader fetch, up to 50K)
3. **Use product-group-level data** to associate search terms with products

However, the Google Ads API has a fundamental limitation: `search_term_view` does not include `segments.product_item_id`. Search terms are associated at the campaign/ad_group level, not at the product level. The current code already works around this by joining via campaign_id.

#### Proposed Backfill Plan

**Phase 1: Expand search_term_view fetch (Days 1-2)**

Increase the `LIMIT` from 1,000 to 50,000 and run for multiple date windows:

```python
# Instead of one 30-day window with LIMIT 1000:
date_windows = [
    ("2025-08-15", "2025-09-14"),  # 6 months ago (if still in retention)
    ("2025-09-15", "2025-10-14"),
    ("2025-10-15", "2025-11-14"),
    ("2025-11-15", "2025-12-14"),
    ("2025-12-15", "2026-01-14"),
    ("2026-01-15", "2026-02-11"),
]
# For each window, fetch up to 50,000 search terms
```

**Estimated yield**: With LIMIT 50,000 across 6 windows, we could capture ~100K-300K unique (query, campaign) pairs, which should cover most active products.

**Phase 2: Product-level performance backfill (Days 2-4)**

Use `shopping_performance_view` which DOES support per-product queries:

```python
# Fetch ALL products with ANY impressions in last 180 days
query = """
    SELECT
        segments.product_item_id,
        segments.date,
        metrics.impressions,
        metrics.clicks,
        metrics.conversions,
        metrics.conversions_value,
        metrics.cost_micros
    FROM shopping_performance_view
    WHERE segments.date BETWEEN '{start}' AND '{end}'
        AND campaign.advertising_channel_type = 'SHOPPING'
        AND metrics.impressions > 0
    ORDER BY segments.product_item_id, segments.date
"""
# No LIMIT needed - stream all results
```

This will give us per-product daily performance for ALL products that had any Shopping ad impressions.

**Phase 3: Keyword Planner enrichment (Days 4-7)**

Batch-enrich all unique search terms with Keyword Planner data:

```python
# Get all unique query_text from search_queries
# Process in batches of 100 keywords
# Rate: ~10 batches/minute = 1,000 keywords/minute
# For 10K unique keywords: ~10 minutes
# For 50K unique keywords: ~50 minutes
```

### 3.2 Performance Data Backfill

#### Approach: Batch by Product ID

The `fetch_batch_product_performance()` function already supports multi-product queries. We should batch offer IDs.

```python
# From variant_index, get all gmc_offer_ids
# Batch into groups of 500 (IN clause limit)
# For each batch, query shopping_performance_view
# Date range: last 180 days (or 2 years for aggregated)
```

**Batching strategy**:
- 72,023 variants / 500 per batch = 145 API calls
- At ~2 seconds per call = ~5 minutes total
- BUT: many variants may have zero impressions

**Optimization**: First query to find which products have ANY data:

```sql
SELECT DISTINCT segments.product_item_id
FROM shopping_performance_view
WHERE segments.date DURING LAST_180_DAYS
    AND campaign.advertising_channel_type = 'SHOPPING'
    AND metrics.impressions > 0
```

Then only backfill products that actually have data.

---

## 4. Batching & Resumability Design

### 4.1 Enhanced Sync Job Schema

The current `search_query_sync_jobs` table needs additional fields for backfill tracking:

```sql
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    backfill_type text;  -- 'search_terms', 'performance', 'keyword_planner'
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    date_window_start date;
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    date_window_end date;
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    batch_index integer DEFAULT 0;
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    total_batches integer;
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    last_processed_offset text;  -- For resumability
ALTER TABLE search_query_sync_jobs ADD COLUMN IF NOT EXISTS
    parent_job_id uuid;  -- Link sub-jobs to parent backfill job
```

### 4.2 Backfill Job Structure

```
Parent Job: "Full Historical Backfill"
  |
  +-- Child Job 1: Search Terms (2025-08-15 to 2025-09-14)
  +-- Child Job 2: Search Terms (2025-09-15 to 2025-10-14)
  +-- Child Job 3: Search Terms (2025-10-15 to 2025-11-14)
  +-- ...
  +-- Child Job 7: Performance Backfill (batch 1/145)
  +-- Child Job 8: Performance Backfill (batch 2/145)
  +-- ...
  +-- Child Job 152: Keyword Planner Enrichment (batch 1/50)
  +-- ...
```

### 4.3 Resumability

Each child job tracks:
- `status`: pending/running/completed/failed
- `batch_index` + `total_batches`: progress tracking
- `last_processed_offset`: for search terms, the last row number processed; for performance, the last offer_id batch
- `error_message`: for debugging failures

**Resume logic**: On restart, query for child jobs with `status = 'running'` or `status = 'pending'`, and resume from `last_processed_offset`.

---

## 5. Backfill Script Design

### Recommended: Standalone Python Script

Rather than extending the existing sync endpoint (which is designed for periodic 30-day refreshes), create a dedicated backfill script.

**Location**: `scripts/backfill_google_ads_data.py`

```python
"""
Google Ads Historical Data Backfill Script.

Usage:
    python scripts/backfill_google_ads_data.py --phase search_terms
    python scripts/backfill_google_ads_data.py --phase performance
    python scripts/backfill_google_ads_data.py --phase keyword_planner
    python scripts/backfill_google_ads_data.py --phase all
    python scripts/backfill_google_ads_data.py --resume JOB_ID

Environment:
    source .venv/bin/activate
    set -a && source .env.vercel && set +a
"""
```

### Key Design Decisions

1. **Run locally, not on Cloud Run**: Backfill is a one-time operation. Running locally avoids container timeout issues and allows easy monitoring.

2. **Sequential date windows**: Process one 30-day window at a time to stay within API quotas and enable resumability.

3. **Upsert semantics**: The `search_queries` unique constraint `(query_text, gmc_offer_id, period_start, period_end)` means re-running a window is idempotent.

4. **Progress logging**: Print progress every 1,000 rows and update `search_query_sync_jobs` for dashboard visibility.

5. **Rate limiting**: Built-in delays between API calls (1-2 seconds for search_stream, 6 seconds between Keyword Planner batches).

---

## 6. Storage Estimates

### Search Terms

| Metric | Estimate | Notes |
|--------|----------|-------|
| Unique search terms (6 months) | ~10,000-50,000 | Based on Shopping campaign volume |
| Products with data | ~5,000-20,000 variants | Many variants share product_id |
| Rows per date window (30 days) | ~5,000-50,000 | With expanded LIMIT |
| Total rows (6 windows) | ~30,000-300,000 | Deduplicated |
| Row size (avg) | ~500 bytes | All columns populated |
| Total storage | ~15MB-150MB | Well within Supabase limits |

### Performance Data

| Metric | Estimate | Notes |
|--------|----------|-------|
| Products with impressions | ~5,000-15,000 | Many variants have zero traffic |
| Days of data | 180 | API retention limit |
| Daily rows per product | 1 | Per product per day |
| Total rows | ~900K-2.7M | Products x days |
| Row size (avg) | ~200 bytes | Simpler schema |
| Total storage | ~180MB-540MB | Manageable |

### Keyword Metrics

| Metric | Estimate | Notes |
|--------|----------|-------|
| Unique keywords | ~10,000-50,000 | From search_queries |
| Row size (avg) | ~300 bytes | Including monthly_searches JSONB |
| Total storage | ~3MB-15MB | Very small |

**Total estimated storage**: ~200MB-700MB for the full backfill. Supabase Free tier allows 500MB; Pro tier allows 8GB. This should fit comfortably.

---

## 7. Execution Timeline

### Day 1: Preparation
- [ ] Add backfill columns to `search_query_sync_jobs` (migration)
- [ ] Write the backfill script skeleton with CLI args, logging, resumability
- [ ] Test with a single 30-day window at LIMIT 100

### Day 2-3: Search Terms Backfill
- [ ] Run Phase 1: Expanded search_term_view fetch across 6 date windows
- [ ] Each window: ~2-5 minutes (API) + ~1 minute (DB upsert)
- [ ] Total: ~20-30 minutes for all search terms
- [ ] Run aggregation to `search_queries_by_master_sku`

### Day 3-4: Performance Backfill
- [ ] Phase 2: Product-level performance from `shopping_performance_view`
- [ ] Discovery query first (which products have data)
- [ ] Batch fetch for products with data
- [ ] Store in `performance_baselines` or new `performance_daily` table
- [ ] Total: ~30-60 minutes depending on data volume

### Day 5-6: Keyword Planner Enrichment
- [ ] Phase 3: Enrich all unique search terms
- [ ] Rate limited: ~1,000 keywords/minute
- [ ] Total: ~10-50 minutes depending on unique keyword count
- [ ] Update both `search_queries` and `keyword_metrics` tables

### Day 7: Validation & Cleanup
- [ ] Verify row counts and coverage percentages
- [ ] Check for data quality issues (NULL master_skus, missing variant mappings)
- [ ] Update dashboard queries if needed for new data volume
- [ ] Document final coverage numbers

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| API quota exceeded | Backfill paused mid-way | Resumability via job tracking; spread across days |
| search_term_view 180-day limit | Cannot get older data | Accept limitation; start collecting going forward |
| Campaign-to-product mapping is imprecise | Some search terms mapped to wrong products | Accept for now; note in data quality column |
| Many products have zero impressions | Less data than expected | Pre-filter with discovery query; document actual coverage |
| Large upserts slow down Supabase | Temporary performance impact | Batch upserts to 500 rows; run during low-traffic hours |
| Keyword Planner rate limits | Enrichment takes longer | Built-in delays; can spread across multiple days |

---

## 9. Recommendations

### Immediate (Backfill)

1. **Create a standalone backfill script** (`scripts/backfill_google_ads_data.py`) rather than extending the existing sync endpoint. The sync endpoint is designed for periodic 30-day refreshes; the backfill has different requirements (date windows, higher limits, resumability).

2. **Start with search terms** (Phase 1) as it provides the most value for content optimization.

3. **Use 30-day windows** for search_term_view queries. This keeps response sizes manageable and provides natural resumability checkpoints.

4. **Run locally** with `.env.vercel` credentials. No need to deploy the backfill code.

### Ongoing (Post-Backfill)

1. **Schedule weekly syncs** via Cloud Scheduler hitting the existing `/search-insights/sync` endpoint with `days=7, limit=5000`. This keeps data fresh without re-processing old data.

2. **Increase the default LIMIT** from 1,000 to 5,000 in the sync endpoint. The current 1,000 limit means we miss long-tail search terms.

3. **Add a performance sync endpoint** to the Cloud Run API for periodic performance data collection (daily/weekly snapshots).

4. **Consider partitioning** the `search_queries` table by `period_start` if row counts exceed 1M. This keeps queries fast for recent data while preserving historical records.

---

## 10. Alternative Approaches Considered

### Option A: Use Google Ads Scripts (Rejected)
Google Ads Scripts can access search term data but run in a different environment and have their own quota limits. The Python API client gives us more control and integrates directly with our pipeline.

### Option B: Use Google Ads Data Transfer to BigQuery (Deferred)
For truly large-scale historical analysis, BigQuery Data Transfer Service can automatically export Google Ads data. This would be a longer-term solution if we need daily granularity across 2+ years. For now, the direct API approach is sufficient.

### Option C: Extend Existing Sync Endpoint (Rejected)
The sync endpoint is designed for periodic refreshes. Adding backfill logic (date windows, resumability, higher limits) would complicate the code. A standalone script is cleaner and easier to monitor/debug.

---

## Appendix: Current Code Analysis

### SearchTermsClient Architecture

```
fetch_search_terms(days, limit)
  -> _fetch_campaign_products(days)     # shopping_performance_view by campaign
  -> search_term_view query             # global top-N by impressions
  -> get_variant_info(gmc_offer_id)     # variant_index lookup (cached)
  -> return list[dict]

save_search_terms_to_db(terms, period_start, period_end, sync_job_id)
  -> dedup by (query_text, gmc_offer_id)
  -> upsert to search_queries (on_conflict: query_text, gmc_offer_id, period_start, period_end)

aggregate_by_master_sku(period_start, period_end)
  -> read from search_queries
  -> group by (master_sku, query_text)
  -> upsert to search_queries_by_master_sku

enrich_with_keyword_metrics(period_start, period_end, batch_size=100)
  -> get unenriched queries (keyword_metrics_updated_at IS NULL)
  -> KeywordPlannerClient.get_historical_metrics(keywords)
  -> update search_queries + search_queries_by_master_sku
```

### fetch_batch_product_performance Architecture

```
fetch_batch_product_performance(offer_ids, start_date, end_date)
  -> builds IN clause for up to N offer_ids
  -> shopping_performance_view with product_item_id filter
  -> aggregates by offer_id with daily breakdown
```

### Sync Job Lifecycle

```
POST /search-insights/sync
  -> creates search_query_sync_jobs row (status: pending)
  -> spawns background thread (run_async_in_thread)
  -> process_sync_job():
      1. Update status -> running
      2. fetch_search_terms(days, limit)
      3. save_search_terms_to_db()
      4. aggregate_by_master_sku()
      5. enrich_with_keyword_metrics() (if requested)
      6. Update status -> completed
```
