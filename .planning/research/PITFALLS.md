# Pitfalls Research

**Domain:** FastAPI monolith decomposition + LLM provider abstraction + model evaluation
**Researched:** 2026-03-03
**Confidence:** HIGH (project-specific pitfalls verified against actual codebase; ecosystem pitfalls MEDIUM from multiple sources)

---

## Critical Pitfalls

### Pitfall 1: Breaking GPT-5.2 JSON Output With System Prompt Changes

**What goes wrong:**
Refactoring `prompts.py` — even moving text, reformatting, or changing section headers — causes GPT-5.2 in strict JSON mode to return empty strings or placeholder-only content. Phase 27 proved this: removing `self_score` and `scoring_rubric` fields, or changing `=== ===` headers, caused Google and Bing platforms to return only `{FINISH_SENTENCE}` with empty descriptions. Shopify returned empty string. All three test approaches failed identically.

**Why it happens:**
GPT-5.2 strict JSON mode (`json_schema` with `strict: true`) creates a constrained grammar from the schema AND the system prompt together. The model's fine-tuning locks certain output patterns to specific prompt structures. Even cosmetic changes shift token positions enough to defeat the internal routing that produces valid field content. `self_score` and `scoring_rubric` are load-bearing because they signal to the model to produce substantive content — without them the model satisfies the schema with minimally valid (but useless) placeholders.

**How to avoid:**
- Never batch prompt changes. Deploy and test with `curl` against production Cloud Run after EACH individual change.
- Treat `prompts.py` as a config artifact that requires regression testing, not a code file that can be refactored freely.
- Before touching any line in `SYSTEM_PROMPT`, run a baseline curl against a known SKU (e.g. `920D-6`) and capture the response. After the change, repeat and diff character counts and field values.
- Preserve `self_score` and `scoring_rubric` as load-bearing fields — do not remove them in the GPT-5.2 bug-fix phase without isolated testing.
- The `=== headers → XML tags` migration (one of the 5 GPT-5.2 bugs) MUST be tested as a single isolated change with full curl verification before anything else touches the prompt.

**Warning signs:**
- Google/Bing descriptions returning only `{FINISH_SENTENCE}` and nothing else
- Shopify descriptions returning empty string `""`
- All three platforms failing simultaneously (not one at a time)
- The schema validates (correct JSON structure) but field values are trivially short

**Phase to address:** Phase: GPT-5.2 bug fixes — must be decomposed into 5 individual PRs, one per bug, each with curl verification before the next begins.

---

### Pitfall 2: Breaking `run_async_in_thread` During Decomposition

**What goes wrong:**
During decomposition, `process_batch_job` and `process_hybrid_batch_job` get moved to new modules. The new modules import `run_async_in_thread` from `main.py`, creating a circular import: `main.py` imports from the new module, new module imports from `main.py`. The fix is to move `run_async_in_thread` to a shared utility module — but if the function is reimplemented incorrectly, background jobs on Cloud Run start dying silently.

The specific failure mode: replacing `daemon=False` with `daemon=True` (or switching to `asyncio.create_task` or `BackgroundTasks`) causes jobs to be killed when the HTTP response completes or when Cloud Run scales the container. Jobs appear to start but never complete; the database row stays `processing` forever.

**Why it happens:**
Cloud Run's container lifecycle terminates non-HTTP work when scaling to zero. `BackgroundTasks` runs in the same asyncio event loop as the HTTP handler — when the response is sent and the loop moves to the next request, pending background tasks can be abandoned. The non-daemon threading pattern (`daemon=False` + dedicated `asyncio.new_event_loop()` per thread) is the only reliable pattern for this environment. It is counterintuitive because daemon threads are the "normal" default.

**How to avoid:**
- Extract `run_async_in_thread` to `feedops/api/job_runner.py` or `feedops/utils/threading.py` as the FIRST step of decomposition, before moving any job processors.
- Never change `daemon=False` to `daemon=True`.
- Never replace the pattern with `asyncio.create_task()`, `BackgroundTasks`, or `concurrent.futures.ThreadPoolExecutor`.
- Write a unit test that verifies the thread is non-daemon before the function is moved: `assert thread.daemon == False`.
- The `run_async_in_thread` implementation must include the crash handler that writes `status=failed` to `batch_generation_jobs` on exception — do not strip this during extraction.

