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
            "description": "Shopify SEO meta description (target 140-160 characters). Compelling standalone summary with primary keyword.",
            "maxLength": 160,
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
# PLATFORM-SPECIFIC SCHEMAS (additive for Phase 25.2 architecture testing)
# ---------------------------------------------------------------------------

_CLAIMS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "claim": {
                "type": "string",
                "description": "The factual claim text included in content.",
            },
            "source_field": {
                "type": "string",
                "description": "Evidence field name backing this claim.",
            },
            "source_value": {
                "type": "string",
                "description": "Exact evidence value backing this claim.",
            },
        },
        "required": ["claim", "source_field", "source_value"],
        "additionalProperties": False,
    },
}

GOOGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "google_title": {
            "type": "string",
            "description": (
                "Google Shopping title. Must start with literal {FINISH_NAME}. "
                "Max 150 chars."
            ),
            "maxLength": 150,
            "pattern": r"^\{FINISH_NAME\}.+",
        },
        "google_short_title": {
            "type": "string",
            "description": "Google short title (max 70 chars).",
            "maxLength": 70,
        },
        "google_description": {
            "type": "string",
            "description": (
                "Google Shopping description, 700-900 chars. Must include literal "
                "{FINISH_SENTENCE} placeholder."
            ),
            "minLength": 700,
        },
        "claims": _CLAIMS_SCHEMA,
    },
    "required": [
        "google_title",
        "google_short_title",
        "google_description",
        "claims",
    ],
    "additionalProperties": False,
}

BING_SCHEMA = {
    "type": "object",
    "properties": {
        "bing_title": {
            "type": "string",
            "description": (
                "Bing Shopping title. Must start with literal {FINISH_NAME}. "
                "Max 150 chars."
            ),
            "maxLength": 150,
            "pattern": r"^\{FINISH_NAME\}.+",
        },
        "bing_description": {
            "type": "string",
            "description": (
                "Bing Shopping description, 700-1000 chars. Front-load key specs "
                "in first 200 chars and include literal {FINISH_SENTENCE}."
            ),
            "minLength": 700,
        },
        "claims": _CLAIMS_SCHEMA,
    },
    "required": ["bing_title", "bing_description", "claims"],
    "additionalProperties": False,
}

SHOPIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "shopify_title": {
            "type": "string",
            "description": (
                "Shopify title for master SKU content. Finish-agnostic; do not "
                "include finish names."
            ),
            "maxLength": 255,
        },
        "shopify_description": {
            "type": "string",
            "description": (
                "Shopify HTML description, 250-400 words. Start with a buyer-problem "
                "or buyer-outcome opening. Never include {FINISH_NAME} or "
                "{FINISH_SENTENCE} placeholders."
            ),
        },
        "shopify_meta_description": {
            "type": "string",
            "description": "Shopify meta description (max 160 chars).",
            "maxLength": 160,
        },
        "claims": _CLAIMS_SCHEMA,
    },
    "required": [
        "shopify_title",
        "shopify_description",
        "shopify_meta_description",
        "claims",
    ],
    "additionalProperties": False,
}

