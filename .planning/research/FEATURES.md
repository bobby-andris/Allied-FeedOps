# Feature Research

**Domain:** Python pipeline decomposition, LLM provider abstraction, and model evaluation
**Researched:** 2026-03-03
**Confidence:** HIGH (direct codebase analysis, existing tests, project briefs)

---

## Context: What Already Exists

Before categorizing features as table stakes vs differentiators, it's important to note what the codebase already has — so the roadmap targets gaps, not rebuilds:

**Already implemented (do not re-build):**
- `providers/base.py` — Abstract `LLMProvider` with `generate()`, `health_check()`, `aclose()`, `name`
- `providers/openai_provider.py` — OpenAI/GPT-5.2 provider (has the 5 known bugs)
- `providers/gemini_provider.py` — Gemini provider
- `providers/factory.py` — `get_provider()` with fallback chain, `FallbackProvider` class
- `providers/reliability.py` — Circuit breaker, retry backoff
- `quality/eval_framework.py` — Automated check suite (banned words, brand position, char limits, description structure)
- `tests/test_eval_framework.py` — Tests for eval checks and regression runner
- `tests/test_providers.py` — Tests for base, OpenAI, Gemini providers
- `api/generation_telemetry.py` — Cost estimation, telemetry extraction (already split from main.py)
- `api/hybrid_generation.py` — Variant adaptation logic (already split)
- `api/multi_sku_detection.py` — Family detection (already split)
- Several routers already split: search_insights, monitoring, gmc_sync, performance_baseline

**The actual gaps targeted by this milestone:**
- Claude (`anthropic`) provider — not yet implemented
- `main.py` still has ~30 Pydantic schemas, ~10 persistence functions, ~8 job management functions, ~4 remaining telemetry functions, ~5 finish processing functions, ~5 generation core functions, and 2 large batch processors (500+ lines each)
- GPT-5.2 bugs are confirmed unfixed in `openai_provider.py:168-185`
- Unified `JobRunner` replacing the duplicated batch processors
- Head-to-head evaluation of Claude vs GPT-5.2 on real content

---

## Feature Landscape

### Table Stakes (Must Have — Decomposition Fails Without These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| All existing API endpoints work identically post-decomposition | Backward compat is the #1 constraint — the dashboard calls these endpoints in production | HIGH | Test with curl against live endpoint after each extraction; routes must remain at same paths |
| `run_async_in_thread()` preserved in new structure | Background jobs die without this pattern on Cloud Run scale-to-zero | MEDIUM | Must survive extraction to job_management module; cannot be replaced with BackgroundTasks |
| Unit tests for each extracted module | The entire point of decomposition is testability — without tests, extraction has no verification | MEDIUM | Each module (`schemas`, `persistence`, `job_management`, `telemetry`, `finish_processing`, `generation`) needs pytest coverage |
| Finish placeholder contract unchanged | `{FINISH_NAME}` and `{FINISH_SENTENCE}` are enforced at write time; breaking this corrupts all variant expansion | LOW | `_enforce_write_time_finish_placeholder_contract()` must move intact to `finish_processing` module |
| Prompt authority chain preserved | `prompt_builder.py` → `prompts.py` → `prompt_loader.py` → `shopping_intelligence.py` is the runtime source of truth | LOW | Decomposition must not alter import paths that break this chain |
| Generation quality unchanged after decomposition | 98% human approval rate must not regress | MEDIUM | Run eval framework on sample SKUs before/after extraction; Phase 27 proved even refactors can break GPT-5.2 |
| Claude provider implements `LLMProvider` interface | Provider abstraction is useless without a Claude implementation to compare | MEDIUM | `generate()`, `health_check()`, `aclose()`, `name` — same contract as OpenAI and Gemini providers |
| GPT-5.2 temperature/reasoning_effort conflict fixed | Passing both is mutually exclusive on GPT-5.2 — currently always passes `temperature=0.7` alongside reasoning_effort | LOW | `openai_provider.py:168-185` — remove temperature when reasoning_effort is set |
| GPT-5.2 reasoning_effort default fixed | When `FEEDOPS_REASONING_EFFORT` env var is unset, no reasoning is sent; GPT-5.2 defaults to zero reasoning | LOW | Default to `"medium"` when unset |
| Bing `{FINISH_NAME}` bug fixed | 85/98 Bing titles have hardcoded finish names — variant expansion is broken for all of them | MEDIUM | Fix prompt instruction in Bing section of `prompts.py`; requires incremental deploy-and-test protocol |
| Regenerate 85 broken Bing titles | Bug fix is useless if existing broken content remains in database | MEDIUM | Batch regeneration of affected Bing titles with corrected placeholder behavior |

