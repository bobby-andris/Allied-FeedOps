# Lifestyle Image Generation - Complete Context & Background

## Executive Summary

This document provides complete context for the lifestyle image generation system integrated into Allied-FeedOps. It covers the business goals, technical implementation, learnings from testing, and guidelines for improvements.

---

## Business Context & Goals

### Why We Built This

**Problem:** Allied Brass product pages need high-quality lifestyle images showing products in real bathroom settings, but:
- Professional photoshoots are expensive ($500-1000 per product)
- We have 41 collection hero products needing images
- Product shots alone don't showcase how products look installed
- Competitors have lifestyle imagery giving them conversion advantages

**Solution:** AI-generated lifestyle images using Google Gemini Imagen API
- Cost: ~$1.50 per product (3 variations)
- Speed: Generate in seconds vs. weeks for photoshoot
- Scalability: Can generate for entire catalog
- Quality target: 90%+ product accuracy (product looks identical to reference)

### Success Criteria

✅ **Product Accuracy** - Generated product must be visually identical to reference image
  - Correct shape, finish, proportions, materials
  - Accurate component details (backplates, end caps, screws, etc.)
  - Proper finish representation (chrome, brass, bronze, etc.)

✅ **Contextual Relevance** - Scene must match product's actual use case
  - Towel bars show towels hanging on them
  - Toilet paper holders show toilet paper on them
  - Glass shelves show toiletries/items stored on them (NOT towels draped)
  - Robe hooks show robes/towels hanging from them

✅ **Brand Consistency** - Images match Allied Brass brand aesthetic
  - High-end, architectural precision
  - Clean, uncluttered bathrooms
  - Professional photography quality
  - Finish-appropriate styling (modern vs. traditional)

❌ **Common Failures to Avoid**
  - Generic bathroom scenes that don't match product type
  - Incorrect product usage (e.g., towels on glass shelves)
  - Reference image obscures product (e.g., toilet paper rolls covering holder detail)
  - Product details change (wrong backplate shape, missing components)

---

## Technical Implementation

### Architecture Overview

The lifestyle image generation is integrated into the Allied-FeedOps content optimization pipeline:

```
optimize.py Pipeline:
├── Step 1: Load Product Data
├── Step 2: Generate Titles/Descriptions (LLM)
├── Step 3: Verify Claims
├── Step 4: Generate Lifestyle Images (NEW)
│   ├── Download reference image from main_image_url
│   ├── Build product-specific prompt
│   ├── Generate 3 variations via Gemini Imagen
│   └── Save to data/lifestyle_images/
├── Step 5: Save to JSON exports
└── Step 6: Generate reports
```

### Key Files

1. **`src/feedops/pipeline/lifestyle_images.py`** - Core generation module
   - `LifestyleImageGenerator` class
   - `generate_for_product()` - Creates 3 variations
   - Template functions: `get_product_inventory()`, `get_scene_context()`, `get_technical_specs()`

2. **`src/feedops/models/candidate.py`** - Data model
   - `lifestyle_images: list[LifestyleImageResult]` - All variations
   - `selected_lifestyle_image: int` - Which variation to use

3. **`src/feedops/pipeline/optimize.py`** - Pipeline integration
   - Step 4: Conditional image generation (controlled by env var)

4. **`src/feedops/pipeline/reporter.py`** - Export formatting
   - Saves lifestyle images data in JSON patches

5. **`src/feedops/quality/review_dashboard.py`** - Streamlit UI
   - `render_lifestyle_images_panel()` - Displays 3 variations side-by-side

### Data Flow

```
Product Catalog.csv
└─> ParentSKU object
    ├─> main_image_url (reference image) ←── CURRENT: Only uses this
    ├─> sn (dimensions image)              ←── AVAILABLE: Not yet used
    ├─> Alternative 2                       ←── AVAILABLE: Not yet used
    ├─> Alternative 3                       ←── AVAILABLE: Not yet used
    └─> Alternative 4                       ←── AVAILABLE: Not yet used
    └─> category (e.g., "Towel Bar", "Glass Shelf")
    └─> collection (e.g., "Argo", "Monte Carlo")

Lifestyle Image Generator
├─> Input: Reference image URL + Category + Collection
├─> Process: Build 3-part prompt
│   ├─ Product Visual Inventory (component descriptions)
│   ├─ Scene Context (bathroom narrative)
│   └─ Technical Specifications (photography direction)
├─> Generate: 3 variations via Gemini Imagen API
└─> Output: LifestyleImageResult objects

JSON Export (google-patch-{sku}.json)
{
  "title": "...",
  "description": "...",
  "lifestyle_images": [
    {
      "image_path": "data/lifestyle_images/AR-41_var1.png",
      "variation_num": 1,
      "generation_success": true,
      "prompt_used": "CRITICAL: This is PRODUCT PHOTOGRAPHY...",
      "timestamp": "20260125_143022"
    },
    ...
  ],
  "selected_lifestyle_image": 1
}
```

