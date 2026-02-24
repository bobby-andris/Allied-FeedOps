# Roadmap: Allied FeedOps

## Milestones

- ✅ **Phase 0 Discovery** — API validation and research (shipped 2026-02-13)
- ✅ **v1.0 Historical Data Backfill** — Phases 05-08 (shipped 2026-02-13)
- ✅ **v1.1 Dashboard UX & Quality** — Phases 9-16 (shipped 2026-02-21)
- ✅ **v1.2 Impact Debug & Fix** — Phases 17-22 (shipped 2026-02-21)
- 🚧 **v1.3a Content Generation Excellence** — Phases 23-25 (in progress)

## Phases

<details>
<summary>✅ Phase 0 Discovery — SHIPPED 2026-02-13</summary>

- [x] Phase 01: API Capability Validation (2/2 plans) — 2026-02-12
- [x] Phase 02: Comprehensive Data Discovery (4/4 plans) — 2026-02-12
- [x] Phase 03: Sample Testing & Analysis (3/3 plans) — 2026-02-13
- [x] Phase 04: Documentation & Decision (2/2 plans) — 2026-02-13

</details>

<details>
<summary>✅ v1.0 Historical Data Backfill — SHIPPED 2026-02-13</summary>

- [x] Phase 05: Job Infrastructure & Foundation (4/4 plans) — 2026-02-13
- [x] Phase 06: Data Collection Pipeline (3/3 plans) — 2026-02-13
- [x] Phase 07: Data Quality & Validation (4/4 plans) — 2026-02-13
- [x] Phase 08: Monitoring & Automation (5/5 plans) — 2026-02-13

</details>

<details>
<summary>✅ v1.1 Dashboard UX & Quality — SHIPPED 2026-02-21</summary>

- [x] Phase 9: SKU Review Revamp (3/3 plans) — 2026-02-18
- [x] Phase 10: Image Workflow Improvements (3/3 plans) — 2026-02-19
- [x] Phase 11: Performance Page Enhancements (3/3 plans) — 2026-02-19
- [x] Phase 12: Dashboard Audit & Cleanup (3/3 plans) — 2026-02-19
- [x] Phase 13: Fix Google Ads Data Sourcing (3/3 plans) — 2026-02-19
- [x] Phase 14: Complete 180-day Backfill & Monitoring Fixes (3/3 plans) — 2026-02-19
- [x] Phase 15: Google Ads Data Backfill & Monitoring Verification (3/3 plans, partial) — 2026-02-20
- [x] Phase 16: Fix Google Ads Backfill Pipeline (3/3 plans) — 2026-02-20

</details>

<details>
<summary>✅ v1.2 Impact Debug & Fix — SHIPPED 2026-02-21</summary>

- [x] Phase 17: Google Shopping Intelligence & Model Research (3/3 plans) — 2026-02-21
- [x] Phase 18: Diagnosis — Establish Ground Truth (3/3 plans) — 2026-02-21
- [x] Phase 19: Measurement Infrastructure (4/4 plans) — 2026-02-21
- [x] Phase 20: Targeted Fixes & Intelligence Application (4/4 plans) — 2026-02-21
- [x] Phase 21: Apply Database Migrations & Update Schema Docs (1/1 plan) — 2026-02-21
- [x] Phase 22: Fix Integration Bugs & Close Documentation Gaps (2/2 plans) — 2026-02-21

</details>

### 🚧 v1.3a Content Generation Excellence (In Progress)

**Milestone Goal:** Fix content quality at its source — repair GPT-5.2 integration bugs, establish gold standards and a differentiation-first quality rubric, rewrite prompts as creative briefs, wire all 8 runtime configs, and validate with human evaluation across 10 representative SKUs.

