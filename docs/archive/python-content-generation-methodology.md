# Python Content Generation Methodology

This document details the exact methodology implemented in the Python pipeline for generating product titles and descriptions. It serves as a reference for comparing and potentially unifying approaches with the TypeScript dashboard.

## Overview

The Python content generation system lives primarily in:
- `src/feedops/pipeline/prompts.py` - SYSTEM_PROMPT, templates, JSON schema
- `src/feedops/pipeline/generator.py` - Candidate generation and parsing
- `src/feedops/pipeline/evidence.py` - Evidence table builder
- `src/feedops/pipeline/optimize.py` - Full optimization pipeline orchestrator
- `src/feedops/pipeline/keyword_placement.py` - Keyword placement plan
- `src/feedops/pipeline/enrichment.py` - Design context, features, competitive positioning
- `src/feedops/pipeline/finish_injection.py` - Variant-specific finish context

## Core Philosophy: Comprehensive Rules + Examples

The Python system uses a **rule-based approach with extensive examples**:

```
APPROACH:
- P0 rules (MUST FOLLOW) = hard validation
- P1 rules (SHOULD FOLLOW) = scored
- P2 rules (NICE TO HAVE) = bonus quality
- GOOD examples = show desired output style
- BAD examples = anti-patterns with explanations
- Self-scoring rubric = LLM rates itself
```

## Architecture: Single-Call Multi-Platform Generation

### Stage 1: Evidence Table Building (`evidence.py`)

Builds structured evidence from ParentSKU model:

```python
def build_evidence_table(parent_sku: ParentSKU) -> list[Evidence]:
    evidence = []

    # Parent-level fields
    parent_fields = [
        ("master_sku", "MasterSKU"),
        ("category", "Category"),
        ("collection", "Collection"),
        ("current_title", "Current Title"),
        ("current_description", "Current Description"),
        ("material", "Material"),
        ("style", "Style"),
        ("shape", "Shape"),
        ("orientation", "Orientation"),
        ("mounting_type", "Mounting Type"),
        ("weight_capacity", "Weight Capacity"),
        ("bullet_1", "Bullet 1"),
        # ... through bullet_6
    ]

    # Variant-level fields (from first variant)
    variant_fields = [
        ("product_length", "Length"),
        ("product_height", "Height"),
        ("product_width", "Width"),
        ("main_image_url", "Main Image URL"),
    ]

    # Available finishes from all variants
    # Available sizes (if multi-size product)

    # External keywords from keyword bank
    # Keyword intent (filtered for finish-neutral terms)

    # On-the-fly enrichment
    enrichment = enrich_product(parent_sku)
    evidence.extend(enrichment.to_evidence_rows())

    return evidence
```

Evidence is formatted as markdown table:

```markdown
## Available Product Data

| Attribute | Value | Source |
|-----------|-------|--------|
| master_sku | 1051 | master_sku |
| category | Paper Towel Holders | category |
| material | Solid Brass | material |
| product_length | 14 in | product_length |
...
```

### Stage 2: Keyword Placement Plan (`keyword_placement.py`)

Builds strategic keyword plan:

```python
def build_keyword_placement_plan(
    parent_sku: ParentSKU,
    evidence: list[Evidence]
) -> KeywordPlan:
    return KeywordPlan(
        primary_keyword="paper towel holder",  # Must appear in titles
        secondary_keywords=["kitchen", "countertop"],  # For descriptions
        bing_synonyms=["paper towel stand", "kitchen roll holder"],
        design_intent_keywords=["modern", "transitional"],  # From enrichment
    )
```

### Stage 3: LLM Generation (`generator.py`)

Single API call generates ALL platforms at once:

```python
async def generate_candidates(
    parent_sku: ParentSKU,
    llm: LLMProvider,
    n: int,
    reasoning_effort: str | None = None,
) -> tuple[list[Candidate], list[str]]:

    # Build cache-optimized split prompt
    system_prompt, user_prompt = build_split_prompt(parent_sku)

    # Optional: fetch product image for vision
    image = None
    if parent_sku.variants:
        image = await fetch_image(parent_sku.variants[0].main_image_url)

    # Call LLM with structured output
    response = await llm.generate_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema=CANDIDATE_SCHEMA,
        image=image,
        n=n,
    )

    # Parse response into Candidate model
    candidates = [parse_candidate_response(r) for r in response]

    # Retry if titles are too short
    for candidate in candidates:
        short_fields = _needs_title_retry(candidate)
        if short_fields:
            # Retry with explicit length instruction
            ...

    return candidates, errors
```

