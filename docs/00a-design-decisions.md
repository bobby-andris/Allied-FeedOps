# Allied FeedOps: Design Decisions

**Status**: FROZEN  
**Date**: 2026-01-23  
**Author**: AI Assistant + Human Review

---

## Executive Summary

FeedOps is a Python-based system to optimize product titles and descriptions at the parent SKU level using real performance data and strict factual verification. This document captures the architectural decisions made during the brainstorming phase.

---

## Decision Summary

| Decision Area | Choice | Rationale |
|---------------|--------|-----------|
| Language | Python | User preference, Pandas for CSV |
| Source of Truth | CSV-primary | Complete offline dataset, no API rate limits for MVP |
| Merchant Center Update | Hybrid (preview → Content API) | Safety + automation balance |
| LLM Provider | OpenAI primary, Gemini fallback | Both keys available |
| Shopify Access | Direct API | Tokens configured |
| Persistence | SQLite for MVP | Local-first, migrate to Supabase later |

---

## A) Source-of-Truth Mapping Strategy

**Decision**: CSV-primary with cross-platform ID mapping

### Data Sources

| Source | Purpose | Access Method |
|--------|---------|---------------|
| Product Catalog CSV | Canonical product attributes | Local file read |
| Shopify Admin API | Live inventory, metafields | REST/GraphQL API |
| Google Merchant Center | Feed status, disapprovals | Content API |
| Google Ads | Performance metrics | GAQL via MCP |
| Google Analytics | Conversion data | GA4 API via MCP |

### Cross-Platform ID Mapping

The CSV `GMCID` column contains the Shopify-based Merchant Center ID:

```
shopify_US_{ShopifyProductID}_{ShopifyVariantID}
```

Example: `shopify_US_4542872518788_32118222192772`

**Mapping table:**

| System | Identifier Field | Example |
|--------|------------------|---------|
| Internal | `MasterSKU` | `1031/18` |
| Internal | `OPTION SKU` | `1031/18-ABR` |
| Shopify | Product ID | `4542872518788` |
| Shopify | Variant ID | `32118222192772` |
| Merchant Center | `item_id` | `shopify_US_4542872518788_32118222192772` |
| Merchant Center | `item_group_id` | `4542872518788` (Shopify Product ID) |
| Amazon | ASIN | `B0031C2B60` |
| UPC/GTIN | Barcode | `13895759595` |

### Conflict Resolution

Priority order (first non-null wins):

1. Product Catalog CSV (canonical for specs)
2. Shopify metafields (for extended attributes)
3. Merchant Center (for feed status only)

**Rule**: CSV values are never overwritten by external sources. External sources inform phrasing/keywords but cannot introduce new facts.

---

## B) Merchant Center Update Strategy

**Decision**: Hybrid approach — preview JSON, then Content API push

### MVP (Phase 1)

1. Generate optimized content
2. Output preview JSON to `exports/merchant-center-patch-{SKU}.json`
3. Human reviews and approves
4. Manual supplemental feed upload OR approved Content API push

### Production (Phase 2)

1. Generate optimized content
2. Output preview JSON
3. Automated approval gate (quality score ≥80%, no new facts)
4. Content API PATCH via `products.update`
5. Automatic rollback if disapproval detected within 24h

### Rollback Strategy

Store previous values before any update:

```json
{
  "sku": "1031/18-ABR",
  "gmc_id": "shopify_US_4542452695172_32116080246916",
  "timestamp": "2026-01-23T10:00:00Z",
  "previous": {
    "title": "Skyline Collection 18 Inch Towel Bar",
    "description": "This stylish contemporary..."
  },
  "updated": {
    "title": "Allied Brass 18-Inch Towel Bar | Solid Brass | Antique Brass | Wall Mount",
    "description": "Crafted from solid brass..."
  }
}
```

Rollback = PATCH with `previous` values.

---

## C) LLM Provider Strategy

**Decision**: Provider-agnostic interface with zod-style validation and repair loop

### Provider Priority

1. **Primary**: OpenAI GPT-4o (structured outputs, JSON mode)
2. **Fallback**: Google Gemini (if OpenAI fails/rate limited)

### JSON Schema Enforcement

```python
# Pseudo-schema for candidate output
CandidateSchema = {
    "title": str,  # max 150 chars
    "description": str,  # min 500 chars recommended
    "claims": [
        {
            "claim": str,
            "source_field": str,
            "source_value": str
        }
    ],
    "self_score": {
        "specificity": int,  # 0-10
        "benefit_coverage": int,
        "keyword_inclusion": int,
        "format_adherence": int,
        "brand_voice": int,
        "factual_accuracy": int
    }
}
```

### Retry/Repair Loop

