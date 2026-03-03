---
phase: 04-gpt52-bug-fixes
plan: 01
subsystem: tests
tags: [regression-tests, gpt52, openai-provider, prompts]
dependency_graph:
  requires: []
  provides: [regression-test-coverage-gpt52-bugs]
  affects: [src/feedops/providers/openai_provider.py, src/feedops/pipeline/prompts.py]
tech_stack:
  added: []
  patterns: [monkeypatch-kwargs-capture, async-pytest-asyncio]
key_files:
  created:
    - tests/test_gpt52_regression.py
  modified:
    - .planning/REQUIREMENTS.md
decisions:
  - "Use empty-properties schema in GPT-03 test so fake response '{}' passes missing-key validation while still verifying response_format construction"
  - "GPT-02 default is 'high' — requirement spec updated to match locked decision from 04-CONTEXT.md"
metrics:
  duration_minutes: 3
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  completed_date: "2026-03-03"
---

# Phase 04 Plan 01: GPT-5.2 Regression Tests Summary

One-liner: Seven targeted regression tests locking down the 5 known GPT-5.2 bug fixes in openai_provider.py and prompts.py using monkeypatch kwargs capture.

## What Was Built

Created `tests/test_gpt52_regression.py` with 7 tests covering all 5 GPT-5.2 bugs (GPT-01 through GPT-05). Tests use the monkeypatch + kwargs capture pattern established in `test_openai_provider_max_tokens.py`.

**Tests written:**

| Test | Bug | Assertion |
|------|-----|-----------|
| `test_gpt01_temperature_not_passed_with_reasoning_effort` | GPT-01 | `temperature` absent from kwargs when `reasoning_effort` is set |
| `test_gpt02_reasoning_effort_defaults_to_high` | GPT-02 | `reasoning_effort == "high"` when env var unset |
| `test_gpt02_reasoning_effort_respects_env_var` | GPT-02 | env var value honored when explicitly set |
| `test_gpt03_json_schema_strict_mode` | GPT-03 | `response_format.type == "json_schema"` and `strict is True` |
| `test_gpt04_prompt_cache_retention_text_path` | GPT-04 | `extra_body["prompt_cache_retention"] == "24h"` on text path |
| `test_gpt04_prompt_cache_retention_image_path` | GPT-04 | `extra_body["prompt_cache_retention"] == "24h"` on image path |
| `test_gpt05_system_prompt_uses_xml_tags` | GPT-05 | SYSTEM_PROMPT has all 5 XML tags, no `===` |

Also updated REQUIREMENTS.md GPT-02 description from `"medium"` to `"high"` to match the locked decision.

## Decisions Made

1. **Empty-properties schema for GPT-03 test**: The fake create returns `{}` which fails missing-key validation if properties are declared. Using `{"type": "object", "properties": {}}` lets the test verify `response_format` kwargs construction without triggering JSON retry logic.

2. **GPT-02 default is "high"**: Updated REQUIREMENTS.md to say `"high"` (was `"medium"`) aligning with 04-CONTEXT.md locked decision: "Keep 'high' as default."

## Deviations from Plan

None — plan executed exactly as written.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 483ce781 | test(04-01): add GPT-5.2 regression tests for bugs GPT-01 through GPT-05 |
| Task 2 | 087dee55 | chore(04-01): update REQUIREMENTS.md GPT-02 default from 'medium' to 'high' |

## Verification Results

All 7 regression tests pass:

```
tests/test_gpt52_regression.py::test_gpt01_temperature_not_passed_with_reasoning_effort PASSED
tests/test_gpt52_regression.py::test_gpt02_reasoning_effort_defaults_to_high PASSED
tests/test_gpt52_regression.py::test_gpt02_reasoning_effort_respects_env_var PASSED
tests/test_gpt52_regression.py::test_gpt03_json_schema_strict_mode PASSED
tests/test_gpt52_regression.py::test_gpt04_prompt_cache_retention_text_path PASSED
tests/test_gpt52_regression.py::test_gpt04_prompt_cache_retention_image_path PASSED
tests/test_gpt52_regression.py::test_gpt05_system_prompt_uses_xml_tags PASSED
7 passed in 1.29s
```

No production code was modified (openai_provider.py and prompts.py untouched).

## Deferred Items

Pre-existing test isolation issue: `test_cli.py::test_optimize_pipeline_integration` and `test_pipeline.py::test_optimize_parent_sku_reports_product_not_found` fail when run in full suite context due to unclosed socket/event loop ResourceWarnings from async test interactions. Both pass individually. Pre-existing issue, unrelated to this plan's changes.

## Self-Check: PASSED

- [x] `tests/test_gpt52_regression.py` exists (213 lines, 7 tests)
- [x] `.planning/REQUIREMENTS.md` GPT-02 says "high"
- [x] Commit 483ce781 exists
- [x] Commit 087dee55 exists
- [x] No production code modified
