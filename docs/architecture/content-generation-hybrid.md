# Hybrid Content Generation for Multi-SKU Products

## Problem Statement

Products like DMF-2 have 4 master_skus that need unique content but share most product attributes:
- `DMF-2/2X` - 2X magnification
- `DMF-2/3X` - 3X magnification
- `DMF-2/4X` - 4X magnification
- `DMF-2/5X` - 5X magnification

**Challenge**: Each needs unique content reflecting specification differences (magnification level, use cases), but generating full content for each is expensive and risks inconsistency.

## Solution: Hybrid Approach

### Strategy

**Base SKU** (DMF-2/2X): Full generation using existing Cloud Run pipeline
- Uses evidence table, gold standard examples
- Generates complete titles, descriptions, finish_sentences
- Model: `gpt-5.2` (full)

**Variant SKUs** (DMF-2/3X, 2/4X, 2/5X): Focused adaptation from base content
- Reads base content from database
- Focused prompt: "Adapt this for ${variantSpec}"
- Updates specifications and use cases
- Maintains brand voice and structure
- Model: `gpt-5.2-variant-adaptation`

### Why Hybrid is Best

| Approach | Quality | Cost | Speed | Consistency |
|----------|---------|------|-------|-------------|
| Find/Replace | 60-70/100 | 1.0x | Instant | High (mechanical) |
| Full Generation | 75-85/100 | 4.0x | 12-16 min | Medium (can drift) |
| **Hybrid** ⭐ | **75-80/100** | **1.6x** | **4-6 min** | **High (ref-based)** |

**Cost Savings**: ~60% reduction for 4-SKU families
**Time Savings**: ~62% faster than full generation

## Implementation

### Files

**Detection**: `dashboard/src/lib/multi-sku-detection.ts`
- `detectMultiSkuFamilies()` - Find product families
- `getRelatedMasterSkus()` - Get all SKUs sharing same product_id
- `extractSpecDifference()` - Extract "2X" vs "5X" differences

**Generation**: `dashboard/src/lib/regeneration/core.ts`
- `regenerateContent()` - Full generation for base SKU
- `adaptVariantContent()` - Adaptation for variant SKUs

**API**: `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`
- Detects multi-SKU families automatically
- Generates base SKUs with full pipeline
- Adapts variant SKUs from base content
- Background processing with job tracking

**Testing**: `dashboard/scripts/test-hybrid-generation.ts`
- Test detection, generation, batch processing locally

## How to Use

### API Request

```bash
POST /api/sku-selection/generate-hybrid

{
  "skus": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X", "DMF-2/5X"],
  "options": {
    "titles": true,
    "descriptions": true,
    "platforms": ["google", "bing", "shopify"]
  }
}
```

### Response

```json
{
  "success": true,
  "job_id": "hybrid-1707404123-abc123",
  "status": "processing",
  "total_skus": 4,
  "multi_sku_families": 1,
  "strategy": {
    "base_skus": 1,      // Full generation
    "variant_skus": 3     // Adaptation
  }
}
```

### Check Status

```bash
GET /api/sku-selection/generate-hybrid?job_id=hybrid-1707404123-abc123
```

## Local Testing

```bash
cd dashboard

# Test detection only
tsx scripts/test-hybrid-generation.ts detect

# Test full generation (DMF-2/2X → DMF-2/3X)
tsx scripts/test-hybrid-generation.ts generate

# Test batch processing
tsx scripts/test-hybrid-generation.ts batch
```

## Prompt Templates

### Base SKU Prompt (Full Generation)

Uses existing prompt from `dashboard/src/lib/regeneration/prompts.ts`:
- System prompt with brand guidelines
- Evidence table with product data, search queries, competitor insights
- Gold standard examples
- Platform-specific context (Google/Bing/Shopify)

### Variant SKU Prompt (Adaptation)

```typescript
const adaptationPrompt = `
You are adapting product content for a variant specification.

BASE PRODUCT: ${baseSku}
BASE CONTENT:
${baseContent}

TARGET PRODUCT: ${variantSku}
KEY DIFFERENCE: Specification changes from ${baseSpec} to ${variantSpec}

TASK:
1. Adapt the content for the ${variantSpec} specification
2. Update numeric specs and measurements (${baseSpec} → ${variantSpec})
3. Adjust use case emphasis based on the specification difference
4. Maintain the SAME brand voice, structure, and key selling points
5. Keep similar length and format

