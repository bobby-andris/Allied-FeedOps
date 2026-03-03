---
phase: 05-claude-provider
plan: "01"
subsystem: providers
tags: [claude, anthropic, llm-provider, structured-outputs, prompt-caching]
dependency_graph:
  requires:
    - feedops.providers.base (LLMProvider ABC, ImageInput, LLMError)
    - feedops.providers.openai_provider (_parse_json_payload)
    - feedops.providers.reliability (circuit_breakers, compute_backoff_seconds, is_retryable_provider_error)
    - feedops.observability (log_event)
    - feedops.observability.metrics (metrics_registry)
  provides:
    - ClaudeProvider (drop-in LLMProvider implementation)
    - _extract_claude_usage (Anthropic -> standard usage dict mapping)
  affects:
    - pyproject.toml (anthropic>=0.84.0 dependency added)
tech_stack:
  added:
    - anthropic>=0.84.0 (AsyncAnthropic, output_config.format structured outputs)
  patterns:
    - output_config.format with json_schema type (GA on claude-sonnet-4-6, no beta header)
    - cache_control ephemeral automatic prompt caching
    - Anthropic base64 source format for image inputs
    - system= kwarg for system prompt (not in messages list)
    - response.content[0].text response extraction path
key_files:
  created:
    - src/feedops/providers/claude_provider.py
    - tests/test_claude_provider.py
  modified:
    - pyproject.toml
decisions:
  - output_config.format with json_schema over tool_use: cleaner, GA, no tool definition overhead
  - reasoning_effort accepted but not acted on in Phase 5; Phase 6 will map to budget_tokens (low=2000, medium=8000, high=20000)
  - Import _parse_json_payload directly from openai_provider (no utils.py extraction needed in Phase 5)
  - anthropic installed into venv via pip install during execution (pyproject.toml updated for future installs)
metrics:
  duration: "3 min"
  completed: "2026-03-03"
  tasks_completed: 2
  files_changed: 3
---

# Phase 05 Plan 01: Claude Provider Implementation Summary

ClaudeProvider implementing LLMProvider ABC using Anthropic SDK with output_config.format json_schema structured outputs, automatic prompt caching, and full parity with OpenAIProvider's metrics/retry/circuit-breaker interface.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add anthropic SDK and implement ClaudeProvider | f522a497 | pyproject.toml, src/feedops/providers/claude_provider.py |
| 2 | Test ClaudeProvider against all 3 content platforms | a56172b2 | tests/test_claude_provider.py |

## What Was Built

### ClaudeProvider (`src/feedops/providers/claude_provider.py`)

Full LLMProvider implementation for Anthropic Claude:

- **Structured output**: Uses `output_config={"format": {"type": "json_schema", "schema": schema}}` — GA constrained decoding for claude-sonnet-4-6, no beta header required
- **Prompt caching**: `cache_control={"type": "ephemeral"}` at request level — automatic caching of static system prompt prefix
- **System prompt**: Passed as `system=` kwarg (NOT as a message in messages list — Anthropic's API design)
- **Image input**: Anthropic base64 source format — `{"type": "image", "source": {"type": "base64", "media_type": ..., "data": ...}}`
- **Response extraction**: `response.content[0].text` (NOT `response.choices[0].message.content` which is OpenAI-only)
- **Usage mapping**: `_extract_claude_usage()` maps `input_tokens`→`prompt_tokens`, `output_tokens`→`completion_tokens`, `cache_read_input_tokens`→`cached_tokens`
- **Retry loop**: JSON parse failure handling with repair prompt appended for text path, rebuilt for image path
- **Circuit breaker**: Uses shared `circuit_breakers` registry from reliability.py
- **Backoff**: Uses shared `compute_backoff_seconds()` from reliability.py
- **Metrics**: `provider_latency_seconds`, `provider_circuit_open_total`, `provider_retry_total`, `provider_error_total` — identical telemetry surface to OpenAIProvider
- **Properties**: `last_usage`, `last_parse_details`, `last_retry_counts` — matching OpenAIProvider interface exactly
- **reasoning_effort**: Accepted without error, not forwarded to Anthropic API (Phase 5 decision); logged at debug level

### Test Suite (`tests/test_claude_provider.py`)

25 tests all passing:

- Platform schema coverage: Google, Bing, Shopify
- API call structure: output_config, cache_control, system= kwarg, no-system case
- Image input: Anthropic base64 source format verified
- Retry logic: invalid JSON retry succeeds on 2nd call; LLMError after max_retries
- Usage extraction: standard and cache_hit scenarios; no-usage-attr edge case
- health_check: True on success, False on exception
- aclose: client.close() called
- reasoning_effort: accepted, not forwarded to API
- Circuit breaker: blocks when open
- Property copies: last_usage, last_parse_details, last_retry_counts return copies

## Decisions Made

1. **output_config.format over tool_use**: Native constrained decoding, no tool definition overhead, GA for claude-sonnet-4-6
2. **reasoning_effort deferred to Phase 6**: Phase 5 only accepts parameter — Phase 6 will map to thinking budget_tokens (low=2000, medium=8000, high=20000)
3. **Direct _parse_json_payload import**: Import from openai_provider directly; utils.py extraction deferred to Phase 6 cleanup if desired
4. **anthropic installed via pip**: Added to pyproject.toml for future installs; installed in venv during execution

## Deviations from Plan

None — plan executed exactly as written. Task 1 then Task 2 in the specified order. TDD note: since Task 1 (implementation) was ordered before Task 2 (tests) in the plan, tests were written after implementation and all 25 passed immediately.

## Self-Check: PASSED

- `src/feedops/providers/claude_provider.py` exists (289 lines, above 150 min)
- `tests/test_claude_provider.py` exists (25 tests, above 100 min_lines)
- `pyproject.toml` contains `anthropic>=0.84.0`
- Commits f522a497 and a56172b2 verified in git log
- Import: `from feedops.providers.claude_provider import ClaudeProvider, _extract_claude_usage` succeeds
- All 25 tests pass: `pytest tests/test_claude_provider.py` → 25 passed in 3.46s
