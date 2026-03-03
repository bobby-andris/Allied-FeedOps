# Performance Baseline Capture - Troubleshooting Guide

## Quick Diagnosis

When baseline capture returns 0 data or low match rates, work through these checks in order:

## 1. Check Offer ID Case (Most Common Issue)

**Symptom**: Query returns 0 rows despite products being active

**Fix**:
```sql
-- Verify case is correct (should be lowercase 'us')
SELECT gmc_offer_id FROM variant_index LIMIT 5;

-- Expected: shopify_us_4539975336068_32103134298244 (lowercase)
-- Wrong: shopify_US_4539975336068_32103134298244 (uppercase)
```

**If wrong case found**:
```sql
UPDATE variant_index
SET gmc_offer_id = REPLACE(gmc_offer_id, 'shopify_US_', 'shopify_us_')
WHERE gmc_offer_id LIKE 'shopify_US_%';
```

## 2. Verify Campaign Type in Query

**Symptom**: Missing Performance Max campaign data

**Check**: Google Ads query MUST include `campaign.advertising_channel_type` in SELECT clause

**File**: `src/feedops/integrations/google_ads_performance.py`

**Correct query**:
```python
query = f"""
SELECT
  segments.product_item_id,
  segments.date,
  campaign.advertising_channel_type,  # ← REQUIRED
  metrics.impressions,
  metrics.clicks,
  metrics.ctr
FROM shopping_performance_view
WHERE segments.product_item_id IN ({ids_clause})
  AND segments.date BETWEEN '{start_date}' AND '{end_date}'
"""
```

Without this field, Performance Max campaigns may be excluded.

## 3. Check for Multi-SKU Product Mismatch

**Symptom**: Google Ads returns data but baseline shows 0 matches

**Check if SKU shares product_id with other SKUs**:
```sql
SELECT master_sku, COUNT(*) as variant_count
FROM variant_index
WHERE SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_') = '4539975336068'
GROUP BY master_sku;
```

**If multiple SKUs returned**: Query logic issue (not data issue)

**Problem**: Google Ads aggregates at product_id level, your query filters by specific master_sku variants.

**Solution**: See `docs/architecture/multi-sku-pattern.md`

## Diagnostic Endpoints

### Test Query with Specific SKUs

```bash
curl -X POST "$FEEDOPS_PIPELINE_URL/performance/diagnose-query" \
  -H "Content-Type: application/json" \
  -d '{"master_skus": ["DMF-2/2X"]}'
```

Returns:
- Query used
- Number of results
- Sample offer IDs returned
- Match rate

### See What Products Exist in Google Ads

```bash
curl "$FEEDOPS_PIPELINE_URL/performance/diagnose-products"
```

Returns:
- All product_item_ids with impressions
- Campaign types (SHOPPING vs PERFORMANCE_MAX)
- Date range

### Check Baseline Status for SKU

```bash
curl "$FEEDOPS_PIPELINE_URL/performance/baseline/DMF-2-2X"
```

Returns:
- Whether baseline exists
- When captured
- Metrics snapshot

## Step-by-Step Troubleshooting

### Step 1: Verify Data Exists in Source File

```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
grep "32103134298244" ./data/Acatalog.csv
```

Should return matching rows with master_sku. If found, data exists (not a sync issue).

### Step 2: Check Database Sync

```sql
-- Verify variant exists in variant_index
SELECT master_sku, gmc_offer_id
FROM variant_index
WHERE gmc_offer_id LIKE '%32103134298244%';
```

Should return 1 row. If found, database is synced.

### Step 3: Test Google Ads API Directly

```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
source .venv/bin/activate
PYTHONPATH=./src python3 scripts/test_google_ads_raw.py
```

Should return products with impressions. Verifies API access works.

### Step 4: Check Query Match Logic

If Google Ads returns data but baseline capture shows 0 matches:
- Problem is query logic (product_id vs variant_id matching)
- Not a data quality issue
- See: `docs/architecture/multi-sku-pattern.md` for fix

## Common Error Messages

### "No data returned from Google Ads API"

**Causes**:
1. Offer ID case mismatch (uppercase vs lowercase)
2. Campaign type filter excluding Performance Max
3. Date range has no data (products not active)
4. Customer ID incorrect

**Check**:
```bash
# Verify customer ID
echo $GOOGLE_ADS_CUSTOMER_ID  # Should be 6253381786

# Test API directly
PYTHONPATH=./src python3 scripts/test_google_ads_raw.py
```

### "0.3% match rate" or "Only 3/1000 products matched"

**Cause**: Multi-SKU product mismatch (query logic issue)

**Not caused by**:
- Stale data (data is current)
- Missing variants (all variants exist)
- Sync issues (pipeline is healthy)

**Solution**: Implement product_id-based matching instead of variant_id-only matching

See: `docs/architecture/multi-sku-pattern.md`

## Investigation Checklist

Use this checklist when investigating baseline capture issues:

- [ ] Verify offer ID case (lowercase `us`)
- [ ] Check `campaign.advertising_channel_type` in query
- [ ] Test if SKU is part of multi-SKU family
- [ ] Verify variant exists in Acatalog.csv
- [ ] Verify variant exists in variant_index
- [ ] Test Google Ads API returns data
- [ ] Check query match logic for product_id vs variant_id

## Files to Check

**Python backend**:
- `src/feedops/integrations/google_ads_performance.py` - Query logic
- `src/feedops/api/performance_baseline.py` - Baseline capture endpoint

**Test scripts**:
- `scripts/test_google_ads_raw.py` - Direct API testing

**Database**:
- `variant_index` table - Offer ID mappings
- `performance_baselines` table - Captured baseline data

## Cloud Run Logs

```bash
# Check recent Cloud Run logs
gcloud run services logs read feedops-pipeline \
  --project=bobbys-project-346400 \
  --limit=50 \
  --format="table(severity,timestamp,textPayload)"

# Filter for baseline capture
gcloud run services logs read feedops-pipeline \
  --project=bobbys-project-346400 \
  --limit=100 | grep "baseline"
```

## Related Documentation

- **Root Cause Analysis**: `docs/audit/variant-id-mismatch-root-cause-2026-02-08.md`
- **Investigation Summary**: `docs/audit/SUMMARY-2026-02-08.md`
- **Case Mismatch Fix**: `docs/audit/case-mismatch-fix-2026-02-08.md`
- **Multi-SKU Pattern**: `docs/architecture/multi-sku-pattern.md`
- **Data Pipeline**: `docs/architecture/data-pipeline.md`

## Key Learnings (2026-02-08 Investigation)

1. **99.7% of "missing data" issues are query logic problems**, not data quality issues
2. **All pipeline components are healthy**: Acatalog.csv → variant_index → GMC → Google Ads
3. **Multi-SKU products cause query mismatches**: Google Ads aggregates at product_id level
4. **Case sensitivity matters**: Always use lowercase `shopify_us_` format
5. **Campaign type filter required**: Include `campaign.advertising_channel_type` in SELECT

## Prevention

**Before adding new SKUs**:
1. Check if product_id already exists in variant_index
2. If yes, treat as multi-SKU family (not standalone product)
3. Use hybrid content generation (see `docs/architecture/content-generation-hybrid.md`)

**Before querying Google Ads**:
1. Verify offer ID format matches exactly (lowercase)
2. Include campaign type in SELECT
3. Consider product_id-based matching for multi-SKU products