---

## Prompt Engineering Strategy

### The "Product-First" Approach

Our testing in `/Users/bobby/Documents/GitHub/google-analytics-mcp/` achieved **90%+ accuracy** using this 3-part prompt structure:

#### 1. Product Visual Inventory
**Purpose:** Exact component-by-component description of the product

**Example for Towel Bar:**
```
PRODUCT VISUAL INVENTORY:
BACKPLATE (2 total - one at each end):
- Shape: Perfect SQUARE measuring 2.5" × 2.5"
- Surface: Flat polished chrome with subtle concentric circles
- Mounting: 4 visible screw holes in a square pattern
- Thickness: 1/4 inch projection from wall

END CAP (2 total - left and right):
- Shape: Cylindrical dome, approximately 1 inch diameter
- Material: Solid polished chrome matching backplate
- Detail: Smooth rounded top with visible seam to bar

HORIZONTAL BAR:
- Length: 24 inches between end caps
- Diameter: 5/8 inch cylindrical bar
- Finish: Seamless polished chrome
- Function: Designed for hanging towels
```

**Why this works:** Forces the model to replicate each component exactly instead of improvising.

#### 2. Scene Context
**Purpose:** Set the bathroom environment matching collection style

**Example for Contemporary Collection:**
```
SCENE CONTEXT:
A professional photographer captures a high-contrast modern bathroom.
Pristine white large-format porcelain walls create a minimalist canvas.
Natural diffused window light from the left creates soft shadows.
The towel bar is mounted 48" from floor on the main wall.
A premium waffle-weave towel in charcoal gray hangs naturally on the bar.
Negative space emphasizes the architectural precision of the fixture.
```

**Example for Traditional Collection:**
```
SCENE CONTEXT:
A warm traditional bathroom with cream subway tiles in herringbone pattern.
Soft ambient lighting creates inviting atmosphere.
The towel bar mounted at standard height with plush white towel.
Warm brass finish complements classic marble countertop visible in background.
```

**Why this works:** Provides environmental context without obscuring product.

#### 3. Technical Specifications
**Purpose:** Control photography quality and composition

```
TECHNICAL SPECIFICATIONS:
Lighting: Bright even 5500K illumination with directional spotlight
Camera: 3/4 angle view, product in sharp focus, background soft
Mood: Clean, minimal, architectural precision
Constraints: Product must remain exact replica of reference
```

---

## Current Implementation Details

### Environment Configuration

```bash
# Required
GEMINI_API_KEY=AIzaSyDNm94Xe2-uez9QMqQpqcqQJZngsY9K5uE
LIFESTYLE_IMAGES_ENABLED=true

# Optional
LIFESTYLE_IMAGES_NUM_VARIATIONS=3
LIFESTYLE_IMAGES_OUTPUT_DIR=data/lifestyle_images
```

### Product Catalog Schema

The catalog CSV contains these image-related columns:

| Column | Purpose | Current Usage | Potential Usage |
|--------|---------|---------------|-----------------|
| Main URL | Primary product photo | ✅ Used as reference | Primary reference |
| sn | Dimensions/diagram | ❌ Not used | Could show product details |
| Alternative 2 | Additional angle | ❌ Not used | Better detail visibility |
| Alternative 3 | Additional angle | ❌ Not used | Component close-ups |
| Alternative 4 | Additional angle | ❌ Not used | Installed view |

### Category-to-Template Mapping

Current implementation in `get_product_inventory()`:

```python
def get_product_inventory(category: str) -> str:
    """Map product category to component descriptions."""

    if "Towel Bar" in category:
        return "BACKPLATE: Square chrome plate...\nEND CAP: Cylindrical dome..."

    elif "Toilet Paper Holder" in category:
        return "BACKPLATE: Round decorative plate...\nARM: Horizontal bar..."

    elif "Glass Shelf" in category:
        return "BACKPLATE: Rectangular mounting plates...\nSHELF: Clear tempered glass..."

    # ... more categories
```