**Warning signs:**
- Batch jobs stuck in `processing` state after container restarts
- Jobs completing successfully in local dev but silently dying in Cloud Run
- No `completed_at` timestamp written to `batch_generation_jobs`
- Thread daemon flag set to `True` in any implementation

**Phase to address:** Phase 1 (module extraction) — extract `run_async_in_thread` first, before touching batch/hybrid processors.

---

### Pitfall 3: Shared State Across Extracted Modules (Global Provider, Supabase Client)

**What goes wrong:**
`main.py` currently calls `get_provider()` inside each SKU loop iteration and calls `get_client()` inline. When `process_batch_job` and `process_hybrid_batch_job` are moved to separate modules, developers centralize the provider instantiation at module load time (e.g., `provider = OpenAIProvider(...)` at the top of a module). This creates shared mutable state across concurrent background threads, leading to race conditions on `_last_usage`, `_last_parse_details`, and `_last_retry_counts` properties of `OpenAIProvider`, which are instance variables mutated during every `generate()` call.

**Why it happens:**
It looks cleaner to instantiate the provider once. The OpenAI SDK is expensive to initialize. The mistake is that `OpenAIProvider` is stateful — it stores per-call diagnostics as instance state, making it unsafe to share across concurrent calls without locking.

**How to avoid:**
- Keep the pattern of calling `get_provider()` inside each SKU processing iteration and calling `await close_provider(provider)` in a `finally` block, exactly as done today in `process_batch_job` (lines 2843-2865).
- When unifying batch/hybrid processors into `JobRunner`, pass `get_provider` as a factory callable rather than a pre-instantiated provider.
- Never instantiate `OpenAIProvider` at module level. Never store it as a class attribute on `JobRunner`.
- For the Claude provider: verify that `anthropic.AsyncAnthropic` is similarly stateless at the call level before assuming the same pattern holds.

**Warning signs:**
- `last_usage` telemetry showing wrong token counts for a SKU
- Batch jobs reporting mismatched retry counts in logs vs. actual behavior
- Race condition errors from `AsyncOpenAI` client under concurrent load

**Phase to address:** Phase 1 (module extraction) and Phase 3 (JobRunner unification).

---

### Pitfall 4: Circular Imports During Decomposition

**What goes wrong:**
As 30+ Pydantic models and 50+ functions are moved out of `main.py`, new modules start importing from each other. The most common failure pattern: a new `schemas.py` module imports from `generation.py` for a type hint, `generation.py` imports from `job_runner.py`, and `job_runner.py` imports from `schemas.py`. Python raises `ImportError: cannot import name X from partially initialized module Y`.

**Why it happens:**
`main.py` currently has everything in one namespace, so there are no circular imports to worry about. The first decomposition attempt naturally groups by responsibility, but responsibilities in this codebase are tightly intertwined (Pydantic request/response schemas reference domain types; domain types reference persistence types).

**How to avoid:**
- Create a `feedops/api/schemas.py` module for all Pydantic request/response models as the very first extraction. Nothing else imports from it except `main.py` and route handlers.
- Create a `feedops/api/types.py` or use existing `feedops/models/` for domain types. `schemas.py` may import from `types.py` but not vice versa.
- Use `TYPE_CHECKING` guards for type-hint-only imports: `if TYPE_CHECKING: from feedops.api.schemas import BatchRequest`.
- Run `python -c "import feedops.api.main"` after every extraction step to catch import errors before they compound.
- Decompose in strict dependency order: types → schemas → utilities → persistence → processors → routes.

**Warning signs:**
- `ImportError: cannot import name X from partially initialized module`
- `AttributeError: partially initialized module` at startup
- Tests that only fail when the full module graph is imported together

**Phase to address:** Phase 1 (module extraction) — define the import DAG before writing any code.

---

### Pitfall 5: Claude Provider Schema Incompatibility

