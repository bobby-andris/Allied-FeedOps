# Pipeline Reliability Rewrite + Model Evaluation

## Section 1: Project Context

### What is Allied-FeedOps?

Allied-FeedOps is a content generation and feed optimization platform for Allied Brass Manufacturing — a US bathroom hardware manufacturer with ~120 master SKUs, each expanding to up to 28 finish variants (~3,300 total Google Merchant Center listings). The platform generates optimized product titles, descriptions, and lifestyle images for Google Shopping, Bing Shopping, and Shopify, then publishes them through Google Sheets supplemental feeds and Shopify's GraphQL API.

### What's been built (v1.0–v1.3b)

The **dashboard** (Next.js/Vercel) provides SKU review, variant review, batch publishing, performance tracking, competitor intelligence, search insights, and content regeneration across 15+ pages. Content generation flows through a **Python Cloud Run pipeline** (FastAPI) that uses GPT-5.2 for title/description generation. The pipeline supports single-SKU, batch, and hybrid multi-SKU generation modes, with automatic variant adaptation for product families sharing the same Shopify product ID.

Publishing writes to a Google Sheets supplemental feed that GMC syncs, plus direct Shopify product updates with lifestyle image CDN management. An automated data collection layer (`ensure-data.ts`) triggers performance baseline capture, search term sync, and keyword planner lookups before content generation to provide evidence-driven optimization context.

Over 55 PRs across v1.0–v1.3b, the system reached production stability: 117 Google SKUs generated with 98% human approval rate (110/117 approved by the business owner). Batch reliability was hardened in PR #55 with 7 critical fixes enabling all remaining SKUs to generate successfully.

### What's broken and why

The Python pipeline's `main.py` has grown to **3,737 lines** containing ~30 Pydantic models, ~50 functions, and 10+ API endpoints in a single file. This monolith creates several problems:

1. **Coupling**: Schema definitions, persistence logic, job orchestration, telemetry, and business rules are interleaved — changing one concern risks breaking others
2. **Duplication**: `process_batch_job()` and `process_hybrid_batch_job()` share ~60% identical logic but are separate 500+ line functions
3. **Testing difficulty**: No unit tests can target individual concerns because everything imports from one module
4. **GPT-5.2 bugs**: 5 known issues (temperature/reasoning_effort conflict, missing reasoning default, legacy JSON mode, no prompt caching, prompt structure) are buried in the monolith and risky to fix without modular isolation
5. **Provider lock-in**: The pipeline is hardcoded to OpenAI/GPT-5.2 with no abstraction for evaluating alternative models (Claude, Gemini)

---

## Section 2: The Milestone — Pipeline Reliability & Model Evaluation

### Goal

Decompose the monolithic pipeline into testable, modular components; fix all known GPT-5.2 bugs; add a model provider abstraction; and run a head-to-head evaluation of Claude vs GPT-5.2 on real product content.

### Phase 1: Decompose main.py

Extract cohesive concerns from `main.py` into focused modules:

- **`schemas.py`** — All Pydantic request/response models (~15 classes)
- **`persistence.py`** — All Supabase read/write functions (`_persist_*`, `_lookup_*`, `_load_*`)
- **`job_management.py`** — Job lifecycle (create, status, idempotency, error formatting)
- **`telemetry.py`** — Metrics emission, generation summaries, diagnostic extraction
- **`intent_scoring.py`** — Query intent and content scoring logic
- **`finish_processing.py`** — Finish sentence validation, parity enforcement, placeholder contracts
- **`generation.py`** — Core generation orchestration (`_generate_with_metrics`, prompt building)

`main.py` retains only route definitions and request handling (target: <500 lines).

**Success criteria**: All existing API endpoints work identically. `pytest` covers each extracted module independently.

### Phase 2: Unify Job Orchestration

Replace the duplicated `process_batch_job()` and `process_hybrid_batch_job()` with a unified `JobRunner` class:

- Single job processing loop with batch/hybrid mode flag
- Shared retry logic, error handling, and status updates
- Configurable SKU processing strategy (full generation vs variant adaptation)
- Proper cancellation support and graceful shutdown

**Success criteria**: Batch and hybrid generation produce identical results to current implementation. Job failure recovery works correctly.

### Phase 3: Fix GPT-5.2 Bugs + Provider Abstraction

