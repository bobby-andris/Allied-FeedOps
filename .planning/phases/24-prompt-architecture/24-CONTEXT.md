# Phase 24: Prompt Architecture - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the entire generation prompt from a compliance document into a creative brief — SYSTEM_PROMPT fully rewritten with XML structure, full Claude Code skills loaded into prompts (not just YAML distillations), category guidance expanded to top-20 revenue categories via shopping_intelligence.yaml as canonical source, and customer framing + competitive positioning handled per-SKU by GPT-5.2 reasoning from skills + evidence.

</domain>

<decisions>
## Implementation Decisions

### SYSTEM_PROMPT Rewrite (PRMT-01)
- **Full rewrite** — scrap the current P0/P1/P2 compliance structure entirely
- Open with creative direction: what great Allied Brass content sounds like, the brand voice, storytelling approach
- Move accuracy guardrail lower in the prompt — Claude has discretion on how to preserve factual grounding without making it the dominant voice (weave into creative brief vs separate section)
- Platform-specific rules: Claude decides whether to keep in system prompt or move to dynamic user prompt based on caching/modularity tradeoffs

### Skill Loading Strategy (PRMT-02)
- **Load full Claude Code skills into prompts, not just YAML distillations** — skills are 5-10x richer and quality upfront is cheaper than reruns
- **Adaptive loading by context:**
  - **Batch runs**: Load ALL full skills into the system prompt (cached across all SKUs = amortized cost)
  - **Single SKU regeneration**: Load core skills always + only platform-relevant skills (e.g., Google-only SKU skips Bing/Shopify skills)
- **Core skills (always load):** brand voice + quality rubric at minimum, but prioritize maximum quality — load as many skills as practical since getting it right the first time avoids expensive regeneration cycles
- **Conditional skills:** Platform-specific (google-shopping-content, bing-shopping-content, shopify-conversion-content), finish guide (only when variant), collection stories (only when collection data exists)
- Existing YAML configs remain as backup/fallback if skill loading fails, but skills are the primary source
- Single unified loader preferred for efficiency (one module loads all skills/configs)

### Customer Framing (PRMT-04)
- **Per master SKU, not generic** — every master SKU gets its own customer framing
- GPT-5.2 reasons out the customer scenario using: full skills (storytelling patterns, brand voice) + product evidence table + its own analysis of who buys this specific product and why
- Not just historical data or YAML templates — the model should think about the product and apply customer scenarios intelligently
- Category-level storytelling patterns from skills serve as inspiration/framework, not rigid templates

### Competitive Positioning (PRMT-05)
- **GPT-5.2 reasons it out per-SKU** from full skills (brand voice competitor contrasts, shopping intelligence USPs) + product evidence
- No separate competitive data pipeline needed — the skills already contain detailed positioning guidance
- Must not make claims that aren't factual — model reasons from evidence, not fabricates
- Falls back to generic brand voice contrasts (brass vs zinc, 28 finishes, lifetime warranty) when product evidence is thin

### Category Guidance (PRMT-03)
- **shopping_intelligence.yaml is the canonical source** — replace the old 3-group `_CATEGORY_GUIDANCE` in prompts.py
- Expand from current 15 categories to cover top-20 revenue categories
- Query database for actual top-20 revenue categories to identify the 5 missing ones
- Old `_CATEGORY_GUIDANCE` dict and `build_category_guidance()` function in prompts.py can be removed

### Claude's Discretion
- Gold standard example placement (system prompt vs user prompt) — balance quality vs caching
- Exact system prompt structure and XML tag naming
- How to split static vs dynamic content for optimal prompt caching
- Loader architecture details (single unified loader vs per-config)
- How aggressively to load skills for single-SKU regeneration (balance quality vs cost)
- Whether platform rules move from system prompt to user prompt

</decisions>

<specifics>
## Specific Ideas

- "Quality upfront is cheaper than reruns" — design for maximum quality in first pass, even if token cost per generation is higher
- Skills are the primary injection source, YAMLs become fallback — this is a significant shift from the original dual-use architecture where YAMLs were the runtime source
- The adaptive batch vs single-SKU loading is a novel pattern — no existing code does this, will need a mode parameter in prompt_builder.py
- shopping_intelligence.py already has the YAML loader pattern (lru_cache) — skill loading can follow a similar caching approach

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. The skill-loading approach is a bigger architectural shift than originally planned but fits within PRMT-02's scope.

</deferred>

---

*Phase: 24-prompt-architecture*
*Context gathered: 2026-02-21*