### Differentiators (Competitive Advantage for this Internal Milestone)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Unified `JobRunner` replacing duplicated batch processors | Eliminates 500+ lines of near-identical logic in `process_batch_job()` and `process_hybrid_batch_job()`; reduces maintenance surface and future bug duplication | HIGH | ~60% shared logic between the two; must produce identical results to current implementation; depends on clean Phase 1 extraction |
| `json_schema` strict mode replacing `json_object` | Eliminates the retry loops caused by GPT-5.2 returning non-conformant JSON in legacy mode; tokens wasted on retry are significant at batch scale | MEDIUM | `openai_provider.py` — switch response_format type; verify schema builder `_build_strict_schema()` already handles this correctly |
| Prompt cache retention for batch runs | `prompt_cache_retention: "24h"` means the static system prompt (18K tokens) is cached across the entire batch run, not just 5-10 minutes | LOW | Adds one header to OpenAI API calls; meaningful cost reduction for 120+ SKU batches |
| Head-to-head model evaluation with human scoring | Produces evidence-based data on Claude vs GPT-5.2 quality, cost, and latency — replaces speculation with measurement | HIGH | 10 diverse SKUs, both providers, human scoring by Bobby/Robert on title quality, description quality, brand voice, accuracy; needs result storage format |
| Cost/quality/latency tradeoff documentation | Makes future provider decisions (and budget conversations) data-driven | LOW | Tabular output from evaluation: cost per SKU, p50/p95 latency, composite eval score, human score |
| `factory.py` support for Claude provider | `get_provider(preferred="claude")` works without code changes — env var `ANTHROPIC_API_KEY` controls availability | LOW | Follows same pattern as existing OpenAI/Gemini factory logic |
| XML tag prompt structure for GPT-5.2 | GPT-5.2 parses XML tags better than `=== ===` headers — documented in `gpt52-best-practices.md` | MEDIUM | Requires incremental deploy-and-test per Phase 27 protocol; treat as one change at a time |
| `main.py` reduced to <500 lines | Route definitions only — makes the file reviewable, approachable for future contributors | MEDIUM | Measured success criterion from project brief; achieved by extracting all 7 identified concern groups |
| Stale job recovery preserved in extraction | Startup sweep that marks stuck `processing` jobs as `failed` must survive lifespan context move | LOW | Currently in `_app_lifespan` in main.py; move to `job_management` module but keep lifespan hook |

### Anti-Features (Deliberately Avoid)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Batching prompt changes during GPT-5.2 bug fixes | Faster to fix all 5 bugs at once | Phase 27 proved even single text changes can break GPT-5.2 strict JSON mode — batching makes it impossible to isolate which change caused regression | Fix one bug per deploy, curl-verify, then proceed |
| Replacing `run_async_in_thread()` with `asyncio.create_task()` or `BackgroundTasks` | Cleaner FastAPI idioms | Cloud Run containers scale to zero mid-request; BackgroundTasks die with the response; jobs would silently terminate | Keep non-daemon thread pattern; document the reason clearly in extracted module |
| Full eval UI in dashboard | Nice for visibility | Out of scope for this milestone; dashboard changes are explicitly excluded; adding UI scope creep risks blocking pipeline work | Store eval results as JSON files or Supabase rows; read with existing dashboard tooling later |
| Prompt content rewriting as part of decomposition | Tempting to improve content during refactor | Phase 27 proved GPT-5.2 is hyper-sensitive; refactoring modules changes import paths and may subtly alter prompt construction; mixing concerns multiplies risk | Decompose first with zero prompt changes; fix GPT-5.2 bugs as a separate discrete phase |
| Claude as primary provider immediately | If eval shows Claude is better, switch now | Evaluation needs controlled data first; switching before evaluation gives no baseline; also requires verifying Claude handles the 18K token system prompt and finish placeholder contract | Run eval, document results, then make a deliberate provider switch decision in a future milestone |
| Generic LLM framework (LangChain, LiteLLM) | Abstracts all provider differences | Adds dependency complexity, hides provider-specific behavior that matters for quality (reasoning_effort, prompt caching, json_schema mode), and creates debugging opacity | Maintain thin hand-written provider implementations; the interface is already clean (3 abstract methods) |
| Parallel decomposition of multiple modules simultaneously | Faster delivery | Circular imports are a real risk when splitting a 3,737-line file; if two modules both need a third thing still in main.py, you get import cycles; also makes CI failures ambiguous | Extract one concern group at a time, run full test suite after each extraction |
| New database tables or schema changes | Nice to track eval results properly | Deferred migrations (034b, 035b) are explicitly blocked; adding new tables risks applying blocked migrations by accident | Use JSON output files for eval results; existing `generated_content` table for content storage |

