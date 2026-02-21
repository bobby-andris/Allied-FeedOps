---
phase: 23-foundation
plan: 01
subsystem: python-pipeline
tags: [gpt52, openai-provider, prompt-engineering, bug-fix]
dependency_graph:
  requires: []
  provides: [fixed-openai-provider, xml-system-prompt, default-reasoning-effort]
  affects: [src/feedops/providers/openai_provider.py, src/feedops/pipeline/prompts.py, src/feedops/pipeline/optimize.py]
tech_stack:
  added: []
  patterns: [json_schema-strict-mode, conditional-temperature, prompt-cache-retention, xml-structured-prompts]
key_files:
  created: []
  modified:
    - src/feedops/providers/openai_provider.py
    - src/feedops/pipeline/prompts.py
    - src/feedops/pipeline/optimize.py
decisions:
  - json_schema strict mode with _build_strict_schema() helper that recursively adds additionalProperties:false
  - Module-level _STRICT_RESPONSE_FORMAT computed once at import time to avoid per-request overhead
  - sampling_params dict pattern for conditional temperature (empty when reasoning_effort set)
  - XML tags preserve all section content unchanged, only delimiters replaced
metrics:
  duration_minutes: 4
  completed_date: 2026-02-21
  tasks_completed: 2
  files_modified: 3
---

# Phase 23 Plan 01: GPT-5.2 Bug Fixes Summary

**One-liner:** Fixed all 5 GPT-5.2 integration bugs — conditional temperature, json_schema strict mode, 24h cache retention, default medium reasoning, and XML-structured system prompt.

## What Was Built

Fixed 5 known bugs in the GPT-5.2 generation pipeline that were causing degraded output quality, wasted tokens, and missed cache savings.

### Task 1: Fix OpenAI Provider (3 bugs)

**File:** `src/feedops/providers/openai_provider.py`

**GPT52-01: Temperature/reasoning_effort mutual exclusion**
- Added `sampling_params` dict that is empty when `reasoning_params` is non-empty
- Conditional `temperature=0.7` only passes when reasoning_effort is NOT set
- Both API call paths (image and non-image) now use `**sampling_params`

**GPT52-03: json_schema strict mode**
- Added `_build_strict_schema()` function that converts `CANDIDATE_SCHEMA` to OpenAI strict format
- Recursively adds `additionalProperties: false` to all object types
- Ensures all properties are listed in `required` arrays
- Module-level `_STRICT_RESPONSE_FORMAT` computed once at import time
- Both API calls now use `response_format=_STRICT_RESPONSE_FORMAT`
- json_object mode documented as legacy fallback in `_build_response_format()` docstring

**GPT52-04: prompt_cache_retention**
- Added `extra_body={"prompt_cache_retention": "24h"}` to both API calls
- Keeps cached prefix alive between SKUs during batch runs (was expiring in 5-10 min)

### Task 2: Fix reasoning_effort default and XML prompt headers (2 bugs)

**File:** `src/feedops/pipeline/optimize.py`

**GPT52-02: Default reasoning_effort**
- Changed `os.environ.get("FEEDOPS_REASONING_EFFORT")` to `os.environ.get("FEEDOPS_REASONING_EFFORT", "medium")`
- GPT-5.2 now uses medium reasoning by default, even when env var is not set

**File:** `src/feedops/pipeline/prompts.py`

**GPT52-05: XML tags for system prompt sections**
- Replaced all 5 `=== SECTION_NAME ===` delimiters with XML open/close tags:
  - `<p0_global_factual_rules>` / `</p0_global_factual_rules>`
  - `<p0_field_isolation_rules>` / `</p0_field_isolation_rules>`
  - `<p1_google_bing_feed_rules>` / `</p1_google_bing_feed_rules>`
  - `<p1_shopify_conversion_rules>` / `</p1_shopify_conversion_rules>`
  - `<p2_style_guidance>` / `</p2_style_guidance>`
- Also converted `=== VARIANT CONTEXT ===` in `FINISH_CONTEXT_TEMPLATE` to `<variant_context>` / `</variant_context>`
- All section content is byte-for-byte identical — only delimiters changed

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1    | a7a285d8 | fix(23-01): fix GPT-5.2 OpenAI provider bugs (temperature, json_schema, cache) |
| 2    | faa0d59b | fix(23-01): fix reasoning_effort default and convert SYSTEM_PROMPT to XML tags |

## Verification Results

All checks passed:
- Import verification: `from feedops.providers.openai_provider import OpenAIProvider` — OK
- Schema builder: `_build_strict_schema()` returns dict with 'strict' and 'json_schema' keys — OK
- No hardcoded `temperature=0.7` in API calls — OK
- `json_schema` present in openai_provider.py (5 occurrences) — OK
- `prompt_cache_retention` present in openai_provider.py (2 occurrences) — OK
- Zero `===` patterns in prompts.py — OK
- `"medium"` default in optimize.py — OK
- All module imports succeed without errors — OK

## Deviations from Plan

None - plan executed exactly as written.

## Pre-existing Test Failures (Out of Scope)

One pre-existing test failure noted (not caused by our changes):
- `tests/api/test_dashboard_approval_state_contract.py::test_master_approval_route_only_versions_content_on_approval_transition`
- Fails on the original codebase before any changes (verified via git stash)
- Tests a specific TypeScript implementation pattern in the dashboard approval route
- Logged to deferred-items for future attention

## Self-Check: PASSED

Files exist:
- `src/feedops/providers/openai_provider.py` — FOUND
- `src/feedops/pipeline/prompts.py` — FOUND
- `src/feedops/pipeline/optimize.py` — FOUND

Commits exist:
- a7a285d8 — FOUND
- faa0d59b — FOUND
