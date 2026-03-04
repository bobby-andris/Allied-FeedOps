---
phase: 09-trivial-dead-code-removal
plan: "01"
subsystem: pipeline
tags: [dead-code, cleanup, generator, finish-processing, generation]
dependency_graph:
  requires: []
  provides: [DEAD-01]
  affects: [src/feedops/pipeline/generator.py, src/feedops/api/finish_processing.py, src/feedops/api/generation.py]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - src/feedops/pipeline/generator.py
    - src/feedops/api/finish_processing.py
    - src/feedops/api/generation.py
    - tests/test_generator_task_prompt_contract.py
decisions:
  - "Removed BING_SCHEMA, FINISH_SENTENCES_SCHEMA, GOOGLE_SCHEMA, SHOPIFY_SCHEMA from generator.py — all became orphaned after deleting the 4 functions"
  - "Removed normalized_platforms, normalized_content_types local vars in generate_per_platform — cascade orphans from include_finish F841 removal"
  - "Updated test_generator_task_prompt_contract.py to remove filter_evidence_for_copy_context monkeypatch — direct consequence of import removal (Rule 1 auto-fix)"
  - "Retained FINISH_CONTEXT_TEMPLATE and VARIANT_USER_PROMPT_TEMPLATE — used by DEAD-05 block deleted in Plan 02"
metrics:
  duration_minutes: 4
  completed_date: "2026-03-04"
  tasks_completed: 2
  files_modified: 4
---

# Phase 9 Plan 01: Remove DEAD-01 Orphan Functions and Re-exports Summary

**One-liner:** Removed 8 zero-caller orphan functions/re-exports plus 12 cascade-orphaned imports from generator.py, finish_processing.py, and generation.py — all ruff-clean and test-green.

## What Was Done

Deleted all DEAD-01 targets identified in the Phase 9 research audit:

**Task 1 — generator.py (4 functions + orphaned imports):**
- Deleted `_payload_value_lengths`, `_generate_with_provider_compat`, `_schema_hash`, `_prompt_hash`
- Removed cascade-orphaned imports: `hashlib`, `inspect`, `time`, `estimate_openai_cost_usd_from_usage`, `diagnostic_mode_enabled`, `diagnostic_skip_finish_subcall_enabled`, `request_cost_usd_cap`, `filter_evidence_for_copy_context`
- Removed newly-orphaned schema imports: `BING_SCHEMA`, `FINISH_SENTENCES_SCHEMA`, `GOOGLE_SCHEMA`, `SHOPIFY_SCHEMA`
- Removed cascade-orphaned local variables: `normalized_platforms`, `normalized_content_types`, `include_finish` (F841)
- Commit: `530a6d18`

**Task 2a — finish_processing.py (1 re-export):**
- Deleted `from feedops.api.generation_telemetry import provider_label as _provider_label  # noqa: F401` (line 7)
- Zero callers confirmed — all importers use generation_telemetry directly
- Commit: `c0f4b1bc`

**Task 2b — generation.py (3 re-exports + 1 unused import):**
- Deleted `_build_finish_sentences_user_prompt`, `_validate_finish_sentences_payload`, `_enforce_finish_sentence_parity` re-export block (lines 26-30)
- Removed unused `get_request_id` import (F401)
- Commit: `47a9ac77`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Cascade schema imports orphaned by function deletion**
- **Found during:** Task 1 ruff verification
- **Issue:** Deleting the 4 functions also orphaned `BING_SCHEMA`, `FINISH_SENTENCES_SCHEMA`, `GOOGLE_SCHEMA`, `SHOPIFY_SCHEMA` imports (those schemas were only used by the deleted functions)
- **Fix:** Removed from import block; retained `FINISH_CONTEXT_TEMPLATE` and `VARIANT_USER_PROMPT_TEMPLATE` per plan instruction (used by DEAD-05 block in Plan 02)
- **Files modified:** `src/feedops/pipeline/generator.py`
- **Commit:** `530a6d18`

**2. [Rule 1 - Bug] Cascade local variables orphaned by include_finish removal**
- **Found during:** Task 1 ruff verification
- **Issue:** `normalized_platforms` and `normalized_content_types` computed values were only used by `include_finish`, which we deleted
- **Fix:** Removed both local variable assignments from `generate_per_platform`
- **Files modified:** `src/feedops/pipeline/generator.py`
- **Commit:** `530a6d18`

**3. [Rule 1 - Bug] Test patching removed symbol**
- **Found during:** Task 2 full test suite run
- **Issue:** `test_generator_task_prompt_contract.py` line 46 patched `gen.filter_evidence_for_copy_context` which no longer exists in `generator.py` after import removal
- **Fix:** Removed the monkeypatch line — function is not in the module being tested
- **Files modified:** `tests/test_generator_task_prompt_contract.py`
- **Commit:** `47a9ac77`

## Verification Results

```
# All 8 DEAD-01 targets removed — 0 results each
grep -rn "_payload_value_lengths|_schema_hash|_prompt_hash" src/feedops/pipeline/generator.py  # 0
grep -rn "_provider_label" src/feedops/api/finish_processing.py  # 0
grep -rn "_build_finish_sentences_user_prompt|_validate_finish_sentences_payload|_enforce_finish_sentence_parity" src/feedops/api/generation.py  # 0

# ruff: All checks passed!
# pytest: 788 passed, 1 skipped (test_cli pre-existing failure unchanged)
```

## Commits

| Commit | Description |
|--------|-------------|
| `530a6d18` | refactor(dead-code): remove 4 orphan functions + unused imports from generator.py (DEAD-01a) |
| `c0f4b1bc` | refactor(dead-code): remove _provider_label re-export from finish_processing.py (DEAD-01b) |
| `47a9ac77` | refactor(dead-code): remove finish processing re-exports from generation.py (DEAD-01c) |

## Self-Check: PASSED

- `src/feedops/pipeline/generator.py` — exists, modified
- `src/feedops/api/finish_processing.py` — exists, modified
- `src/feedops/api/generation.py` — exists, modified
- `tests/test_generator_task_prompt_contract.py` — exists, modified (auto-fix)
- Commits `530a6d18`, `c0f4b1bc`, `47a9ac77` — all present in git log
