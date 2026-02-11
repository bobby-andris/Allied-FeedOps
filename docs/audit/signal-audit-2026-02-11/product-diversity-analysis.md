# Allied Brass Product Diversity Analysis

## Executive Summary

Allied Brass has **2,892 unique master SKUs** across **32 categories** and **46 collections**. The user is correct: products are highly unique. Category-level keyword generalization would be **harmful** for cold-start keyword propagation. A **Functional Sub-Type (FST) clustering** approach is recommended instead.

---

## 1. Category-Level Diversity (32 categories)

| Category | SKU Count | Functional Sub-Types |
|----------|-----------|---------------------|
| Towel Bars | 666 | 3 (Standard, Double, Accent Detail) |
| Glass Shelves | 464 | **10** (Single, Double, Triple, +Towel Bar, +Gallery Rail, +Gallery+TB, Vanity, Corner) |
| Toilet Paper Holders | 230 | 5 (Standard, Euro Style, 2-Post, Upright, Recessed) |
| Shower Door Hardware | 198 | TBD |
| Wall Mirrors | 134 | **10** (Round/Oval/Rect/Landscape/Arched x Tilt or Rail-Mounted) |
| Wood Shelves | 122 | TBD |
| Guest Towel Holders | 100 | Low |
| Make-Up Mirrors | 96 | TBD |
| Cabinet Hardware | 92 | TBD |
| Grab Bars | 88 | TBD |
| + 22 more categories | 702 | Varies |

**Key Finding**: The largest categories have **3-10 distinct functional sub-types**, each with meaningfully different search intent.

---

## 2. Deep Dive: Glass Shelves (464 SKUs, 10 Functional Sub-Types)

| Functional Sub-Type | SKU Count | Search Intent Difference |
|---------------------|-----------|------------------------|
| Standard Glass Shelf | 104 | "glass bathroom shelf" |
| Double Glass Shelf (Two Tiered) | 66 | "two tier glass shelf bathroom" |
| Double Glass Shelf with Towel Bar | 65 | "glass shelf with towel bar" |
| Glass Shelf with Integrated Towel Bar | 62 | "glass vanity shelf towel bar" |
| Glass Shelf with Gallery Rail | 48 | "glass shelf gallery rail bathroom" |
| Glass Shelf with Gallery Rail + Towel Bar | 36 | "glass shelf gallery rail towel bar" |
| Glass Vanity Shelf with Beveled Edges | 33 | "beveled glass vanity shelf" |
| Triple Glass Shelf | 22 | "triple tier glass shelf bathroom" |
| Triple Glass Shelf with Towel Bar | 16 | "triple glass shelf towel bar" |
| Corner Glass Shelf | 12 | "corner glass shelf bathroom" |

**Analysis**: A customer searching for "corner glass shelf" has fundamentally different intent than one searching "triple tier glass shelf with towel bar." Propagating generic "glass shelf" keywords would:
- Dilute relevance for specialized products
- Miss long-tail keywords that drive conversion for unique configurations
- Waste budget on broad terms that don't match product functionality

---

## 3. Deep Dive: Towel Bars (666 SKUs, 3 Sub-Types)

| Functional Sub-Type | SKU Count |
|---------------------|-----------|
| Towel Bar with Accent Detail (Dotted/Grooved/Twist) | 249 |
| Standard Towel Bar | 233 |
| Double Towel Bar | 184 |

**Analysis**: Towel Bars have fewer functional sub-types, but the differentiation is still meaningful. "Double towel bar" is a distinct search query from "towel bar." Accent details (dotted, grooved, twist) are aesthetic differentiators that matter less for search intent but could be relevant for branded queries.

---

## 4. Deep Dive: Toilet Paper Holders (230 SKUs, 5 Sub-Types)

| Functional Sub-Type | SKU Count |
|---------------------|-----------|
| Standard | 70 |
| Euro Style | 62 |
| 2-Post | 54 |
| Upright | 24 |
| Recessed | 20 |

**Analysis**: "Recessed toilet paper holder" vs "euro style toilet paper holder" are completely different product categories in the customer's mind. Mounting type (recessed vs wall mount) is a critical differentiator.

---

## 5. Deep Dive: Wall Mirrors (134 SKUs, 10 Sub-Types)

| Functional Sub-Type | SKU Count |
|---------------------|-----------|
| Round Tilt Mirror | 19 |
| Oval Tilt Mirror | 19 |
| Rectangular Tilt Mirror | 19 |
| Landscape Rectangular Tilt Mirror | 19 |
| Arched Top Tilt Mirror | 19 |
| Round Rail-Mounted Mirror | 8 |
| Oval Rail-Mounted Mirror | 8 |
| Rectangular Rail-Mounted Mirror | 7 |
| Landscape Rectangular Rail-Mounted | 8 |
| Arched Top Rail-Mounted Mirror | 8 |

**Analysis**: Shape (round/oval/rectangular/arched) x Mount Type (tilt/rail) = 10 distinct products. "Arched top frameless rail mounted mirror" is a completely different search than "round tilt mirror."

---

## 6. Cross-Cutting Dimensions

### Accent Patterns (Product-Wide)
| Accent Type | SKU Count |
|-------------|-----------|
| Plain (no accent) | 2,270 |
| Twisted | 208 |
| Dotted | 207 |
| Grooved | 207 |

~21% of all SKUs have accent details. These are aesthetic variations that share functional search intent with their plain counterparts but may have distinct queries for design-conscious buyers.

