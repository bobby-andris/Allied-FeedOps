---
status: gaps_found
phase: 25
updated: 2026-02-23
---

# Phase 25 Verification: Evaluate & Iterate

## Verification Status: GAPS FOUND

Plan 25-01 (deploy + regenerate) completed successfully. Plan 25-02 (human evaluation) completed Round 1 but **failed all three success criteria**. Iteration is required before Plan 25-03 (publish) can proceed.

## What Was Tested

- 10 SKUs across 10 categories regenerated via Cloud Run `/regenerate` endpoint
- GPT-5.2 with skill-enriched prompts (Phase 24 architecture: creative brief, 8 runtime skills, 24-category YAML guidance)
- Blind A/B comparison: old vs new content shown without labels, human-scored

### SKUs Tested
1025U (Paper Towel Holders), 1016 (Towel Rings), 102 (Cabinet Hardware), 1020-3 (Multi Hooks), 1024 (Toilet Paper Holders), 1020 (Robe Hooks), DMF-2/2X (Make-Up Mirrors), WP-2/16-GAL (Glass Shelves), 1098 (Shower Curtain Brackets), CL-22 (Retractable Hooks)

6 with gold standard examples, 4 without. 1 multi-SKU family member (DMF-2/2X).

## Round 1 Results

| # | SKU | Category | New Won Title? | New Won Desc? | Differentiation |
|---|-----|----------|:-:|:-:|:-:|
| 1 | 1025U | Paper Towel Holders | No | **Yes** | **Yes** |
| 2 | 1016 | Towel Rings | No | **Yes** | No |
| 3 | 102 | Cabinet Hardware | No | **Yes** | **Yes** |
| 4 | 1020-3 | Multi Hooks | No | No | No |
| 5 | 1024 | Toilet Paper Holders | No | No | No |
| 6 | 1020 | Robe Hooks | No | No | No |
| 7 | DMF-2/2X | Make-Up Mirrors | No | No | No |
| 8 | WP-2/16-GAL | Glass Shelves | No | **Yes** | **Yes** |
| 9 | 1098 | Shower Curtain | No | **Yes** | No |
| 10 | CL-22 | Retractable Hooks | No | **Yes** | No |

**Title wins (new):** 0/10 (target: 8/10) — FAIL
**Description wins (new):** 6/10 (target: 8/10) — FAIL
**Differentiation passes:** 3/10 (target: 8/10) — FAIL

## Gaps

### Gap 1: Titles never include finish name
- **status:** failed
- **severity:** critical
- **evidence:** 0/10 new titles won. Old titles always include finish (e.g., "Antique Bronze 6-Inch...") while new titles omit it. Evaluator chose old title every time primarily because of finish name presence.
- **root_cause:** The `/regenerate` endpoint generates for master SKU without `finish_code`. The SYSTEM_PROMPT `platform_rules` section says "Product type in first 30 chars" but does NOT mandate finish name. The `FINISH_CONTEXT_TEMPLATE` in `prompts.py` DOES say "include finish_name early in title" but is only injected when `finish_code` is explicitly passed.
- **files_affected:** `src/feedops/pipeline/prompts.py` (platform_rules, FINISH_CONTEXT_TEMPLATE), `src/feedops/api/main.py` (regenerate endpoint)

