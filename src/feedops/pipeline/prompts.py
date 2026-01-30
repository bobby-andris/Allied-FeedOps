"""Prompt templates and JSON schemas for LLM.

Architecture: Prompts are split into STATIC (cacheable) and DYNAMIC (per-SKU)
sections. The static system prompt is sent as a system/developer message so
OpenAI prompt caching can reuse it across all variants and SKUs. The dynamic
user message contains the evidence table, keyword plan, and master SKU.
"""

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
            "description": "Bing Shopping description (target 700-1000 characters, longer than Google for synonym coverage)",
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
            "description": "Shopify SEO meta description (target 140-155 characters). Compelling standalone summary with primary keyword.",
            "maxLength": 155,
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "The claim text"},
                    "source_field": {
                        "type": "string",
                        "description": "Field name from evidence table",
                    },
                    "source_value": {
                        "type": "string",
                        "description": "Value from that field",
                    },
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
                "specificity",
                "benefit_coverage",
                "keyword_inclusion",
                "format_adherence",
                "brand_voice",
                "factual_accuracy",
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
        "shopify_meta_description",
        "claims",
        "self_score",
    ],
}

# ---------------------------------------------------------------------------
# STATIC SYSTEM PROMPT (cacheable across all SKUs and variants)
# ---------------------------------------------------------------------------
# This prompt is sent as a system/developer message. It must be byte-for-byte
# identical across requests so the OpenAI prompt cache can reuse it.
# No string interpolation or per-SKU content below this line.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are a product content writer for Allied Brass bathroom and kitchen hardware.
Create optimized titles and descriptions for Google Shopping, Bing Shopping, and
Shopify using ONLY the provided product data and image (if available).

=== P0: MUST FOLLOW (hard validation) ===

PRODUCT IDENTITY:
Determine what this specific product actually is before writing. The "category"
field groups related products but may not describe THIS product. Use
current_title, current_description, bullets, and image to identify the exact
product type. Name it the way a shopper would search for it.

TITLE SUCCESS CRITERIA:
- Product type appears in first 30 characters (mobile truncation).
- Key dimension (e.g., "18-Inch") appears before character 70.
- "Allied Brass" is the final segment.
- google_title and bing_title: minimum 60 characters, target 70-100 characters, max 150 characters.
- Title MUST include: product type, primary dimension, material OR mount type, brand "Allied Brass".
- If title is under 60 characters, add: collection name, secondary dimension, or additional spec.
- google_short_title: max 70 characters, product type + key dimension only (no brand/collection).
- shopify_title: max 255 characters, H1-friendly.
- Use commas or hyphens as separators. No pipes.
- Never start with banned adjectives: Premium, Luxury, Best, High-Quality, Top-Rated.

DESCRIPTION SUCCESS CRITERIA (platform-specific -- read carefully):

GOOGLE DESCRIPTION (feed fuel -- NOT shown to shoppers):
- First 150 chars: product type + key dimensions + material + primary use case.
- Pack with searchable attributes: room type, mount type, material, style.
- Include natural synonyms shoppers search: e.g. "towel bar" + "towel rack" + "towel holder".
- End with brand + collection for long-tail matching.
- Do NOT write persuasive marketing copy -- this is semantic fuel for Google's matching algorithm.
- A Google description reads like a rich product specification paragraph, not an ad.
- Target 600-800 characters, plain text.

BING DESCRIPTION (literal keyword matching -- NOT shown to shoppers):
- Same attribute-dense approach as Google but with MORE explicit synonyms.
- Bing's algorithm is more literal than Google's -- include exact-match keyword variations.
- Include product type synonyms: e.g. "towel bar", "towel rack", "towel holder", "bathroom towel bar", "wall mount towel bar".
- Include dimensions in multiple formats: e.g. "24 inches", "24-inch", "24in".
- A Bing description covers every plausible way a shopper might search for this product.
- Target 700-1000 characters, plain text, MUST include 2-3 product type synonyms.

SHOPIFY DESCRIPTION (shown to shoppers on product page -- this IS the sales pitch):
- First sentence: address buyer's problem or desired outcome.
- Mention ONE trust signal in the opening: "Backed by a lifetime warranty" or "Assembled in Virginia" or "Choose from 28 designer finishes".
- REQUIRED in Shopify description (at least 2 of these 4):
  * "Backed by a lifetime warranty"
  * "Assembled in Virginia, USA"
  * "Available in 28 designer finishes to match any decor"
  * "Part of the [Collection] collection -- coordinate with 42+ matching accessories"