### Style-to-Scene Mapping

Current implementation in `get_scene_context()`:

```python
def get_scene_context(style: str = "modern") -> str:
    """Map collection style to bathroom scene."""

    if style == "contemporary":
        return "High-contrast modern bathroom. White large-format tiles..."

    elif style == "traditional":
        return "Warm traditional bathroom. Cream subway tiles..."

    elif style == "transitional":
        return "Elegant transitional bathroom. Neutral color palette..."
```

---

## Testing Results & Learnings

### What Worked Well ✅

1. **Product-First Prompt Strategy**
   - 90%+ accuracy on towel bars, robe hooks, towel rings
   - Component-by-component descriptions prevented improvisation
   - Technical constraints maintained product fidelity

2. **3 Variations Approach**
   - Gives options when one fails
   - Different angles/compositions for selection
   - Cost effective (~$1.50 per product)

3. **Integration into Pipeline**
   - Seamless generation alongside content
   - Saved in JSON for dashboard display
   - Environment variable control for easy enable/disable

### Issues Discovered ❌

#### Issue 1: Reference Image Obscures Product Detail

**Example:** Toilet paper holder with toilet paper rolls installed
- **Problem:** Paper rolls block view of decorative backplate
- **Impact:** Generated image misses critical product details
- **Root Cause:** Only using `main_image_url` which is styled for website, not reference
- **Solution Needed:** Use multiple reference images (Alternative 2, 3, 4) showing clear product views

**Evidence:**
```
QN-24-RR-2 (Toilet Paper Holder):
- main_image_url: Shows product with toilet paper (obscured)
- Alternative 2/3: Likely show product without paper (clear detail)
```

#### Issue 2: Generic Scene Not Tailored to Product

**Example:** All products get same "modern bathroom" scene
- **Problem:** Glass shelf, towel bar, toilet paper holder all in identical white tile bathroom
- **Impact:** Images look repetitive, lack product-specific context
- **Root Cause:** `get_scene_context()` only uses collection style, not product category
- **Solution Needed:** Make scenes product-category-aware

**Current (Generic):**
```python
scene = get_scene_context(style="modern")
# Returns: "Modern bathroom with white tiles..." (same for all products)
```

**Needed (Product-Specific):**
```python
scene = get_scene_context(style="modern", category="Glass Shelf")
# Returns: "Modern bathroom vanity area, glass shelf mounted above sink,
#           holding premium skincare products, amber glass bottles..."

scene = get_scene_context(style="modern", category="Towel Bar")
# Returns: "Modern shower wall, towel bar mounted outside glass enclosure,
#           plush white towel hanging naturally..."
```

#### Issue 3: Incorrect Product Usage in Scene

**Example:** Glass shelf with towel draped over it (from your screenshot)
- **Problem:** People don't drape towels on glass shelves - they store items on them
- **Impact:** Scene doesn't match real-world product use
- **Root Cause:** Scene templates don't specify correct product usage
- **Solution Needed:** Add product-category-specific usage rules

**Product Usage Rules (Missing):**

| Product Category | Correct Usage | Incorrect Usage |
|------------------|---------------|-----------------|
| Towel Bar | Towels hanging from bar | Towels folded on top |
| Glass Shelf | Toiletries/items stored ON shelf | Towels draped OVER shelf |
| Toilet Paper Holder | Toilet paper on holder | Empty holder |
| Robe Hook | Robe/towel hanging FROM hook | Items placed ON hook |
| Towel Ring | Towel pulled THROUGH ring | Towel wrapped AROUND ring |

---

## Data Available for Improvements

### Product Catalog Fields

The CSV contains rich metadata we're not yet using:

```csv
Category: "Towel Bar", "Glass Shelf", "Toilet Paper Holder", etc.
Collection: "Argo", "Monte Carlo", "Prestige Regal", etc.
Style: Can be inferred from collection metadata
Main URL: Primary product image (currently used)
sn: Dimensions diagram (shows product clearly without styling)
Alternative 2-4: Additional product angles (NOT CURRENTLY USED)
Bullet 1-6: Product features and benefits
Narraive Copy: Marketing description of product
Material: "Brass", "Glass", etc.
Finish: "Polished Chrome", "Antique Brass", etc.
Mounting type: "Wall mount", "Cabinet mount", etc.
```

### Collection Metadata

Located in `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/enrichment/collection-metadata.json`:

