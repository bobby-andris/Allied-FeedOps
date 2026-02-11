# Gold Standard Examples - Investigation Results

## Status: FULLY POPULATED (10 examples with complete content)

## Database Details

**Table**: `prompt_templates`
**Active row**: `content-generation-v2` (id: `1a3bec14-96cb-44a3-b37d-ce7c2936eee7`)
**Column**: `gold_standard_examples` (JSONB, NOT NULL)
**Version**: `2.1.0`

## What's Inside

All 10 examples have the complete structure:

| # | SKU | Category | Google Title | Google Desc Len | Shopify Desc Len | has_why_it_works |
|---|-----|----------|-------------|-----------------|------------------|------------------|
| 1 | AP-41/24 | Towel Bars - Standard | {FINISH_NAME} 24 Inch Solid Brass Towel Bar - Wall Mounted - Astor Place - Allied Brass | 444 | 426 | YES |
| 2 | DT-41-24-HK | Towel Bars - With Hooks | {FINISH_NAME} Towel Bar with Hooks 24 Inch - Space-Saving Dual Function - Dottingham - Allied Brass | 557 | 539 | YES |
| 3 | CU-GRS-24 | Grab Bars/ADA - Safety | {FINISH_NAME} Decorative ADA Grab Bar 24 Inch - Stylish Safety Rail - Cube Design - Allied Brass | 557 | 539 | YES |
| 4 | FR-24R | Toilet Paper Holders - Rollerless | {FINISH_NAME} Rollerless Toilet Paper Holder - No Spring to Break - Fresno - Allied Brass | 578 | 560 | YES |
| 5 | CL-GLT-24 | Toilet Paper Holders - Standard | {FINISH_NAME} Toilet Paper Holder with Glass Shelf - Phone Shelf Built In - Carolina - Allied Brass | 603 | 585 | YES |
| 6 | CL-27-92 | Mirrors - Wall Mounted | {FINISH_NAME} Frameless Wall Mirror 21x26 Inch - Rail Mounted Design - Carolina - Allied Brass | 593 | 575 | YES |
| 7 | RDM-4/3X | Mirrors - Makeup/Magnifying | {FINISH_NAME} Makeup Mirror 8 Inch 3X Magnification - Wall Mount Swivel - Retro Dot - Allied Brass | 532 | 514 | YES |
| 8 | AP-1TB/22 | Shelves - Glass | {FINISH_NAME} Glass Shelf with Towel Bar 22 Inch - 2-in-1 Space Saver - Astor Place - Allied Brass | 589 | 571 | YES |
| 9 | BSK-275LA | Shower Accessories - Basket | {FINISH_NAME} Shower Basket Caddy - Rust Proof Solid Brass - Wall Mount - Allied Brass | 620 | 602 | YES |
| 10 | CL-22 | Statement/Niche - Retractable | {FINISH_NAME} Retractable Wall Hook - Push Back When Not in Use - Carolina - Allied Brass | 593 | 575 | YES |

## Each Example Contains

Per-example keys: `index`, `style`, `title`, `category`, `material`, `collection`, `master_sku`, `source_data`, `why_selected`, `product_length`, `gold_standard_content`

### `gold_standard_content` sub-keys:
- `google_title` - Full Google/Bing title with {FINISH_NAME} placeholder
- `google_description` - Full Google/Bing description (444-620 chars)
- `shopify_title` - Shopify-specific title (no finish, no brand suffix)
- `shopify_description` - Shopify-specific description (426-602 chars)
- `why_it_works` - Explanation of quality for few-shot calibration

### `source_data` sub-keys (input evidence):
- `bullets` - Product bullet points from catalog
- `narrative_copy` - Marketing narrative

## Also Populated in prompt_templates

- **`category_guidance`** (JSONB): Has guidance for categories including "Shelves - Glass", "Towel Bars - Standard", "Grab Bars/ADA - Safety", "Mirrors - Wall Mounted", etc.
- **`platform_rules`** (JSONB): Has rules for `bing`, `google`, and `shopify` platforms including title structure, brand suffix, description placeholders.

## Code That Consumes Gold Examples

### Python (runtime authority):
- `src/feedops/api/prompt_loader.py`:
  - `format_gold_standard_examples()` - Single-platform formatter (lines 184-243)
  - `format_gold_standard_examples_bundle()` - Cross-platform formatter (lines 246-299)
  - Reads from `gold_standard_content` sub-object: `google_title`, `google_description`, `shopify_title`, `shopify_description`, `why_it_works`
- `src/feedops/pipeline/generator.py`:
  - Uses `format_gold_standard_examples_bundle(max_examples=2)` in 3 places (lines 145, 179, 467)
  - Injected as `## Gold Standard Examples` section into generation prompts

### TypeScript (legacy/reference):
- `dashboard/src/lib/prompts/loader.ts` (line 145) - reads `gold_standard_examples.examples`

## Previous Audit Discrepancy Explained

The earlier audit that reported "0 gold standard examples" likely checked for `generated_content` key (which is indeed absent) rather than `gold_standard_content` key (which IS present and populated). The field name is `gold_standard_content`, not `generated_content`.

## Conclusion

**Gold standard examples ARE fully populated and actively wired into the generation pipeline.** The system has 10 diverse examples spanning 10 product categories, each with complete cross-platform content (Google/Bing + Shopify) including titles, descriptions, and quality explanations. The Python generator injects up to 2 of these as few-shot examples in every generation prompt.

### Signal Strength Assessment
- **Data completeness**: 10/10 (all examples have full content)
- **Code integration**: ACTIVE (generator.py calls format_gold_standard_examples_bundle in 3 places)
- **Diversity**: 10 distinct categories covered
- **No action needed**: Examples are present and wired in