## The CANDIDATE_SCHEMA (JSON Output Structure)

```python
CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "google_title": {
            "type": "string",
            "description": "Google Shopping title (max 150 characters)",
            "maxLength": 150,
        },
        "google_short_title": {
            "type": "string",
            "description": "Google short title (max 70 characters)",
            "maxLength": 70,
        },
        "google_description": {
            "type": "string",
            "description": "Google Shopping description (target 600-800 characters)",
        },
        "bing_title": {
            "type": "string",
            "description": "Bing Shopping title (max 150 characters)",
            "maxLength": 150,
        },
        "bing_description": {
            "type": "string",
            "description": "Bing Shopping description (target 700-1000 characters)",
        },
        "shopify_title": {
            "type": "string",
            "description": "Shopify product title (max 255 characters)",
            "maxLength": 255,
        },
        "shopify_description": {
            "type": "string",
            "description": "Shopify product description (HTML allowed)",
        },
        "shopify_meta_description": {
            "type": "string",
            "description": "Shopify SEO meta description (target 140-155 characters)",
            "maxLength": 155,
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "source_field": {"type": "string"},
                    "source_value": {"type": "string"},
                },
                "required": ["claim", "source_field", "source_value"],
            },
        },
        "self_score": {
            "type": "object",
            "properties": {
                "specificity": {"type": "integer", "minimum": 0, "maximum": 10},
                "benefit_coverage": {"type": "integer", "minimum": 0, "maximum": 10},
                "keyword_inclusion": {"type": "integer", "minimum": 0, "maximum": 10},
                "format_adherence": {"type": "integer", "minimum": 0, "maximum": 10},
                "brand_voice": {"type": "integer", "minimum": 0, "maximum": 10},
                "factual_accuracy": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": [...all six dimensions...],
        },
    },
    "required": [...all fields...],
}
```

## The SYSTEM_PROMPT (~302 lines)

### P0: MUST FOLLOW (Hard Validation)

```
PRODUCT IDENTITY:
- Determine what this specific product actually is before writing
- Use current_title, current_description, bullets, and image to identify exact product type
- Name it the way a shopper would search for it

TITLE SUCCESS CRITERIA:
- Product type appears in first 30 characters (mobile truncation)
- Key dimension appears before character 70
- "Allied Brass" is the final segment
- google_title and bing_title: minimum 60 characters, target 70-100, max 150
- Title MUST include: product type, primary dimension, material OR mount type, brand
- Never start with banned adjectives: Premium, Luxury, Best, High-Quality, Top-Rated

DESCRIPTION SUCCESS CRITERIA:
- WHO is searching (homeowner, designer, someone replacing)
- WHAT questions they have ($80 vs $20 Amazon alternative)
- WHY Allied Brass is worth it (style, personalization, innovation, durability)

PLATFORM CONTEXT:
- Google/Bing (variant): First impression, make them click
- Shopify (master): Already clicked, help them buy

FACTUAL ACCURACY:
- Never invent specifications
- Every claim traceable to evidence table
- Keywords are search intent signals, NOT product facts

BANNED CONTENT:
- No source citations, no internal SKU codes
- No internal terminology (MasterSKU, finish injection, evidence table)
- No ALL CAPS, no URLs, no pricing
- BANNED WORDS: finest, luxurious, premium, exclusive, exceptional, etc.
```

### P1: SHOULD FOLLOW (Scored)

```
PRODUCT INNOVATION CONTEXT:
- Shower baskets: ventilated wires drain water
- Grab bars: decorative ADA compliance
- Toilet paper holders: rollerless, multi-roll, recessed
- Towel bars: double bars, integrated hooks
- Garment rods: retractable
- Mirrors: tilting, magnifying, swing arm

BRAND VOICE:
- Confident, specific phrasing ("crafted", "enduring")
- Direct statements ("provides" not "helps provide")
- Highlight: solid brass, lifetime warranty, 28 finishes, 42+ collections

DESIGN CONTEXT:
- Use collection_context, design_style, feature_benefits when available

ROOM CONTEXT:
- Kitchen products: use "kitchen" only
- Bathroom products: use "bathroom" or "bath" only
```

### P2: NICE TO HAVE (Bonus Quality)

```
- Natural query language: "18-Inch" not "18in"
- Confirm details against image if provided
- Meta description NOT a truncation
- Short title works as overlay label
- Installation ease messaging when supported
```

### GOOD EXAMPLES (4 detailed examples with WHY IT WORKS)