**What goes wrong:**
The Claude provider is implemented by copying the OpenAI provider pattern, passing the same schema dict. Claude's structured outputs API uses `output_config.format` with `type: json_schema` — which looks the same as OpenAI's format. But Claude applies schema compilation (converts to a grammar at request time), and complex schemas with many nested objects produce very large grammars that significantly increase time-to-first-token. Schemas that are fine for GPT-5.2 (8-12 field flat objects) may work fine for Claude, but deeply nested or heavily constrained schemas can produce 2-5x latency increases.

Additionally, Claude structured outputs require the `anthropic-version: 2023-06-01` header AND are ZDR (Zero Data Retention) — responses are not stored by Anthropic. The Python SDK handles the header automatically, but the ZDR constraint means prompt caching (which this project uses via `extra_body={"prompt_cache_retention": "24h"}`) does not apply to the `output_config` path. Prompt caching still works for the messages/system prompt, but the JSON schema itself is cached separately for up to 24 hours.

**Why it happens:**
The `LLMProvider` base class (`base.py`) has a clean `generate()` interface that suggests both providers can receive the same inputs. The schema format looks identical. Developers assume behavioral parity and don't test Claude's structured output path separately with production-complexity schemas.

**How to avoid:**
- Test the Claude provider with the actual feedops response schema (7-9 platform content fields) against a real SKU before declaring the provider abstraction complete.
- Measure time-to-first-token for Claude structured outputs vs. no structured outputs on the same prompt to detect grammar compilation overhead.
- The Claude provider's `generate()` must pass schema via `output_config={"format": {"type": "json_schema", "schema": schema}}`, NOT via `response_format` (OpenAI's parameter name). The base class interface must accommodate provider-specific kwarg routing.
- Verify that `extra_body={"prompt_cache_retention": "24h"}` passed to the OpenAI provider is silently ignored by the Anthropic SDK (not an error) — or strip it at the provider level.

**Warning signs:**
- `TypeError: unexpected keyword argument 'response_format'` from Anthropic SDK
- Claude provider latency 3-5x higher than GPT-5.2 on same prompt
- Schema validation errors that only appear with Claude, not GPT-5.2

**Phase to address:** Phase: Claude provider implementation — test with production schema before the evaluation phase.

---

### Pitfall 6: Evaluation Bias When Claude Is Writing the Eval Rubric

**What goes wrong:**
The head-to-head evaluation (Claude vs. GPT-5.2) uses the existing `quality_rubric.yaml` as the scoring rubric. If the evaluation scoring is also done by Claude, there is self-preference bias: Claude rates Claude outputs higher regardless of actual quality. Conversely, if GPT-5.2 is the judge, it will favor GPT-5.2 outputs. Research from 2025 shows 48.4% of pairwise verdicts can reverse simply by swapping the order in which outputs are presented to the judge (positional bias).

**Why it happens:**
The natural implementation is "use the best available LLM to judge quality" — which means Claude or GPT-5.2. Neither is a neutral judge of their own output. The rubric was designed for GPT-5.2 optimization, making it structurally biased toward GPT-5.2's output style.

**How to avoid:**
- Use Robert's manual review as the ground truth for the 10 evaluation SKUs. Human judgment is the only unbiased signal.
- If automated scoring is used, use a different model family (e.g., Gemini) as judge, not Claude or GPT-5.2.
- Present outputs to the human judge blind (labels removed, order randomized) to prevent the 98%-approval-rate anchoring effect from biasing evaluation of Claude's different style.
- Evaluate on concrete, objective criteria from the existing approval patterns: `{FINISH_NAME}` first in title, no hardcoded finish names in descriptions, no fabricated specs, collection keyword present. Count rule violations, don't just score holistically.
- Record cost and latency per SKU alongside quality — these are objective and should be a primary evaluation dimension.

**Warning signs:**
- Claude scores consistently higher than GPT-5.2 when Claude is the judge
- GPT-5.2 scores consistently higher when GPT-5.2 is the judge
- Scores don't correlate with Robert's subjective preference
- Evaluation results not actionable (no clear recommendation to switch vs. stay)