Fix all 5 known GPT-5.2 issues (see CLAUDE.md "GPT-5.2 Known Issues"):

1. Remove `temperature=0.7` when `reasoning_effort` is set (mutually exclusive)
2. Default `reasoning_effort` to `"medium"` when env var is unset
3. Switch from `json_object` to `json_schema` strict mode
4. Add `prompt_cache_retention: "24h"` for batch runs
5. Restructure system prompt with XML tags (GPT-5.2 parses better)

Add a provider abstraction layer (`providers/base.py`) supporting:
- OpenAI/GPT-5.2 (existing, refactored)
- Anthropic/Claude (new)
- Common interface: `generate(system_prompt, user_prompt, schema) -> structured_output`

**Success criteria**: GPT-5.2 generation quality unchanged or improved. Claude provider functional and tested. Bug #5 (prompt restructure) requires careful incremental testing per Phase 27 learnings.

### Phase 4: Head-to-Head Model Evaluation

Run a controlled evaluation comparing Claude vs GPT-5.2:

- Select 10 diverse SKUs (mix of categories, single vs multi-SKU products)
- Generate content with both providers using identical prompts
- Human scoring by Bobby/Robert on title quality, description quality, brand voice, accuracy
- Compare cost per SKU, latency, and consistency across runs

**Success criteria**: Clear data on which provider produces better content for which scenarios. Cost/quality tradeoff documented.

### Phase 5: Fix Bing {FINISH_NAME} Bug

85/98 Bing titles have hardcoded finish names instead of `{FINISH_NAME}` placeholder. This is a prompt-level issue:

- Diagnose why Bing titles don't use the placeholder (likely missing instruction in Bing-specific prompt section)
- Fix the prompt to enforce `{FINISH_NAME}` in Bing titles
- Regenerate the 85 broken Bing titles
- Verify variant expansion works correctly with placeholders

**Success criteria**: All Bing titles use `{FINISH_NAME}` placeholder. Variant expansion produces correct finish-specific titles.

### What's NOT in scope

- v1.3c dashboard phases (tier intelligence redesign, distribution scoring, revenue leakage) — PAUSED
- v1.4 closed-loop optimization (performance-informed regeneration)
- Deferred database migrations (034b GA4 attribution, 035b intent execution)
- New dashboard pages or UI changes

---

## Section 3: Critical Reference Documents

### Before starting each phase

| Phase | Read first |
|-------|-----------|
| Phase 1 | `src/feedops/api/main.py` (the monolith), `src/feedops/api/prompt_builder.py`, `src/feedops/providers/openai_provider.py` |
| Phase 2 | Lines 2792-3614 of `main.py` (batch + hybrid processors), `docs/architecture/hybrid-generation-architecture.md` |
| Phase 3 | `docs/research/gpt52-best-practices.md`, `CLAUDE.md` "GPT-5.2 Known Issues" section |
| Phase 4 | `docs/research/model-comparison.md`, `docs/plans/round2-evaluation-scorecard.md` |
| Phase 5 | `.claude/skills/bing-shopping-content`, `src/feedops/pipeline/prompts.py` |

### Key architectural decisions to preserve

1. **`run_async_in_thread()` pattern** — Non-daemon threads with dedicated asyncio event loops. This is the solution to FastAPI BackgroundTasks being killed on container scale-to-zero. Do not replace with BackgroundTasks.
2. **Prompt authority chain** — `prompt_builder.py` (orchestrator) → `prompts.py` (SYSTEM_PROMPT) → `prompt_loader.py` (DB data) → `shopping_intelligence.py` (YAML configs). The Python pipeline is the single source of truth.
3. **Finish placeholder contract** — `{FINISH_NAME}` in titles, `{FINISH_SENTENCE}` in descriptions. Enforced at write time by `_enforce_write_time_finish_placeholder_contract()`. Never bypass this.
4. **Offer ID format** — Database uses lowercase `shopify_us_`, GMC requires uppercase `shopify_US_`. Transform at publish time only.
5. **Content storage** — Generated content in Supabase only (not git). `candidate_content` → human approval → `approved_content` (immutable).

### The 5 GPT-5.2 bugs with file locations

