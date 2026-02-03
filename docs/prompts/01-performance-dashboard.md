# Task: Implement Live Performance Dashboard

## Objective
Replace the hardcoded placeholder data in the Performance page with real data from Google Ads and Google Analytics APIs.

## Current State
- Performance page exists at `dashboard/src/app/(dashboard)/performance/page.tsx`
- Page has placeholder/mock data for SKU 1051
- Environment variables are configured in Vercel:
  - `GOOGLE_ADS_*` (6 variables for Google Ads API)
  - `GOOGLE_SERVICE_ACCOUNT_KEY` (base64 encoded for GA4)
  - `GOOGLE_PROJECT_ID`

## Files to Modify/Create
1. `dashboard/src/app/api/performance/route.ts` - NEW API route for fetching performance data
2. `dashboard/src/app/(dashboard)/performance/page.tsx` - Update to fetch real data

## Requirements

### 1. Create Performance API Route (`/api/performance`)

The API should:
- Accept query params: `sku` (optional), `platform` (optional), `dateRange` (7d/30d/90d)
- Fetch performance metrics from Google Ads for Shopping campaigns
- Return baseline vs current metrics comparison

**Google Ads Query Pattern** (from existing Python CLI):
```python
# Offer ID format: shopify_us_{shopify_product_id}_{variant_id}
# Query pattern: segments.product_item_id LIKE '%{shopify_product_id}%'
```

**Metrics to fetch**:
- Impressions
- Clicks
- CTR (calculated)
- Conversions (from conversions_value or conversions)
- CVR (calculated)
- Cost
- ROAS (calculated)

### 2. Database Tables to Query

From Supabase:
- `performance_baselines` - Pre-optimization baseline metrics
- `performance_snapshots` - Post-publish metrics (if populated)
- `publish_events` - To know when SKUs were published (to calculate baseline vs post period)

### 3. Google Ads API Integration

Use the google-ads-api npm package or make direct REST calls.

**Environment variables available**:
```
GOOGLE_ADS_DEVELOPER_TOKEN
GOOGLE_ADS_CUSTOMER_ID=6253381786
GOOGLE_ADS_LOGIN_CUSTOMER_ID=7338022535
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
```

**GAQL Query example**:
```sql
SELECT
  segments.product_item_id,
  segments.date,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value
FROM shopping_performance_view
WHERE segments.date BETWEEN '2026-01-01' AND '2026-01-31'
  AND segments.product_item_id LIKE '%4545063682180%'
```

### 4. Update Performance Page

- Convert to client component or use server actions for data fetching
- Add loading states
- Add error handling for API failures
- Implement date range selector functionality
- Add refresh button functionality
- Show "No data" state when no published SKUs

## Reference Files
- `src/feedops/cli/main.py` - Existing Python CLI with Google Ads integration patterns
- `CLAUDE.md` - Contains Google Ads customer ID and offer ID format
- `.env.vercel` - Environment variable names

## Success Criteria
1. Performance page loads real data from Google Ads
2. Baseline vs current comparison works for published SKUs
3. Date range selector filters data correctly
4. Page handles errors gracefully (API failures, no data)
5. Works on Vercel deployment (not just localhost)

## Notes
- Customer ID: 6253381786 (Allied Brass Google Ads account)
- Only SKU 1051 has been published so far (Feb 3, 2026) but it was reverted
- Us the google ads mcp server and context7 mcp server to become an expert on how 
- Shopify Product ID for 1051: 4545063682180