```
1. Call LLM with structured output request
2. Parse response as JSON
3. Validate against schema
4. IF validation fails:
   a. Extract error message
   b. Re-prompt with: "Fix this JSON error: {error}"
   c. Retry up to 3 times
5. IF still invalid after 3 retries: fail with audit log
```

### Prompt Template Structure

```
SYSTEM: You are a product feed optimization specialist...

EVIDENCE TABLE:
| Field | Value | Source |
|-------|-------|--------|
| MasterSKU | 1031/18 | CSV |
| Category | Towel Bars | CSV |
| Material | Brass | CSV |
| ...

CONSTRAINTS:
- Title: max 150 chars, first 70 chars critical
- Description: min 500 chars, benefit-first opening
- ONLY use facts from the evidence table
- NO invented specifications

RUBRIC (self-score each 0-10):
1. Specificity: specific claims / total claims
2. Benefit Coverage: benefit in first 150 chars
3. Keyword Inclusion: brand + type + size in title
4. Format Adherence: character limits met
5. Brand Voice: premium, no superlatives
6. Factual Accuracy: all claims verified

OUTPUT FORMAT:
{JSON schema}
```

---

## D) Batch Strategy

**Decision**: Progressive batches with explicit approval gates

### Progression

| Stage | Scope | Approval |
|-------|-------|----------|
| 1 | Single SKU dry-run | Automatic (no write) |
| 2 | 10 SKUs | Human review |
| 3 | 100 SKUs | Human spot-check (10%) |
| 4 | Full catalog | Automated with circuit breaker |

### Circuit Breaker (Stage 4)

Halt processing if:
- Error rate > 5% in last 100 items
- Quality score average < 75% in last 50 items
- Any Merchant Center disapproval detected

### Audit Logging

Every optimization logged to SQLite:

```sql
CREATE TABLE optimization_runs (
    id INTEGER PRIMARY KEY,
    master_sku TEXT,
    variant_sku TEXT,
    timestamp TEXT,
    llm_provider TEXT,
    llm_model TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    quality_score REAL,
    status TEXT,  -- 'success', 'failed', 'rejected'
    error_message TEXT
);
```

---

## E) Prompting Strategy

**Decision**: Evidence table injection with self-verification

### Evidence Table Format

The prompt includes a structured table of ALL available facts:

```markdown
## Available Product Data

| Attribute | Value | Source |
|-----------|-------|--------|
| MasterSKU | 1031/18 | catalog_csv.MasterSKU |
| Title | Skyline Collection 18 Inch Towel Bar | catalog_csv.Title |
| Category | Towel Bars | catalog_csv.Category |
| Collection | Skyline | catalog_csv.Collection |
| Material | Brass | catalog_csv.Material |
| Finish | Antique Brass | catalog_csv.Finish |
| Length | 20.8 | catalog_csv.Length |
| Mounting Type | Wall mount | catalog_csv.Mounting type |
| Weight Capacity | 10 | catalog_csv.Weight capacity |
| Included | Towel bar, mounting plates and all installation hardware. | catalog_csv.Included |
```

### Claim Verification Requirement

Output must include explicit claim→source mappings:

```json
{
  "claims": [
    {
      "claim": "18-inch length",
      "source_field": "catalog_csv.Length",
      "source_value": "20.8"
    },
    {
      "claim": "solid brass construction",
      "source_field": "catalog_csv.Material",
      "source_value": "Brass"
    }
  ]
}
```

**Verification rule**: If `source_field` is empty or value doesn't match, claim is rejected.

---

## CSV Column Mapping

### Actual CSV Columns → FeedOps Model