### Gap 2: Differentiation is generic category-level, not product-specific
- **status:** failed
- **severity:** critical
- **evidence:** 3/10 pass differentiation. Evaluator quotes: "Description A tries to be too cute and seems stuffed with fluff" (1020-3). "Gets differentiation wrong — the real differentiator is that shower rod mounts are usually ugly and take away from the aesthetic but ours enhance the room" (1098). "Doesn't identify differentiators correctly and they don't seem genuine" (DMF-2/2X).
- **root_cause_architecture:** The prompt architecture has TWO layers that both contribute guidance, and they conflict:
  1. **Skills** (`.claude/skills/*/SKILL.md`) — 172K-254K chars of rich, nuanced brand voice, storytelling patterns, competitive positioning, and platform rules. Loaded by `skill_loader.py` and appended to SYSTEM_PROMPT.
  2. **Hardcoded Python** (`prompts.py` SYSTEM_PROMPT + `prompt_builder.py` customer_framing/competitive_positioning blocks) — ~2K chars of static, generic guidance that gets injected into EVERY prompt.
  The hardcoded Python blocks provide GENERIC competitive bullets identical for every product: "Solid brass vs die-cast zinc", "28 finishes vs 4-12", "41 collections", "Concealed mounting", "Lifetime warranty". GPT-5.2 latches onto these simple, explicit instructions rather than the richer (but longer) skill content. The skills contain nuanced guidance about product-specific storytelling, but the hardcoded blocks override that nuance with a fixed checklist.
- **root_cause_data:** The `prompt_builder.py` customer framing block provides only `Product category: X` and `Collection: Y` — no product-specific data. The evidence table HAS `narrative_copy` and `bullet_1` through `bullet_6` with manufacturer descriptions of what makes each product unique, but these are never extracted and highlighted in the prompt. GPT-5.2 invents scenarios from scratch instead of building on the real product story.
- **files_affected:** `src/feedops/pipeline/prompts.py` (creative_direction, competitive framing in SYSTEM_PROMPT), `src/feedops/api/prompt_builder.py` (customer_framing block lines 258-282, competitive_positioning block lines 284-308)

### Gap 3: New descriptions oscillate between "too fluffy" and "too robotic"
- **status:** failed
- **severity:** high
- **evidence:** Evaluator overall note: "There were a lot of descriptions where one was too robotic (focused on dimensions and mounting) without focusing on design. Meanwhile the other seemed too fluffy — trying to focus on differentiators but did so in a way that did not come across genuinely."
- **root_cause:** The `creative_direction` in SYSTEM_PROMPT teaches GPT-5.2 to open with "a scenario, a benefit, or a problem — never a spec." This pushes toward manufactured scenarios ("Stop draping towels over the shower door") that feel fluffy. When GPT-5.2 tries to follow BOTH the "never lead with specs" rule AND the generic competitive checklist, it produces unnatural copy. The old descriptions were more straightforward (spec-heavy but honest), which evaluators preferred 4/10 times.
- **fix_direction:** The creative direction should teach GPT-5.2 to lead with what makes THIS product's DESIGN special (grounded in evidence), not with manufactured problems or generic competitive frames.
- **files_affected:** `src/feedops/pipeline/prompts.py` (creative_direction block)

### Gap 4: Factual errors in generated content
- **status:** failed
- **severity:** critical
- **evidence:** SKU 1024 (Toilet Paper Holders): New description claims "quick roll change without wrestling a spring-loaded roller" but this IS a spring-loaded design. SKU WP-2/16-GAL: Suggests hanging "along the tub wall" which doesn't make sense for this product.
- **root_cause:** The `accuracy_guardrail` in SYSTEM_PROMPT says "Every claim must be verifiable from the evidence table" but the creative_direction simultaneously pushes for scenario-based openers that encourage the model to invent context. When GPT-5.2 tries to create a compelling scenario, it sometimes fabricates product features.
- **files_affected:** `src/feedops/pipeline/prompts.py` (accuracy_guardrail needs strengthening, creative_direction needs to stop encouraging invented scenarios)

### Gap 5: "28 finishes" mentioned on variant-specific listings
- **status:** failed
- **severity:** medium
- **evidence:** Evaluator note: "Many descriptions include information about offering the product in 28 finishes when these descriptions are for specific variants in one finish."
- **root_cause:** The competitive_positioning block in `prompt_builder.py` always includes "28 finishes vs competitors' 4-12 finish options" regardless of whether the listing is for a specific variant. On a variant page for "Antique Bronze Towel Ring," mentioning 28 other finishes is irrelevant noise.
- **files_affected:** `src/feedops/api/prompt_builder.py` (competitive_positioning block)

