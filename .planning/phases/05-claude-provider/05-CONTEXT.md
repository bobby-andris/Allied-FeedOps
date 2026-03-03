# Phase 5: Claude Provider - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `ClaudeProvider` that produces structured product content (Google, Bing, Shopify) through the same `LLMProvider` interface as `OpenAIProvider`. An environment variable (`FEEDOPS_PROVIDER=claude`) selects the provider at runtime. No changes to prompt construction, generation orchestration, or other modules — the provider is a drop-in replacement.

</domain>

<decisions>
## Implementation Decisions

### Structured output approach
- Claude's discretion on which structured output mechanism to use (tool_use forced, native JSON mode, or constrained output) — researcher investigates current API capabilities and picks the most reliable approach
- Mirror OpenAI provider's retry-on-bad-JSON logic for consistency — same safety net pattern, can tune retry count separately
- Full metrics parity: expose `last_usage`, `last_parse_details`, `last_retry_counts` properties — enables apples-to-apples comparison in Phase 6 evaluation
- Full image input support (ImageInput) from day one — Claude supports vision natively, keep provider complete

### Model & reasoning config
- Default model configurable via `FEEDOPS_CLAUDE_MODEL` env var, default to Sonnet 4 — best balance of quality/cost/speed for production content generation
- Claude's discretion on whether/how to map `reasoning_effort` to extended thinking — researcher investigates whether extended thinking improves content quality for this use case
- Claude's discretion on prompt caching implementation — researcher/planner determine based on expected batch sizes and cost impact
- Add `anthropic` SDK to pyproject.toml dependencies — Claude's discretion on version pinning strategy

### Factory & env var design
- Claude's discretion on cleanest factory integration — extend existing `get_provider()` or new env var pattern, whichever is cleanest
- No fallback chains initially — keep Claude standalone for Phase 6 evaluation. Isolated results needed for clean comparison
- Claude's discretion on API key env var naming (ANTHROPIC_API_KEY vs FEEDOPS_ANTHROPIC_API_KEY) — pick based on GCP secrets naming and SDK conventions
- GCP secret setup is a separate manual ops task — Phase 5 is code-only

### Prompt compatibility
- Same prompt verbatim — Phase 6 evaluation needs identical prompts for fair comparison. Claude handles XML tags natively
- Keep self_score and scoring_rubric in prompt for Claude — same prompt means same fields. Interesting to compare self-assessment. Can remove later if evaluation shows it's unnecessary
- ClaudeProvider receives the same `(system_prompt, user_prompt, schema)` tuple — no changes to `prompt_builder.py`. Clean separation of concerns
- Schema validation tests for all 3 platforms (Google, Bing, Shopify) — required by PROV-05

### Claude's Discretion
- Structured output mechanism selection (tool_use vs JSON mode vs constrained output)
- Extended thinking token budgets and whether to use them at all
- Prompt caching implementation details (cache_control breakpoints)
- SDK version pinning strategy
- Factory integration pattern (extend get_provider vs separate env var)
- API key env var naming convention
- Retry logic configuration (retry counts, backoff strategy)
- Circuit breaker integration (existing `reliability.py` patterns)

</decisions>

<specifics>
## Specific Ideas

- The Phase 4 verification script (`verify_content_quality.py`) should be reusable for testing Claude provider output — run it with FEEDOPS_PROVIDER=claude to validate content quality
- Phase 6 evaluation needs identical prompts between providers — any prompt divergence confounds the comparison
- The existing `FallbackProvider` wrapper should NOT include Claude until after Phase 6 evaluation proves which provider is better

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `providers/base.py`: `LLMProvider` ABC with `generate()`, `health_check()`, `aclose()`, `name` — Claude provider implements this interface
- `providers/factory.py`: `get_provider(preferred)` handles "openai"/"gemini" with fallback — extend for "claude"
- `providers/openai_provider.py`: Reference implementation — same patterns for retry logic, metrics tracking, error handling
- `providers/reliability.py`: Circuit breakers and backoff logic — reusable for Claude provider
- `providers/gemini_provider.py`: Second reference implementation — simpler than OpenAI, shows minimum viable provider
- `scripts/verify_content_quality.py`: Post-deploy verification — reusable for Claude provider testing

### Established Patterns
- Provider tests mock the SDK client and verify call arguments (see `tests/api/test_openai_provider_smoke.py`)
- `_parse_json_payload()` in OpenAI provider handles JSON normalization — Claude provider may need similar
- `_build_strict_schema()` converts schemas to OpenAI's strict format — Claude needs equivalent schema handling
- `log_event()` and `metrics_registry` used throughout for observability — Claude provider should follow same patterns

### Integration Points
- `factory.py:64-126`: `get_provider()` — add Claude branch
- `generation/executor.py:48,113`: Imports and uses `LLMProvider` — no changes needed (polymorphic)
- `pipeline/generator.py:65,153`: Same — uses `LLMProvider` interface
- `api/job_runner.py`: Job processing uses provider from factory — transparent provider swap
- `Dockerfile` / `pyproject.toml`: Add anthropic SDK dependency
- GCP: New secret `feedops-anthropic-api-key` bound to runtime SA (manual ops task)

</code_context>

<deferred>
## Deferred Ideas

- Claude-optimized prompt variant — evaluate after Phase 6 baseline comparison with identical prompts
- Claude fallback chains (OpenAI→Claude or Claude→OpenAI) — evaluate after Phase 6 proves provider strengths
- Extended thinking fine-tuning for content quality — evaluate in Phase 6 with different thinking budgets
- `output_verbosity` parameter exploration for Claude — new API feature, untested for product content

</deferred>

---

*Phase: 05-claude-provider*
*Context gathered: 2026-03-03*
