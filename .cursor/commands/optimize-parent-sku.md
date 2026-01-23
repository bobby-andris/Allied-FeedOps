---
description: Optimize product titles and descriptions for a parent SKU and its variants
---

# /optimize-parent-sku

## Purpose
Generate optimized product titles and descriptions for a parent SKU and all its variants, following research-backed optimization rules.

## Usage
```
/optimize-parent-sku [SKU or product identifier]
```

## Workflow

### Phase 1: Data Collection

1. **Retrieve product data** for the specified SKU:
   - Parent product attributes
   - All variant attributes (sizes, finishes, etc.)
   - Current title and description
   - Category/collection information

2. **Gather performance data** (if available):
   - Current impressions, clicks, conversions
   - Search query matches
   - Competitor positioning

3. **Identify gaps**:
   - Missing attributes that could improve matching
   - Underutilized character space
   - Generic language opportunities

### Phase 2: Analysis

**Data Analyst** agent evaluates:

```markdown
## Current State Analysis

### Title Audit
- Current length: [X] chars (target: 70-150)
- Brand position: [First 70 / After 70 / Missing]
- Product type position: [First 70 / After 70]
- Key dimension: [Included / Missing]
- Functional modifier: [Included / Missing / N/A]

### Description Audit  
- Current length: [X] chars (target: 500+)
- Opening hook quality: [Strong / Weak / Missing]
- Benefit coverage: [Yes / Partial / No]
- Specificity level: [High / Medium / Low]

### Optimization Opportunities
1. [Opportunity 1]
2. [Opportunity 2]
3. [Opportunity 3]
```

### Phase 3: Content Generation

**Feed Copywriter** agent generates:

1. **Parent product**:
   - Optimized title (following structure rules)
   - Optimized description (following format rules)

2. **Each variant** (if applicable):
   - Variant-specific title (with distinguishing attribute)
   - Variant-specific description (if significantly different)

### Phase 4: Verification

**Verifier** agent validates:

1. Factual accuracy against source data
2. Quality scoring (target: 80%+)
3. Platform compliance (Google, Bing, Shopify)
4. Character limit adherence

### Phase 5: Output

```markdown
# Optimization Results: [Product Name]

## Parent SKU: [SKU]

### Before
**Title**: [original title]
**Description**: [original description]

### After
**Title**: [optimized title]
**Description**: [optimized description]

### Quality Score: [X]%

---

## Variant: [Variant Name] (SKU: [variant SKU])

### Before
**Title**: [original]

### After  
**Title**: [optimized]

[Repeat for each variant]

---

## Verification Summary
| Check | Status |
|-------|--------|
| Factual Accuracy | ✅ |
| Quality Score | 87% |
| Google Compliance | ✅ |
| Bing Compliance | ✅ |
| Character Limits | ✅ |

## Next Steps
1. Review and approve changes
2. Export to feed format
3. Submit to platforms
```

## Example

```
/optimize-parent-sku AB-TOWEL-24
```

**Output**:
```markdown
# Optimization Results: 24-Inch Towel Bar

## Parent SKU: AB-TOWEL-24

### Before
**Title**: Allied Brass Towel Bar 24
**Description**: This towel bar is made of brass and measures 24 inches. Available in multiple finishes.

### After
**Title**: Allied Brass 24-Inch Towel Bar | Solid Brass | Wall Mount | Concealed Hardware
**Description**: 
Crafted from solid brass that will never corrode, peel, or tarnish, this 24-inch towel bar brings enduring elegance to your bathroom with secure wall mounting.

**Key Highlights**
• Solid brass construction – corrosion-proof durability that outlasts chrome-plated alternatives
• 24-inch length – ideal size for standard bath towels with room to spare
• Concealed mounting hardware – clean lines with no visible screws
• Coordinates with Allied Brass collections – match your existing fixtures

**Specifications**
- Length: 24 inches
- Material: Solid brass
- Mount type: Wall mount, concealed hardware
- Includes: Mounting hardware and installation template

Backed by Allied Brass's lifetime warranty on construction.

### Quality Score: 92%

---

## Variant: Polished Chrome (SKU: AB-TOWEL-24-PC)

### Before
**Title**: Allied Brass Towel Bar 24 - Chrome

### After
**Title**: Allied Brass 24-Inch Towel Bar | Solid Brass | Polished Chrome | Wall Mount

---

## Variant: Oil Rubbed Bronze (SKU: AB-TOWEL-24-ORB)

### Before
**Title**: Allied Brass Towel Bar 24 - ORB

### After
**Title**: Allied Brass 24-Inch Towel Bar | Solid Brass | Oil Rubbed Bronze | Wall Mount
```

## Flags

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview changes without saving |
| `--variants-only` | Only optimize variant titles, not parent |
| `--platform=google` | Optimize specifically for Google Shopping |
| `--platform=bing` | Optimize specifically for Microsoft Shopping |
| `--export=csv` | Export results to CSV format |
