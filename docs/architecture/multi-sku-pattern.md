# Multi-SKU Product Pattern

## Overview

Multiple master_skus can share the same Shopify product_id. This is common for product variants with specification differences (magnification levels, capacities, sizes, etc.).

## Example: DMF-2 (Magnifying Mirror) Family

**Product ID**: `4539975336068` (shared across all)

**Master SKUs**:
- `DMF-2/2X` - 2X magnification (100 variants)
- `DMF-2/3X` - 3X magnification (100 variants)
- `DMF-2/4X` - 4X magnification (100 variants)
- `DMF-2/5X` - 5X magnification (100 variants)

## Impact on Queries

### The Problem

Google Ads aggregates performance at **product_id level**, but we query by specific **master_sku variants**.

### Why This Causes Mismatches

1. Query requests baseline for `DMF-2/2X` → gets 100 variant offer IDs
2. Google Ads query returns data for variant `32103134298244` (from DMF-2/5X)
3. Our code only looks for DMF-2/2X variants in results
4. **Result**: No match (0.3% match rate before fix)

### Solution: Product-ID Based Matching

```python
def extract_product_id(offer_id: str) -> str:
    """
    Extract product_id from offer_id.
    shopify_us_4539975336068_32103134298244 → 4539975336068
    """
    parts = offer_id.split('_')
    return parts[2] if len(parts) >= 4 else ""

# Accept matches where product_id matches (not just variant_id)
matched_results = [
    r for r in results
    if extract_product_id(r.offer_id) in our_product_ids
]
```

### Alternative: Expand Variant Lists

Query with all related variants:
- Detect related master_skus via shared product_id
- Query with all related variants (400 instead of 100)
- More API overhead but guaranteed coverage

## Impact on Content Generation

### The Challenge

Each master_sku needs **unique content** reflecting its specification differences.

**Example**: `DMF-2/2X` vs `DMF-2/5X`
- Same product family (magnifying mirror)
- Different magnification levels (2X vs 5X)
- Different use cases (general grooming vs detailed work)
- **Cannot** use find/replace - needs semantic understanding

### Solution: Hybrid Content Generation

See `docs/architecture/content-generation-hybrid.md` for implementation details.

**Quick summary**:
- **Base SKU** (DMF-2/2X): Full generation using existing pipeline
- **Variant SKUs** (2/3X, 2/4X, 2/5X): Adaptation from base content
- **Result**: 60% cost savings, maintains consistency

## Detection Queries

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

### Get Related SKUs for a Product

```sql
-- Example: Find all SKUs for DMF-2 family
SELECT DISTINCT master_sku
FROM variant_index
WHERE gmc_offer_id LIKE 'shopify_us_4539975336068_%'
ORDER BY master_sku;
```

## Implementation

**Multi-SKU Detection**: `dashboard/src/lib/multi-sku-detection.ts`
- `detectMultiSkuFamilies()` - Find product families
- `getRelatedMasterSkus()` - Get all SKUs sharing same product_id
- `extractSpecDifference()` - Extract "2X" vs "5X" differences

**Hybrid Generation**: `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`
- Detects multi-SKU families automatically
- Full generation for base SKUs
- Adaptation for variant SKUs

## Investigation History

- **2026-02-08**: Root cause discovered during baseline capture investigation
- See: `docs/audit/variant-id-mismatch-root-cause-2026-02-08.md`
- See: `docs/audit/SUMMARY-2026-02-08.md`
