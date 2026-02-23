# Evaluation Results

## Round 1 Summary

| # | SKU | Category | Title Winner | Desc Winner | New Won Title? | New Won Desc? | Differentiation | Notes |
|---|-----|----------|:-:|:-:|:-:|:-:|:-:|-------|
| 1 | 1025U | Paper Towel Holders | B (OLD) | A (NEW) | No | Yes | Yes | New desc better but mentions 28 finishes on variant listing |
| 2 | 1016 | Towel Rings | B (OLD) | A (NEW) | No | Yes | No | Both too dimension-focused, not enough design/style |
| 3 | 102 | Cabinet Hardware | A (OLD) | B (NEW) | No | Yes | Yes | New has good opening line, better differentiation |
| 4 | 1020-3 | Multi Hooks | B (OLD) | B (OLD) | No | No | No | New too "cute"/fluffy, old too spec-heavy |
| 5 | 1024 | Toilet Paper Holders | B (OLD) | B (OLD) | No | No | No | New has FACTUALLY INCORRECT claims (spring-loaded) |
| 6 | 1020 | Robe Hooks | B (OLD) | B (OLD) | No | No | No | New too fluffy, old too straightforward |
| 7 | DMF-2/2X | Make-Up Mirrors | TIE | B (OLD) | No | No | No | Neither identifies differentiators correctly |
| 8 | WP-2/16-GAL | Glass Shelves | B (OLD) | A (NEW) | No | Yes | Yes | Good opening but wrong use cases (tub wall?) |
| 9 | 1098 | Shower Curtain | A (OLD) | B (NEW) | No | Yes | No | Gets differentiation wrong — real value is aesthetic |
| 10 | CL-22 | Retractable Hooks | B (OLD) | A (NEW) | No | Yes | No | Differentiation attempts feel unnatural |

**Title wins (new):** 0/10 ✗✗ (target: 8/10)
**Description wins (new):** 6/10 ✗ (target: 8/10)
**Differentiation passes:** 3/10 ✗✗ (target: 8/10)
**Pass criteria:** NOT MET — iteration required

## Root Cause Analysis

### Issue 1: Titles never include finish name (0/10 new titles won)

**Root cause:** The `/regenerate` endpoint generates content for the master SKU without passing `finish_code`. Without finish context, GPT-5.2 generates generic titles like "Towel Ring 6-Inch Solid Brass" instead of "Antique Bronze 6-Inch Solid Brass Towel Ring". The old titles include specific finish names because they were generated differently.

**The prompt says:** "Google/Bing title requirements: Product type in first 30 chars" but does NOT mandate finish name inclusion.

**Fix:** The SYSTEM_PROMPT platform_rules must explicitly require finish name in Google/Bing titles when finish context is provided. Additionally, the default regeneration flow should include finish context.

### Issue 2: Differentiation is generic category-level, not product-specific (3/10 pass)

**Root cause:** `prompt_builder.py` lines 284-308 inject the SAME competitive positioning bullets for EVERY product:
- "Solid brass vs die-cast zinc"
- "28 finishes vs competitors' 4-12"
- "41 collections"
- "Concealed mounting hardware"
- "Lifetime warranty"

GPT-5.2 sees these generic frames and produces generic differentiation. It doesn't know what makes *this specific product's design* special because the prompt doesn't tell it.

**Example (evaluator's words on SKU 9, shower brackets):** "The differentiator is that often times the shower rod mounts are ugly and take away from the aesthetic of the bathroom but ours are beautifully designed to enhance the room" — this is product-specific design insight that exists nowhere in the prompt.

**Fix:** Extract product-specific differentiators from the evidence table (narrative_copy, bullets, unique features). Replace generic competitive bullets with product-derived design advantages. Let the SYSTEM_PROMPT teach the model HOW to find product-specific differentiation rather than providing a fixed checklist.

### Issue 3: Customer framing is generic questions, not product-specific insight

**Root cause:** `prompt_builder.py` lines 258-282 provide only `Product category: X` and `Collection: Y` as product context, then ask GPT-5.2 generic questions like "What specific problem does this product solve?" This leads to generic openers like "Stop draping towels over the shower door" that feel manufactured.

**Fix:** Feed the product's own narrative_copy and bullet points into the customer framing block. The manufacturer's own words contain the real customer scenarios and use cases. GPT-5.2 should REWRITE and ELEVATE this existing content, not invent scenarios from scratch.

### Issue 4: "28 finishes" mentioned on variant-specific listings

**Root cause:** The competitive positioning block always mentions "28 finishes" regardless of whether the listing is for a specific variant. On a variant page (e.g., "Antique Bronze Towel Ring"), mentioning 28 other finishes is irrelevant.

**Fix:** When generating for a specific variant, omit the "28 finishes" competitive point. When generating for master SKU (Shopify), keep it.

## Proposed Fix: Broader Prompt Rewrite

### Changes to `src/feedops/pipeline/prompts.py` (SYSTEM_PROMPT)

1. **Creative direction**: Shift from "make shoppers click instead of Home Depot" to "tell this product's SPECIFIC design story." Emphasize: the differentiation comes from the PRODUCT DATA, not generic competitive frames.

2. **Add explicit title instruction**: "Google/Bing titles MUST include the specific finish name when finish context is provided."

3. **Rewrite competitive framing guidance**: Instead of "here are 5 competitive advantages," teach the model: "Find what makes this SPECIFIC product's design special from the evidence. The competitive edge is in the design details (aesthetics, how it enhances the room, craftsmanship choices), not generic material claims."

### Changes to `src/feedops/api/prompt_builder.py`

1. **Customer framing**: Extract narrative_copy and top bullets from evidence and inject them. Replace generic questions with: "Here is the manufacturer's description of this product: [narrative]. Here are the key features: [bullets]. Use these as your foundation — rewrite and elevate this content into compelling shopping copy."

2. **Competitive positioning**: Extract product-specific features from evidence (dimensions, unique mechanisms like retractable, specific materials, design details). Build a product-specific competitive context instead of the fixed 5-bullet template.

3. **Variant awareness**: When platform is Google/Bing and content is for a variant, omit "28 finishes" from competitive positioning.