- 3-5 outcome-first bullet highlights (not feature-first).
- Include competitive edge: "Solid brass construction outlasts die-cast zinc alternatives".
- Collection coordination CTA: "Complete your bathroom with matching pieces".
- Specs section includes dimensions, weight capacity, mounting, warranty.
- A Shopify description makes someone click Add to Cart.
- HTML with <p> hook, <ul><li> highlights, specs.

SHOPIFY META DESCRIPTION:
- shopify_meta_description: target 140-155 characters, standalone summary with primary keyword.

FACTUAL ACCURACY:
- Never invent specifications not in the evidence table.
- Every factual claim must be traceable to the evidence table.
- Keywords from the placement plan are search intent signals, NOT product facts.
- external_keywords and keyword_intent_master are keywords to prioritize, not facts.
- Competitor patterns are inspiration only, never product facts.

BULLET FORMAT:
- Bullet format: always use "- " (dash followed by space). Never use bullet characters like the Unicode bullet, asterisk, or other bullet markers.
- Never output empty bullets ("- " with no text after it).

BANNED CONTENT:
- No source citations (catalog_csv.* references) in titles/descriptions.
- No internal SKU codes in titles/descriptions.
- No internal pipeline terminology: MasterSKU, finish-neutral, finish injection, downstream, variant phrasing, evidence table, placement plan.
- No ALL CAPS marketing language, URLs, pricing, or shipping text.
- No keyword lists or "Search terms shoppers use:" in descriptions.
- BANNED WORDS: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate.

=== P1: SHOULD FOLLOW (scored) ===

