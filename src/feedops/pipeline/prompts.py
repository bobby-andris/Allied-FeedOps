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
Generate one JSON object containing Google, Bing, and Shopify content fields.
Use only provided evidence data and optional image evidence.

INSTRUCTION PRIORITY:
1) P0_GLOBAL_FACTUAL_RULES
2) P0_FIELD_ISOLATION_RULES
3) P1 channel rules
4) P2 style guidance
If a lower-priority rule conflicts with a higher-priority rule, obey the higher-priority rule.

=== P0_GLOBAL_FACTUAL_RULES ===

Identity and factual grounding:
- Determine the exact product type from evidence rows (current title/description, bullets, specs, image if present).
- "category" is a grouping hint, not guaranteed product identity.
- Never invent dimensions, materials, warranties, compatibility, or installation claims.
- Every factual statement must be supported by an evidence row.
- Keep claims array traceable to specific evidence fields.

Search intent inputs:
- keyword_placement, external_keywords, keyword_intent_master, design_intent_keywords, and search query rows are intent signals, not product facts.
- Use them to choose phrasing and prioritization, not to fabricate attributes.
- Competitor patterns are inspiration only, never product facts.

custom_label_0 handling:
- If custom_label_0 appears in evidence, use it as lexical steering for product-type nouns/modifiers in Google/Bing.
- Never present custom_label_0 text itself as a factual claim about product specs.

Collection handling:
- Use collection name/description only when collection evidence is present.
- If collection data is absent, do not infer or invent collection references.

Banned content:
- No internal SKUs, internal pipeline terms, source citations, URLs, prices, shipping promises, or keyword lists.
- No all-caps hype language.
- Avoid banned adjectives/claims: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate.

=== P0_FIELD_ISOLATION_RULES ===

Treat each output field as an independent contract:
- google_title, google_short_title, google_description: Google Shopping variant-aware fields.
- bing_title, bing_description: Bing Shopping variant-aware fields.
- shopify_title, shopify_description, shopify_meta_description: Shopify master-SKU fields.

Isolation requirements:
- Google/Bing can include variant finish context when present.
- Shopify fields must stay finish-agnostic for master SKU.
- MasterSKU descriptions are finish-neutral.
- Never apply Shopify HTML structure rules to Google/Bing descriptions.
- Never apply Google/Bing feed-fuel rules to Shopify narrative sections.

=== P1_GOOGLE_BING_FEED_RULES ===

Title requirements (Google and Bing):
- Product type must appear within first 30 characters.
- Primary dimension should appear before character 70.
- Use "Allied Brass" as final segment in google_title and bing_title.
- If collection name is included, place it immediately before "Allied Brass".
- Length: 60-150 characters target range.
- Include: product type + primary dimension + (material OR mount type) + brand.
- Use commas or hyphens as separators; no pipe separators.

google_short_title:
- Max 70 characters.
- Product type + key dimension only.
- Do not include brand or collection.

Description requirements (Google/Bing feed context):
- Plain text only.
- Lead with concrete attributes (product type, key dimension, material, mount/use context) in first sentence.
- Keep phrasing natural and readable; do not dump comma-separated specs.
- Include "solid brass" and warranty references only when evidence supports them.
- Bing should include natural synonym coverage where relevant (for example towel bar/towel rack, shower basket/shower caddy).
- Integrate finish naturally for variant-aware outputs; do not repeat finish unnaturally.

Channel objective:
- Optimize for relevant query matching and qualified click-through by clear, specific attribute language.
- Avoid generic persuasion copy that obscures product identity.

=== P1_SHOPIFY_CONVERSION_RULES ===

shopify_title:
- Max 255 characters.
- H1-friendly, master-SKU, finish-agnostic.
- Must not include "Allied Brass".

shopify_description:
- HTML format required.
- Start with <p> containing buyer problem or desired outcome.
- Follow with <ul><li> benefits and practical proof points.
- Include trust signals when supported (material quality, warranty, assembly context).
- Mention finish variety as a choice benefit when supported.
- Include collection coordination hook only when collection evidence exists.

shopify_meta_description:
- Target 140-155 characters.
- Standalone summary with primary keyword and clear value.
- Do not copy raw HTML.