1. `src/feedops/providers/openai_provider.py:168-185` — temperature + reasoning_effort conflict
2. `src/feedops/providers/openai_provider.py` — reasoning_effort from `FEEDOPS_REASONING_EFFORT` env var, defaults to nothing
3. `src/feedops/providers/openai_provider.py` — `json_object` instead of `json_schema` strict mode
4. `src/feedops/providers/openai_provider.py` — no `prompt_cache_retention`
5. `src/feedops/pipeline/prompts.py` — `=== ===` headers instead of XML tags

### The main.py analysis (3,737 lines)

**Endpoint count**: 10+ routes (`/optimize-sku`, `/regenerate`, `/batch-optimize`, `/hybrid-generate`, `/generate-images`, `/health`, `/backfill/*`)

**Function groupings by concern**:
- **Schemas** (~20 Pydantic models): `OptimizeRequest`, `RegenerateRequest`, `BatchOptimizeRequest`, `HybridGenerateRequest`, etc.
- **Persistence** (~10 functions): `_persist_regeneration_result`, `_persist_generated_content_and_history`, `_persist_finish_prompt_lineage`, `_lookup_generated_content_id`, `_load_generated_content_row`
- **Job management** (~8 functions): `_create_regeneration_job`, `_find_active_regeneration_job`, `_find_active_hybrid_job`, `_upsert_batch_job_sku_status`, `_normalize_regeneration_job_row`
- **Telemetry** (~4 functions): `_emit_generation_summary`, `_telemetry_scope_for_content`, `_extract_query_intent_generation_diagnostics`
- **Finish processing** (~5 functions): `_enforce_write_time_finish_placeholder_contract`, `_validate_finish_sentences_payload`, `_enforce_finish_sentence_parity`, `_should_persist_finish_sentences`
- **Generation core** (~5 functions): `_generate_with_metrics`, `_build_generation_user_prompt`, `_build_finish_sentences_user_prompt`, `_normalize_generation_options`, `_content_field_key`
- **Batch processors** (~2 large functions, 500+ lines each): `process_batch_job`, `process_hybrid_batch_job`

---

## Section 4: Technical Constraints

### Pre-deploy gates (MANDATORY)

Before any `git push`:
```bash
cd dashboard && npm run build  # MUST pass
npx tsc --noEmit               # Zero errors
npm run lint                   # Fix all issues
```

### Database schema check

ALWAYS read `docs/database/SCHEMA.md` before writing any Supabase query. This prevents column name errors (e.g., `approval_status` not `status`).

### The `run_async_in_thread` pattern

FastAPI `BackgroundTasks` are killed when Cloud Run containers scale to zero or during deployments. The solution is `run_async_in_thread()` in `main.py` — non-daemon threads with dedicated asyncio event loops that survive the HTTP response lifecycle. Used by `/hybrid-generate`, `/batch-optimize`, `/generate-images`, `/search-insights/sync`. See `docs/audit/background-task-fix-2026-02-08.md`.

When extracting job management code, this pattern MUST be preserved. Do not replace with `asyncio.create_task()` or `BackgroundTasks`.

### Content generation prompt sensitivity (CRITICAL)

**Phase 27 learning**: GPT-5.2 strict JSON mode is hyper-sensitive to system prompt changes. Even minor text modifications to `SYSTEM_PROMPT` in `prompts.py` can cause GPT-5.2 to produce empty or placeholder-only content. The `self_score` and `scoring_rubric` fields are load-bearing — removing them causes empty descriptions.

**Protocol for prompt changes**:
1. Make ONE change at a time
2. Deploy to Cloud Run
3. Test with `curl` against the live endpoint
4. Verify full content is produced (not just `{FINISH_SENTENCE}`)
5. Only then make the next change

Never batch prompt changes. Never test prompt changes locally only — the strict JSON mode behavior differs between local and deployed environments.

---

## Section 5: How to Start

1. **Read this document** end-to-end for context
2. **Read `CLAUDE.md`** for all operational details (database schema, publishing workflow, deployment, troubleshooting)
3. **Run `/gsd:new-project`** to initialize a fresh `.planning/` directory with this document as the project brief
4. The codebase is the source of truth — old planning docs in `.planning-archive-v1.3c/` are historical reference only
5. Start with Phase 1 (decompose main.py) — it's prerequisite for all other phases and lowest risk
