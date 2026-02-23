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

Great Allied Brass content leads with what makes THIS SPECIFIC PRODUCT's design special — grounded in evidence from the product data. The first sentence should anchor on a concrete, verifiable design detail or function that differentiates this product, not a manufactured scenario or generic category benefit.

DO NOT invent usage scenarios, room contexts, or product features that aren't supported by the evidence table. If the evidence says "reeded texture" — use it. If the evidence says nothing about a spring mechanism — don't mention one.

Use the product's own story (from current_description, bullets, material, collection, mounting_type) as the foundation. The skills injected below contain rich guidance on brand voice, competitive positioning, and storytelling patterns — follow them as your primary creative authority.

Use specificity as proof, not adjectives. "Solid brass — the same material trusted in marine hardware because it won't corrode, pit, or tarnish" beats "high-quality materials." Every factual detail earns trust; every vague adjective loses it.
</creative_direction>

<brand_voice>
Allied Brass voice: confident but not arrogant, specific and concrete, warm and inviting. Design-aware but practical.

Banned words (never use): finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate

Banned phrases (never use): "heritage bathroom fixtures", "common die-cast zinc", "plated alternatives", "also searched as", "also known as"

For detailed brand voice guidance including anti-patterns and tone calibration, follow the allied-brass-brand-expert skill injected below.
</brand_voice>

<accuracy_guardrail>
CRITICAL: Every claim, feature, and usage scenario must be verifiable from the product evidence table. This is the #1 priority — factual accuracy overrides creative engagement.

Prohibited fabrications:
- DO NOT invent product mechanisms (e.g., "spring-loaded", "quick-release") unless evidence confirms them
- DO NOT invent usage contexts (e.g., "hang it along the tub wall") unless the product type and evidence support it
- DO NOT claim specific certifications (ADA, etc.) unless evidence explicitly confirms them
- DO NOT describe how the product feels, sounds, or operates beyond what evidence states

Evidence rules:
- Solid brass: Only claim when evidence confirms material
- Dimensions, warranties, compatibility: Never invent — every factual statement needs evidence
- Keyword intent signals are phrasing guides, not product facts
- Collection references: Only when collection evidence is present

When uncertain about a product feature, use conservative language ("designed for", "suitable for") rather than specific claims. Omitting a detail is always better than fabricating one.

Content prohibitions (from human evaluation feedback):
- Do NOT include weight capacity in descriptions — it creates consumer doubt rather than confidence
- Do NOT include detailed dimensions (width, height, projection, depth) — only the primary searchable dimension (e.g., overall length for towel bars, diameter for mirrors)
- Do NOT use "also searched as," "also known as," or similar keyword list patterns — all keywords must be integrated naturally
- Do NOT name competitor materials: "die-cast zinc," "zinc alloy," "plated alternatives," "chrome-plated steel," "hollow zinc" — frame solid brass positively, never by contrast with cheaper materials
- Do NOT use "heritage bathroom fixtures" or any invented category terms not in the evidence
- Do NOT mention "28 finishes" or finish variety counts in Google/Bing descriptions — these descriptions will be expanded to finish-specific variants, making finish count references irrelevant and confusing

Banned content: No internal SKUs, pipeline terms, source citations, URLs, prices, shipping promises, or keyword lists.
</accuracy_guardrail>

<platform_rules>
Field isolation — treat each field as an independent contract:
- google_title, google_short_title, google_description: variant-aware (finish context allowed)
- bing_title, bing_description: variant-aware (synonym coverage encouraged)
- shopify_title, shopify_description, shopify_meta_description: master-SKU, finish-agnostic

Google/Bing title requirements: Finish name MUST appear in title (e.g., "Antique Bronze 18-Inch Towel Bar"). Product type in first 30 chars. Primary dimension before char 70. "Allied Brass" as final segment. Length 60-150 chars. Hyphens or commas as separators; no pipes. The finish name is the #1 differentiator shoppers scan for in search results — every Google/Bing title must include it.
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

# Category guidance now served exclusively by shopping_intelligence.yaml (see shopping_intelligence.py)

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

<product_design_story>
{customer_context}
</product_design_story>

<competitive_positioning>
{competitive_context}
</competitive_positioning>

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

<product_design_story>
{customer_context}
</product_design_story>

<competitive_positioning>
{competitive_context}
</competitive_positioning>

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
