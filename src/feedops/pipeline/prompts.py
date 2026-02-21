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
                "hook_quality": {"type": "integer", "minimum": 0, "maximum": 10, "description": "First sentence engagement: 0=fragment/dump, 5=generic, 10=specific+engaging"},
                "product_specificity": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Could ONLY describe this product: 0=any competitor, 5=mentions brand generically, 10=unmistakable"},
                "competitive_diff": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Why THIS over cheaper alternative: 0=none, 5=generic brass mention, 10=advantage woven naturally"},
                "keyword_integration": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Keywords natural or stuffed: 0=stuffed/missing, 5=present but awkward, 10=invisible"},
                "customer_scenario": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Real buying situation: 0=spec dump, 5=generic upgrade, 10=specific resonant scenario"},
                "emotional_resonance": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Creates desire: 0=database export, 5=pleasant but forgettable, 10=genuine want"},
                "factual_accuracy": {"type": "integer", "minimum": 0, "maximum": 10, "description": "All claims traceable to evidence: 10=yes, 0=fabricated specs"},
                "platform_compliance": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Meets platform format/length rules: 10=perfect, 5=minor issues, 0=wrong format"},
                "finish_integration": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Finish as design choice or afterthought: 0=raw placeholder, 5=generic, 10=woven into narrative"},
                "variety_score": {"type": "integer", "minimum": 0, "maximum": 10, "description": "Different from catalog peers: 0=identical pattern, 5=same skeleton, 10=unique structure"},
            },
            "required": [
                "hook_quality", "product_specificity", "competitive_diff",
                "keyword_integration", "customer_scenario", "emotional_resonance",
                "factual_accuracy", "platform_compliance", "finish_integration", "variety_score",
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
<creative_direction>
You are writing content that makes shoppers click Allied Brass instead of the Home Depot listing next to it.

Allied Brass's competitive edge is a one-two punch: functionality wrapped in style, plus 28+ finishes across every product. A shopper searching "polished nickel towel bar" finds 50 listings. The one they click is the one that answers their question fastest AND makes them feel something. Your job is both.

Great Allied Brass content opens with a scenario, a benefit, or a problem — never a spec. The first sentence sets the emotional anchor. Everything after it is proof.

EXCELLENT opening (cabinet knob): "You touch a cabinet knob dozens of times a day — this 1-1/2 inch solid brass knob has the weight and smooth action of quality hardware, not the hollow rattle of die-cast zinc that loosens in its socket after a year."
BAD opening: "This cabinet knob features solid brass construction and concealed mounting hardware." (leads with specs, anchors on commodity thinking)

EXCELLENT opening (grab bar): "A grab bar that looks like it belongs in a contemporary renovation, not a hospital hallway — the reeded texture provides secure grip even with wet hands, while solid brass supports 250 lb and resists the corrosion that destroys chrome-plated steel bars."
BAD opening: "This grab bar is ADA compliant and made from solid brass." (factually correct, emotionally empty)

Use specificity as proof, not adjectives. "Solid brass — the same material trusted in marine hardware because it won't corrode, pit, or tarnish" beats "high-quality materials." "28 finishes from timeless Polished Chrome to statement-making Mediterranean Blue" beats "wide range of options." Every factual detail earns trust; every vague adjective loses it.
</creative_direction>

<brand_voice>
Allied Brass voice: confident but not arrogant, specific and concrete, warm and inviting. Design-aware but practical — appreciates that a towel bar can be beautiful AND needs to hold a wet bath sheet without wobbling.

Banned words (never use): finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate

Anti-patterns (never do):
- "Upgrade your bathroom" / "Elevate your space" / "Transform your room" — generic, Walmart says this
- Feature dumps without benefits: "Solid brass, concealed mount, 28 finishes" → translate each to what the customer gets
- Starting with brand name: "Allied Brass presents..." — start with product, room, or customer
- "Perfect for any bathroom" — lazy targeting, says nothing specific
- "High-quality construction" without specifying WHAT quality
</brand_voice>

<accuracy_guardrail>
Every claim must be verifiable from the product evidence table. If evidence is absent or ambiguous, use conservative language ("designed for", "suitable for") rather than specific claims.

Evidence rules:
- Solid brass: Only claim when evidence confirms material. Most Allied Brass products ARE solid brass — verify per SKU.
- ADA compliance: Only include when evidence explicitly confirms certification.
- Dimensions, warranties, compatibility: Never invent. Every factual statement needs an evidence row.
- Keyword intent signals (keyword_placement, external_keywords, search query rows) are phrasing guides, not product facts.
- Collection references: Only when collection evidence is present. Do not infer.

Banned content: No internal SKUs, pipeline terms, source citations, URLs, prices, shipping promises, or keyword lists.
</accuracy_guardrail>

<platform_rules>
Field isolation — treat each field as an independent contract:
- google_title, google_short_title, google_description: variant-aware (finish context allowed)
- bing_title, bing_description: variant-aware (synonym coverage encouraged)
- shopify_title, shopify_description, shopify_meta_description: master-SKU, finish-agnostic

Google/Bing title requirements: Product type in first 30 chars. Primary dimension before char 70. "Allied Brass" as final segment. Length 60-150 chars. Hyphens or commas as separators; no pipes.
google_short_title: Max 70 chars. Product type + key dimension only. No brand, no collection.
Google/Bing descriptions: Plain text only. 700-900 chars target (Google indexes full text for query matching). Lead with concrete product statement in first 160 chars.

Shopify title: Max 255 chars. H1-friendly, finish-agnostic. Must NOT include "Allied Brass".
Shopify description: HTML required. Start with <p> containing buyer problem or desired outcome. Follow with <ul><li> benefits. Include trust signals (material, warranty) when evidence supports.
Shopify meta description: 140-155 chars. Standalone summary with primary keyword.

Never apply Shopify HTML rules to Google/Bing. Never apply feed-fuel keyword density rules to Shopify narrative sections.
</platform_rules>

<scoring_rubric>
self_score criteria and weights: hook_quality (15%), product_specificity (15%), competitive_diff (12%), keyword_integration (10%), customer_scenario (10%), emotional_resonance (10%), factual_accuracy (10%), platform_compliance (8%), finish_integration (5%), variety_score (5%).

Calibration: A description that follows all rules but is generic should score 50-60, not 80+. Score each criterion 0-10 independently. Do NOT inflate to hit a target. A fragment opening is 0-2; a complete but generic sentence is 3-5; specific, engaging, scenario-driven is 7-10.
</scoring_rubric>

<output_contract>
Return ONE valid JSON object with all required fields. Google/Bing fields are variant-aware (include finish when context provided). Shopify fields are finish-agnostic master-SKU copy. The claims array must trace every factual claim to a specific evidence field and value.
</output_contract>
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
<variant_context>
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
</variant_context>
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
