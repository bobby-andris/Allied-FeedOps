---
phase: 20-targeted-fixes-intelligence-application
plan: 03
subsystem: python-pipeline
tags: [prompt-parity, feature-flags, shopping-intelligence, prompt-builder, fix-01, fix-02, goog-04]
dependency_graph:
  requires:
    - shopping-intelligence-yaml-config
    - shopping-intelligence-loader
  provides:
    - shared-prompt-builder
    - prompt-parity-fix
    - observable-feature-flags
  affects:
    - src/feedops/api/main.py
    - src/feedops/api/prompt_builder.py
key_files:
  created:
    - src/feedops/api/prompt_builder.py
  modified:
    - src/feedops/api/main.py
decisions:
  - "build_core_prompt() is the single canonical prompt construction function for all generation paths (FIX-01)"
  - "PROMPT_CONTRACT_V2 gates Shopping intelligence section in user prompt — produces structurally observable diff when toggled"
  - "SEGMENT_STRATEGY_V1 gates segment strategy guidance section — also observable structural diff"
  - "INTENT_CURATOR_V1 effect stays upstream in evidence.py (raw vs curated evidence content) — not a prompt structure change"
  - "_build_generation_user_prompt() refactored as thin DEPRECATED wrapper around build_core_prompt() for backward compat"
  - "apply_feedback_layer() uses additive pattern — appends to core prompt, never forks it"
  - "corrections=[] passed for now at all call sites; Plan 04 will wire sku_corrections DB lookup"
  - "Raw evidence list passed directly from build_evidence_table() to build_core_prompt() for keyword placement enrichment"
tech_stack:
  added: []
  patterns:
    - "Shared prompt builder module pattern (single source of truth for prompt construction)"
    - "FIX-02: Observable feature flag gating via structural prompt section inclusion/exclusion"
    - "Additive feedback layer (append, not fork) for session feedback and persistent corrections"
metrics:
  duration: "~3 minutes"
  completed: "2026-02-21T11:01:00Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 1
requirements_completed:
  - FIX-01
  - FIX-02
  - GOOG-04
---

# Phase 20 Plan 03: Shared Prompt Builder + Prompt Parity Summary

**One-liner:** Shared `prompt_builder.py` module with `build_core_prompt()` achieving structural prompt parity across all generation paths, with PROMPT_CONTRACT_V2 and SEGMENT_STRATEGY_V1 gating observable section inclusion.

## What Was Built

### Task 1: Create shared prompt_builder.py module

**`src/feedops/api/prompt_builder.py`** — New shared module with two exported functions:

**`build_core_prompt(parent_sku, evidence, evidence_markdown, platform, content_type, finish_code=None) -> str`**

Canonical prompt construction function. Construction order:

1. **Evidence table** — `evidence_markdown` (pre-formatted)
2. **Target platform + content type** header
3. **Keyword placement plan** — `build_keyword_placement_plan(parent_sku, evidence)` then `format_keyword_placement_section()`. Graceful skip on error.
4. **Segment strategy guidance** — Only when `SEGMENT_STRATEGY_V1` enabled. Extracts `custom_label_0` values from `merchant_center_items`, calls `resolve_segment_strategy()` then `format_segment_strategy_guidance()`. Graceful skip on error.
5. **Shopping intelligence section** — **Only when `PROMPT_CONTRACT_V2` enabled**. Calls `get_shopping_intelligence_section(custom_label_0)` from Plan 01. This makes FIX-02 observably structural.
6. **Category guidance** — `get_category_guidance()` with `build_category_guidance()` fallback.
7. **Gold standard examples** — Uses `format_gold_standard_examples_bundle(max_examples=2)` (cross-platform bundle, mirrors `generator.py`). Falls back to `format_gold_standard_examples()` if bundle fails.
8. **Finish context** — Platform-specific finish handling (google/bing vs shopify, with finish_code integration).
9. **JSON output instruction** — Canonical schema instruction.

**`apply_feedback_layer(core_prompt, corrections=None, session_feedback=None) -> str`**

Additive feedback layer per architecture principle — appends to core, never forks it:
- `corrections`: Persistent corrections from sku_corrections table (Plan 04 will populate; `[]` for now)
- `session_feedback`: Single-request reviewer feedback text
- If both empty/None, returns `core_prompt` unchanged

