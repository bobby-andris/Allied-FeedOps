"""Prompt templates and JSON schemas for LLM."""

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
            "description": "Google Shopping description (min 500 characters recommended)",
        },
        "bing_title": {
            "type": "string",
            "description": "Bing Shopping title (max 150 characters)",
            "maxLength": 150,
        },
        "bing_description": {
            "type": "string",
            "description": "Bing Shopping description (min 500 characters recommended)",
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
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "The claim text"},
                    "source_field": {"type": "string", "description": "Field name from evidence table"},
                    "source_value": {"type": "string", "description": "Value from that field"},
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
            "required": [
                "specificity", "benefit_coverage", "keyword_inclusion",
                "format_adherence", "brand_voice", "factual_accuracy"
            ],
        },
    },
    "required": [
        "google_title",
        "google_short_title",
        "google_description",
        "bing_title",
        "bing_description",
        "shopify_title",
        "shopify_description",
        "claims",
        "self_score",
    ],
}

SYSTEM_PROMPT = """You are a product feed optimization specialist for Allied Brass bathroom hardware.

Your task is to create optimized product titles and descriptions for Google Shopping, Bing Shopping,
and Shopify using ONLY the provided product data and image (if available).

Unified research: Title and description are equally important outputs. Use the same evidence,
keywords, and buyer intent analysis to craft both.

CRITICAL RULES:
- No source citations in customer-facing fields (titles/descriptions). Titles/descriptions must be citation-free.
  Never include catalog_csv.* or (catalog_csv.*) references in customer-facing text.
- Only the claims array may include source attribution (source_field/source_value). Titles/descriptions
  must be clean.
- Never invent specifications not in the data.
- If an image is provided, confirm material, finish, color, and visible features against it.
  Do not describe features that are not visible in the image and not present in data.
- Allied Brass is a niche brand: lead with benefits/keywords and place the brand at the end.
- Title zones: 1-30 characters (mobile) and 31-70 characters (desktop) are most critical. Front-load
  product type, primary dimension, and key benefit.
- No promotional language, ALL CAPS, URLs, pricing, or shipping text.

Platform-specific guidance:
Google Shopping / Performance Max:
- Semantic matching allows synonyms, but front-loaded keywords still matter.
- Feed is a seed prompt for PMax asset generation; content must work across Search, Display, and YouTube.
- Provide a clean google_short_title for overlays.
- Keep descriptions plain text (avoid HTML).

Microsoft / Bing Shopping:
- More literal matching; include explicit synonyms in descriptions.
- Brand is required in titles; include it even if placed at the end.
- Copilot confidence improves with complete, specific attributes.

Shopify (On-Site):
- Title becomes H1; prioritize clarity and SEO.
- First ~155 characters may appear as the meta snippet.
- Description should be HTML with a <p> hook, <ul><li> highlights, and specs/warranty detail."""

OPTIMIZATION_TEMPLATE = """
{system_prompt}

{evidence_table}

## Title Structure Formula (niche brand)
[Key Benefit/Use Case] + [Product Type] + [Key Dimension] + [Material/Finish] + [Brand]

Example: 24-Inch Wall Mount Towel Bar Solid Brass | Polished Chrome | Allied Brass

## Description Structure (shared research, platform-specific formatting)
1. Opening Hook (first 150 chars): Primary benefit + key spec
2. Key Highlights: 3-5 bullet points with benefit + feature
3. Detail Section: Specs, installation, warranty

## Platform Output Requirements
Output fields (must map to schema):
Google Shopping (feed):
- google_title: max 150 characters, benefit/keyword first, brand at end
- google_short_title: max 70 characters, clean overlay-friendly wording
- google_description: plain text, benefit-first opening, no HTML

Bing Shopping (feed):
- bing_title: max 150 characters, include brand, add extra keywords after 70 chars
- bing_description: plain text with explicit synonyms included naturally

Shopify (On-Site):
- shopify_title: H1-friendly, readable, SEO-aware (<=255 chars)
- shopify_description: HTML description with <p> hook, <ul><li> highlights, and specs

## Scoring Rubric (self-score each 0-10)
1. Specificity: Specific/verifiable claims vs generic
2. Benefit Coverage: Benefits in first 150 characters
3. Keyword Inclusion: Target keywords in optimal positions
4. Format Adherence: Character limits and structure
5. Brand Voice: Premium tone, no superlatives
6. Factual Accuracy: Every claim traceable to evidence

## Output Format
Respond with valid JSON matching this schema:
{schema}

Now optimize the title and description for MasterSKU: {master_sku}
"""