---

## Feature Dependencies

```
[main.py Schemas extraction]
    └──enables──> [Unit tests for schemas module]
    └──enables──> [Persistence extraction] (needs clean schema imports)
    └──enables──> [Job management extraction] (needs clean schema imports)

[Persistence extraction]
    └──enables──> [Job management extraction] (job state reads/writes need persistence)
    └──enables──> [Generation extraction] (content persistence needs clean module)

[Job management extraction]
    └──enables──> [Unified JobRunner] (can't unify what hasn't been isolated)
    └──preserves──> [run_async_in_thread pattern]

[Generation extraction]
    └──enables──> [GPT-5.2 bug fixes] (modular isolation makes bugs safer to fix)
    └──enables──> [Head-to-head evaluation] (both providers use same generation path)

[GPT-5.2 bug #3: json_schema strict mode]
    └──validates-against──> [_build_strict_schema() in openai_provider.py] (already implemented)

[GPT-5.2 bug #5: XML prompt structure]
    └──requires──> [Deploy-and-test protocol] (one change, deploy, curl verify)
    └──conflicts-with──> [Prompt content rewriting] (never mix structural and content changes)

[Claude provider implementation]
    └──requires──> [LLMProvider base interface] (already exists)
    └──requires──> [factory.py update] (add "claude" to get_provider())
    └──enables──> [Head-to-head evaluation]

[Head-to-head evaluation]
    └──requires──> [Claude provider functional]
    └──requires──> [GPT-5.2 bugs fixed] (need clean baseline to compare against)
    └──enhances──> [Cost/quality/latency documentation]

[Bing {FINISH_NAME} bug fix]
    └──requires──> [Incremental prompt change protocol]
    └──enables──> [Regenerate 85 broken Bing titles]
    └──independent-of──> [main.py decomposition] (can run in parallel or after)
```

### Dependency Notes

- **Decompose before fixing GPT-5.2 bugs:** Modular isolation means bug fixes happen in a focused, testable file rather than a 3,737-line monolith. This is a risk reduction dependency, not a hard technical one — but strongly recommended.
- **Fix GPT-5.2 bugs before running evaluation:** The evaluation needs a clean GPT-5.2 baseline. Comparing Claude against a buggy GPT-5.2 produces misleading results.
- **Claude provider before evaluation:** Obvious — can't run head-to-head without both providers.
- **Bing bug is independent:** The `{FINISH_NAME}` fix touches `prompts.py` and Supabase batch regeneration — neither depends on main.py decomposition. Can be scheduled before or after decomposition phases.
- **Unified JobRunner after module extraction:** The two batch processors can only be cleanly unified after their shared logic has been extracted into discrete dependency modules. Attempting unification on the monolith would create a 1,000+ line single function.

---

## MVP Definition

### Phase 1 Deliverable: Decomposed, Tested, Backward-Compatible

- [ ] `schemas.py` extracted with all ~20 Pydantic models — tests pass
- [ ] `persistence.py` extracted with all ~10 Supabase read/write functions — tests pass
- [ ] `job_management.py` extracted with job lifecycle functions — tests pass, `run_async_in_thread()` preserved
- [ ] `finish_processing.py` extracted with placeholder contract enforcement — tests pass
- [ ] `generation.py` extracted with core generation orchestration — tests pass
- [ ] `telemetry.py` extracted with remaining metrics functions — tests pass
- [ ] `main.py` at <500 lines — route definitions only
- [ ] All API endpoints smoke-tested (curl against deployed Cloud Run)

### Phase 2 Deliverable: Unified Job Orchestration

- [ ] `JobRunner` class replaces `process_batch_job()` and `process_hybrid_batch_job()`
- [ ] Batch and hybrid modes produce identical results to current implementation
- [ ] Job failure recovery tested

