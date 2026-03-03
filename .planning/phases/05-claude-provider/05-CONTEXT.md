# Phase 5: Claude Provider - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement `ClaudeProvider` that produces structured product content (Google, Bing, Shopify) through the same `LLMProvider` interface as `OpenAIProvider`. An environment variable (`FEEDOPS_PROVIDER=claude`) selects the provider at runtime. No changes to prompt construction, generation orchestration, or other modules — the provider is a drop-in replacement.

</domain>

<decisions>
## Implementation Decisions

### Model selection (USER DECISION)
- Default model: Claude Sonnet 4.6 (`claude-sonnet-4-6`)
- Configurable via `FEEDOPS_CLAUDE_MODEL` env var, defaults to `claude-sonnet-4-6`
- Allows swapping to Opus or Haiku without code changes (useful for Phase 6 evaluation)

### Prompt compatibility (USER DECISION)
- Same prompt verbatim as GPT-5.2 — no Claude-specific prompt optimization in Phase 5
- Rationale: Phase 27 proved prompt changes are extremely risky. Claude-optimized prompts deferred to after Phase 6 evaluation when we have real output data to compare
- Keep self_score and scoring_rubric in prompt — same prompt means same fields
- ClaudeProvider receives the same `(system_prompt, user_prompt, schema)` tuple — no changes to `prompt_builder.py`

### Fallback chains (USER DECISION)
- No fallback chains initially — keep Claude standalone
- Rationale: Phase 6 needs isolated results for clean head-to-head comparison. Fallback chains would mask per-provider failure modes
- The existing `FallbackProvider` wrapper stays as-is (OpenAI/Gemini only). Add Claude to fallback after Phase 6 data

### API key (USER DECISION)
- Use `ANTHROPIC_API_KEY` (standard SDK convention) — already set up in Cloud Run, Vercel, and locally
- GCP secret `feedops-anthropic-api-key` already created and bound to runtime SA

### Extended thinking / reasoning (USER DECISION)
- Researcher should investigate whether extended thinking improves content quality for this use case
- Don't assume it's needed — Claude's base reasoning may be sufficient for product descriptions
- Decision on thinking budget mapping deferred to research findings

### Structured output approach
- Claude's discretion on mechanism (tool_use forced, native JSON mode, or constrained output) — researcher investigates current API capabilities
- Mirror OpenAI provider's retry-on-bad-JSON logic for consistency
- Full metrics parity: expose `last_usage`, `last_parse_details`, `last_retry_counts` — enables apples-to-apples Phase 6 comparison
- Full image input support (ImageInput) from day one — Claude supports vision natively

### Claude's Discretion
- Structured output mechanism selection (tool_use vs JSON mode vs constrained output)
- Extended thinking token budgets (pending research findings)
- Prompt caching implementation (cache_control breakpoints for batch cost savings)
- SDK version pinning strategy for `anthropic` package
- Factory integration pattern (extend existing `get_provider()`)
- Retry logic configuration (retry counts, backoff strategy)
- Circuit breaker integration (existing `reliability.py` patterns)
- Schema validation test depth for PROV-05

</decisions>

<specifics>
## Specific Ideas

- Phase 4 verification script (`verify_content_quality.py`) should be reusable for testing Claude output — run with `FEEDOPS_PROVIDER=claude`
- No prompt engineering in this phase — learned from Phase 27 that prompt changes are high-risk and need iterative deploy-and-test
- Phase 6 evaluation needs identical prompts between providers — any divergence confounds the comparison

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
- GCP: Secret `feedops-anthropic-api-key` already created and bound to runtime SA (done)

</code_context>

<deferred>
## Deferred Ideas

- Claude-optimized prompt variant (possibly using skill-creator) — evaluate after Phase 6 baseline comparison with identical prompts. Phase 27 proved prompt changes need iterative testing with real output data
- Claude fallback chains (OpenAI->Claude or Claude->OpenAI) — evaluate after Phase 6 proves provider strengths
- Extended thinking fine-tuning for content quality — evaluate in Phase 6 with different thinking budgets if research shows benefit
- `output_verbosity` parameter exploration — new API feature, untested for product content

</deferred>

---

*Phase: 05-claude-provider*
*Context gathered: 2026-03-03*
