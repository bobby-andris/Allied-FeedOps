# Phase 23: Foundation - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix GPT-5.2 integration bugs and establish the creative direction layer — gold standard examples across major categories and a quality rubric that rewards differentiation over compliance. The creative direction is captured in 8 Claude Code skills and 8 runtime YAML configs; this phase wires them into the live pipeline and loads gold standards into the database.

</domain>

<decisions>
## Implementation Decisions

### Creative Direction (Already Complete)

All creative direction decisions are captured in the 8 Claude Code skills:

- **Voice & brand**: `allied-brass-brand-expert` — tone (confident but accessible, design-aware but practical), banned words, emotional anchoring pattern, competitor contrast rules, the one-two punch (functionality + finish variety)
- **Quality rubric**: `quality-evaluation` — 10 weighted criteria replacing the current 6-criterion self_score (Hook Quality 15%, Product Specificity 15%, Competitive Differentiation 12%, Keyword Integration 10%, Customer Scenario 10%, Emotional Resonance 10%, Factual Accuracy 10%, Platform Compliance 8%, Finish Integration 5%, Variety Score 5%)
- **Gold standards**: 30 total examples already written across 3 platform skills — 10 Google (avg 89.3/100), 10 Bing (avg 87.8/100), 10 Shopify (avg 88.7/100) — covering paper towel holders, toilet paper holders, grab bars, cabinet knobs, mirrors, makeup mirrors, glass shelves, multi hooks, guest towel holders, corner shower baskets
- **Finish expertise**: `finish-expertise` — all 28 finishes with visual descriptions, design context, search keywords, and 3 example sentences each
- **Product storytelling**: `product-storytelling` — 4 opening approaches (scenario, benefit, design, problem), customer scenarios by category, feature-to-benefit translations, design style hooks
- **Collection storytelling**: `collection-storytelling` — 41 collections with style categories, 5 integration patterns, cross-sell language

### Gold Standard Loading

- Gold examples from the 3 platform skills need to be inserted into the `prompt_templates` table
- The 10 Google Shopping gold standards are the primary set for pipeline injection (Google is the primary platform)
- Categories covered: towel bars, grab bars, shower accessories, mirrors, cabinet hardware, toilet paper holders, paper towel holders, multi hooks, guest towel holders, glass shelves — exceeds the 7-category minimum
- Format: store as `gold_standard_examples` JSONB in `prompt_templates`

### GPT-5.2 Bug Fixes (Technical — No User Decisions Needed)

All 5 bugs are documented in CLAUDE.md and `docs/research/gpt52-best-practices.md`:
1. Temperature/reasoning_effort conflict (mutually exclusive params)
2. Missing reasoning_effort default (unset = zero reasoning)
3. Legacy json_object instead of json_schema strict mode
4. No prompt_cache_retention for batch runs
5. System prompt uses === headers instead of XML tags

### Quality Rubric Wiring

- Replace the 6-criterion `self_score` in `prompts.py` CANDIDATE_SCHEMA with the 10-criterion rubric from `quality-evaluation` skill
- The `quality_rubric.yaml` runtime config already exists — needs to be loaded by prompt_builder.py
- Batch evaluation capability: ability to score multiple SKUs programmatically (GOLD-04)

### Claude's Discretion

- Exact implementation approach for each GPT-5.2 bug fix
- How to structure gold standard data in prompt_templates JSONB
- Batch evaluation implementation details
- XML tag naming conventions for the system prompt restructuring

</decisions>

<specifics>
## Specific Ideas

- The 10 Google Shopping gold standards in `google-shopping-content` skill are the canonical examples — average 856 chars, average score 89.3/100
- Current content scores ~31-52/100 on the new rubric vs 81-98/100 on the old rubric — the 50-point gap IS the problem
- The quality-evaluation skill includes 10 before/after examples showing exactly what's wrong and how to fix it
- Runtime YAML configs are designed to stay under specific token budgets (brand_voice under 40 lines, storytelling_patterns under 120 lines)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. All creative direction work was pre-captured in the skill creation sessions.

</deferred>

---

*Phase: 23-foundation*
*Context gathered: 2026-02-21*
