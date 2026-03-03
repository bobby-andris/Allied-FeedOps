# Pipeline Reliability Rewrite + Model Evaluation

## What This Is

A reliability and extensibility overhaul of the Allied-FeedOps Python content generation pipeline. The monolithic `main.py` (3,737 lines) is decomposed into testable modules, all known GPT-5.2 bugs are fixed, a model provider abstraction is added, and Claude vs GPT-5.2 are evaluated head-to-head on real product content. The Bing `{FINISH_NAME}` placeholder bug (85/98 titles broken) is also fixed.

## Core Value

The pipeline produces high-quality product content reliably at scale — decomposition and bug fixes must not regress the 98% human approval rate or break any existing API endpoints.

## Requirements

### Validated

<!-- Existing capabilities that must be preserved -->

- ✓ Single-SKU content generation (`/optimize-sku`) — v1.0
- ✓ Content regeneration with feedback (`/regenerate`) — v1.0
- ✓ Batch job creation and status tracking (`/batch-optimize`, `/batch-status`) — v1.2
- ✓ Hybrid multi-SKU generation with variant adaptation (`/hybrid-generate`) — v1.3b
- ✓ Lifestyle image generation (`/generate-images`) — v1.3b
- ✓ Performance baseline capture (`/performance/capture-baseline`) — v1.2
- ✓ Search insights sync (`/search-insights/sync`) — v1.2
- ✓ Health check with Supabase status (`/health`) — v1.0
- ✓ `run_async_in_thread()` background task pattern — v1.3b
- ✓ Finish placeholder contract (`{FINISH_NAME}`, `{FINISH_SENTENCE}`) — v1.3a
- ✓ Prompt authority chain (prompt_builder → prompts.py → prompt_loader → shopping_intelligence) — v1.3a
- ✓ 98% human approval rate on generated Google content — v1.3b

### Active

<!-- Current scope — building toward these -->

- [ ] Decompose main.py into focused modules (schemas, persistence, job management, telemetry, intent scoring, finish processing, generation)
- [ ] Reduce main.py to <500 lines (route definitions and request handling only)
- [ ] Unit test coverage for each extracted module
- [ ] Unify `process_batch_job()` and `process_hybrid_batch_job()` into single `JobRunner`
- [ ] Fix GPT-5.2 bug: temperature + reasoning_effort conflict
- [ ] Fix GPT-5.2 bug: missing reasoning_effort default
- [ ] Fix GPT-5.2 bug: legacy json_object → json_schema strict mode
- [ ] Fix GPT-5.2 bug: no prompt_cache_retention for batch runs
- [ ] Fix GPT-5.2 bug: system prompt structure (=== headers → XML tags)
- [ ] Model provider abstraction (`providers/base.py`) with common interface
- [ ] Claude provider implementation
- [ ] Head-to-head evaluation: Claude vs GPT-5.2 on 10 diverse SKUs
- [ ] Cost/quality/latency tradeoff documentation
- [ ] Fix Bing {FINISH_NAME} bug (85/98 titles have hardcoded finish names)
- [ ] Regenerate broken Bing titles with correct placeholders

### Out of Scope

- v1.3c dashboard phases (tier intelligence redesign, distribution scoring, revenue leakage) — PAUSED
- v1.4 closed-loop optimization (performance-informed regeneration) — future milestone
- Deferred database migrations (034b GA4 attribution, 035b intent execution) — not yet evaluated
- New dashboard pages or UI changes — pipeline-only milestone
- Prompt content rewriting — Phase 27 proved GPT-5.2 is hyper-sensitive; prompt changes are incremental only

## Context

**Codebase state:** 55+ PRs merged across v1.0–v1.3b. Production pipeline at `src/feedops/api/main.py` serving all content generation. Dashboard at `dashboard/` auto-deploys via Vercel. Pipeline auto-deploys via Cloud Build to Cloud Run.

**The monolith problem:** `main.py` has ~30 Pydantic models, ~50 functions, 10+ API endpoints in a single file. `process_batch_job()` and `process_hybrid_batch_job()` share ~60% identical logic as separate 500+ line functions. No unit tests can target individual concerns.

**Critical learning from Phase 27:** GPT-5.2 strict JSON mode is hyper-sensitive to system prompt changes. Even minor text modifications cause empty/placeholder-only content. `self_score` and `scoring_rubric` are load-bearing. Never batch prompt changes — deploy and test with curl after EACH individual change.

**Bing bug:** 85/98 Bing titles have hardcoded finish names instead of `{FINISH_NAME}` placeholder. This is a prompt-level issue — the Bing-specific prompt section likely lacks the placeholder instruction.

**GPT-5.2 bugs:** 5 confirmed issues in `openai_provider.py` and `prompts.py` (temperature/reasoning conflict, missing default, legacy JSON mode, no prompt caching, === headers).

## Constraints

- **Backward compatibility**: All existing API endpoints must work identically after decomposition
- **Background task pattern**: `run_async_in_thread()` MUST be preserved — do not replace with `BackgroundTasks` or `asyncio.create_task()`
- **Prompt sensitivity**: System prompt changes require deploy-and-test protocol (one change at a time, curl verification)
- **Pre-deploy gates**: `cd dashboard && npm run build`, `npx tsc --noEmit`, `npm run lint` must all pass before any push
- **Content storage**: Generated content in Supabase only (not git)
- **Python pipeline**: All pipeline changes in Python (not Node.js/TypeScript)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Decompose before fixing bugs | Modular isolation makes bug fixes safer and testable | — Pending |
| Unify batch/hybrid after extraction | Depends on clean module boundaries from Phase 1 | — Pending |
| Provider abstraction before evaluation | Need common interface to run head-to-head comparison | — Pending |
| Incremental prompt changes only | Phase 27 proved GPT-5.2 crashes on batch prompt changes | ✓ Good |
| Preserve run_async_in_thread | Container lifecycle kills BackgroundTasks on scale-to-zero | ✓ Good |

---
*Last updated: 2026-03-03 after initialization*