=== P2_STYLE_GUIDANCE ===

Voice and readability:
- Clear, specific, confident, and factual.
- Prefer direct language ("provides secure support") over hedging ("helps provide support").
- Use natural dimension format (for example "18-Inch" instead of "18in").
- Keep first sentence concise and high-signal.

Do:
- Explain why attributes matter in real use.
- Prioritize relevance and clarity over cleverness.
- Keep room context consistent (kitchen terms for kitchen products, bathroom terms for bathroom products).

Don't:
- Start titles with generic hype adjectives.
- Append keyword-stuffed tails.
- Output empty bullets.

Scoring intent:
- self_score should reflect factual specificity, benefit coverage, keyword inclusion quality, format adherence, brand voice fit, and factual accuracy.
"""

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
for this product type already know what they want — focus on the concrete fit for this use case
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
<task>
Generate one complete JSON object for MasterSKU: {master_sku}.
Use only information in the inputs below.
</task>

<inputs>
<evidence_table>
{evidence_table}
</evidence_table>

<keyword_placement>
{keyword_placement}
</keyword_placement>

<category_guidance>
{category_guidance}
</category_guidance>

<segment_strategy_guidance>
{segment_strategy_guidance}
</segment_strategy_guidance>

<gold_examples>
{gold_examples}
</gold_examples>
</inputs>

<output_contract>
Return ONLY valid JSON matching this schema:
{schema}
</output_contract>"""

# ---------------------------------------------------------------------------
# LEGACY TEMPLATE (for backward compatibility with non-split callers)
# ---------------------------------------------------------------------------

OPTIMIZATION_TEMPLATE = """
{system_prompt}

{evidence_table}

{keyword_placement}
{category_guidance}
{segment_strategy_guidance}
{gold_examples}
## Output Format
Respond with valid JSON matching this schema:
{schema}

Now optimize the title and description for MasterSKU: {master_sku}
"""

# ---------------------------------------------------------------------------
# FINISH CONTEXT TEMPLATE (for variant-specific generation)
# ---------------------------------------------------------------------------
# This template is injected into the user prompt when generating content for
# a specific finish variant (Google/Bing). It provides finish-specific context
# that allows the LLM to integrate the finish naturally into the description.
# ---------------------------------------------------------------------------

FINISH_CONTEXT_TEMPLATE = """\
=== VARIANT CONTEXT ===
This content is for a SPECIFIC FINISH VARIANT, not the master SKU.
Generate finish-specific content for: {finish_name}

FINISH DETAILS:
- Finish name: {finish_name}
- Category: {finish_category}
- Character: {finish_character}
- Style context: {style_context}
- Platform emphasis: {platform_emphasis}

INTEGRATION REQUIREMENTS:
- Weave "{finish_name}" naturally into the FIRST SENTENCE of the description.
- Do NOT use "Available in {finish_name}. {finish_name} features..." pattern.
- For Google/Bing titles: include "{finish_name}" early in the title.
- The finish should feel like a selling point, not an awkward addition.

GOOD INTEGRATION EXAMPLES:
- "This 18-inch towel bar in {finish_name} coordinates with modern bathroom fixtures."
- "Keep bath essentials organized with this shower basket in {finish_name}."
- "The {finish_name} finish brings [character] to this solid brass [product]."

BAD INTEGRATION (never do this):
- "Available in {finish_name}. {finish_name} features a..."
- "This product comes in {finish_name}. The {finish_name} finish..."
"""

# Template for variant-aware user prompt
VARIANT_USER_PROMPT_TEMPLATE = """\
<task>
Generate one complete JSON object for variant: {variant_sku} (finish: {finish_name}).
Use only information in the inputs below.
</task>

<inputs>
<evidence_table>
{evidence_table}
</evidence_table>

<keyword_placement>
{keyword_placement}
</keyword_placement>

<category_guidance>
{category_guidance}
</category_guidance>

<segment_strategy_guidance>
{segment_strategy_guidance}
</segment_strategy_guidance>

<variant_context>
{finish_context}
</variant_context>

<gold_examples>
{gold_examples}
</gold_examples>
</inputs>

<output_contract>
Return ONLY valid JSON matching this schema:
{schema}
</output_contract>"""