## User Direction for Gap Closure

**Critical architectural insight from the user:**

> "It seems like the creative briefs, customer framing, and competitive positioning for each product were guesses based on the broader product category without focusing on the individual product itself and what makes it unique and different."

> "Can we ensure that our skills are truly being utilized? A lot of your code seems to hardcode this but if we're truly using our skills wouldn't we want to change this in our skills directly?"

**The user's mandate:** Skills (`.claude/skills/*/SKILL.md`) should be the **single source of truth** for brand voice, storytelling patterns, competitive positioning, and platform rules. The hardcoded guidance in `prompts.py` and `prompt_builder.py` should be minimized — serving only as structural scaffolding that defers to skills, not as parallel guidance that competes with skills.

**The fix should:**
1. **Audit what skills contain vs what's hardcoded** — identify duplications and conflicts
2. **Remove or reduce hardcoded guidance** that duplicates or contradicts skills
3. **Update skills** where the evaluation revealed gaps (e.g., skills should teach product-specific design storytelling, not generic competitive frames)
4. **Feed product-specific data** (narrative_copy, bullets) into the prompt so GPT-5.2 has real differentiators to work with instead of inventing them
5. **Fix title generation** to always include finish name for Google/Bing
6. **Re-run all 10 SKUs** and re-evaluate

## Artifacts

- Blind A/B comparison: `.planning/phases/25-evaluate-iterate/25-01-evaluation-comparisons.md`
- Evaluation results: `.planning/phases/25-evaluate-iterate/25-02-evaluation-results.md`
- Raw evaluator input: `docs/blind_test_evaluations.txt`
- Plan 25-01 summary: `.planning/phases/25-evaluate-iterate/25-01-SUMMARY.md`

## Key Files for Gap Closure

### Prompt architecture (where hardcoded guidance lives)
- `src/feedops/pipeline/prompts.py` — SYSTEM_PROMPT (creative_direction, brand_voice, accuracy_guardrail, platform_rules), USER_PROMPT_TEMPLATE, VARIANT_USER_PROMPT_TEMPLATE
- `src/feedops/api/prompt_builder.py` — build_core_prompt() assembles user prompt with customer_framing (lines 258-282), competitive_positioning (lines 284-308)
- `src/feedops/api/prompt_loader.py` — get_system_prompt() appends skill content to SYSTEM_PROMPT

### Skill loader (how skills get injected)
- `src/feedops/pipeline/skill_loader.py` — loads SKILL.md files, wraps in XML tags, appends to system prompt

### Skills (the source of truth that should be the authority)
- `.claude/skills/allied-brass-brand-expert/SKILL.md` — brand voice, competitive positioning
- `.claude/skills/product-storytelling/SKILL.md` — design storytelling patterns
- `.claude/skills/google-shopping-content/SKILL.md` — Google Shopping title/description rules
- `.claude/skills/bing-shopping-content/SKILL.md` — Bing Shopping rules
- `.claude/skills/shopify-conversion-content/SKILL.md` — Shopify conversion rules
- `.claude/skills/quality-evaluation/SKILL.md` — 10-criterion quality rubric
- `.claude/skills/finish-expertise/SKILL.md` — finish integration guidance
- `.claude/skills/collection-storytelling/SKILL.md` — collection DNA for 41 collections

### Runtime configs (YAML distillations of skills — secondary to skills)
- `src/feedops/config/*.yaml` — 8 config files, loaded by shopping_intelligence.py and prompt_builder.py

### Evidence data (where product-specific differentiators exist)
- Evidence table includes: `narrative_copy`, `bullet_1` through `bullet_6`, `material`, `mounting_type`, `weight_capacity`, `warranty`, dimensions, collection info
- Currently: only `material` is extracted by prompt_builder.py for competitive positioning
- Needed: narrative_copy and bullets should be extracted and highlighted as the product's design story

### Regeneration endpoint
- `src/feedops/api/main.py` — `/regenerate` endpoint (needs to pass finish context for Google/Bing title generation)
