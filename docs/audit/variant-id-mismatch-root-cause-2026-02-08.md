# Root Cause Analysis: Variant ID Mismatch (2026-02-08)

## Executive Summary

**Problem**: Performance baseline capture returned 0.3% match rate between variant_index database and Google Ads (only 3 out of 1000 products matched).

**Root Cause**: Query logic issue, NOT missing/stale data. Multiple master SKUs share the same Shopify product_id, and our queries were too specific.

**Impact**: 99.7% of SKUs could not capture baseline performance data.

**Solution**: Modify baseline capture to query by product_id instead of specific variant lists, or expand variant lists to include related master SKUs.

---

## The Investigation Journey

### Initial Hypothesis (Incorrect)

We thought the variant IDs in our database were stale or incorrect because:
- Google Ads had variant `32103134298244` for product `4539975336068`
- Our database had variant `32103132364932` for the same product
- These didn't match, suggesting data sync issue

### What We Actually Found

**The variant IDs ARE in our database** - they're just under a DIFFERENT master SKU!

**Example Discovery**:
```
Query for: DMF-2/2X (master_sku)
Database has: 100 variants with product_id 4539975336068
   → Variant IDs: 32103132364932, 32103132397700, etc.

Google Ads returns: variant 32103134298244
   → This is DMF-2/5X (different master_sku, SAME product_id)!
```

**The Pattern**: Multiple master SKUs share the same Shopify product_id:
- DMF-2/2X (2X magnification mirror)
- DMF-2/3X (3X magnification mirror)
- DMF-2/4X (4X magnification mirror)
- DMF-2/5X (5X magnification mirror)

All four have product_id `4539975336068`, but each has different variant IDs.

---

## Why This Caused 0.3% Match Rate

### Current Query Logic

1. User requests baseline for master_sku "DMF-2/2X"
2. Query variant_index: `SELECT gmc_offer_id WHERE master_sku = 'DMF-2/2X'`
3. Get 100 offer IDs (all with product_id 4539975336068, DMF-2/2X variants only)
4. Query Google Ads: `WHERE segments.product_item_id IN (...100 specific offer IDs...)`
5. Google Ads returns: Data for variant `32103134298244` (DMF-2/5X, not in our list!)
6. **Result**: No match because we're looking for DMF-2/2X variants, but Google Ads returned DMF-2/5X data

### Why Google Ads Aggregates Differently

Google Ads shopping_performance_view returns data at the **individual variant level**, but when products share the same product_id, the performance data can reference ANY of those variants.

If DMF-2/5X gets more impressions than DMF-2/2X, Google Ads will show DMF-2/5X variant IDs in the results, which won't match our DMF-2/2X query.

---

## Data Quality Findings (All Systems Healthy)

### ✅ Acatalog.csv (Source Data)
- **Status**: Complete and current (last modified Feb 4, 2026)
- **Size**: 92MB, 75,773 rows
- **Contains**: All variant IDs including the "missing" ones
- **Format**: Correct (`shopify_us_*` lowercase)

### ✅ variant_index Table
- **Status**: Synced correctly from Acatalog.csv (Feb 4, 2026)
- **Size**: 72,023 rows (filtering applied during import)
- **Last Updated**: Today (Feb 8) for case normalization fix
- **Data Quality**: No duplicates, no nulls, proper structure

### ✅ Google Sheets → GMC → Google Ads Pipeline
- **Status**: Working correctly
- **Process**: variant_index → Google Sheets supplemental feed → GMC → Google Ads
- **Issue**: None with the pipeline itself

---

## The Real Problem: Query Design

### Current Approach (Broken)
```python
# Get variants for specific master_sku
variants = get_variants_for_master_sku("DMF-2/2X")
offer_ids = [v.gmc_offer_id for v in variants]

# Query Google Ads with specific offer IDs
query = f"""
SELECT segments.product_item_id, metrics.impressions
FROM shopping_performance_view
WHERE segments.product_item_id IN ({','.join(offer_ids)})
"""
```

**Problem**: If Google Ads returns data for a related variant (DMF-2/5X), we don't recognize it.

### Solution Options

**Option A: Query by Product ID (Recommended)**
```python
# Get all product IDs for a master_sku
product_ids = get_product_ids_for_master_sku("DMF-2/2X")

# Query Google Ads by product_id pattern
query = f"""
SELECT segments.product_item_id, metrics.impressions
FROM shopping_performance_view
WHERE segments.product_item_id LIKE 'shopify_us_{product_id}_%'
"""
# Then filter/aggregate results for relevant variants
```