**Helper `_extract_custom_label_0(parent_sku)`**: Extracts first `custom_label_0` value from `merchant_center_items`, falling back to `parent_sku.category`.

### Task 2: Wire main.py to use shared prompt_builder

**`src/feedops/api/main.py`** — Four call sites updated:

| Call site | Location | Change |
|-----------|----------|--------|
| `/regenerate` endpoint | Line ~969 | `build_core_prompt()` + `apply_feedback_layer(session_feedback=request.feedback)` |
| `/optimize-sku` endpoint | Line ~838 | `build_core_prompt()` (no feedback layer) |
| `process_batch_job()` | Line ~1465 | `build_core_prompt()` (no feedback layer) |
| `generate_full_content()` in hybrid | Line ~1699 | `build_core_prompt()` (no feedback layer) |

All four call sites pass the raw `evidence` list from `build_evidence_table()` directly to `build_core_prompt()` for keyword placement enrichment.

**`_build_generation_user_prompt()`** — Refactored as DEPRECATED wrapper:
- Now delegates to `build_core_prompt()` + `apply_feedback_layer()` internally
- Accepts optional `evidence=[]` parameter for compatibility
- Docstring clearly marks it DEPRECATED
- Not deleted — backward compatibility maintained for any external callers

## Feature Flag Observability (FIX-02)

| Flag | Effect | Observable? |
|------|--------|-------------|
| `PROMPT_CONTRACT_V2` | Controls Shopping intelligence section inclusion | Yes — structurally absent when disabled |
| `SEGMENT_STRATEGY_V1` | Controls segment strategy guidance section | Yes — structurally absent when disabled |
| `INTENT_CURATOR_V1` | Controls evidence curation in evidence.py | Upstream — evidence content differs, not prompt structure |

## Decisions Made

1. **Evidence list threading** — The raw `evidence` list from `build_evidence_table()` is now passed through to `build_core_prompt()` at all call sites. This enables keyword placement plan construction with real data (not just `evidence=[]` fallback).

2. **Deprecated wrapper signature** — Added `evidence: list | None = None` parameter to `_build_generation_user_prompt()` to allow gradual migration of any remaining callers.

3. **Bundle-first gold examples** — `build_core_prompt()` tries `format_gold_standard_examples_bundle()` first (cross-platform bundle, mirrors `generator.py` pattern), falls back to platform-specific `format_gold_standard_examples()` if the bundle fails.

4. **Additive feedback pattern** — `apply_feedback_layer()` appends to the core prompt rather than weaving feedback throughout. This keeps core prompt structure clean and makes feedback effect predictable.

## Deviations from Plan

None — plan executed exactly as written.

The plan said to check for `format_gold_standard_examples_bundle` availability in prompt_loader.py — it exists at line 275. Used as the primary path.

The `/regenerate` endpoint already had `evidence` (raw rows) from `build_evidence_table(parent_sku)` at line 992 — passed directly to `build_core_prompt()` as the plan specified.

## Self-Check

### Files created:
- `src/feedops/api/prompt_builder.py` — FOUND

### Files modified:
- `src/feedops/api/main.py` — FOUND (4 call sites updated, deprecated wrapper refactored)

### Commits:
- `57369167` — feat(20-03): create shared prompt_builder.py module
- `14050d14` — feat(20-03): wire main.py to use shared prompt_builder

### Verification commands passed:
- `from feedops.api.prompt_builder import build_core_prompt, apply_feedback_layer` — imports OK
- `build_core_prompt.__doc__[:80]` — prints docstring
- `grep -n 'build_core_prompt' main.py` — finds 4 direct call sites + import + deprecated wrapper
- `grep -n '_build_generation_user_prompt' main.py` — shows only definition (DEPRECATED), not call sites
- `apply_feedback_layer(test_core, session_feedback='...')` — 'Reviewer Feedback' in output
- `apply_feedback_layer(test_core)` — returns core_prompt unchanged
- `apply_feedback_layer(test_core, corrections=[...])` — 'Persistent Corrections' in output
- `PROMPT_CONTRACT_V2=1` → `is_prompt_contract_v2_enabled() == True`
- `PROMPT_CONTRACT_V2=0` → `is_prompt_contract_v2_enabled() == False`
- `get_shopping_intelligence_section('Towel Bars')` contains `=== GOOGLE SHOPPING OPTIMIZATION ===`

## Self-Check: PASSED
