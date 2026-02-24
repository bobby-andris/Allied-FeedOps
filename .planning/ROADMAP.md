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

### Phase 25.2: Optimal Content Generation (INSERTED)

**Goal:** Achieve optimal baseline content generation quality for every SKU in the catalog. Google and Bing need variant-level content (finish-specific). Shopify needs master-SKU content (finish-agnostic). The output must be content Bobby would approve on first read — correct titles, compelling descriptions, zero constraint violations.

**Depends on:** Phase 25.1 (findings)
**Requirements:** (research + implementation phase — serves v1.3a Content Generation Excellence)

**Why this phase exists:** 5+ prompt iterations have failed to produce content that passes human review. The failures aren't about prompt size — they're about not understanding how to construct a prompt that produces perfect output from GPT-5.2 for our specific use case. Key problems:

1. **Skills are model-agnostic but aren't being used correctly** — Agent Skills (agentskills.io) are an open format designed for ANY LLM (Claude, GPT, Gemini, etc.). The spec recommends SKILL.md < 5000 tokens with references/ loaded on demand. Our skills are 5-10x oversized and ALL 8 are dumped into every GPT-5.2 call simultaneously (~260K chars). The skill knowledge is valuable — it just needs to be loaded correctly per the spec.
2. **Platform-specific skill routing is broken** — `skill_loader.py` has platform-specific loading (`google-shopping-content` for Google, etc.) but `get_system_prompt()` is called with no arguments everywhere — so GPT-5.2 gets Google + Bing + Shopify guidance simultaneously, creating conflicting rules for a single generation call.
3. **Generation architecture forces impossible multi-tasking** — One call generates 8+ fields across 3 platforms with different rules each. A_Current returned EMPTY Bing/Shopify for 2/3 test SKUs.
4. **Evidence table feeds GPT-5.2 content we explicitly ban** — banned words ("finest"), bad grammar ("insure"), competitor names in keywords. GPT-5.2's grounding bias echoes evidence over instructions.
5. **{FINISH_SENTENCE} has no mechanism in the output schema** — GPT-5.2 can't produce a placeholder it doesn't know about.

**Tools & Resources:**
- `mcp__openaiDeveloperDocs__*` — USE FIRST to verify current GPT-5.2 API behavior, prompting best practices, structured outputs, reasoning effort. Do not assume — verify against live docs.
- Agent Skills spec: https://agentskills.io/specification — Skills are model-agnostic, < 5000 tokens recommended, references/ loaded on demand
- `.claude/skills/` — The 8 content skills (model-agnostic, need right-sizing per spec)
- `src/feedops/config/*.yaml` — YAML runtime configs (overlap with skills — may need consolidation)
- `src/feedops/pipeline/skill_loader.py` — Current skill injection (loads ALL skills, platform routing dead code)
- `src/feedops/api/prompt_builder.py` — Assembles user prompt with evidence, keywords, category guidance
- `src/feedops/providers/openai_provider.py` — GPT-5.2 API call parameters
- `scripts/ab_prompt_test.py` — Test harness (v2.1, variant-level, 6 SKUs)
- `.planning/phases/25.2-gpt52-prompt-engineering/ROOT-CAUSE-ANALYSIS.md` — Failure analysis from 5+ iterations

**Critical instructions for agents:**

1. **The goal is OPTIMAL CONTENT, not prompt optimization** — Every decision should be evaluated by: "Does this produce better titles and descriptions?" Not "Is this fewer tokens?" or "Is this architecturally clean?" The only metric that matters is Bobby reading the output and saying "yes, this is good."

2. **Check OpenAI docs via MCP FIRST** — Use `mcp__openaiDeveloperDocs__search_openai_docs` and `mcp__openaiDeveloperDocs__fetch_openai_doc` to understand how GPT-5.2 wants to receive prompts. Cross-reference our `openai_provider.py` parameters against current docs. Our existing research (`docs/research/gpt52-best-practices.md`) may be outdated.

3. **Understand the skill format** — Agent Skills (agentskills.io) are model-agnostic. They work with Claude, GPT, Gemini, and others. The format is: SKILL.md (< 5000 tokens recommended) + references/ loaded on demand. Our skills are oversized but contain the right domain knowledge. Figure out how to use them correctly — either right-size them per spec, or extract the essential knowledge into the prompt properly.