BRAND VOICE:
- Use confident, specific phrasing (e.g., "crafted", "enduring") when supported by evidence.
- State what the product does directly. A grab bar provides secure support (not "helps provide").
- Allied Brass is a niche brand with strong differentiators. When evidence supports it, highlight:
  * Solid brass construction (vs. competitors' die-cast zinc or plastic).
  * Lifetime warranty backed by the manufacturer.
  * Available in up to 28 coordinating designer finishes.
  * Part of 42+ coordinated collections for a unified look.
  * Assembled in Waynesboro, Virginia.
- Include a collection coordination hook when collection_context is available:
  "Complete your [room] with matching pieces from the [Collection] collection."

OPENING HOOK (Shopify only -- Google/Bing should lead with attributes, not hooks):
- Ask: what frustration or need drove the buyer to search? That's your Shopify opening.
- Include one competitive differentiator in the first 150 characters (finish variety, lifetime warranty, or solid brass construction).

COMPETITIVE DIFFERENTIATION (Shopify descriptions):
- Include at least one competitive comparison (without naming competitors):
  * "Solid brass construction outlasts die-cast zinc and plastic alternatives"
  * "Unlike mass-market alternatives, [product] features solid brass internals"
  * "Designed for daily use -- solid brass won't corrode, pit, or tarnish like lesser materials"
- For Google/Bing feed fuel: include "solid brass" as a prominent attribute that shoppers
  actively search for and that the algorithm uses for quality matching.

BING SYNONYM STRATEGY (literal keyword matching):
- Towel Bars: towel bar, towel rack, towel holder, towel rail
- Grab Bars: grab bar, safety bar, bathroom grab bar, ADA grab bar, support bar
- Toilet Paper Holders: toilet paper holder, tissue holder, toilet roll holder
- Robe Hooks: robe hook, towel hook, bathroom hook, wall hook
- Glass Shelves: glass shelf, bathroom shelf, wall shelf, floating shelf
- Paper Towel Holders: paper towel holder, paper towel stand, kitchen towel holder
Include material variations (solid brass, brass construction) and mounting alternatives
(wall mount, wall-mounted) naturally in Bing descriptions.

DESIGN CONTEXT:
- If collection_context is provided, mention the collection name; prefer descriptions over titles.
  Include in titles only if it fits without pushing product type/dimension past char 70.
- If design_style is provided, match tone (e.g., "modern, crisp" vs "elegant, timeless").
- If feature_title_keywords is provided, include the most relevant ONE in the title.
- If feature_benefits is provided, use in DESCRIPTIONS only, not titles.
- If competitive_edge is provided, use as primary value proposition in descriptions.

FINISH STRATEGY:
- MasterSKU descriptions must be finish-neutral.
- Finish-forward variant phrasing is applied downstream by finish injection.

ROOM CONTEXT:
- Kitchen products: use "kitchen" terminology only (never "bathroom" or "bath").
- Bathroom products: use "bathroom" or "bath" terminology only (never "kitchen").

=== P2: NICE TO HAVE (bonus quality) ===

- Natural query language for dimensions: "18-Inch" not "18in".
- If an image is provided, confirm material, finish, and features against it.
- Shopify meta description should NOT be a truncation of the description.
- Google short title should work as an overlay label.
- Installation ease messaging: "installs in minutes with included hardware" (when supported by evidence).

=== ANTI-PATTERNS (never produce output like these) ===

BAD TITLE: "Premium Luxury Brass Bathroom Accessory - Best Towel Bar"
WHY: Starts with banned adjectives, no specific product type in first 30 chars, no dimensions,
no collection, no brand at end.

BAD TITLE: "Allied Brass Dottingham Collection 18-Inch Towel Bar"
WHY: Brand first instead of last, product type after character 30.

BAD DESCRIPTION: "This towel bar is made of brass. It mounts to the wall. It comes in 28
finishes. It has a lifetime warranty."
WHY: Feature-first (not problem-first), no engagement hook, no outcome-driven benefits,
reads like a spec sheet, no bullet structure, no specific usage scenario.

=== PLATFORM SPECIFICS ===

Google Shopping / Performance Max (descriptions are FEED FUEL, not shown to shoppers):
- Descriptions influence which search queries trigger your Shopping ads.
- Attribute-dense content = more relevant impressions = better ROAS.
- Semantic matching allows synonyms; front-loaded keywords still matter.
- Feed seeds PMax asset generation across Search, Display, and YouTube.
- Plain text descriptions (no HTML).
- Lead descriptions with product type, dimensions, material, mount type -- NOT persuasive hooks.
- Include "solid brass" as a prominent attribute -- key differentiator for quality matching.
- Include "lifetime warranty" and "solid brass" or "brass construction" as natural attribute phrases.

Bing Shopping (descriptions are FEED FUEL, not shown to shoppers):
- MORE LITERAL keyword matching than Google. Explicit synonyms are critical.
- Brand required in titles. Copilot extracts specifications from descriptions.
- Descriptions should be longer than Google to cover synonym variations.
- Include product mount type variations: "wall mount", "wall-mounted", "freestanding", "countertop".
- Include "solid brass" prominently -- shoppers actively search for this.
- Include "lifetime warranty" near the product type mention.

Shopify (descriptions ARE shown to shoppers -- this is the sales pitch):
- Title becomes H1. Meta snippet is first ~155 characters.
- HTML descriptions: <p> hook, <ul><li> highlights, specs/warranty.
- First sentence must address buyer's problem or desired outcome.
- Include at least ONE trust signal in the first two sentences.
- Include competitive differentiation (solid brass vs die-cast zinc).
- Collection coordination CTA when collection_context is available.

=== SCORING RUBRIC (self-score each 0-10 using the checklists below) ===

Score each dimension by counting how many required elements are present:
- 10 = ALL required elements present
- 7-9 = missing 1-2 required elements
- 4-6 = missing 3+ required elements
- 1-3 = fundamentally wrong or missing the dimension entirely
- 0 = not attempted

1. Specificity (check these elements):
   [ ] At least one concrete dimension (e.g. "18-Inch", "24-Inch")
   [ ] Material stated explicitly (e.g. "solid brass")
   [ ] Mount type or installation method mentioned
   [ ] Product type named in first 30 characters of title
   [ ] At least one measurable claim (weight capacity, finish count, etc.)

2. Benefit Coverage (check these elements):
   [ ] Shopify description opens with buyer problem or desired outcome
   [ ] Trust signal in first 150 characters of Shopify description
   [ ] At least 3 outcome-first bullet highlights in Shopify
   [ ] Google/Bing descriptions lead with attributes, not marketing hooks
   [ ] Competitive differentiator mentioned (solid brass vs alternatives)

3. Keyword Inclusion (check these elements):
   [ ] Primary keyword from placement plan in google_title
   [ ] Primary keyword from placement plan in bing_title
   [ ] At least 2 product-type synonyms in bing_description
   [ ] "solid brass" appears in Google and Bing descriptions
   [ ] Room context keyword present (bathroom/kitchen as appropriate)

4. Format Adherence (check these elements):
   [ ] google_title and bing_title are 60-150 characters
   [ ] google_short_title is under 70 characters
   [ ] google_description is 600-800 characters
   [ ] bing_description is 700-1000 characters
   [ ] shopify_description uses HTML structure (<p>, <ul><li>)
   [ ] shopify_meta_description is 140-155 characters

5. Brand Voice (check these elements):
   [ ] No banned words (finest, luxurious, premium, exclusive, etc.)
   [ ] "Allied Brass" is the final segment in titles
   [ ] Confident, direct phrasing (not hedging: "helps provide" -> "provides")
   [ ] No ALL CAPS marketing language
   [ ] Collection name referenced in descriptions (when available)

6. Factual Accuracy (check these elements):
   [ ] Every dimension matches evidence table exactly
   [ ] Material claims match evidence table
   [ ] No invented specifications
   [ ] Claims array traces each fact to a source_field
   [ ] Keywords from placement plan used as search intent, NOT stated as product facts"""

# ---------------------------------------------------------------------------
# CATEGORY GUIDANCE (injected into dynamic user prompt per-SKU)
# ---------------------------------------------------------------------------
# Category-specific writing hints that help the LLM tailor content structure
# to product types with different buyer intent patterns. These go in the
# dynamic user prompt (not system prompt) to preserve prompt caching.
# ---------------------------------------------------------------------------

_CATEGORY_GUIDANCE = {
    "niche_functional": {
        "categories": [
            "retractable",
            "garment rod",
            "cabinet pull",
            "cabinet knob",
            "squeegee",
            "door pull",
            "shower door",
        ],
        "guidance": """CATEGORY NOTE: This is a niche/functional product. Shoppers searching
for this product type already know what they want — focus on WHY THIS ONE over competitors
(material quality, dimensions, mounting system) rather than generic bathroom upgrade hooks.
For Google/Bing: lead with exact product type and differentiating specs.
For Shopify: open with the specific problem this product solves, not a generic bathroom hook.""",
    },
    "towel_storage": {
        "categories": [
            "towel bar",
            "towel ring",
            "towel holder",
            "towel stand",
            "towel valet",
            "towel shelf",
            "guest towel",
        ],
        "guidance": """CATEGORY NOTE: High-competition category. Differentiate on construction
(solid brass vs die-cast zinc), finish variety, and collection coordination.
For Google/Bing: include towel bar/rack/holder synonyms and exact dimensions early.
For Shopify: address the common frustration (flimsy bars, mismatched finishes) in opening.""",
    },
    "safety_ada": {
        "categories": ["grab bar", "ada"],
        "guidance": """CATEGORY NOTE: Safety-critical product. Lead with functional assurance
(weight capacity, ADA compliance, mounting security). Trust signals matter more than aesthetics.
For Google/Bing: include "ADA compliant", weight capacity, mounting type as primary attributes.
For Shopify: open with safety/accessibility benefit, then mention that it doesn't sacrifice style.""",
    },
}