FINISH_SENTENCES_SCHEMA = {
    "type": "object",
    "properties": {
        "sentences": {
            "type": "array",
            "description": "Exactly 28 finish sentences, one per supported finish.",
            "minItems": 28,
            "maxItems": 28,
            "items": {
                "type": "object",
                "properties": {
                    "finish_code": {
                        "type": "string",
                        "description": "Internal finish code (e.g., PNI, ORB).",
                    },
                    "finish_name": {
                        "type": "string",
                        "description": "Display finish name.",
                    },
                    "sentence": {
                        "type": "string",
                        "description": (
                            "Product-specific finish sentence, 40-80 characters."
                        ),
                        "minLength": 40,
                        "maxLength": 80,
                    },
                },
                "required": ["finish_code", "finish_name", "sentence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["sentences"],
    "additionalProperties": False,
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
Find the ONE design detail that makes THIS product worth noticing and lead with it — what would a bathroom designer point out that a shopper wouldn't?

DO NOT invent usage scenarios, room contexts, or product features that aren't supported by the evidence table. If the evidence says "reeded texture" — use it. If the evidence says nothing about a spring mechanism — don't mention one.

Use the product's own story (from current_description, bullets, material, collection, mounting_type) as the foundation.

Use specificity as proof, not adjectives. "Solid brass — the same material trusted in marine hardware because it won't corrode, pit, or tarnish" beats "high-quality materials." Every factual detail earns trust; every vague adjective loses it.
</creative_direction>

<objective_hierarchy>
Primary objective: produce the strongest product-specific content for the target platform so the right shopper clicks and buys.

Priority order:
1. Product truth and factual accuracy from evidence.
2. Clear, product-specific differentiation a real shopper can understand quickly.
3. Platform readability and format compliance.
4. Keyword enrichment only when it improves priorities 1-3.

If a keyword hint conflicts with product truth, category fidelity, or natural language clarity, ignore the hint.
</objective_hierarchy>

<brand_voice>
Allied Brass voice: confident but not arrogant, specific and concrete, warm and inviting. Design-aware but practical.

Banned words (never use): finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate

Banned phrases (never use): "heritage bathroom fixtures", "common die-cast zinc", "plated alternatives", "also searched as", "also known as"
</brand_voice>

<accuracy_guardrail>
CRITICAL: Every claim, feature, and usage scenario must be verifiable from the product evidence table. This is the #1 priority — factual accuracy overrides creative engagement.

Prohibited fabrications:
- DO NOT invent product mechanisms (e.g., "spring-loaded", "quick-release") unless evidence confirms them
- DO NOT invent usage contexts (e.g., "hang it along the tub wall") unless the product type and evidence support it
- DO NOT claim specific certifications (ADA, etc.) unless evidence explicitly confirms them
- DO NOT describe how the product feels, sounds, or operates beyond what evidence states

When uncertain about a product feature, use conservative language ("designed for", "suitable for") rather than specific claims. Omitting a detail is always better than fabricating one.

Content prohibitions (from human evaluation feedback):
- Do NOT include weight capacity in descriptions — it creates consumer doubt rather than confidence
- Do NOT include detailed dimensions (width, height, projection, depth) — only the primary searchable dimension (e.g., overall length for towel bars, diameter for mirrors)
- Do NOT use "also searched as," "also known as," or similar keyword list patterns — all keywords must be integrated naturally
- Do NOT name competitor materials: "die-cast zinc," "zinc alloy," "plated alternatives," "chrome-plated steel," "hollow zinc" — frame solid brass positively, never by contrast with cheaper materials
- Do NOT use "heritage bathroom fixtures" or any invented category terms not in the evidence
- In variant-facing descriptions, do NOT mention finish variety counts (e.g., "28 finishes")
- Never use banned promo words in customer-facing copy: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate

Banned content: No internal SKUs, pipeline terms, source citations, URLs, prices, shipping promises, or keyword lists.
</accuracy_guardrail>

<output_contract>
Return ONE valid JSON object that matches the platform schema exactly. Do not add extra keys.
The claims array must trace every factual claim to a specific evidence field and value.
</output_contract>
"""

# Category guidance now served exclusively by shopping_intelligence.yaml (see shopping_intelligence.py)

# ---------------------------------------------------------------------------
# PLATFORM-SPECIFIC CREATIVE BRIEFS (v2 per-platform prompts)
# ---------------------------------------------------------------------------
# These are purpose-built GPT-5.2 instructions that replace the extracted
# skill snippets. They encode Bobby/Robert's Round 2 evaluation feedback
# as actionable creative direction, not reference material.
#
# Each brief is combined with SYSTEM_PROMPT by get_platform_system_prompt()
# in skill_loader.py to form the complete system prompt for that platform.
# ---------------------------------------------------------------------------

GOOGLE_BRIEF = """\
<platform_rules>
Google fields only:
- google_title: variant-aware and must begin with literal {FINISH_NAME}
- google_short_title: concise scannable short title
- google_description: plain text variant description that includes literal {FINISH_SENTENCE}

Do not generate Bing or Shopify behavior in this task.
</platform_rules>

<google_objective_priority>
Google optimization order:
1. Product truth and category-faithful naming.
2. Specific differentiation that helps a shopper choose this product.
3. Readable, scan-friendly phrasing that sounds human.
4. Keyword enrichment only when it improves 1-3.

Never force awkward copy to satisfy keyword hints.
Write product copy, not commentary about search behavior.
</google_objective_priority>

<finish_sentence_contract>
{FINISH_SENTENCE} is generated in a separate finish-sentence API call from the same product evidence.
In this Google description call, treat {FINISH_SENTENCE} as a pre-written sentence that will be inserted
during variant expansion (one finish sentence per variant).

Integration requirements:
- Use {FINISH_SENTENCE} exactly once, as its own sentence.
- Keep sentence flow natural before and after insertion.
- Do not rewrite, paraphrase, or expand {FINISH_SENTENCE}.

Good flow:
"[Product-specific opening sentence]. {FINISH_SENTENCE} [Evidence-based support sentence]."
Good flow:
"[Concrete spec opening sentence.] [Differentiator sentence.] {FINISH_SENTENCE} [Trust close sentence]."
Anti-example:
"If you're searching for options, {FINISH_SENTENCE} {FINISH_SENTENCE} [fragment]."
</finish_sentence_contract>

<title_formula>
Write Google Shopping titles using this exact structure:

{FINISH_NAME} [Product Function] [Collection Name Collection*] [Primary Dimension*] [Optional Style Cue*] - Allied Brass

Rules:
- {FINISH_NAME} is ALWAYS the first element. It is a literal placeholder — output it exactly.
- Product function in the first 30 characters after {FINISH_NAME} (e.g., "Towel Bar", "Robe Hook", "Soap Dish").
- Product noun must match the category intent in evidence:
  - Category "Towel Bars" -> use "Towel Bar" (not "Towel Rack")
- Category "Robe Hooks" -> use "Robe Hook"
- Category "Toilet Paper Holders" -> use "Toilet Paper Holder"
- If the product belongs to a named collection, include "[Name] Collection" (always with the word "Collection").
- Include the primary dimension ONLY when the product varies by size (towel bars: yes; robe hooks: no).
- Add a style cue only when evidence supports it (style, collection language, or current description). If unsupported, omit it.
- "Solid Brass" should NOT appear in the title — save prime title space for converting keywords.
- "Allied Brass" is always the final segment, separated by a dash or comma.
- For towel-bar categories, NEVER include the phrase "towel rack" in Google title text. Use "Towel Bar" only.
- Total length: 60-150 characters. Shorter is better if it captures the key terms.

Good: {FINISH_NAME} 24-Inch Towel Bar - Skyline Collection - Allied Brass
Good: {FINISH_NAME} Robe Hook, Contemporary Wall Mount - Waverly Place Collection - Allied Brass
Bad: {FINISH_NAME} 24-Inch Wall Mounted Solid Brass Towel Rack - Skyline Bathroom Towel Holder Brass - Allied Brass  ← keyword-stuffed
Bad: {FINISH_NAME} Solid Brass Robe Hook (2.5" x 2.5" x 1.5") - Allied Brass  ← unnecessary dims
</title_formula>

<google_short_title>
Max 70 characters. Product type + primary dimension only. No brand, no collection, no finish.
Category-fidelity rule still applies:
- "Towel Bars" category -> short title must use "Towel Bar" (never "Towel Rack")
Example: "24-Inch Wall Mounted Towel Bar" or "Double Robe Hook"
</google_short_title>

<description_brief>
Write a Google Shopping description that makes a shopper pick Allied Brass over the generic listing next to it.

Structure (700-900 characters target, plain text; never add filler just to hit length):
1. OPEN with what makes THIS product's design special — a concrete detail from the evidence (e.g., "petite spherical end pieces," "reeded texture grip," "concealed post design"). Not a generic benefit.
2. Place {FINISH_SENTENCE} exactly once where finish context flows naturally — typically after the design opening or as a transition sentence. It is a literal placeholder; output it exactly as {FINISH_SENTENCE}.
3. BUILD with 2-3 evidence-grounded selling points: solid brass durability, collection coordination, mounting style, or a design detail that differentiates this product.
4. CLOSE with a practical trust signal: warranty, what's included, or installation confidence.

What to INCLUDE:
- Product-specific design details from the evidence (dimensions, mounting type, design elements)
- The primary searchable dimension (overall length for bars, diameter for mirrors)
- Collection name when available (for coordination selling)
- Natural keyword integration only when it improves clarity and buying intent.
- Translate keyword hints into clean buyer language; do not mirror raw query fragments.

What to EXCLUDE (these kill conversions or create doubt):
- Weight capacity (creates doubt, not confidence)
- Detailed dimensions beyond the primary one (width, height, projection, depth — these belong in the spec sheet)
- Competitor material names (die-cast zinc, plated alternatives, zinc alloy, chrome-plated steel)
- "Heritage bathroom fixtures" or invented category terms
- "Also searched as" or keyword list patterns
- Meta-search commentary (e.g., mentioning what someone searched for)
- "28 finishes" or finish count references (this listing IS a specific finish variant)
- "Bathroom humidity" as a key selling point (technically true but feels like filler)
- Installation specifics (screw sizes, exact hardware counts)
</description_brief>

<output_contract>
Return JSON with keys: google_title, google_short_title, google_description, claims.
</output_contract>

<final_quality_gate>
Before returning JSON, perform one silent final pass:
- Remove banned promo words (finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate).
- Remove any meta-search narration ("if you're searching", "if you've been comparing", etc.).
- For "Towel Bars" category, keep "Towel Bar" terminology in both google_title and google_short_title.
If any violation appears, rewrite before returning.
</final_quality_gate>
"""

GOOGLE_BRIEF_V3 = """\
<platform_rules>
Google fields only:
- google_title: variant-aware, must begin with literal {FINISH_NAME}
- google_short_title: concise scannable short title (max 70 chars)
- google_description: plain text variant description including literal {FINISH_SENTENCE}

Do not generate Bing or Shopify behavior in this task.
</platform_rules>

<title_formula>
Google Shopping titles: max 150 characters. Use pipe `|` separators to pack keyword segments.

Structure:
{FINISH_NAME} [Collection Name] [Product Type] | [Key Differentiator — material, size, style] | Allied Brass

Rules:
- {FINISH_NAME} is ALWAYS the first element. It is a literal placeholder — output it exactly.
- Product function within the first 30 characters after {FINISH_NAME} (e.g., "Towel Bar", "Robe Hook", "Soap Dish").
- Product noun must match the category intent in evidence:
  - Category "Towel Bars" -> use "Towel Bar" (not "Towel Rack")
  - Category "Robe Hooks" -> use "Robe Hook"
  - Category "Toilet Paper Holders" -> use "Toilet Paper Holder"
- If the product belongs to a named collection, include "[Name] Collection" (always with the word "Collection").
- Include dimensions when relevant and the product varies by size (e.g., "24 Inch", "18 Inch").
- Include material if premium (Solid Brass, Stainless Steel) — but only once.
- Use style/function descriptors shoppers search for (Traditional, Frameless, Tilting, Wall-Mounted, Freestanding, etc.).
- "Allied Brass" is always the final segment.
- Total length: 60-150 characters. Shorter is better if it captures the key terms.

Good: {FINISH_NAME} Astor Place Collection Frameless Oval Tilt Mirror | Solid Brass Wall-Mounted Vanity Mirror | Allied Brass
Good: {FINISH_NAME} 24 Inch Towel Bar | Solid Brass Traditional Bath Accessory | Astor Place Collection | Allied Brass
Good: {FINISH_NAME} Pipeline Collection Wall-Mount Paper Towel Holder | Industrial Steampunk Style | Allied Brass
Bad: {FINISH_NAME} 24-Inch Wall Mounted Solid Brass Towel Rack - Skyline Bathroom Towel Holder Brass - Allied Brass  <- keyword-stuffed
Bad: {FINISH_NAME} Solid Brass Robe Hook (2.5" x 2.5" x 1.5") - Allied Brass  <- unnecessary dims
</title_formula>

<google_short_title>
Max 70 characters. Product type + primary dimension only. No brand, no collection, no finish.
Category-fidelity rule still applies:
- "Towel Bars" category -> short title must use "Towel Bar" (never "Towel Rack")
Example: "24-Inch Wall Mounted Towel Bar" or "Double Robe Hook"
</google_short_title>

<finish_sentence_contract>
{FINISH_SENTENCE} is generated by a separate finish-sentence API call from the same product evidence.
In this Google description call, treat {FINISH_SENTENCE} as a pre-written sentence that will be inserted
during variant expansion (one finish sentence per variant).

Integration requirements:
- Use {FINISH_SENTENCE} exactly once, as its own sentence.
- Place it after the opening hook (1-2 sentences in), where it reads naturally as a transition into design and material details.
- Keep sentence flow natural before and after insertion.
- Do not rewrite, paraphrase, expand, or duplicate {FINISH_SENTENCE}.

Good flow: "[Benefit-forward opening hook.] {FINISH_SENTENCE} [Design romance and material details.]"
Good flow: "[Concrete spec opening.] [Differentiator sentence.] {FINISH_SENTENCE} [Trust close.]"
Bad flow: "[Awkward transition ...] {FINISH_SENTENCE} {FINISH_SENTENCE} [fragment]."
</finish_sentence_contract>

<description_brief>
Write a Google Shopping description that makes a shopper pick Allied Brass over the generic listing next to it.
Target 800-1100 characters — long enough for rich romance copy that sells the design, not just the specs.

Description structure (follow this order):
1. BENEFIT-FORWARD OPENING HOOK — Lead with what the product does for the customer, not what it is. Frame as a relatable scenario or outcome. Include the collection name and product type keyword in the opening. Do NOT start with generic openers like "Add timeless elegance to your bathroom…" or "Upgrade your bathroom with…" or "This [product] brings refined style…" — those are filler, not hooks.
2. {FINISH_SENTENCE} — Insert after the opening hook (1-2 sentences in), where it reads naturally as a transition. Output exactly as {FINISH_SENTENCE}.
3. DESIGN ROMANCE COPY — Describe how the product looks and feels in the space: the silhouette, the profile of the hardware, how brackets or mounts sit against the wall, the visual effect of the finish, the proportions. Use specific, evocative language (e.g., "disc pivot hardware that sits nearly flush against the mirror surface for a refined, furniture-quality appearance"). This is what differentiates descriptions from generic specs — paint a picture.
4. MATERIAL AND DURABILITY — What it's made of (iron, solid brass), why that matters (corrosion resistance, humidity tolerance), and how the finish is applied (powder-coated, plated).
5. KEY FEATURES AND USE CONTEXT — Concrete details: mounting style, adjustability, space-saving benefit, ideal use locations. Be specific about how the product functions.
6. CROSS-SELL WITH SPECIFIC PIECES — When the product belongs to a collection, mention coordinating items by name (e.g., "coordinates with Astor Place Collection towel bars, robe hooks, and other hardware") rather than generic "coordinating pieces."
7. INSTALLATION NOTE — Mention included hardware, assembly requirements, and note color-coordinated/color-matched screws or concealed mounting where applicable.
8. WARRANTY CLOSE — End with: "Backed by a Limited Lifetime Warranty."

What to EXCLUDE (these kill conversions or create doubt):
- Weight capacity (creates doubt, not confidence)
- Detailed dimensions beyond the primary one (width, height, projection, depth)
- Competitor material names (die-cast zinc, plated alternatives, zinc alloy, chrome-plated steel)
- "Heritage bathroom fixtures" or invented category terms
- "Also searched as" or keyword list patterns
- Meta-search commentary (mentioning what someone searched for)
- "28 finishes" or finish count references (this listing IS a specific finish variant)
- Installation specifics (screw sizes, exact hardware counts)
- Thin descriptions under 600 characters — if the description feels short, add more design detail or use-case context
- HTML tags or special characters
</description_brief>

<worked_examples>
EXAMPLE 1 — Towel Bar (Astor Place Collection, 24 inch, solid brass):

google_title: "{FINISH_NAME} Astor Place Collection 24 Inch Solid Brass Towel Bar | Traditional Wall-Mounted Bathroom Hardware | Allied Brass"

google_description: "A towel bar that earns its spot on the wall — this Astor Place Collection 24-inch solid brass towel bar delivers the kind of heft and clean lines you'd expect from well-made bathroom hardware, with a traditional round-post design that anchors the room without overwhelming it. {FINISH_SENTENCE} The solid brass construction resists the corrosion and tarnishing that plague lesser materials in humid bathroom environments, keeping its good looks intact through years of daily use. Mounts securely to the wall with included hardware and concealed fasteners for a polished, seamless installation. Coordinates naturally with Astor Place Collection robe hooks, toilet paper holders, and other wall-mounted bath accessories for a cohesive traditional hardware set throughout the space. All mounting hardware included; assembly required. Backed by a Limited Lifetime Warranty."

EXAMPLE 2 — Industrial Paper Towel Holder (Pipeline Collection):

google_title: "{FINISH_NAME} Pipeline Collection Wall-Mount Paper Towel Holder | Industrial Steampunk Style | Allied Brass"

google_description: "Bring bold, workshop-inspired character to your kitchen or prep area with this Pipeline Collection wall-mounted paper towel holder, styled with a true steampunk industrial pipe-fitting silhouette that reads as an intentional design statement rather than a DIY afterthought. {FINISH_SENTENCE} The exposed pipe aesthetic features authentic-looking fittings and connection points that give the piece its industrial credibility, while the sturdy iron construction with a durable powder-coated finish ensures it holds up to the daily wear of a working kitchen or utility space. Wall mounting keeps paper towels close at hand while freeing up valuable countertop room — ideal beside a sink, near a coffee station, in a laundry room, or in a garage work area. Color-coordinated screws help the installation look cohesive, and all required mounting hardware is included. Coordinates with Pipeline Collection towel bars, robe hooks, and shelf brackets for a full industrial hardware set. Backed by a Limited Lifetime Warranty."

EXAMPLE 3 — Tilt Mirror (Astor Place Collection, frameless oval, beveled, solid brass):

google_title: "{FINISH_NAME} Astor Place Collection Frameless Oval Tilt Mirror | Solid Brass Wall-Mounted Vanity Mirror | Allied Brass"

google_description: "The right viewing angle for everyone — this Astor Place Collection frameless oval tilt mirror mounts to the wall on two minimal solid brass pivot brackets that let you adjust the mirror forward or backward, making it effortless to dial in a comfortable reflection for different heights and grooming needs at the vanity. {FINISH_SENTENCE} The clean frameless oval form with a polished beveled edge brings a crisp, architectural quality to the bathroom wall — no ornate frame competing for attention, just beautifully proportioned glass and understated round disc pivot hardware that sits nearly flush against the mirror surface for a refined, furniture-quality appearance. Solid brass construction resists corrosion and humidity for lasting good looks in everyday bathroom environments, while concealed screw mounting creates a seamless, floating installation with no exposed fasteners. Coordinates naturally with other Astor Place Collection pieces for a cohesive traditional bathroom hardware set. Mirror glass, two pivot brackets, and all installation hardware included; assembly required. Backed by a Limited Lifetime Warranty."
</worked_examples>

<output_contract>
Return JSON with keys: google_title, google_short_title, google_description, claims.
</output_contract>

<final_quality_gate>
Before returning JSON, perform one silent final pass:
- Remove banned promo words (finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate).
- Remove any meta-search narration ("if you're searching", "if you've been comparing", etc.).
- Verify {FINISH_SENTENCE} appears exactly once in google_description.
- Verify google_title starts with {FINISH_NAME}.
- Verify google_description ends with "Backed by a Limited Lifetime Warranty."
- For "Towel Bars" category, keep "Towel Bar" terminology in both google_title and google_short_title.
If any violation appears, rewrite before returning.
</final_quality_gate>
"""

BING_BRIEF = """\
<platform_rules>
Bing fields only:
- bing_title: variant-aware and must begin with literal {FINISH_NAME}
- bing_description: plain text variant description that includes literal {FINISH_SENTENCE}

Do not generate Google or Shopify behavior in this task.
</platform_rules>

<bing_objective_priority>
Bing optimization order:
1. Product truth and category-faithful naming.
2. Specific differentiation that helps a shopper choose this product.
3. Readable, scan-friendly phrasing that sounds human.
4. Keyword enrichment only when it improves 1-3.

Never force awkward copy to satisfy keyword hints.
Write product copy, not commentary about search behavior.
</bing_objective_priority>

<finish_sentence_contract>
{FINISH_SENTENCE} is generated in a separate finish-sentence API call from the same product evidence.
In this Bing description call, treat {FINISH_SENTENCE} as a pre-written sentence inserted during
variant expansion (one finish sentence per variant).

Integration requirements:
- Use {FINISH_SENTENCE} exactly once, as its own sentence.
- Keep sentence flow natural before and after insertion.
- Do not rewrite, paraphrase, or expand {FINISH_SENTENCE}.

Good flow:
"[Spec-led opening sentence]. {FINISH_SENTENCE} [Evidence-based support sentence]."
Good flow:
"[Concrete product sentence.] [Practical value sentence.] {FINISH_SENTENCE} [Trust close sentence]."
Anti-example:
"If you're comparing options, {FINISH_SENTENCE} {FINISH_SENTENCE} [fragment]."
</finish_sentence_contract>

<title_formula>
Same structure as Google titles:
{FINISH_NAME} [Product Function] [Collection Name Collection] [Primary Dimension*] - Allied Brass

Bing shoppers scan titles quickly. Front-load the most important product identifier after {FINISH_NAME}.
Keep title nouns literal and category-faithful. Use synonym variations in the description body, not in the title.
When category intent is explicit in evidence, keep the primary noun exact:
- "Towel Bars" category -> "Towel Bar" (NEVER "Towel Rack" in title)
- "Robe Hooks" category -> "Robe Hook"
- "Toilet Paper Holders" category -> "Toilet Paper Holder"
</title_formula>

<description_brief>
Write a Bing Shopping description optimized for literal relevance and natural shopper readability.

Structure (700-1000 characters total, plain text):
1. OPEN with a concrete product specification sentence — what this product IS, its primary dimension, and material. Bing rewards front-loaded specs in the first 200 characters.
2. Place {FINISH_SENTENCE} naturally after the opening specs. Output it exactly once as a literal placeholder sentence.
3. BUILD with design details and practical selling points, using synonym variants only when they fit naturally and improve clarity.
4. CLOSE with collection coordination or warranty.

Bing-specific: Keep wording literal and clean. Use synonym variants conditionally, never by quota.
Never use "also searched as" lists or mention what someone searched for.

Same EXCLUDE rules as Google: no weight capacity, no detailed dims, no competitor materials, no "28 finishes," no keyword stuffing.
Also ban promo words in customer-facing copy: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate.
</description_brief>

<output_contract>
Return JSON with keys: bing_title, bing_description, claims.
</output_contract>

<final_quality_gate>
Before returning JSON, perform one silent final pass:
- Remove banned promo words (finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate).
- Remove any meta-search narration ("if you're searching", "if you've been comparing", etc.).
- For "Towel Bars" category, keep "Towel Bar" terminology in bing_title.
If any violation appears, rewrite before returning.
</final_quality_gate>
"""

SHOPIFY_BRIEF = """\
<platform_rules>
Shopify fields only:
- shopify_title: finish-agnostic product page heading
- shopify_description: finish-agnostic HTML conversion copy
- shopify_meta_description: short SERP summary

Do not generate Google/Bing variant behavior in this task.
</platform_rules>

<title_rules>
Shopify product title — this is the H1 on the product page.
- Finish-agnostic (no specific finish names — the product page covers all finishes)
- Do NOT include "Allied Brass" in the title
- Include collection name with "Collection" keyword when available
- Include primary dimension when the product varies by size
- Max 255 characters, but shorter is better (aim for 40-80 chars)
- Must work as a page heading a shopper would actually read
- Keep product noun faithful to category intent ("Towel Bar" for towel-bar categories).

Good: "Skyline Collection 24-Inch Wall Mounted Towel Bar"
Good: "Contemporary Double Robe Hook - Waverly Place Collection"
Bad: "Allied Brass Skyline Collection Solid Brass 24-Inch Wall Mount Towel Bar Holder Rack"
</title_rules>

<description_brief>
Write a Shopify product description in HTML that helps a shopper who landed on this page decide to buy.

Structure:
1. Opening <p>: Start with a buyer problem or desired outcome, then connect it to THIS product. What gap does this product fill in the bathroom? Be specific to the product, not generic.
2. Design story <p>: What makes this product's design special? Collection identity, design elements, style context.
3. Benefits <ul><li>: 4-6 bullet points covering solid brass construction, key dimensions, mounting style, and collection coordination. Use <strong> for the lead phrase of each bullet.
4. Closing <p>: Trust signal — warranty, what's included, or collection coordination call-to-action.

Do NOT mention any specific finish — this content serves all 28 variants.
Do NOT include weight capacity, detailed dimensions, or installation specifics.
Do NOT use "heritage bathroom fixtures" or competitor material names.
Do NOT use banned promo words in customer-facing copy: finest, luxurious, premium, exclusive, exceptional, unparalleled, superior, exquisite, ultimate.
</description_brief>

<meta_description>
140-160 characters. Standalone summary with the primary keyword. Must work as a Google SERP snippet.
Include product type, key differentiator, and collection name.
</meta_description>

<output_contract>
Return JSON with keys: shopify_title, shopify_description, shopify_meta_description, claims.
</output_contract>
"""

FINISH_BRIEF = """\
<platform_rules>
Finish-sentence fields only:
- sentences: array of finish sentence objects

Do not generate Google/Bing/Shopify long-form copy in this task.
</platform_rules>

<finish_sentence_rules>
Generate exactly 28 finish sentences — one for each Allied Brass finish.

Each sentence connects THIS SPECIFIC PRODUCT to THIS SPECIFIC FINISH. Not generic finish blurbs.

Rules:
- 40-80 characters per sentence (concise — these get inserted into descriptions)
- Reference the product type or a design detail, not just the finish color
- Vary the sentence structure across finishes — don't use the same template 28 times
- The sentence should read naturally when dropped into a product description mid-paragraph

Good for a towel bar: "Antique Brass warms the straight bar with a soft, aged glow."
Good for a robe hook: "Polished Chrome keeps the curved hook bright and easy to clean."
Bad (generic): "Antique Brass adds warm tones to your bathroom." ← not product-specific
Bad (too long): "The Antique Brass finish gives this 24-inch wall-mounted towel bar a soft, aged warmth that coordinates with traditional bathroom hardware." ← exceeds 80 chars
</finish_sentence_rules>

<output_contract>
Return JSON with key: sentences.
</output_contract>
"""

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
