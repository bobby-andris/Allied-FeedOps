# Phase 20: Targeted Fixes & Intelligence Application - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Apply targeted fixes and intelligence from Phases 17-19 to content and image generation. Wire prompt paths correctly, activate feature flags, integrate Google Shopping ranking intelligence into prompts, incorporate visual ranking factors into image generation, and switch to GPT-5.2. Does NOT include new UI features, new generation capabilities, or measurement infrastructure (already complete in Phase 19).

</domain>

<decisions>
## Implementation Decisions

### Prompt parity (FIX-01)
- Shared module approach: extract prompt construction into a common module that both single-SKU and batch paths import
- Base prompt is identical for both paths (segment strategy, keyword plan, gold examples, Shopping intelligence)
- Single-SKU path layers user feedback on top of the shared base prompt
- Feedback is additive — enriches the base prompt, doesn't fork it
- Pattern: `batch = core_prompt(sku) → model` / `single-SKU = core_prompt(sku) + feedback_layer → model`

### User feedback on single-SKU regeneration
- Structured controls + free-text: tone/style selector, content emphasis (finish, dimensions, use case, compatibility, luxury positioning), length control (title and description independently), plus free-text for anything else
- Feedback weighting: user corrections are strongly weighted but model can still balance against SEO/Shopping best practices (weighted blend, not hard override)
- Persistent corrections: feedback saved per SKU record — every future regeneration for that SKU automatically includes prior corrections
- Addresses the recurring issue of prompts ignoring feedback: persistent corrections accumulate, so repeated issues get resolved permanently

### Feature flag activation (FIX-02)
- Wire PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 to active generation code paths
- Toggling a flag must produce an observably different prompt structure
- Implementation details at Claude's discretion

### Google Shopping prompt integration (GOOG-04)
- Separate "Google Shopping Optimization" section in the prompt — distinct from base rules, independently updatable
- Three-layer intelligence hierarchy:
  1. **Universal rules** — fundamental Shopping ranking factors that apply to all products
  2. **Category-specific guidance** — varies by custom_label_0 (60 product categories driving Shopping funnels, see AB_GADS_ACCT_STRUCTURE.md)
  3. **Product-type/product-specific intelligence** — auto-inferred from search term data, competitor patterns, and product attributes
- Curated + auto-inferred: system auto-generates category intelligence, manual overrides/additions take priority
- Storage: Claude's discretion with lean toward Python YAML/config files (version-controlled, reviewable, deploys as a unit)
- Allied Brass USP: products are both beautifully designed AND highly functional — intelligence must reflect this dual positioning, not generic category descriptions
- custom_label_0 is the primary segmentation key (maps to Shopping funnel campaigns: `AVD - Shopping - US - {custom_label_0} - {HIGH|MEDIUM|LOW}`)

### Image generation guidance (GOOG-05)
- Balance lifestyle aspiration with product clarity — product fidelity is the non-negotiable constraint
- Product must be indistinguishable from the actual physical product (exact details, finish accuracy, design precision)
- Scene enhances the product, never competes with it
- Three-dimensional image intelligence:
  1. **Category** — drives the scene environment (bathroom hardware in bathroom settings, etc.)
  2. **Finish** — drives lighting and material rendering (oil-rubbed bronze vs polished chrome look very different)
  3. **Collection** — drives staging style/environment (Pipeline collection gets industrial-loft feel, Carolina Crystal gets elegant traditional setting, etc.)
- Collection descriptions already exist in database (imported from `data/Collection_Descriptions_Complete_All_41_20260124.csv`) — 41 collections with design DNA, style group, subgroup, and design keywords
- Collection-inspired environments but product accuracy cannot be compromised for scene aesthetics

### Model switch (MODEL-03)
- Straight switch to GPT-5.2 — benchmarks are clear (90.0/100 vs GPT-4o at 76.4/100), no A/B needed
- Implementation: change model param, change `max_tokens` to `max_completion_tokens`, strengthen accuracy guardrail
- Cost is negligible (under $20 for full 2,784 SKU catalog at batch pricing)
- Fallback strategy: Claude's discretion (configurable vs hardcoded)
- Gemini 2.5 Pro noted as future batch alternative (87.8/100, 1M context window) — do not implement now

### Claude's Discretion
- Feature flag implementation approach (how PROMPT_CONTRACT_V2 and INTENT_CURATOR_V1 wire to code paths)
- Intelligence storage format (YAML vs JSON config, exact file structure) — lean toward Python config files
- Model configurability (env var vs hardcode for GPT-5.2)
- Exact structured feedback UI components (specific control designs)
- How auto-inferred category intelligence is generated and refreshed

</decisions>

<specifics>
## Specific Ideas

- "I don't want to silo our output by having intel be the same for every product in every category — it inhibits one of our USPs"
- "The best we can do to achieve product-specific intelligence will only make our output better and stand out that much more"
- "Sometimes there are things the prompt gets wrong regardless of how many times it is regenerated with feedback" — persistent corrections solve this
- "Never compromise the ability to focus on the product to ensure that the exact product is used and matches every detail and is indistinguishable from our actual product" — product fidelity is sacred
- Collection design DNA should inform image generation: Pipeline = industrial, Carolina Crystal = elegant traditional, Pacific Beach = coastal modern, etc.
- Shopping funnel segmentation (custom_label_0) is already the backbone of the Google Ads account structure — intelligence should follow the same segmentation

</specifics>

<deferred>
## Deferred Ideas

- Gemini 2.5 Pro as offline batch generation alternative — future phase when batch volume warrants it
- Dashboard UI for editing category-specific intelligence rules — future phase (for now, config files are sufficient)
- Collection description enrichment/updates — verify database import is complete, but collection data management is separate scope

</deferred>

---

*Phase: 20-targeted-fixes-intelligence-application*
*Context gathered: 2026-02-21*