```json
{
  "Argo": {
    "design_style": "contemporary",
    "aesthetic_keywords": ["clean lines", "minimalist", "geometric"],
    "target_customer": "Modern homeowners",
    "price_tier": "mid-range"
  },
  "Monte Carlo": {
    "design_style": "traditional",
    "aesthetic_keywords": ["ornate", "classic", "decorative"],
    "target_customer": "Traditional/luxury homeowners",
    "price_tier": "premium"
  }
}
```

---

## Proposed Improvements

### Priority 1: Multi-Image Reference System

**Current:** Only uses `main_image_url`
**Problem:** Main image may be styled (toilet paper, towels, etc.) obscuring product
**Solution:** Use all available product images as reference

**Implementation:**
```python
def get_product_images(parent_sku: ParentSKU) -> list[str]:
    """Get all available product reference images."""
    images = []

    # Primary image
    if parent_sku.variants and parent_sku.variants[0].main_image_url:
        images.append(parent_sku.variants[0].main_image_url)

    # Additional angles (from CSV Alternative 2, 3, 4 columns)
    if hasattr(parent_sku, 'alternative_images'):
        images.extend([img for img in parent_sku.alternative_images if img])

    return images

# Usage in prompt
reference_images = get_product_images(parent_sku)
prompt = f"""
CRITICAL: Replicate the EXACT product shown in these reference images.
Reference Image 1: {reference_images[0]} (primary view)
Reference Image 2: {reference_images[1]} (detail view - use for accurate components)
Reference Image 3: {reference_images[2]} (alternate angle)

Focus on Image 2 for component details if Image 1 has staging elements.
"""
```

### Priority 2: Product-Category-Specific Scenes

**Current:** Same scene for all product types
**Problem:** Glass shelf gets towel bar scene
**Solution:** Map category to appropriate scene context

**Implementation:**
```python
def get_scene_context(style: str, category: str) -> str:
    """Generate scene based on style AND product category."""

    # Base environment from style
    if style == "contemporary":
        base_env = "Modern bathroom with white large-format tiles, "
    else:
        base_env = "Traditional bathroom with cream subway tiles, "

    # Product-specific scene
    if "Glass Shelf" in category:
        return base_env + """
        glass shelf mounted above floating vanity.
        Premium toiletries organized on shelf: amber glass serum bottles,
        white ceramic soap dispenser, small succulent plant.
        Shelf holds decorative items, NOT towels.
        Soft lighting creates reflections in glass.
        """

    elif "Towel Bar" in category:
        return base_env + """
        towel bar mounted on shower wall outside glass enclosure.
        Plush towel hanging naturally from the bar (not folded).
        Towel shows natural drape and weight.
        Bar positioned at 48" height for accessibility.
        """

    elif "Toilet Paper Holder" in category:
        return base_env + """
        toilet paper holder mounted on wall next to toilet.
        White premium toilet paper roll on holder.
        Holder positioned at standard 26" height.
        Clean, minimal surrounding area.
        """

    elif "Robe Hook" in category:
        return base_env + """
        robe hook mounted on wall near shower entry.
        Plush white bathrobe hanging FROM hook (not draped over).
        Single hook with robe showing natural hang.
        """
```

### Priority 3: Product Usage Validation

**Current:** No validation that scene matches product use
**Problem:** Towels on glass shelves, empty toilet paper holders
**Solution:** Add usage rules enforcement

**Implementation:**
```python
PRODUCT_USAGE_RULES = {
    "Glass Shelf": {
        "correct_usage": "toiletries, skincare products, decorative items stored ON shelf",
        "incorrect_usage": "towels, robes, or fabric items draped OVER shelf",
        "constraint": "CRITICAL: Shelf must hold items, NOT have towels draped on it"
    },
    "Towel Bar": {
        "correct_usage": "towel hanging FROM bar showing natural drape",
        "incorrect_usage": "towel folded on top, multiple towels stacked",
        "constraint": "CRITICAL: Single towel must hang naturally from bar"
    },
    "Toilet Paper Holder": {
        "correct_usage": "toilet paper roll installed on holder",
        "incorrect_usage": "empty holder, towel on holder",
        "constraint": "CRITICAL: Must show toilet paper on holder"
    }
}

def get_usage_constraints(category: str) -> str:
    """Get strict usage rules for product category."""
    rules = PRODUCT_USAGE_RULES.get(category, {})
    return f"""
    USAGE CONSTRAINTS:
    ✅ Correct: {rules.get('correct_usage', '')}
    ❌ Forbidden: {rules.get('incorrect_usage', '')}

    {rules.get('constraint', '')}
    """
```