**Dependency chain:** GPT-5.2 bugs fixed first (can't evaluate quality with broken model config) → creative direction locked (gold standards + rubric) → prompt architecture rewritten → evaluate and ship.

- [x] **Phase 23: Foundation** — Fix GPT-5.2 bugs, create gold standards, rewrite quality rubric (completed 2026-02-21)
- [x] **Phase 24: Prompt Architecture** — Rewrite SYSTEM_PROMPT as creative brief, wire all 8 runtime configs, expand category guidance (completed 2026-02-21)
- [ ] **Phase 25: Evaluate & Iterate** — Generate 10 test SKUs, human eval, iterate, publish test batch

## Phase Details

### Phase 23: Foundation
**Goal**: The generation pipeline runs correctly on GPT-5.2 and has a creative direction layer to generate against — gold standard examples across major categories and a rubric that rewards differentiation over compliance.
**Depends on**: Phase 22 (v1.2 complete)
**Requirements**: GPT52-01, GPT52-02, GPT52-03, GPT52-04, GPT52-05, GOLD-01, GOLD-02, GOLD-03, GOLD-04
**Success Criteria** (what must be TRUE):
  1. A SKU generated through the pipeline produces output without API errors caused by temperature/reasoning_effort conflict or missing cache retention config
  2. Generated content uses structured JSON output (json_schema strict mode) — no fallback retry loops from legacy json_object format
  3. The system prompt and all injected config sections use XML tags, not === headers — visually verifiable in prompt logs
  4. At least 15 gold standard examples exist in the prompt_templates table, covering towel bars, grab bars, shower accessories, mirrors, and at least 3 other categories
  5. Running a quality evaluation on a batch of SKUs returns a score breakdown rewarding differentiation and emotional resonance, not just rule compliance
**Plans**: 2 plans
Plans:
- [ ] 23-01-PLAN.md — Fix all 5 GPT-5.2 integration bugs (temperature/reasoning conflict, default reasoning_effort, json_schema strict mode, cache retention, XML tags)
- [ ] 23-02-PLAN.md — Load 15 gold standards into DB, replace self_score with 10-criterion rubric, create batch evaluation script

### Phase 24: Prompt Architecture
**Goal**: The entire generation prompt is rewritten from a compliance document into a creative brief — SYSTEM_PROMPT rebuilt with XML structure and positive examples, all 8 runtime YAML configs loaded and injected, category guidance expanded to cover the top-20 revenue categories, and customer use case and competitive positioning evidence added to every prompt.
**Depends on**: Phase 23
**Requirements**: PRMT-01, PRMT-02, PRMT-03, PRMT-04, PRMT-05
**Success Criteria** (what must be TRUE):
  1. The SYSTEM_PROMPT in prompts.py is restructured with XML tags (not === headers) and opens with a creative direction section rather than a list of restrictions
  2. All 8 YAML configs (brand_voice, quality_rubric, finish_guide, storytelling_patterns, collection_stories, platform_bing, platform_shopify, shopping_intelligence) are loaded by prompt_builder.py and appear in generated prompt logs
  3. A product in any of the top-20 revenue categories receives category-specific guidance in its prompt (not the generic fallback)
  4. The prompt for any SKU includes a customer framing block (who buys this, what problem it solves) and a competitive positioning block
**Plans**: 2 plans
Plans:
- [ ] 24-01-PLAN.md — Rewrite SYSTEM_PROMPT as creative brief, build unified skill loader, wire skills into prompt_builder.py
- [ ] 24-02-PLAN.md — Expand category guidance to 20+ categories, add customer framing and competitive positioning blocks, remove legacy category guidance

### Phase 25: Evaluate & Iterate
**Goal**: The improved pipeline is validated against reality — 10 representative SKUs regenerated with the new prompt architecture, old vs. new descriptions compared side-by-side with human scores, iteration applied where scores fall short, and a test batch published to begin measuring CTR/CVR delta.
**Depends on**: Phase 24
**Requirements**: EVAL-01, EVAL-02, EVAL-03, EVAL-04, EVAL-05, EVAL-06
**Success Criteria** (what must be TRUE):
  1. 10 SKUs spanning at least 4 different product categories have been regenerated using the Phase 24 prompt architecture
  2. A side-by-side comparison document exists showing old vs. new descriptions for all 10 SKUs with human quality scores
  3. At least 8 of the 10 new descriptions are rated "significantly better" by human evaluation (not Claude self-scoring)
  4. At least 8 of the 10 new descriptions pass the differentiation test: a reader can identify them as Allied Brass, not a generic hardware store
  5. Average quality score across the 10 test SKUs on the new rubric is at or above 85%
  6. The test batch is published to Google Sheets supplemental feed so CTR/CVR delta measurement can begin
**Plans**: 7 plans
Plans:
- [x] 25-01-PLAN.md — Deploy skill-enriched prompts to Cloud Run, select 10 representative SKUs, regenerate, build blind A/B comparison document
- [x] 25-02-PLAN.md — Human blind evaluation, quality scoring (Round 1: FAIL — 0/10 titles, 6/10 desc, 3/10 diff)
- [ ] 25-03-PLAN.md — Approve and publish highest-scoring SKU to Google Sheets supplemental feed
- [x] 25-04-PLAN.md — Gap closure: refactor prompt architecture (skills as authority, product-specific data, finish in titles, accuracy guardrail)
- [x] 25-05-PLAN.md — Gap closure: regenerate all 10 SKUs with refactored prompts, Round 2 human evaluation (FAIL — 4/10 titles, 6/10 desc consensus)
- [ ] 25-06-PLAN.md — Gap closure: update skills (remove competitor materials, add Robert's title formula, evidence exclusion rules) + SYSTEM_PROMPT prohibitions
- [ ] 25-07-PLAN.md — Gap closure: regenerate all 10 SKUs with Round 3 fixes, Round 3 human evaluation

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01-04 | Phase 0 | 11/11 | Complete | 2026-02-13 |
| 05-08 | v1.0 | 16/16 | Complete | 2026-02-13 |
| 09-16 | v1.1 | 24/24 | Complete | 2026-02-21 |
| 17-22 | v1.2 | 17/17 | Complete | 2026-02-21 |
| 23 | v1.3a | 2/2 | Complete | 2026-02-21 |
| 24 | 2/2 | Complete    | 2026-02-21 | - |
| 25 | 5/7 | In Progress|  | - |

---
*Phase 0 completed: 2026-02-13*
*v1.0 milestone completed: 2026-02-13*
*v1.1 milestone completed: 2026-02-21*
*v1.2 milestone completed: 2026-02-21*
*v1.3a roadmap created: 2026-02-21*

### Phase 25.1: Prompt Architecture Research (INSERTED)

**Goal:** Investigate why GPT-5.2 produces keyword-stuffed, monotonous, filler-heavy content despite 3 rounds of iteration. Audit the assembled prompt for anti-patterns and contradictions, design a completely rethought prompt architecture based on GPT-5.2 best practices, and validate with A/B tests before returning to Phase 25 evaluation.
**Depends on:** Phase 25
**Requirements:** (research phase — serves v1.3a Content Generation Excellence)
**Status:** PARTIAL — audit + architecture done, A/B test revealed deeper GPT-5.2 adherence problems. Superseded by Phase 25.2.
**Plans:** 3/3 plans executed (plan 03 revealed fundamental issues → spawned 25.2)

Plans:
- [x] 25.1-01-PLAN.md — Track 1 internal audit: dump full assembled prompt, token count, contradiction map, GPT-5.2 anti-pattern scorecard
- [x] 25.1-02-PLAN.md — Design new prompt architecture from scratch: CTCO framework, distilled constraints, new system prompt under 15K chars
- [x] 25.1-03-PLAN.md — A/B test 3 prompt variations on representative + unseen SKUs, mini human review checkpoint (RESULT: C_Optimized best but still fails constraints)

### Phase 25.2: GPT-5.2 Prompt Engineering — Empirical Approach (INSERTED)

**Goal:** Determine exactly what GPT-5.2 does and does not follow at different reasoning effort levels through empirical atomic testing, then build a production prompt validated one constraint at a time — not theoretically designed and tested all at once.

**Depends on:** Phase 25.1 (findings)
**Requirements:** (research + implementation phase — serves v1.3a Content Generation Excellence)

**Why this phase exists:** Phase 25.1 revealed that writing a prompt "for GPT-5.2" based on documentation and Claude-optimized patterns doesn't work. Three iterations have failed because we're designing prompts theoretically and testing them as a complete unit. Key findings:
1. **All 8 SKILL.md files (~260K chars) dumped raw into GPT-5.2 system prompt** — these were written for Claude Code (an AI coding assistant), not for GPT-5.2 runtime consumption. They contain markdown, interactive instructions, "you the AI assistant" guidance.
2. **Platform-specific skill loading is dead code** — `get_system_prompt()` is called with no arguments everywhere. GPT-5.2 always gets google + bing + shopify skills simultaneously, creating conflicting guidance.
3. **Generating 8+ fields (3 platforms) in one call is architecturally flawed** — GPT-5.2 can't apply google-shopping rules to Google fields AND bing-shopping rules to Bing fields AND shopify rules to Shopify fields simultaneously. Evidence: A_Current returned EMPTY Bing/Shopify for 2/3 SKUs.
4. GPT-5.2 at reasoning_effort=medium skims constraint lists — banned words leak, integration patterns ignored
5. Evidence table contains "poison pills" (banned words, bad grammar) that GPT-5.2 echoes due to conservative grounding bias
6. {FINISH_SENTENCE} as a publishing-pipeline concept has no mechanism in the JSON schema
7. We've never tested what GPT-5.2 actually follows vs ignores — only tested full prompts end-to-end

**Tools & Resources:**
- `mcp__openaiDeveloperDocs__*` — Search/fetch OpenAI developer docs for GPT-5.2 prompting best practices, structured outputs, reasoning effort, prompt caching. USE THESE FIRST before making assumptions about GPT-5.2 behavior.
- `docs/research/gpt52-best-practices.md` — Existing research (may be outdated or incomplete — cross-reference with live docs)
- `scripts/ab_prompt_test.py` — Existing test harness (v2.1, variant-level, 6 SKUs)
- `.planning/phases/25.1-prompt-architecture-research/` — All Phase 25.1 artifacts (audit, architecture, test results)
- `.planning/phases/25.2-gpt52-prompt-engineering/ROOT-CAUSE-ANALYSIS.md` — Detailed failure analysis

**Critical instructions for agents:**
1. **Check OpenAI docs FIRST** — Use `mcp__openaiDeveloperDocs__search_openai_docs` and `mcp__openaiDeveloperDocs__fetch_openai_doc` to verify current GPT-5.2 API behavior before writing any prompts or API calls. Our existing research may be wrong or outdated.
2. **Verify we're using the API correctly** — Check: Are we passing `reasoning_effort` correctly? Is `temperature` conflicting? Is `json_schema` strict mode configured right? Is `max_completion_tokens` appropriate? Is `text.verbosity` being used? Are we using the right model string?
3. **Understand the skill architecture** — There are TWO separate systems:
   - **Claude Code skills** (`.claude/skills/*/SKILL.md`): Written for Claude Code as an AI assistant. 260K chars total. Currently ALL dumped into GPT-5.2 system prompt via `skill_loader.py`. This is wrong — they were never designed for GPT-5.2.
   - **YAML runtime configs** (`src/feedops/config/*.yaml`): Distilled versions meant for GPT-5.2. Loaded by `prompt_builder.py` via `shopping_intelligence.py`. Some overlap/conflict with the SKILL.md injection.
   - The skills contain genuinely valuable domain expertise that must be properly distilled for GPT-5.2 — not raw-dumped or ignored.
4. **Think deeply about prompt construction** — The fundamental question is: "What does GPT-5.2 need to produce a perfect title and description for ONE product on ONE platform?" Consider:
   - Should generation be split by platform? (Google call, Bing call, Shopify call — each with platform-specific skill knowledge and schema)
   - How should product information flow into the prompt? (Raw evidence dump vs. curated per-platform data)
   - What's the right balance of constraints vs. examples vs. product data?
   - How do we distill skill knowledge (title formula, finish rules, brand voice, buyer scenarios) into something GPT-5.2 actually follows?
5. **Run local tests** — Every change must be validated with actual GPT-5.2 API calls, not just dry-runs. Use `--sku 1025U` for quick single-SKU tests. Validate outputs against constraint checklist before declaring success.
6. **Build bottom-up** — Start with the simplest possible prompt that works, add constraints one at a time, validate each addition. Do NOT design a complete prompt theoretically and test it end-to-end.

**Success Criteria** (what must be TRUE):
1. A constraint adherence map exists showing which instruction types GPT-5.2 follows at low/medium/high reasoning effort
2. Evidence sanitization rules exist that prevent the evidence table from feeding banned words/patterns to the model
3. The {FINISH_SENTENCE} mechanism works correctly — either as a literal placeholder or a separate generation step
4. Zero competitor brand leaks across 6+ test SKUs
5. Zero banned words across 6+ test SKUs
6. Title formula followed consistently (finish first, collection, product type) across 6+ test SKUs
7. Description quality passes Bobby's gut-check on representative SKUs
8. API call parameters verified against current OpenAI docs (reasoning_effort, temperature, json_schema, max_completion_tokens, text.verbosity)

Plans:
- [ ] 25.2-01-PLAN.md — Research + API audit: Query OpenAI docs via MCP for current GPT-5.2 best practices (prompting, structured outputs, reasoning effort). Audit our API call parameters against docs. Audit skill/config wiring in prompt_builder.py. Atomic constraint testing: test individual instructions (banned words, title formula, finish placement, competitor prohibition) in isolation at low/medium/high reasoning effort. Build an empirical adherence map. Run local tests to validate.
- [ ] 25.2-02-PLAN.md — Evidence sanitization + {FINISH_SENTENCE} mechanism: clean evidence table inputs, decide and implement the finish sentence approach, test field-splitting if needed (separate Google/Bing/Shopify calls). Local test validation.
- [ ] 25.2-03-PLAN.md — Build production prompt from validated constraints: assemble only instructions GPT-5.2 demonstrably follows, run full 6-SKU test, Bobby gut-check