```
GOOD GOOGLE DESCRIPTION (finish-specific variant):
"This 14-inch freestanding paper towel holder in Polished Chrome keeps kitchen roll within reach.
The mirror-like finish coordinates with chrome faucets and modern fixtures..."

WHY IT WORKS: Finish woven naturally into opening. Each sentence adds value. No repetition.
Answers "will it tip?" and "will it scratch my counter?"
```

### ANTI-PATTERNS (5+ examples with WHY it's bad)

```
BAD GOOGLE/BING DESCRIPTION: "Finished in Antique Brass, shower basket, 18.75 in L x 2.25 in H..."

WHY: Opens with dimension dump in first sentence. The structure is robotic.
```

### SCORING RUBRIC (6 Dimensions with Checklists)

```
Score each dimension by counting how many required elements are present:
- 10 = ALL required elements present
- 7-9 = missing 1-2 required elements
- 4-6 = missing 3+ required elements
- 1-3 = fundamentally wrong
- 0 = not attempted

1. Specificity (5 checklist items)
2. Benefit Coverage (5 checklist items)
3. Keyword Inclusion (5 checklist items)
4. Format Adherence (6 checklist items)
5. Brand Voice (5 checklist items)
6. Factual Accuracy (5 checklist items)
```

## Category-Specific Guidance

```python
_CATEGORY_GUIDANCE = {
    "niche_functional": {
        "categories": ["retractable", "garment rod", "cabinet pull", "squeegee", ...],
        "guidance": """CATEGORY NOTE: Niche/functional product. Focus on WHY THIS ONE
        over competitors (material quality, dimensions, mounting system)...""",
    },
    "towel_storage": {
        "categories": ["towel bar", "towel ring", "towel holder", ...],
        "guidance": """CATEGORY NOTE: High-competition category. Differentiate on
        construction (solid brass vs die-cast zinc), finish variety...""",
    },
    "safety_ada": {
        "categories": ["grab bar", "ada"],
        "guidance": """CATEGORY NOTE: Safety-critical product. Lead with functional
        assurance (weight capacity, ADA compliance, mounting security)...""",
    },
}
```

## Finish Injection (for Variant Generation)

For Google/Bing variants, the `FINISH_CONTEXT_TEMPLATE` is injected:

```python
FINISH_CONTEXT_TEMPLATE = """
=== VARIANT CONTEXT ===
This content is for a SPECIFIC FINISH VARIANT, not the master SKU.
Generate finish-specific content for: {finish_name}

FINISH DETAILS:
- Finish name: {finish_name}
- Category: {finish_category}
- Character: {finish_character}
- Style context: {style_context}

INTEGRATION REQUIREMENTS:
- Weave "{finish_name}" naturally into the FIRST SENTENCE
- Do NOT use "Available in {finish_name}. {finish_name} features..." pattern

GOOD INTEGRATION:
- "This 18-inch towel bar in {finish_name} coordinates with..."

BAD INTEGRATION:
- "Available in {finish_name}. {finish_name} features a..."
"""
```

## Claims Tracing

Every factual claim in the output must map to evidence:

```json
{
  "claims": [
    {
      "claim": "14-inch freestanding paper towel holder",
      "source_field": "product_length",
      "source_value": "14 in"
    },
    {
      "claim": "solid brass construction",
      "source_field": "material",
      "source_value": "Solid Brass"
    },
    {
      "claim": "lifetime warranty",
      "source_field": "warranty",
      "source_value": "Limited Lifetime"
    }
  ]
}
```

## Self-Scoring

The LLM rates its own output:

```json
{
  "self_score": {
    "specificity": 9,
    "benefit_coverage": 8,
    "keyword_inclusion": 7,
    "format_adherence": 10,
    "brand_voice": 8,
    "factual_accuracy": 10
  }
}
```

## Output Processing

### Title Normalization

```python
def _normalize_title_separators(title: str) -> str:
    """
    - Convert pipes to commas
    - Remove empty segments and dangling punctuation
    - Ensure 'Allied Brass' appears once as the last segment
    """

def _trim_title_to_length(title: str, max_len: int) -> str:
    """
    - Drop least-critical trailing segments first
    - Preserve brand at end
    - Hard truncate at word boundary if needed
    """
```

### Title Retry Logic

```python
_MIN_TITLE_LENGTH = 60

def _needs_title_retry(candidate: Candidate) -> list[str]:
    """If google_title or bing_title < 60 chars, retry with explicit instruction."""
```

## File-Based Output

Python generates patch files for each platform:

```
dashboard_data/{batch_name}/
  google-patch-1051.json
  bing-patch-1051.json
  shopify-patch-1051.json
  reports/
    1051-report.md
```