### Phase 3 Deliverable: Fixed GPT-5.2 + Claude Provider

- [ ] All 5 GPT-5.2 bugs fixed (incremental, one per deploy)
- [ ] Claude provider functional with `LLMProvider` interface
- [ ] `get_provider(preferred="claude")` works
- [ ] Unit tests for Claude provider

### Phase 4 Deliverable: Model Evaluation

- [ ] 10 diverse SKUs selected and documented
- [ ] Content generated with both Claude and GPT-5.2
- [ ] Human scoring completed by Bobby/Robert
- [ ] Cost/quality/latency comparison documented

### Phase 5 Deliverable: Bing Fix

- [ ] Root cause of `{FINISH_NAME}` absence diagnosed in `prompts.py`
- [ ] Prompt fixed and deployed (incremental protocol)
- [ ] 85 broken Bing titles regenerated
- [ ] Variant expansion verified correct

### Add After Validation

- [ ] Automated regression eval integrated into CI — once eval framework is proven, run on every batch generation to catch regressions automatically
- [ ] Provider performance dashboard — surface eval results in the existing dashboard UI (future milestone)

### Future Consideration

- [ ] Primary provider switch to Claude — if evaluation demonstrates quality advantage; decision requires human-scored data from Phase 4
- [ ] LLM-as-judge scoring — supplement human scoring with automated LLM-based quality scoring; requires careful calibration against human ground truth

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Backward-compatible decomposition (Phase 1) | HIGH — unlocks all testability | HIGH | P1 |
| GPT-5.2 temperature/reasoning_effort fix | HIGH — eliminates a silent quality bug | LOW | P1 |
| GPT-5.2 reasoning_effort default fix | HIGH — zero reasoning means degraded content | LOW | P1 |
| Finish placeholder contract preserved | HIGH — broken contract corrupts all variants | LOW | P1 |
| Claude provider implementation | HIGH — needed for evaluation | MEDIUM | P1 |
| Bing `{FINISH_NAME}` bug fix | HIGH — 85/98 Bing titles are broken | MEDIUM | P1 |
| Regenerate 85 broken Bing titles | HIGH — fix without regeneration is useless | MEDIUM | P1 |
| Unit tests for each extracted module | HIGH — the reason for decomposition | MEDIUM | P1 |
| Head-to-head evaluation (Phase 4) | HIGH — produces provider decision data | HIGH | P1 |
| Unified JobRunner (Phase 2) | MEDIUM — reduces maintenance burden | HIGH | P2 |
| GPT-5.2 json_schema strict mode fix | MEDIUM — reduces retry waste | MEDIUM | P2 |
| GPT-5.2 prompt cache retention fix | MEDIUM — cost reduction at batch scale | LOW | P2 |
| GPT-5.2 XML prompt structure fix | MEDIUM — quality improvement, high risk | HIGH | P2 |
| Cost/quality/latency documentation | MEDIUM — informs future decisions | LOW | P2 |
| `main.py` <500 lines target | LOW — internal metric, not user-facing | MEDIUM | P2 |
| LLM-as-judge automated scoring | LOW — nice, but human scoring is ground truth | HIGH | P3 |
| Provider performance dashboard UI | LOW — deferred; out of milestone scope | HIGH | P3 |

**Priority key:**
- P1: Must have for milestone success
- P2: Should have, complete within milestone if capacity allows
- P3: Defer to future milestone

---

## Sources

- Direct codebase analysis: `src/feedops/api/main.py` (3,737 lines, function groupings)
- Direct codebase analysis: `src/feedops/providers/` (base, openai, gemini, factory, reliability)
- Direct codebase analysis: `src/feedops/quality/eval_framework.py` + `tests/test_eval_framework.py`
- Project brief: `docs/setup/pipeline-rewrite-brief.md` (Section 3: main.py analysis)
- Project context: `.planning/PROJECT.md` (Active requirements, out-of-scope items, constraints)
- Domain knowledge: `CLAUDE.md` (GPT-5.2 Known Issues, Phase 27 learnings, prompt sensitivity)
- Memory: `memory/MEMORY.md` (Phase 27 critical learnings, Bing bug details)

---

*Feature research for: Pipeline decomposition, LLM provider abstraction, model evaluation*
*Researched: 2026-03-03*
