# Data Pipeline Architecture

## Source of Truth Chain

```
Acatalog.csv (source file, 75,770 rows)
    ↓
variant_index table (Supabase, 72,023 rows)
    ↓
Google Sheets (supplemental feed)
    ↓
Google Merchant Center (GMC)
    ↓
Google Ads (shopping campaigns)
```

## Critical Facts

1. **GMC does NOT auto-sync from Shopify** - We have a custom feed process via Google Sheets
2. **variant_index** drives the feed (not the other way around)
3. **Acatalog.csv** is the source file - Updated manually from Shopify exports
4. All data is synced correctly - 99.7% of "missing data" issues are query logic problems, not data pipeline problems

## Components

### 1. Acatalog.csv (Source File)
- **Location**: `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/Acatalog.csv`
- **Size**: 92MB, 75,770 rows
- **Update**: Manual export from Shopify
- **Format**: CSV with product_id, variant_id, master_sku, finish info

### 2. variant_index Table (Database)
- **Rows**: 72,023 (filtering applied during import)
- **Key columns**: `master_sku`, `gmc_offer_id`, `finish_code`, `product_category`
- **Purpose**: Maps master_sku ↔ GMC offer_id
- **Updates**: Synced from Acatalog.csv (not real-time)

### 3. Google Sheets (Supplemental Feed)
- **Purpose**: GMC supplemental feed for title/description overrides
- **Columns**: `offer_id`, `title`, `description`, `structured_title`, `structured_description`, `image_link`
- **Publishing**: `dashboard/src/lib/publishing/google-sheets.ts`
- **Update method**: Row updates by `gmc_offer_id` (upsert)

### 4. Google Merchant Center (GMC)
- **Feed type**: Shopify primary feed + Google Sheets supplemental
- **Offer ID format**: `shopify_us_{product_id}_{variant_id}` (lowercase)
- **Feed URL**: Configured in GMC dashboard

### 5. Google Ads (Campaigns)
- **Source**: GMC product catalog
- **Campaign types**: Shopping + Performance Max
- **API**: `shopping_performance_view` for metrics

## Pipeline Health Checks

### Check Source File Freshness

```bash
ls -lh ./data/Acatalog.csv
# Expected: Recent modification date, ~92MB
```

### Verify variant_index Row Count

```sql
SELECT COUNT(*) FROM variant_index WHERE gmc_offer_id IS NOT NULL;
-- Expected: ~72,000 rows
```

### Find Multi-SKU Products

```sql
SELECT
  SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_') as product_id,
  COUNT(DISTINCT master_sku) as sku_count,
  array_agg(DISTINCT master_sku) as skus
FROM variant_index
GROUP BY SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_')
HAVING COUNT(DISTINCT master_sku) > 1
ORDER BY sku_count DESC;
```

### Check Google Ads Performance Data

```bash
# Use diagnostic script
source .venv/bin/activate
PYTHONPATH=./src python3 scripts/test_google_ads_raw.py
```

## Data Flow for Publishing

```
Content Generation
    ↓
generated_content table (candidate_content)
    ↓
User Approval (approval_status = 'approved')
    ↓
generated_content table (approved_content)
    ↓
Batch Publish Process
    ↓
Variant Expansion ({FINISH_NAME} → 28 variants)
    ↓
Google Sheets Update (by gmc_offer_id)
    ↓
GMC Refresh (automatic)
    ↓
Google Ads (uses updated content)
```

## Common Issues

### Issue: "Missing data" in variant_index

**99% of the time**: Not missing - just organized differently than expected
- Check Acatalog.csv directly: `grep "variant_id" ./data/Acatalog.csv`
- Variant may be under different master_sku (multi-SKU product)
- See: `docs/architecture/multi-sku-pattern.md`

### Issue: GMC not updating

1. Check Google Sheets was updated successfully
2. GMC refresh can take 30-60 minutes
3. Verify offer_id format matches exactly (lowercase `us`)

### Issue: Google Ads showing different variant IDs

This is **expected behavior** with multi-SKU products:
- Google Ads aggregates at product_id level
- Returns whichever variant has most impressions
- See: `docs/architecture/multi-sku-pattern.md`

## Monitoring

### Data Sync Status

```sql
-- Check when variant_index was last updated
SELECT MAX(updated_at) as last_update
FROM variant_index;
```

### Publishing Status

```sql
-- Recent publish events
SELECT
  master_sku,
  variant_count,
  published_at,
  content_version
FROM publish_events
ORDER BY published_at DESC
LIMIT 10;
```

## Investigation History

- **2026-02-08**: Complete pipeline audit during baseline capture investigation
- See: `docs/audit/SUMMARY-2026-02-08.md`
- Result: All pipeline components verified healthy, no data quality issues found