### Collection Distribution (Top 10)
| Collection | SKU Count | Categories Spanned |
|------------|-----------|-------------------|
| (null/unset) | 295 | 19 |
| Clearview | 183 | 13 |
| Pacific Grove | 176 | 9 |
| Dottingham | 133 | 20 |
| Waverly Place | 132 | 20 |
| Prestige Regal | 122 | 19 |
| Prestige Skyline | 112 | 19 |
| Carolina | 102 | 19 |
| Carolina Crystal | 101 | 19 |
| Pipeline | 95 | 19 |

**Key Insight**: Major collections span 13-20 categories. This means a "Dottingham" collection includes towel bars, soap dishes, mirrors, shelves, etc. Collection-level keyword grouping would be **too broad** — it crosses functional boundaries.

---

## 7. Assessment of Cold-Start Keyword Strategies

### Strategy A: Category-Level Generalization — REJECTED

**Example**: All 464 Glass Shelf SKUs share "glass shelf" keywords.

**Problems**:
- "Corner glass shelf" customer sees "triple glass shelf with towel bar" — irrelevant
- Wastes Keyword Planner API quota on overly broad seeds
- Dilutes keyword quality scores
- Ignores that 10 functional sub-types serve 10 different customer needs

**Verdict**: Too coarse. Would actively harm keyword relevance.

### Strategy B: Collection-Level Grouping — REJECTED

**Example**: All "Dottingham" products share keywords.

**Problems**:
- Dottingham spans 20 categories — a Dottingham towel bar and Dottingham mirror share no functional keywords
- Collection is a design/brand attribute, not a functional attribute
- Only useful for branded search queries ("dottingham towel bar"), which are extremely low volume

**Verdict**: Wrong axis of similarity for keyword propagation.

### Strategy C: Functional Sub-Type (FST) Clustering — RECOMMENDED

**Approach**: Extract functional product type from title using pattern matching, then cluster SKUs that serve the same customer need.

**Example Clusters**:
- `Glass Shelves > Double Glass Shelf with Towel Bar` (65 SKUs) — all share "double glass shelf towel bar" keywords
- `Glass Shelves > Corner Glass Shelf` (12 SKUs) — all share "corner glass shelf" keywords
- `Toilet Paper Holders > Recessed` (20 SKUs) — all share "recessed toilet paper holder" keywords

**How to Extract FST**:
```
title → remove collection name → remove size → remove accent detail → functional core
```
Example: "Carolina Crystal Collection 16 Inch Gallery Glass Shelf with Towel Bar" → "Gallery Glass Shelf with Towel Bar"

**Benefits**:
1. Products within an FST cluster serve the **same customer search intent**
2. Keywords from one "Double Glass Shelf with Towel Bar" are directly relevant to all others
3. Preserves the uniqueness of specialized configurations
4. ~50-80 FST clusters across the catalog (manageable for KP queries)

### Strategy D: Attribute-Based Composite Key — SUPPLEMENTARY

**Approach**: `category + mounting_type + functional_modifier`

**Example**: `Glass Shelves | Wall mount | Gallery Rail + Towel Bar`

**Benefits**:
- More systematic than title parsing
- Captures mounting_type dimension (important for Toilet Paper Holders: wall vs recessed)

**Limitation**: Requires functional_modifier extraction from titles anyway, so this is essentially FST with explicit attribute decomposition.

**Verdict**: Good refinement of Strategy C, but FST is the core engine.

---

## 8. Recommended Cold-Start Signal Strategy

### Primary: Functional Sub-Type (FST) Clustering

1. **Extract FST from titles** using regex/pattern matching:
   - Strip collection name, size dimensions, accent details
   - Remaining string = functional product type

2. **For each FST cluster**, generate one Keyword Planner query:
   - Seed: FST name (e.g., "double glass shelf with towel bar brass bathroom")
   - Get: Search volume, competition, CPC data
   - Apply: To ALL SKUs in that FST cluster

3. **Accent variants share parent FST keywords**:
   - "Continental Towel Ring with Dotted Accents" inherits keywords from "Towel Ring" FST
   - Accent is an aesthetic differentiator, not a functional one
   - Exception: If accent-specific queries exist in search data, preserve them

4. **Collection names as supplementary branded keywords**:
   - Add "{collection} {category}" as secondary keywords only
   - Low priority — branded queries have minimal volume for niche hardware

### Estimated Scale

- **~60-80 FST clusters** across the catalog
- **1 KP query per FST** = 60-80 API calls (well within rate limits)
- **Coverage**: 100% of 2,892 SKUs get relevant cold-start keywords
- **Quality**: Keywords match actual customer search intent, not generic category terms

### Implementation Sketch

```sql
-- Step 1: Extract FST from titles
SELECT
  master_sku,
  category,
  -- Strip collection, size, accent to get functional core
  regexp_replace(
    regexp_replace(
      regexp_replace(title, '\d+ Inch ', ''),
      '(Collection |Crystal )', ''),
    ' with (Dotted|Grooved|Twist(ed)?) (Accents?|Detail)', ''),
    '') as functional_subtype
FROM product_catalog;

-- Step 2: Group by FST, query KP once per group
-- Step 3: Propagate keywords to all SKUs in each FST cluster
```

---

## 9. Key Takeaway

The user is absolutely right: Allied Brass products are highly unique within categories. "Glass Shelves" alone contains 10 distinct functional configurations. Category-level keyword generalization would be harmful. **Functional Sub-Type clustering** preserves this uniqueness while still enabling cold-start keyword propagation across the ~622 SKUs that lack direct search data.