**Phase to address:** Phase: Model evaluation — design the evaluation protocol before running any comparisons.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep all Pydantic models in `main.py` during decomposition | Avoids circular import work | Tests cannot import schemas without importing all of main.py; test suite becomes slow | Never — schemas must be extracted first |
| One `process_batch_job` function handles both batch and hybrid paths via flags | Avoids creating JobRunner | Grows to 1000+ lines; adding a third job type requires understanding all existing logic | Never in this codebase — unified logic must be extracted clean |
| Skip unit tests for extracted modules, rely on integration tests | Faster extraction | Bugs in extracted modules are only caught by full Cloud Run deploys; debug cycle is 10+ minutes | Only acceptable for lifespan/middleware code that cannot be unit tested |
| Import `process_batch_job` back into `main.py` via lazy import inside the route handler | Quick fix for circular import | Hidden dependency, import errors only surface at runtime | Acceptable temporarily if flagged with a TODO and fixed in the same PR |
| Reuse the same `OpenAIProvider` instance across SKUs in a batch | Avoids per-SKU init overhead | Race conditions on `_last_usage` etc. in concurrent runs | Never — provider init cost is negligible vs. LLM call latency |
| Fix all 5 GPT-5.2 bugs in one PR | Fewer deploys | If one bug fix breaks output, impossible to isolate which change caused it | Never — each bug fix must be a separate PR with curl verification |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenAI GPT-5.2 | Passing `temperature=0.7` when `reasoning_effort` is also set | These are mutually exclusive on GPT-5.2. Current code at line 372-374 already handles this correctly — do not regress it during refactoring |
| OpenAI GPT-5.2 | Assuming `FEEDOPS_REASONING_EFFORT` env var is always set | Default is `"high"` in `openai_provider.py:334` — must set a sensible default, not leave unset |
| Anthropic Claude | Using `response_format=` parameter (OpenAI syntax) | Claude uses `output_config={"format": {...}}` — different parameter name entirely |
| Anthropic Claude | Assuming `prompt_cache_retention` in `extra_body` works the same way | OpenAI uses `extra_body`; Claude uses `cache_control` headers on specific message blocks |
| Supabase | Writing raw batch job status inside a module that's also imported by `main.py` lifespan | Lifespan runs at startup, before background jobs exist — recovery sweep logic in `_app_lifespan` must stay in `main.py` or a dedicated startup module |
| Cloud Run | Assuming `BackgroundTasks` survives container scale-down | It does not. Only `daemon=False` threads with dedicated event loops survive. See `run_async_in_thread` implementation |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Provider instantiated once at module level, shared across all SKUs | Works fine for single-SKU runs; fails with race conditions in batch | Instantiate provider per SKU inside the processing loop | Any batch larger than 1 with concurrent SKUs |
| Importing `from feedops.api.main import *` in tests | Tests pass in isolation, fail when run together due to state leakage | Import only specific functions/classes, never star-import from main | When test count exceeds ~20 |
| Using `asyncio.run()` inside `run_async_in_thread` instead of `loop.run_until_complete()` | `asyncio.run()` creates AND closes a loop — double-close errors on cleanup | Use `asyncio.new_event_loop()` + `loop.run_until_complete()` + `loop.close()` in `finally` | Every time on Python 3.10+ |
| System prompt cache misses in GPT-5.2 batch runs | Prompt tokens not being cached between SKUs; cost 2x higher than expected | Ensure system prompt is passed as separate `system` message (not embedded in user prompt) and that `prompt_cache_retention: "24h"` is set | After every batch >5 SKUs |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Module extraction complete:** Each extracted module has its own unit test file — verify `tests/api/test_[module].py` exists for every new file
- [ ] **`run_async_in_thread` moved:** Verify `thread.daemon == False` in the new location — easy to accidentally flip during copy/paste
- [ ] **GPT-5.2 bug fixes complete:** After each bug fix, run `curl -X POST $FEEDOPS_PIPELINE_URL/optimize-sku -d '{"master_sku":"920D-6"}'` and verify description length >500 chars and no placeholder-only content
- [ ] **Claude provider complete:** Test with ALL three platforms (google, bing, shopify) — not just one. Bing is where the `{FINISH_NAME}` placeholder requirement is most commonly violated
- [ ] **Bing `{FINISH_NAME}` bug fixed:** Run `SELECT COUNT(*) FROM generated_content WHERE platform='bing' AND candidate_content::text LIKE '%Polished%' OR candidate_content::text LIKE '%Satin%'` — should be 0 after fix
- [ ] **JobRunner unification:** Verify both `/batch-optimize` and `/hybrid-generate` endpoints use the unified runner by checking that `process_batch_job` and `process_hybrid_batch_job` functions no longer exist as separate definitions
- [ ] **Provider abstraction complete:** `get_provider()` returns a `ClaudeProvider` instance when `FEEDOPS_PROVIDER=claude` env var is set — not just a factory that exists but isn't wired

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| GPT-5.2 prompt change causes empty output | MEDIUM | `git revert` the specific prompts.py commit; verify revert fixes output with curl; re-attempt the change in isolation with smaller scope |
| `run_async_in_thread` daemon=True in production | HIGH | Immediate revert and redeploy; manually update stuck `batch_generation_jobs` rows to `failed` via Supabase; audit any jobs that started during the regression window |
| Circular import breaks startup | LOW | `ImportError` at startup is immediately visible in Cloud Run logs; `git revert` the offending extraction commit; restructure import DAG before retrying |
| Claude provider returns wrong schema | LOW | Claude structured output errors are explicit (schema violation) unlike GPT-5.2 silent placeholder output; fix schema mapping in provider and test locally before deploying |
| Evaluation bias produces wrong recommendation | MEDIUM | Re-run evaluation blind with Robert as judge; discard automated scoring results; use cost/latency as tiebreaker when human scores are similar |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| GPT-5.2 prompt sensitivity | GPT-5.2 bug fixes phase — one bug per PR, curl after each | curl `/optimize-sku` for 920D-6; description length >500 chars; no placeholder-only content |
| `run_async_in_thread` breaking | Module extraction — extract helper first, write daemon=False test | `pytest tests/api/test_job_runner.py::test_thread_is_non_daemon` |
| Shared provider state | Module extraction + JobRunner unification | Run batch of 3 SKUs concurrently; verify `last_usage` tokens match logs per SKU |
| Circular imports | Module extraction — define import DAG before writing code | `python -c "import feedops.api.main"` passes with zero warnings after each extraction step |
| Claude provider schema mismatch | Claude provider implementation | Run `curl` against Claude provider with production schema for 3 diverse SKUs; verify all fields populated |
| Evaluation bias | Model evaluation phase — design protocol before running | All 10 evaluation SKUs reviewed blind by Robert before automated scores are generated |
| Bing `{FINISH_NAME}` bug | Bing fix phase | SQL check: 0 rows with hardcoded finish names in Bing candidate_content |