### Patch File Structure

```json
{
  "master_sku": "1051",
  "platform": "google",
  "variants": [
    {
      "variant_sku": "1051-ABR",
      "finish": "Antique Brass",
      "title": "...",
      "description": "..."
    }
  ]
}
```

## Key Differences from TypeScript

| Aspect | Python | TypeScript |
|--------|--------|------------|
| **Output format** | Structured JSON with all platforms | Plain text, one platform at a time |
| **API calls per SKU** | 1 call (all platforms) | 6 calls (title + desc × 3 platforms) |
| **Character limits** | Enforced in schema | Not enforced |
| **Examples** | 4 good, 5+ bad with explanations | None |
| **Self-scoring** | Required in output | None |
| **Claims tracing** | Required in output | None |
| **Category guidance** | 3 category types | None |
| **Storage** | JSON patch files | Supabase tables |
| **Finish handling** | Generation-time per variant | Display-time composition |
| **Prompt length** | ~302 lines | ~45 lines |

## Prompt Caching Strategy

The SYSTEM_PROMPT is static (byte-for-byte identical across all SKUs):

```python
def build_split_prompt(parent_sku: ParentSKU) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt) tuple.

    system_prompt: Identical across all requests → OpenAI prompt caching
    user_prompt: Per-SKU evidence, keywords, schema
    """
    return SYSTEM_PROMPT, user_prompt
```

## Example Full Output

```json
{
  "google_title": "14-Inch Countertop Paper Towel Holder, Solid Brass, Allied Brass",
  "google_short_title": "14-Inch Countertop Paper Towel Holder",
  "google_description": "This 14-inch freestanding paper towel holder keeps kitchen roll within reach. Solid brass construction with weighted base prevents tipping while the felt pad protects countertops. Compact 5x5 inch footprint fits beside the sink or stove. Choose from 28 designer finishes. Backed by a limited lifetime warranty.",
  "bing_title": "14-Inch Freestanding Paper Towel Holder Stand, Solid Brass, Allied Brass",
  "bing_description": "This 14-inch freestanding paper towel holder stand keeps kitchen roll within easy reach on your countertop. The solid brass paper towel stand features a weighted base that prevents tipping while the felt pad protects your counter surface. Compact 5x5 inch footprint fits beside the sink or stove. Kitchen roll holder available in 28 designer finishes to match your fixtures. Backed by Allied Brass's limited lifetime warranty.",
  "shopify_title": "14-Inch Countertop Paper Towel Holder",
  "shopify_description": "<p>Tired of flimsy paper towel holders that tip over every time you tear a sheet? This solid brass paper towel holder features a weighted base that stays put. Backed by a lifetime warranty.</p><ul><li>14-inch height accommodates jumbo rolls</li><li>Solid brass construction outlasts plastic alternatives</li><li>Felt pad protects countertops from scratches</li><li>Choose from 28 designer finishes to match your kitchen</li></ul>",
  "shopify_meta_description": "Solid brass countertop paper towel holder with weighted base. 14-inch height fits jumbo rolls. 28 finishes. Lifetime warranty. Free shipping.",
  "claims": [
    {"claim": "14-inch", "source_field": "product_length", "source_value": "14 in"},
    {"claim": "solid brass", "source_field": "material", "source_value": "Solid Brass"},
    {"claim": "28 finishes", "source_field": "available_finishes", "source_value": "28"}
  ],
  "self_score": {
    "specificity": 9,
    "benefit_coverage": 9,
    "keyword_inclusion": 8,
    "format_adherence": 10,
    "brand_voice": 8,
    "factual_accuracy": 10
  }
}
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `src/feedops/pipeline/prompts.py` | SYSTEM_PROMPT, CANDIDATE_SCHEMA, templates |
| `src/feedops/pipeline/generator.py` | generate_candidates, parse_candidate_response |
| `src/feedops/pipeline/evidence.py` | build_evidence_table, format_evidence_markdown |
| `src/feedops/pipeline/optimize.py` | optimize_parent_sku orchestrator |
| `src/feedops/pipeline/keyword_placement.py` | build_keyword_placement_plan |
| `src/feedops/pipeline/enrichment.py` | enrich_product (design context, features) |
| `src/feedops/pipeline/finish_injection.py` | get_finish_metadata |
| `src/feedops/pipeline/verifier.py` | verify_claims against evidence |
| `src/feedops/pipeline/reporter.py` | generate_all_variant_patches |
| `src/feedops/models.py` | ParentSKU, Variant, Candidate, Claim, Score models |