CRITICAL:
- This is a specification variant of the same product family
- Maintain consistency with the base content's storytelling and tone
- Focus only on meaningful differences (specs, use cases)
- Do NOT reinvent the entire description - adapt strategically
`;
```

## Example Output

### Base SKU (DMF-2/2X) - Full Generation

**Title**:
```
{FINISH_NAME} 2X Magnification Bathroom Mirror - Premium Wall Mount Mirror with Crystal Clear Optics - Dotted Collection - Allied Brass
```

**Description**:
```
Transform your daily grooming routine with professional-grade 2X magnification.
Perfect for precise makeup application, skincare routines, and detailed grooming
tasks. Premium construction ensures distortion-free reflection for years...
```

### Variant SKU (DMF-2/5X) - Adapted

**Title**:
```
{FINISH_NAME} 5X Magnification Bathroom Mirror - Professional Detail Mirror with Ultra-Clear Optics - Dotted Collection - Allied Brass
```

**Description**:
```
Achieve professional-level precision with powerful 5X magnification designed
for detailed makeup artistry and intricate grooming work. Ideal for applying
eyeliner, tweezing, and skincare detail work where clarity is paramount...
```

**Changes**:
- Updated magnification level (2X → 5X)
- Adjusted use cases (general grooming → detailed professional work)
- Maintained same brand voice, structure, collection name

## Performance Metrics (Expected)

### DMF-2 Family (4 SKUs)

**Without Hybrid**:
- 4 full generations
- Cost: 4x
- Time: 12-16 minutes
- Quality: 75-85/100
- Consistency: Medium (voice can drift)

**With Hybrid**:
- 1 full generation + 3 adaptations
- Cost: 1.6x (~60% savings)
- Time: 4-6 minutes (~62% faster)
- Quality: 75-80/100
- Consistency: High (reference-based)

### Larger Families

For products with more variants (e.g., 8 SKUs):
- Cost savings: ~70%
- Time savings: ~75%
- Consistency improvement even more pronounced

## Database Tracking

**Content table** (`generated_content`):
- Base SKU: `generation_model = "gpt-5.2"`
- Variant SKU: `generation_model = "gpt-5.2-variant-adaptation"`

**History table** (`regeneration_history`):
- Base SKU: `mode = "full"`
- Variant SKU: `mode = "variant-adaptation"`

## Backfilling Missing Content

### Find Multi-SKU Products Without Content

```sql
-- Find all multi-SKU families
SELECT
  SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_') as product_id,
  array_agg(DISTINCT master_sku ORDER BY master_sku) as skus,
  COUNT(DISTINCT master_sku) as sku_count
FROM variant_index
GROUP BY SUBSTRING(gmc_offer_id FROM 'shopify_us_(\d+)_')
HAVING COUNT(DISTINCT master_sku) > 1
ORDER BY sku_count DESC;

-- Get SKUs without generated content
SELECT DISTINCT vi.master_sku
FROM variant_index vi
LEFT JOIN generated_content gc ON vi.master_sku = gc.master_sku
WHERE gc.id IS NULL
ORDER BY vi.master_sku;
```

### Run Backfill

```bash
# Generate content for missing SKUs
curl -X POST http://localhost:3000/api/sku-selection/generate-hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "skus": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X", "DMF-2/5X"],
    "options": {
      "titles": true,
      "descriptions": true,
      "platforms": ["google", "bing", "shopify"]
    }
  }'
```

## Future Enhancements

### Python Implementation (Recommended for Production)

Current implementation is dashboard-side (TypeScript). For large-scale production use:

1. **Port to Cloud Run** (`src/feedops/api/main.py`)
   - Better for large batches (50+ SKUs)
   - Async processing, better scalability
   - Single source of truth

2. **Smart Routing**
   - Small batches (<10 SKUs): Dashboard endpoint
   - Large batches (>10 SKUs): Cloud Run endpoint

See: `docs/audit/hybrid-generation-implementation-2026-02-08.md`

## Investigation History

- **2026-02-08**: Implemented hybrid approach
- **Problem**: Only base SKUs had content, variants missing
- **Solution**: Variant adaptation with 60% cost savings
- See: `docs/audit/hybrid-generation-implementation-2026-02-08.md`