4. **Think about what GPT-5.2 needs per output** — For each product:
   - **Google variant**: Needs finish name, title formula, product evidence, category guidance, gold examples, brand voice. Produces: google_title, google_short_title, google_description.
   - **Bing variant**: Needs finish name, Bing-specific rules (front-load specs, synonym coverage), product evidence. Produces: bing_title, bing_description.
   - **Shopify master**: Needs product evidence, HTML format rules, buyer scenarios, trust signals. Finish-agnostic. Produces: shopify_title, shopify_description, shopify_meta_description.
   - Should these be separate calls with platform-specific prompts? Or one call with clear field isolation? What actually produces better output?

5. **Run local tests for EVERY change** — Actual GPT-5.2 API calls with real product data. `--sku 1025U` for quick validation. No dry-runs, no theoretical analysis. The output either passes Bobby's review or it doesn't.

6. **Build incrementally and validate** — Start simple, validate it works, add complexity only when needed. Don't design a complete system and test end-to-end.

**Success Criteria** (what must be TRUE):
1. Google/Bing titles start with {FINISH_NAME} (the only hard rule). Collection name included only when the product belongs to one of the 41 named collections (see `data/Nov2024 New Collection Descriptions.xlsx`). Beyond that, the LLM should craft the best title for the product — no rigid formula that restricts output quality.
2. Descriptions are compelling, specific to the product, and pass Bobby's gut-check
3. Zero competitor brand names in any generated content
4. Zero banned words (finest, luxurious, premium, etc.) in any generated content
5. {FINISH_SENTENCE} correctly integrated into variant descriptions (not standalone)
6. Shopify content is finish-agnostic, HTML formatted, with buyer-problem-first openings
7. All fields populated (no empty Bing/Shopify fields)
8. Quality validated across 6+ test SKUs spanning different product categories
9. API parameters verified against current OpenAI docs

**Plans:** 2/3 plans executed

Plans:
- [x] 25.2-01-PLAN.md — Per-platform schemas, platform-specific system prompts with extracted skill knowledge, test harness extension, empirical GPT-5.2 validation (placeholder preservation, constraint adherence)
- [x] 25.2-02-PLAN.md — Wire per-platform generation into pipeline endpoints (prompt_builder, generator, main.py, hybrid_generation) with FEEDOPS_PROMPT_VERSION feature flag
- [ ] 25.2-03-PLAN.md — Full 6-SKU validation across all platforms, side-by-side comparison, Bobby gut-check review

### Phase 25.3: Prompt Rewrite from Human Feedback (INSERTED)

**Goal:** Write the prompt GPT-5.2 actually needs — a purpose-built creative brief based on Bobby/Robert's feedback — instead of dumping extracted skill snippets and adding post-processing to fix bad output.

**Depends on:** Phase 25.2 (per-platform architecture), Round 2 evaluation (Bobby/Robert feedback)

**Why this phase exists:** After 6+ iterations of prompt work (Phases 25, 25.1, 25.2, Codex attempt), the architecture is solid (per-platform calls, schemas, feature flag) but the actual prompt content is wrong. The per-platform system prompts are extracted snippets from Claude Code skill files — research documents, not GPT-5.2 instructions. The per-platform user prompts are thin (missing product design story, competitive positioning, segment strategy). Codex tried to fix this by adding ~200 lines of Python post-processing to regex-fix model output. That's the wrong approach. The prompt itself needs to be rewritten.

**Root cause (confirmed by review):**
- System prompts read like compliance checklists, not creative briefs
- Skill knowledge is dumped as reference material, not distilled into actionable instructions
- Per-platform user prompts are missing context that build_core_prompt() has
- Round 2 feedback from Bobby/Robert gives EXACT specifications for what good content looks like
- None of that feedback has been encoded into the prompt

**Success Criteria:**
1. GPT-5.2 produces content that passes Bobby's gut-check for 8/10 test SKUs (titles AND descriptions)
2. No post-processing layer needed beyond basic safety (max length trim, JSON validation)
3. Robert's title formula is followed by the model without enforcement code
4. Zero constraint violations (banned words, competitor names, etc.) from the model itself

**Plans:**
- [ ] 25.3-01-PLAN.md — Cherry-pick useful Codex changes (JSON parser, skill sanitizer, enrichment fix), discard post-processing layer
- [ ] 25.3-02-PLAN.md — Rewrite per-platform system prompts as GPT-5.2 creative briefs; enrich per-platform user prompts with product design story and competitive positioning
- [ ] 25.3-03-PLAN.md — 10-SKU validation with Bobby/Robert gut-check review (success gate: 8/10 consensus wins)
- [ ] 25.3-04-PLAN.md — Deploy FEEDOPS_PROMPT_VERSION=v2 to production, close v1.3a