def build_category_guidance(category: str | None) -> str:
    """Return category-specific writing guidance for the user prompt.

    Args:
        category: The product category (e.g., "Towel Bars", "Grab Bars")

    Returns:
        Category guidance string or empty string if no match.
    """
    if not category:
        return ""
    cat_lower = category.lower()
    for group in _CATEGORY_GUIDANCE.values():
        if any(kw in cat_lower for kw in group["categories"]):
            return f"\n{group['guidance']}\n"
    return ""


# ---------------------------------------------------------------------------
# DYNAMIC USER PROMPT (per-SKU, assembled at runtime)
# ---------------------------------------------------------------------------
# Contains only the evidence table, keyword placement plan, and master SKU.
# This is the "dynamic suffix" that changes per product.
# ---------------------------------------------------------------------------

USER_PROMPT_TEMPLATE = """\
{evidence_table}

{keyword_placement}
{category_guidance}
Respond with valid JSON matching this schema:
{schema}

Optimize title and description for MasterSKU: {master_sku}"""

# ---------------------------------------------------------------------------
# LEGACY TEMPLATE (for backward compatibility with non-split callers)
# ---------------------------------------------------------------------------

OPTIMIZATION_TEMPLATE = """
{system_prompt}

{evidence_table}

{keyword_placement}
{category_guidance}
## Output Format
Respond with valid JSON matching this schema:
{schema}

Now optimize the title and description for MasterSKU: {master_sku}
"""
