# Allied FeedOps: Workflow Guide

## Canonical Workflow For Generation Work

For generation-affecting changes, this workflow guide is subordinate to the canonical process documents:

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/architecture/generation-prompt-lineage-contract.md`
5. `docs/architecture/generation-pipeline-routing-reference.md`
6. `docs/development/generation-change-checklist.md`
7. `docs/operations/deploy-and-certify-generation.md`

Any older workflow section in this file that conflicts with those docs should be treated as background context, not operating law.

## Optimization Workflows

This document covers the end-to-end workflows for feed optimization.

## Current Merge Gate For Generation Changes

No generation-affecting PR is ready until all of the following are complete:

1. Source review explains the request-to-task-to-provider flow.
2. Host verification passes.
3. Local container smoke passes with artifact review.
4. The exact deployed Cloud Run revision is identified and re-tested.
5. Supabase lineage rows match the observed runtime.
6. Dashboard readback matches persisted artifacts.
7. A dated experiment report records the evidence set.

---

## Workflow 1: Single Product Optimization

Use when optimizing one product (parent SKU) and its variants.

### Step 1: Gather Product Data

**Required Data**:
```yaml
product:
  sku: "AB-TOWEL-24"
  brand: "Allied Brass"
  product_type: "Towel Bar"
  collection: "Waverly Place"  # if applicable
  
attributes:
  dimensions:
    length: "24 inches"
    depth: "3 inches"
    projection: "2.5 inches"
  material: "Solid Brass"
  mount_type: "Wall Mount"
  hardware: "Concealed"
  
variants:
  - sku: "AB-TOWEL-24-PC"
    finish: "Polished Chrome"
  - sku: "AB-TOWEL-24-ORB"
    finish: "Oil Rubbed Bronze"
  - sku: "AB-TOWEL-24-SN"
    finish: "Satin Nickel"

current_content:
  title: "Allied Brass Towel Bar 24"
  description: "24 inch towel bar in brass."

certifications: []  # ADA, UL, etc. if applicable
warranty: "Lifetime construction, 5-year finish"
```

### Step 2: Analyze Current State

**Data Analyst** evaluates:

```markdown
## Current Title Analysis
- Length: 26 characters (UNDER-UTILIZED - target 70-150)
- Brand position: ✅ First
- Product type: ✅ Present
- Dimension: ⚠️ Present but format non-standard ("24" vs "24-Inch")
- Material: ❌ Missing
- Functional modifier: ❌ Missing
- Quality Score: 35%

## Current Description Analysis
- Length: 27 characters (CRITICAL - target 500+)
- Benefit statement: ❌ Missing
- Specific claims: 1 (dimension)
- Vague claims: 0
- Quality Score: 15%

## Optimization Priority: HIGH
- Missing 85% of potential title value
- Missing 95% of potential description value
```

### Step 3: Generate Optimized Content

**Feed Copywriter** produces:

```markdown
## Optimized Title
`Allied Brass 24-Inch Towel Bar | Solid Brass | Wall Mount | Concealed Hardware`

### Title Verification
- Length: 76 characters ✅
- Brand in first 70: ✅ "Allied Brass"
- Product type in first 70: ✅ "Towel Bar"
- Dimension in first 70: ✅ "24-Inch"
- Material: ✅ "Solid Brass"
- Functional: ✅ "Wall Mount", "Concealed Hardware"

## Optimized Description
Crafted from solid brass that will never corrode, peel, or tarnish, this 24-inch 
towel bar brings enduring elegance to your bathroom with secure wall mounting.

**Key Highlights**
• Solid brass construction – corrosion-proof durability that outlasts chrome-plated alternatives
• 24-inch length – ideal size for standard bath towels with room to spare
• Concealed mounting hardware – clean lines with no visible screws
• Part of the Waverly Place collection – coordinates with matching bathroom accessories

**Specifications**
- Length: 24 inches
- Projection: 2.5 inches
- Material: Solid brass
- Mount type: Wall mount, concealed hardware
- Includes: Mounting hardware and installation template

Backed by Allied Brass's lifetime warranty on construction and 5-year finish guarantee.

### Description Verification
- Length: 742 characters ✅
- Opening hook: ✅ Benefit-first with key spec
- Bullet points: ✅ 4 highlights
- Specific claims: 8 ✅
- Vague claims: 0 ✅
```

### Step 4: Verify Content

**Verifier** agent scores:

```markdown
## Quality Score Report

| Dimension | Score | Notes |
|-----------|-------|-------|
| Specificity | 10/10 | All 8 claims verifiable |
| Benefit Coverage | 10/10 | Strong benefit-first opening |
| Keyword Inclusion | 9/10 | All key terms present |
| Format Adherence | 10/10 | All requirements met |
| Brand Voice | 9/10 | Premium, confident tone |
| Factual Accuracy | 10/10 | All claims traced to source |

### Composite Score: 97%
### Status: ✅ APPROVED

## Source Verification
| Claim | Source | Verified |
|-------|--------|----------|
| 24-inch | attributes.dimensions.length | ✅ |
| Solid brass | attributes.material | ✅ |
| Concealed hardware | attributes.hardware | ✅ |
| Wall mount | attributes.mount_type | ✅ |
| Waverly Place | product.collection | ✅ |
| Lifetime warranty | product.warranty | ✅ |
| 5-year finish | product.warranty | ✅ |
| 2.5 inch projection | attributes.dimensions.projection | ✅ |
```

### Step 5: Generate Variants

Apply parent optimization pattern to each variant:

```markdown
## Variant Titles