| CSV Column | Model Field | Type | Notes |
|------------|-------------|------|-------|
| `MasterSKU` | `master_sku` | str | Parent product ID |
| `OPTION SKU` | `option_sku` | str | Variant ID |
| `CoreSKU` | `core_sku` | str | Internal reference |
| `UPC` | `upc` | str | Barcode |
| `GTIN` | `gtin` | str | Global Trade Item Number |
| `GMCID` | `gmc_id` | str | Contains Shopify IDs |
| `Amazon ASIN` | `amazon_asin` | str | Amazon identifier |
| `Finish` | `finish` | str | Full finish name |
| `Finish Code` | `finish_code` | str | Short code (ABR, PC, etc.) |
| `Position` | `position` | int | Sort order |
| `Category` | `category` | str | Product category |
| `Collection` | `collection` | str | Collection name |
| `Title` | `current_title` | str | Current title |
| `List` | `list_price` | Decimal | MSRP |
| `Wholesale` | `wholesale_price` | Decimal | Wholesale price |
| `Map` | `map_price` | Decimal | MAP price |
| `Narraive Copy` | `current_description` | str | Current description (typo in source) |
| `Bullet 1` | `bullet_1` | str | Feature bullet |
| `Bullet 2` | `bullet_2` | str | Feature bullet |
| `Bullet 3` | `bullet_3` | str | Feature bullet |
| `Bullet 4` | `bullet_4` | str | Feature bullet |
| `Bullet 5` | `bullet_5` | str | Feature bullet |
| `Bullet 6` | `bullet_6` | str | Feature bullet |
| `Length` (first) | `product_length` | float | Product dimension |
| `Height` (first) | `product_height` | float | Product dimension |
| `Width` (first) | `product_width` | float | Product dimension |
| `Projection` | `projection` | float | Wall projection |
| `Weight` (first) | `product_weight` | float | Product weight |
| `Length` (second) | `shipping_length` | float | Shipping box dimension |
| `Height` (second) | `shipping_height` | float | Shipping box dimension |
| `Width` (second) | `shipping_width` | float | Shipping box dimension |
| `Weight` (second) | `shipping_weight` | float | Shipping weight |
| `Installation` | `installation_url` | str | Install PDF URL |
| `Specification` | `specification_url` | str | Spec PDF URL |
| `Main` | `main_image` | str | Main image filename |
| `Main URL` | `main_image_url` | str | Main image full URL |
| `sn` | `alt_image_1` | str | Alternate image 1 |
| `Alternative 2` | `alt_image_2` | str | Alternate image 2 |
| `Alternative 3` | `alt_image_3` | str | Alternate image 3 |
| `Alternative 4` | `alt_image_4` | str | Alternate image 4 |
| `Center to center` | `center_to_center` | float | Mounting spacing |
| `Diameter` | `diameter` | float | Bar/tube diameter |
| `Screw size` | `screw_size` | str | Mounting screw spec |
| `Mirror Height` | `mirror_height` | float | Mirror dimension |
| `Mirror width` | `mirror_width` | float | Mirror dimension |
| `Thickness` | `thickness` | float | Glass/material thickness |
| `Weight capacity` | `weight_capacity` | float | Load capacity (lbs) |
| `Material` | `material` | str | Primary material |
| `Style` | `style` | str | Design style |
| `Shape` | `shape` | str | Product shape |
| `Orientation` | `orientation` | str | Horizontal/vertical |
| `Tilting` | `tilting` | str | Tilt capability |
| `Mounting type` | `mounting_type` | str | Mount method |
| `Assembly required` | `assembly_required` | bool | Needs assembly |
| `Item number` | `item_number` | str | Item number |
| `Included` | `included_items` | str | What's in the box |

### Handling Duplicate Column Names

The CSV has duplicate column names (`Length`, `Height`, `Width`, `Weight`). 

**Resolution**: Use 0-indexed positional references when parsing:

| Index | Column Name | Model Field | Notes |
|-------|-------------|-------------|-------|
| 23 | Length | `product_length` | First occurrence |
| 24 | Height | `product_height` | First occurrence |
| 25 | Width | `product_width` | First occurrence |
| 26 | Projection | `projection` | Unique |
| 27 | Weight | `product_weight` | First occurrence |
| 28 | Length | `shipping_length` | Second occurrence |
| 29 | Height | `shipping_height` | Second occurrence |
| 30 | Width | `shipping_width` | Second occurrence |
| 31 | Weight | `shipping_weight` | Second occurrence |

**Implementation note**: When using pandas, rename columns during load:
```python
# After loading, rename duplicate columns by position
df.columns = [col if i not in DUPLICATE_POSITIONS else POSITIONAL_MAPPING[i] 
              for i, col in enumerate(df.columns)]
```

---

## Environment Variables

Required variables (names only, never log values):

```
# LLM Providers
OPENAI_API_KEY
GEMINI_API_KEY

# Shopify
SHOPIFY_STORE_URL
SHOPIFY_API_KEY
SHOPIFY_ACCESS_TOKEN
SHOPIFY_API_SECRET

# Google Merchant Center
GMC_MERCHANT_ID
GMC_API_KEY

# Database (existing, not used for MVP)
DB_TYPE
DB_HOST
DB_PORT
DB_NAME
DB_USER
DB_PASSWORD
```

---

## Out of Scope for MVP

1. Microsoft/Bing Merchant Center integration
2. Real-time Shopify webhook sync
3. A/B testing infrastructure
4. Multi-language support
5. Supabase persistence (deferred to post-MVP)
6. Automated Content API push (preview-only for MVP)

---

## Quality Bar

- Factual Accuracy score must be ≥8/10 (hard requirement)
- Composite quality score must be ≥80% for approval
- All claims must map to evidence table
- No ungrounded claims allowed
- Dry-run only until export + rollback verified