---

## Cost & Performance

### API Costs
- Model: `gemini-3-pro-image-preview`
- Cost per image: ~$0.50
- 3 variations per product: ~$1.50
- 41 collection heroes: ~$61.50 total
- Full catalog (500+ products): ~$750

### Generation Time
- Single image: 15-30 seconds
- 3 variations: 45-90 seconds
- Pipeline integration adds ~60 seconds per product

### Quality Metrics (Target)
- Product accuracy: 90%+ (visual match to reference)
- Scene relevance: 95%+ (appropriate context)
- Usability: 80%+ (at least 1 of 3 variations acceptable)

---

## Example Outputs

### Success Case: Argo Towel Bar (Contemporary)

**Reference Image:** Clear view of polished chrome towel bar
**Generated Scene:** Modern white bathroom, single charcoal towel hanging naturally
**Product Accuracy:** 95% - Correct backplate shape, finish, proportions
**Scene Relevance:** 100% - Towel hanging correctly, clean modern aesthetic
**Result:** ✅ Approved for use

### Failure Case: Glass Shelf with Towel (Your Example)

**Reference Image:** Clear view of glass shelf with brass mounting
**Generated Scene:** Modern bathroom with glass shelf
**Product Accuracy:** 85% - Shelf and mounts look correct
**Scene Relevance:** 0% - Towel draped OVER shelf (incorrect usage)
**Result:** ❌ Rejected - Wrong product usage

### Failure Case: Toilet Paper Holder (Your Example)

**Reference Image:** Product WITH toilet paper rolls (obscured detail)
**Generated Scene:** Bathroom with toilet paper holder
**Product Accuracy:** 60% - Missing backplate details due to obscured reference
**Scene Relevance:** 90% - Toilet paper on holder (correct usage)
**Result:** ❌ Rejected - Inaccurate product detail

---

## Testing Protocol

### How to Test Changes

1. **Run single product test:**
   ```bash
   cd /Users/bobby/Documents/GitHub/Allied-FeedOps
   poetry run python test_lifestyle_integration.py
   ```

2. **Review generated images:**
   - Check `data/lifestyle_images/` for output files
   - Verify product accuracy (90%+ visual match)
   - Verify scene relevance (appropriate context)
   - Verify usage correctness (product used correctly)

3. **View on dashboard:**
   ```bash
   streamlit run src/feedops/quality/review_dashboard.py
   ```

4. **Validate JSON exports:**
   - Check `exports/google-patch-{sku}.json`
   - Verify `lifestyle_images` array exists
   - Verify `selected_lifestyle_image` field

### Quality Checklist

For each generated image, verify:

- [ ] **Product Components:** Backplate, end caps, bar/shelf/holder match reference
- [ ] **Finish Accuracy:** Chrome/brass/bronze looks correct
- [ ] **Proportions:** Product dimensions look accurate
- [ ] **Scene Context:** Bathroom style matches collection (modern/traditional)
- [ ] **Product Usage:** Item used correctly (towels on bars, toiletries on shelves)
- [ ] **Photography:** Professional quality, good lighting, sharp focus
- [ ] **Brand Fit:** Looks like Allied Brass marketing material

---

## File Locations Reference

### Implementation Files
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/lifestyle_images.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/models/candidate.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/optimize.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/pipeline/reporter.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/quality/data_loader.py`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/quality/review_dashboard.py`

### Data Files
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/catalog/Product Catalog.csv`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/enrichment/collection-metadata.json`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/data/lifestyle_images/` (generated images)

### Testing & Reference
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/test_lifestyle_integration.py`
- `/Users/bobby/Documents/GitHub/google-analytics-mcp/generate_lifestyle_images_production.py` (original working code)
- `/Users/bobby/Documents/GitHub/google-analytics-mcp/test_revised_prompts.py` (prompt testing)

---

## Next Steps

1. **Implement Multi-Image Reference** - Use Alternative image URLs for better product detail
2. **Enhance Scene Mapping** - Make scenes product-category-specific
3. **Add Usage Constraints** - Enforce correct product usage in scenes
4. **Test with 30 SKUs** - Validate improvements across eval set
5. **Iterate on Failures** - Refine prompts based on error patterns

---

**Document Version:** 1.0
**Last Updated:** 2026-01-25
**Status:** Active - Ready for improvements