---

## Sources

- Project post-mortem: Phase 27 prompt sensitivity (`CLAUDE.md` + `memory/MEMORY.md` — Phase 27 critical discovery)
- Project audit: `docs/audit/background-task-fix-2026-02-08.md` — `run_async_in_thread` rationale
- Codebase: `src/feedops/api/main.py` lines 243-287 — actual `run_async_in_thread` implementation
- Codebase: `src/feedops/providers/openai_provider.py` lines 333-374 — temperature/reasoning_effort conflict handling
- Official: [Claude Structured Outputs API](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — schema API shape, ZDR constraints (MEDIUM confidence — API shape confirmed current)
- Official: [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) — confirms BackgroundTasks lifecycle limitation (HIGH confidence)
- Community: [FastAPI circular import patterns](https://github.com/fastapi/fastapi/issues/2848) — common circular import solutions (MEDIUM confidence)
- Research: [LLM evaluation bias 2025](https://www.mdpi.com/2078-2489/16/8/652) — positional bias in pairwise comparisons (MEDIUM confidence)
- Research: [LLM-as-judge self-preference bias](https://cameronrwolfe.substack.com/p/llm-as-a-judge) — self-preference bias documentation (MEDIUM confidence)

---
*Pitfalls research for: Pipeline Reliability Rewrite + Model Evaluation*
*Researched: 2026-03-03*