### Polished Chrome (AB-TOWEL-24-PC)
`Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount`

### Oil Rubbed Bronze (AB-TOWEL-24-ORB)
`Allied Brass 24-Inch Towel Bar | Solid Brass | Oil Rubbed Bronze | Wall Mount`

### Satin Nickel (AB-TOWEL-24-SN)
`Allied Brass 24-Inch Towel Bar | Solid Brass | Satin Nickel | Wall Mount`
```

### Step 6: Export and Deploy

Output in platform-specific formats:
- Google Merchant Center feed
- Microsoft Merchant Center feed
- Shopify product update

---

## Workflow 2: Bulk Feed Audit

Use when assessing entire product catalog for optimization opportunities.

### Step 1: Import Full Feed

Load product feed data (CSV, JSON, or via MCP connection).

### Step 2: Score All Products

**Data Analyst** runs quality scoring across catalog:

```sql
-- Pseudo-query for scoring
SELECT 
  sku,
  title,
  CHAR_LENGTH(title) as title_length,
  CHAR_LENGTH(description) as desc_length,
  calculate_quality_score(title, description, attributes) as quality_score
FROM products
ORDER BY quality_score ASC;
```

### Step 3: Identify Priorities

```markdown
## Feed Audit Summary

### By Quality Score
| Score Range | Count | % | Action |
|-------------|-------|---|--------|
| 90-100% | 45 | 18% | Monitor |
| 80-89% | 67 | 27% | Optional tune |
| 70-79% | 52 | 21% | Schedule optimization |
| <70% | 86 | 34% | **Priority optimization** |

### Top Priority Products (Score < 70%)
1. AB-GRAB-18: 42% - Missing ADA mention, short description
2. AB-MIRROR-OV: 38% - Generic title, no benefits
3. AB-TOWEL-18: 45% - Missing material, no hooks
...

### Quick Wins (High traffic, low score)
| SKU | Monthly Views | CVR | Score | Potential |
|-----|---------------|-----|-------|-----------|
| AB-TOWEL-24 | 12,450 | 1.2% | 35% | High |
| AB-GRAB-24 | 8,230 | 0.8% | 42% | High |
| AB-MIRROR-RECT | 6,120 | 0.5% | 38% | High |
```

### Step 4: Batch Optimization

Process priority products:

```
FOR each product in priority_list:
  1. Gather product data
  2. Generate optimized content
  3. Verify against rubric
  4. Queue for review
```

### Step 5: Review and Approve

Human review of generated content before deployment.

### Step 6: Deploy and Measure

Push to platforms and track:
- Impression changes
- CTR changes
- CVR changes
- ROAS changes

---

## Workflow 3: New Product Launch

Use when adding new products to the catalog.

### Step 1: Product Data Entry

Ensure all required fields are populated:

```yaml
required_fields:
  - sku
  - brand
  - product_type
  - dimensions (all relevant)
  - material
  - mount_type (if applicable)
  
recommended_fields:
  - collection
  - functional_modifiers
  - certifications
  - warranty
  - weight_capacity (if applicable)
  - included_items
```

### Step 2: Generate Initial Content

Run `/optimize-parent-sku [NEW-SKU]` with complete data.

### Step 3: Verify Before Launch

Ensure quality score ≥80% before publishing.

### Step 4: Platform Submission

Submit to:
1. Google Merchant Center
2. Microsoft Merchant Center
3. Shopify (if applicable)

### Step 5: Post-Launch Monitoring

Track initial performance:
- First 7 days: Impression volume
- First 14 days: CTR trends
- First 30 days: Conversion patterns

Adjust if needed based on search query data.

---

## Workflow 4: Performance-Triggered Optimization

Use when performance data indicates optimization opportunity.

### Trigger Conditions

```yaml
optimization_triggers:
  - condition: "high_views_low_conversion"
    threshold: "impressions > 1000 AND cvr < 1%"
    action: "Review description for missing info"
    
  - condition: "low_ctr"
    threshold: "impressions > 1000 AND ctr < 0.5%"
    action: "Review title for relevance"
    
  - condition: "quality_score_drop"
    threshold: "quality_score decreased > 10% MoM"
    action: "Check for compliance issues"
    
  - condition: "competitor_outperforming"
    threshold: "impression_share < 50% AND competitor_visible"
    action: "Analyze competitor titles"
```

### Process

1. **Alert**: System identifies products meeting trigger conditions
2. **Diagnose**: Data Analyst identifies likely cause
3. **Optimize**: Feed Copywriter generates improved content
4. **Test**: Consider A/B test for high-value products
5. **Deploy**: Push winning variation
6. **Monitor**: Track improvement

---

## Quality Gates

### Gate 1: Data Completeness
- All required attributes present
- No conflicting data
- Source of truth identified

### Gate 2: Content Generation
- Title follows structure formula
- Description follows benefit-first format
- No hallucinated claims

### Gate 3: Verification
- Quality score ≥80%
- All claims verified against source
- Platform compliance checked

### Gate 4: Human Review (Optional)
- For high-value products
- For significant changes
- For new categories

### Gate 5: Post-Deployment
- No disapprovals within 48 hours
- Performance trending positive within 14 days

---

## Rollback Procedures

If optimization causes issues:

### Immediate Rollback
```
1. Revert to previous content version
2. Re-submit to platforms
3. Document issue for analysis
```

### Gradual Rollback
```
1. Identify specific problematic element
2. Create modified version
3. Test on subset
4. Deploy if successful
```

### Root Cause Analysis
```
1. What changed?
2. What was the impact?
3. Why did it happen?
4. How to prevent recurrence?
```