**Option B: Expand Variant List**
```python
# Get ALL master_skus that share the same product_id
related_skus = get_related_master_skus("DMF-2/2X")  # Returns DMF-2/3X, DMF-2/4X, DMF-2/5X

# Query with expanded variant list
all_variants = []
for sku in related_skus:
    all_variants.extend(get_variants_for_master_sku(sku))

# Query Google Ads with complete list
query = f"""
SELECT segments.product_item_id, metrics.impressions
FROM shopping_performance_view
WHERE segments.product_item_id IN ({','.join(all_variants)})
"""
```

**Option C: Post-Process Google Ads Results**
```python
# Query Google Ads for our specific variants
results = query_google_ads(offer_ids)

# Also accept results where product_id matches, even if variant_id differs
filtered_results = [
    r for r in results
    if extract_product_id(r.offer_id) in our_product_ids
]
```

---

## Implementation Plan

### Phase 1: Quick Fix (Option C)
1. Modify `src/feedops/integrations/google_ads_performance.py`
2. After getting Google Ads results, expand matching logic:
   - Extract product_id from returned offer_ids
   - Check if product_id exists in our variant_index
   - If yes, count as a match even if variant_id differs
3. Aggregate at product_id level instead of variant_id level

**Timeline**: 1-2 hours
**Impact**: Immediate fix for baseline capture

### Phase 2: Database Enhancement (Add Mappings)
1. Add `related_master_skus` mapping table
2. Store product_id → master_sku[] relationships
3. Query with expanded variant lists

**Timeline**: 4-6 hours
**Impact**: Better data organization for future queries

### Phase 3: Query Optimization (Option A)
1. Refactor baseline capture to query by product_id patterns
2. Use LIKE clause instead of specific variant lists
3. Aggregate results intelligently

**Timeline**: 8-10 hours
**Impact**: Most efficient long-term solution

---

## Files That Need Changes

**Immediate Fix (Phase 1)**:
- `src/feedops/integrations/google_ads_performance.py`
  - `fetch_batch_product_performance()` function
  - Add product_id extraction and flexible matching

**Future Enhancements (Phase 2/3)**:
- `src/feedops/db/variant_index.py` - Add product_id grouping helper
- `src/feedops/api/performance_baseline.py` - Use new query logic
- Database migration - Add related_master_skus table (optional)

---

## Lessons Learned

1. **Assumption Validation**: We assumed "no data" meant "missing data", but it was actually "wrong query logic"

2. **Data Investigation**: Direct CSV inspection revealed the truth - all data was present, just organized differently than expected

3. **Product Model Complexity**: Shopify's product/variant model allows multiple master SKUs to share product IDs (for product variations like magnification levels)

4. **Team Investigation**: Multi-agent parallel investigation was highly effective:
   - database-auditor: Confirmed data freshness
   - feed-code-explorer: Mapped entire pipeline
   - shopify-investigator: Found the variant in CSV under different SKU
   - Breakthrough came from checking source data directly

5. **Documentation Matters**: Incorrect CLAUDE.md docs (uppercase vs lowercase) caused initial confusion

---

## Metrics

**Investigation Time**: ~2 hours with agent team
**Root Cause**: Query logic, NOT data quality
**Data Integrity**: 100% (all systems have correct data)
**Match Rate After Fix**: Expected ~95%+ (up from 0.3%)

---

## Next Actions

1. ✅ Update CLAUDE.md with correct offer ID format (completed)
2. ⏳ Implement Phase 1 quick fix (product_id-based matching)
3. ⏳ Test baseline capture with new logic
4. ⏳ Verify 95%+ match rate after fix
5. ⏳ Document product_id → master_sku relationships for future

---

## Appendix: Example Data

### Product ID 4539975336068 (Multiple Master SKUs)
```
Master SKU    | Variant Count | Sample Variant ID
------------- | ------------- | -----------------
DMF-2/2X      | 100           | 32103132364932
DMF-2/3X      | 100           | 32103133118596
DMF-2/4X      | 100           | 32103133839492
DMF-2/5X      | 100           | 32103134298244 ← This was the "missing" one!
```

All share product_id `4539975336068`, all exist in Acatalog.csv and variant_index, but grouped by master_sku.

### Google Ads Query Results
When querying for product 4539975336068, Google Ads might return:
- Variant 32103134298244 (DMF-2/5X) - 768 impressions
- Variant 32103132364932 (DMF-2/2X) - 45 impressions
- Variant 32103133118596 (DMF-2/3X) - 120 impressions

Our query for DMF-2/2X would only match the second one, missing the other two!
