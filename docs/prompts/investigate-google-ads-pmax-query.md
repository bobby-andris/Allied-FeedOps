# Investigation Prompt: Google Ads Performance Max Query Issue

## ✅ RESOLVED (2026-02-08)

**Root Cause**: Query was missing `campaign.advertising_channel_type` in SELECT clause, which prevented Performance Max campaign data from being included.

**Fix**: Added `campaign.advertising_channel_type` to SELECT clause in both `_fetch_performance_via_api` and `fetch_batch_product_performance` functions. No WHERE clause filter needed - query now returns data from ALL campaign types (Shopping + Performance Max).

**Commit**: See git history for implementation details.

---

## Problem Summary (Original)

The `/performance/capture-baseline` endpoint in Cloud Run is successfully calling the Google Ads API but returning "No performance data found" for ~56 out of 60 review SKUs. Only 4 SKUs in the database have baseline data, but all products are enabled in either Shopping or Performance Max (pmax) campaigns.

**Critical finding**: The query uses `shopping_performance_view` which may not include Performance Max campaign data.

## What's Already Working

✅ `/performance/capture-baseline` endpoint implemented and deployed to Cloud Run
✅ Google Ads API authentication working (loads from environment variables)
✅ Endpoint successfully calls `fetch_batch_product_performance()` with GMC offer IDs
✅ No authentication errors, no API errors
✅ Query syntax is valid (returns results for 4 SKUs that have Shopping campaign data)

## The Query in Question

**File**: `src/feedops/integrations/google_ads_performance.py` (lines 329-344)

```python
query = f"""
SELECT
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_micros
FROM shopping_performance_view
WHERE
  segments.product_item_id IN ({ids_clause})
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
ORDER BY segments.product_item_id, segments.date
"""
```

**Issue**: `shopping_performance_view` may only return traditional Shopping campaign data, not Performance Max campaigns.

## Investigation Tasks

### 1. Use Context7 MCP to Research Google Ads API
**Goal**: Determine how to query Performance Max product performance

Search queries to try:
- "Google Ads API Performance Max product performance"
- "shopping_performance_view Performance Max campaigns"
- "Google Ads API pmax product level metrics"
- "Google Ads API product_item_id Performance Max"

### 2. Key Questions to Answer
- Does `shopping_performance_view` include Performance Max data?
- Is there a separate view for Performance Max campaigns?
- Do we need to query `campaign.advertising_channel_type = 'PERFORMANCE_MAX'` separately?
- What's the correct resource/view for product-level Performance Max metrics?

### 3. Test SKUs to Verify
Review SKUs with no data (should have pmax or shopping data):
- DMF-2/2X
- WP-2/16-GAL
- 920D-6 (has old baseline data but not current 30-day data)
- 1051 (has old baseline data but not current 30-day data)

## Relevant Files

### Core Implementation
- `src/feedops/api/performance_baseline.py` - Baseline capture endpoint
- `src/feedops/integrations/google_ads_performance.py` - Query logic (needs fix)

### Database
- `performance_baselines` table - Only 4 SKUs have data (should be ~60)
- `variant_index` table - Maps master_sku to gmc_offer_id (GMC offer ID format)

### Testing
```bash
# Test endpoint (should return data for all review SKUs)
curl -X POST https://feedops-pipeline-623866089882.us-east1.run.app/performance/capture-baseline \
  -H "Content-Type: application/json" \
  -d '{"master_skus": ["DMF-2/2X", "WP-2/16-GAL", "920D-6"]}'
```

## Expected Outcome

After fixing the query:
- All ~60 review SKUs should have baseline data captured
- Both Shopping and Performance Max campaign metrics should be included
- The query should work for both campaign types

## GMC Offer ID Format

GMC offer IDs use this format: `shopify_US_{product_id}_{variant_id}` (uppercase US)

Example: `shopify_US_7721863643362_42804912849122`

## Google Ads API Context

- Customer ID: `6253381786`
- All products enabled in Shopping OR Performance Max campaigns
- Need product-level metrics (not campaign-level)
- Need to filter by `product_item_id` (GMC offer ID)

## Success Criteria

✅ Query returns data for all review SKUs (not just 4)
✅ Works for both Shopping and Performance Max campaigns
✅ Endpoint successfully populates `performance_baselines` table with 60+ SKUs
✅ No changes needed to endpoint logic (only query modification)

## Starting Point

Use Context7 MCP to look up Google Ads API documentation first, then modify the query in `google_ads_performance.py` based on findings.
