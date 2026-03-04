# Phase 9: Trivial Dead Code Removal - Research

**Researched:** 2026-03-04
**Domain:** Python dead code deletion — orphan functions, feature-flag-gated blocks, re-export cleanup
**Confidence:** HIGH (all findings verified by direct source file inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Delete in separate atomic commits per logical group — easier to bisect if something breaks
- DEAD-01 orphan functions first (lower risk), then DEAD-05 feature flag block (larger change)
- Run `pytest tests/` and `ruff check src/` after each commit to confirm green
- Delete the flag check, dead code branches, and all comments/docstrings that reference `FEEDOPS_VARIANT_AT_LLM_TIME` — clean removal, no vestigial references
- Spans 3 files: generator.py, finish_injection.py, reporter.py
- Remove `_provider_label` re-export from finish_processing.py (it re-exports from generation_telemetry.py — callers should import directly)
- Remove finish processing re-exports from generation.py (lines 26-30)
- Do NOT touch main.py re-exports — that's Phase 11 (DEAD-03)

### Claude's Discretion
- Exact ordering of individual function deletions within DEAD-01
- Whether to combine small deletions in the same file into one commit
- How to handle any docstring references to deleted functions in other files

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEAD-01 | Remove 8 orphaned functions/re-exports with zero callers: `_payload_value_lengths`, `_schema_hash`, `_prompt_hash`, `_generate_with_provider_compat` in generator.py; `_provider_label` re-export in finish_processing.py; 3 finish processing re-exports in generation.py | All 8 targets located and verified zero-caller status in source |
| DEAD-05 | Remove ~500 lines of variant generation code behind never-enabled `FEEDOPS_VARIANT_AT_LLM_TIME` feature flag | Block mapped precisely: generator.py lines 741-936, reporter.py lines 32-41 + 863-875, finish_injection.py docstring + debug string references |
</phase_requirements>

---

## Summary

Phase 9 is a pure-subtraction phase: delete orphan functions and a never-enabled feature flag block across 5 Python files. No new code, no schema changes, no production behavior changes. The flag `FEEDOPS_VARIANT_AT_LLM_TIME` has never been set to a truthy value in any environment — removing it is safe.

The research identified one planning-critical nuance: `tests/test_pipeline.py` imports and tests `build_variant_prompt` directly (lines 10-16, tests at 846-887). These tests exist specifically for dead code being deleted. The CONTEXT says "No test changes required" — but those 2 tests will fail when the function is deleted. The planner must decide whether to delete those 2 tests in the same commit as the code deletion (safest: same atomic commit so tests never run against a broken import) or treat them as "required" test changes that must accompany DEAD-05.

Beyond that nuance, all targets are clearly located with exact line numbers, no callers exist, and ruff already reports many of the imports as unused. The baseline test suite has 1 pre-existing failure (`test_cli.py::test_optimize_pipeline_integration`) unrelated to this work — planners should note this is a known pre-existing failure and not count it as a regression.

**Primary recommendation:** Execute DEAD-01 commits first (generator.py functions + re-exports in finish_processing.py and generation.py), then DEAD-05 (variant generation block). Delete the 2 `build_variant_prompt` tests in the same commit as the DEAD-05 deletion.

---

## Standard Stack

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| ruff | installed (`.venv`) | Lint/unused-import detection | Project standard; already reports F401/F841 errors |
| pytest | installed (`.venv`) | Test runner | Project standard; asyncio_mode=auto configured |
| git | system | Atomic commits | Locked decision — one commit per logical group |

### Verification Commands
```bash
# After each commit — both must pass:
.venv/bin/pytest tests/ -q --tb=short
.venv/bin/ruff check src/feedops/pipeline/generator.py src/feedops/api/finish_processing.py src/feedops/api/generation.py src/feedops/pipeline/reporter.py src/feedops/pipeline/finish_injection.py
```

---

## Architecture Patterns

### Deletion Pattern
This phase is purely subtractive. No new abstractions, no refactors. Each deletion follows:
1. Confirm zero callers via grep
2. Delete function/block
3. Remove orphaned imports that were only used by the deleted code
4. Run `ruff check` + `pytest` before committing
5. Commit with descriptive message

### Anti-Patterns to Avoid
- **Deleting imports before confirming they're unused elsewhere** — ruff will flag if you miss a real usage
- **Deleting the `else` branch in reporter.py** — the `else:` block (lines 876-897) is the LIVE path; only delete the `if use_llm_variant:` branch and the helper function
- **Cleaning up non-target ruff errors in the same commit** — stay focused; other ruff violations are pre-existing and out of scope

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Finding all callers of a function | Custom grep script | `grep -rn "function_name"` on src/ and tests/ — already done |
| Import cleanup after deletion | Manual counting | ruff F401 report immediately shows orphaned imports |

---

## Exact Deletion Map (CRITICAL)

### Commit 1: DEAD-01a — generator.py orphan functions (4 functions)

**File:** `src/feedops/pipeline/generator.py`

Functions to delete:
- `_payload_value_lengths` — lines **138-148** (10 lines)
- `_generate_with_provider_compat` — lines **151-181** (31 lines)
- `_schema_hash` — lines **184-187** (4 lines)
- `_prompt_hash` — lines **190-193** (4 lines)

**Imports to remove after deletion** (all become unused):
- Line 4: `import hashlib` — used ONLY by `_schema_hash` and `_prompt_hash`
- Line 5: `import inspect` — used ONLY by `_generate_with_provider_compat`
- Line 10: `import time` — already unused (F401 in ruff baseline)
- Line 18: `from feedops.api.generation_telemetry import estimate_openai_cost_usd_from_usage` — unused (F401)
- Lines 19-23: `from feedops.api.runtime_controls import (diagnostic_mode_enabled, diagnostic_skip_finish_subcall_enabled, request_cost_usd_cap)` — all unused (F401)
- Line 37: `filter_evidence_for_copy_context` from evidence import — unused (F401)
- Lines 50-56: `BING_SCHEMA`, `FINISH_SENTENCES_SCHEMA`, `FINISH_CONTEXT_TEMPLATE`, `GOOGLE_SCHEMA`, `SHOPIFY_SCHEMA`, `VARIANT_USER_PROMPT_TEMPLATE` from prompts — `FINISH_CONTEXT_TEMPLATE` and `VARIANT_USER_PROMPT_TEMPLATE` are used only by the DEAD-05 block; the rest are already unused F401

**Important:** `FINISH_CONTEXT_TEMPLATE` and `VARIANT_USER_PROMPT_TEMPLATE` are used by `build_variant_prompt` which is part of the DEAD-05 block. They become unused after DEAD-05 is deleted, not after DEAD-01a. Do NOT remove them in Commit 1.

**Also in generator.py:** Line 518 `include_finish = (...)` — F841 (assigned but never used). Can be removed in Commit 1 as part of cleanup (it's in `generate_per_platform`, not related to feature flag).

**Zero-caller verification:**
```bash
grep -rn "_payload_value_lengths\|_schema_hash\|_prompt_hash\b\|_generate_with_provider_compat" src/ tests/ | grep -v ".pyc" | grep -v "generator.py"
# Expected: 0 results (tests/test_hybrid_generation_parity.py patches hybrid_generation._generate_with_provider_compat — a DIFFERENT function in a different module)
```

Note on test_hybrid_generation_parity.py: Lines 167-168 and 262-263 monkeypatch `hybrid_generation._generate_with_provider_compat` — this patches the copy in `src/feedops/generation/hybrid_generation.py`, NOT the dead copy in generator.py. Safe to delete generator.py's copy.

### Commit 2: DEAD-01b — finish_processing.py re-export removal

**File:** `src/feedops/api/finish_processing.py`

Delete line **7**:
```python
from feedops.api.generation_telemetry import provider_label as _provider_label  # noqa: F401 — re-exported for callers
```

**Zero-caller verification:**
```bash
grep -rn "from feedops.api.finish_processing import.*_provider_label\|from feedops.api.finish_processing import.*provider_label" src/ tests/
# Expected: 0 results
```

Callers of `_provider_label` (generation.py:23, job_runner.py:23) already import directly from `feedops.api.generation_telemetry`. The re-export in finish_processing.py is vestigial.

### Commit 3: DEAD-01c — generation.py re-export block removal (lines 26-30)

**File:** `src/feedops/api/generation.py`

Delete lines **26-30**:
```python
from feedops.api.finish_processing import (  # noqa: F401 - used in type hints / external callers
    _build_finish_sentences_user_prompt,
    _validate_finish_sentences_payload,
    _enforce_finish_sentence_parity,
)
```

**Zero-caller verification:**
```bash
grep -rn "from feedops.api.generation import.*_build_finish\|from feedops.api.generation import.*_validate_finish\|from feedops.api.generation import.*_enforce_finish" src/ tests/
# Expected: 0 results
```

Callers of these symbols:
- `main.py` (lines 299-303): imports DIRECTLY from `finish_processing`, not from `generation`
- `routes.py` (lines 122-125): imports DIRECTLY from `finish_processing`, not from `generation`
- `tests/api/test_finish_processing.py`: imports DIRECTLY from `finish_processing`

The generation.py block was a re-export that no callers actually used as a re-export path.

**Also in generation.py:** Line 44 has `get_request_id` unused import (pre-existing F401). Can combine into this commit.

### Commit 4: DEAD-05 — FEEDOPS_VARIANT_AT_LLM_TIME full removal

This is the largest change. Spans 3 files.

**File 1: `src/feedops/pipeline/generator.py`**

Delete the entire block from line **741** to line **936** (end of file):
- Section comment block (lines 741-747)
- `_variant_generation_enabled()` function (lines 750-755)
- `build_variant_prompt()` function (lines 758-824)
- `generate_variant_candidate()` async function (lines 827-891)
- `generate_variant_candidates_batch()` async function (lines 894-936)

After deleting these, also remove from the imports block:
- `FINISH_CONTEXT_TEMPLATE` (line 53) — used only by `build_variant_prompt`
- `VARIANT_USER_PROMPT_TEMPLATE` (line 56) — used only by `build_variant_prompt`

File shrinks from 936 lines to approximately 438 lines (~53% reduction).

**File 2: `src/feedops/pipeline/reporter.py`**

Three cleanup sites:

1. Lines **32-41**: Delete `_variant_at_llm_time_enabled()` function entirely

2. Lines **815-818** (docstring): Remove the `variant_candidate` parameter docstring line that references `FEEDOPS_VARIANT_AT_LLM_TIME`:
   ```
   variant_candidate: Optional pre-generated candidate with finish-integrated
       content. When provided and FEEDOPS_VARIANT_AT_LLM_TIME is enabled,
       uses this instead of post-processing via generate_variant_description().
   ```
   Keep the `variant_candidate: Candidate | None = None` parameter — it becomes unused but must be handled. Actually: since `_variant_at_llm_time_enabled()` is deleted, the entire `use_llm_variant` logic block (lines 862-875) is deleted. This means `variant_candidate` parameter becomes unused. Remove it from the function signature too.

3. Lines **862-875**: Delete the `use_llm_variant` block:
   ```python
   # Check if we should use pre-generated variant content (LLM-at-variant-time)
   use_llm_variant = _variant_at_llm_time_enabled() and variant_candidate is not None

   if use_llm_variant:
       # Use pre-generated content with naturally integrated finish
       ...
   else:
       # Fallback: Use post-processing via finish_injection
       variant_title = ...
       variant_description = ...
   ```
   After removing `if use_llm_variant: ... else:`, dedent the `else` block body so it becomes the direct code path (no conditional).

**File 3: `src/feedops/pipeline/finish_injection.py`**

Three reference sites:
1. Lines **9-25** (module docstring): Remove the "DEPRECATION NOTICE" paragraph referencing `FEEDOPS_VARIANT_AT_LLM_TIME=1` and the "DEPRECATED FUNCTIONS" list
2. Lines **615-620** (function docstring inside `generate_variant_description`): Remove the `.. deprecated::` directive paragraph that says "Use generator.generate_variant_candidate() with FEEDOPS_VARIANT_AT_LLM_TIME=1"
3. Lines **641-644** (debug log inside `generate_variant_description`): Remove the `logging.debug(...)` call mentioning `FEEDOPS_VARIANT_AT_LLM_TIME=1`

**CRITICAL: Test changes required for DEAD-05 commit**

`tests/test_pipeline.py` lines **10-16** import `build_variant_prompt`, and tests at lines **846-887** test it:
- `test_build_variant_prompt_uses_canonical_prompt_loader` (line 846)
- `test_build_variant_prompt_includes_gold_examples_when_available` (line 878)

These 2 tests must be deleted in the SAME commit as the DEAD-05 code deletion. The import at line 13 (`build_variant_prompt,`) must also be removed. This contradicts the CONTEXT statement "No test changes required" — surfaced here as a planning decision. The planner should resolve this by including these 2 test deletions in the DEAD-05 commit.

---

## Common Pitfalls

### Pitfall 1: Deleting the LIVE `else` branch in reporter.py
**What goes wrong:** The `if use_llm_variant: ... else:` structure has a LIVE else branch (lines 876-897) that runs post-processing via `generate_variant_description`. Deleting too much removes production functionality.
**How to avoid:** Only delete lines 862-875 (the `if use_llm_variant:` block and its body). Convert the `else:` into flat code by dedenting.

### Pitfall 2: Conflating hybrid_generation._generate_with_provider_compat with generator._generate_with_provider_compat
**What goes wrong:** `tests/test_hybrid_generation_parity.py` patches `_generate_with_provider_compat` on `hybrid_generation` module. You might think the function in generator.py has a live caller.
**How to avoid:** The patches target `feedops.generation.hybrid_generation._generate_with_provider_compat` (a separate copy in a different module), not `feedops.pipeline.generator._generate_with_provider_compat`. The generator.py copy is truly zero-caller.

### Pitfall 3: Pre-existing test failure treated as regression
**What goes wrong:** `tests/test_cli.py::test_optimize_pipeline_integration` was already failing before Phase 9 begins. If this test is seen as failing after a commit, it could be mistakenly blamed on the deletion.
**How to avoid:** Note at the start of the phase that this test was already failing. Only treat new failures as regressions.

### Pitfall 4: Missing the `variant_candidate` parameter cleanup in reporter.py
**What goes wrong:** `generate_variant_patch_preview()` accepts `variant_candidate: Candidate | None = None`. After deleting `_variant_at_llm_time_enabled()` and the `if use_llm_variant` block, the parameter is unused. If left in, ruff may not flag it (it's a parameter, not a local var), but callers passing it get silently-ignored data.
**How to avoid:** Remove `variant_candidate` from the function signature in the same commit as the DEAD-05 deletion. Check if any callers pass this argument:
```bash
grep -rn "variant_candidate" src/ tests/ | grep -v ".pyc"
```

### Pitfall 5: Not removing module-level `os` import from reporter.py after deletion
**What goes wrong:** `_variant_at_llm_time_enabled()` uses `os.getenv()`. After removing the function, `os` may be unused.
**How to avoid:** Run ruff on reporter.py after the deletion to catch any newly-orphaned imports.

---

## Code Examples

### Pattern: Removing an if/else where only the else branch is live

Before (reporter.py lines 862-897):
```python
# Check if we should use pre-generated variant content (LLM-at-variant-time)
use_llm_variant = _variant_at_llm_time_enabled() and variant_candidate is not None

if use_llm_variant:
    # Use pre-generated content with naturally integrated finish
    if platform == "google":
        variant_title = _normalize_title_separators(variant_candidate.google_title)
        variant_description = variant_candidate.google_description
    elif platform == "bing":
        variant_title = _normalize_title_separators(variant_candidate.bing_title)
        variant_description = variant_candidate.bing_description
    else:  # shopify
        variant_title = _normalize_title_separators(variant_candidate.shopify_title)
        variant_description = variant_candidate.shopify_description
else:
    # Fallback: Use post-processing via finish_injection
    variant_title = _normalize_title_separators(
        generate_variant_title(...)
    )
    variant_description = generate_variant_description(...)
```

After (dead `if` removed, `else` body promoted to direct code):
```python
# Use post-processing via finish_injection
variant_title = _normalize_title_separators(
    generate_variant_title(...)
)
variant_description = generate_variant_description(...)
```

### Pattern: Removing a re-export line with noqa comment

Before (finish_processing.py line 7):
```python
from feedops.api.generation_telemetry import provider_label as _provider_label  # noqa: F401 — re-exported for callers
```

After: Delete the entire line. Callers already import from `generation_telemetry` directly.

### Pattern: Removing a re-export block with noqa comment

Before (generation.py lines 26-30):
```python
from feedops.api.finish_processing import (  # noqa: F401 - used in type hints / external callers
    _build_finish_sentences_user_prompt,
    _validate_finish_sentences_payload,
    _enforce_finish_sentence_parity,
)
```

After: Delete all 5 lines. Callers (`main.py`, `routes.py`) import directly from `finish_processing`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (installed in `.venv`) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]`, testpaths=["tests"], asyncio_mode="auto" |
| Quick run command | `.venv/bin/pytest tests/test_pipeline.py tests/test_hybrid_generation_parity.py -q --tb=short` |
| Full suite command | `.venv/bin/pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Notes |
|--------|----------|-----------|-------------------|-------|
| DEAD-01 | Orphan functions removed from generator.py | import smoke | `.venv/bin/pytest tests/test_pipeline.py -q --tb=short` | Existing suite tests the live functions remain intact |
| DEAD-01 | `_provider_label` re-export gone from finish_processing | import smoke | `.venv/bin/pytest tests/api/test_finish_processing.py -q --tb=short` | Confirms finish_processing still importable without the re-export |
| DEAD-01 | Finish processing re-exports gone from generation.py | import smoke | `.venv/bin/pytest tests/api/test_generation.py -q --tb=short` | Confirms generation.py still importable |
| DEAD-05 | Variant generation block gone from generator.py | manual-confirm | `grep -c "FEEDOPS_VARIANT_AT_LLM_TIME" src/feedops/pipeline/generator.py` → must be 0 | Structural check |
| DEAD-05 | All FEEDOPS_VARIANT_AT_LLM_TIME refs gone | manual-confirm | `grep -rn "FEEDOPS_VARIANT_AT_LLM_TIME" src/` → must be 0 | Clean removal verification |
| DEAD-01 + DEAD-05 | ruff passes on target files | lint | `.venv/bin/ruff check src/feedops/pipeline/generator.py src/feedops/api/finish_processing.py src/feedops/api/generation.py src/feedops/pipeline/reporter.py src/feedops/pipeline/finish_injection.py` | Must return 0 errors |

### Sampling Rate
- **Per commit:** `.venv/bin/pytest tests/ -q --tb=short` (full suite ~37 seconds — fast enough to run after every commit)
- **Phase gate:** Full suite green (minus the 1 pre-existing failure in `test_cli.py`) before moving to Phase 10

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements. No new test files needed.

---

## Open Questions

1. **test_pipeline.py `build_variant_prompt` tests**
   - What we know: 2 tests (`test_build_variant_prompt_uses_canonical_prompt_loader`, `test_build_variant_prompt_includes_gold_examples_when_available`) directly import and call `build_variant_prompt`
   - What's unclear: CONTEXT.md says "No test changes required" but these tests test dead code — deleting the functions breaks these tests
   - Recommendation: Include deletion of these 2 tests (and the import at line 13) in the DEAD-05 commit. They are tests of dead code, not tests of live behavior. This is consistent with the spirit of "no test changes required for the live test suite."

2. **`variant_candidate` parameter in `generate_variant_patch_preview`**
   - What we know: Parameter is `Candidate | None = None`, used only by the dead `if use_llm_variant` branch
   - What's unclear: Are any callers passing `variant_candidate=...` to this function?
   - Recommendation: Run `grep -rn "variant_candidate" src/ tests/` before the DEAD-05 commit. If no callers pass it, remove from signature in same commit.

3. **`os` import in reporter.py post-deletion**
   - What we know: `_variant_at_llm_time_enabled()` uses `os.getenv()`; `_gmc_structured_only_enabled()` also uses `os.getenv()` (line 53)
   - What's unclear: Whether `os` stays needed after removing `_variant_at_llm_time_enabled`
   - Recommendation: `_gmc_structured_only_enabled()` at line 53 also uses `os.getenv()` — `os` import stays. No action needed.

---

## Sources

### Primary (HIGH confidence)
- Direct source inspection of `src/feedops/pipeline/generator.py` (936 lines) — confirmed exact line numbers for all 4 DEAD-01 functions and entire DEAD-05 block
- Direct source inspection of `src/feedops/api/finish_processing.py` — confirmed re-export at line 7
- Direct source inspection of `src/feedops/api/generation.py` — confirmed re-export block at lines 26-30
- Direct source inspection of `src/feedops/pipeline/reporter.py` — confirmed DEAD-05 impact sites at lines 32-41, 863-875
- Direct source inspection of `src/feedops/pipeline/finish_injection.py` — confirmed 3 docstring/debug references
- grep-based caller analysis across `src/` and `tests/` — confirmed zero-caller status for all DEAD-01 targets
- `ruff check` run — confirmed 13 existing violations on target files, 12 auto-fixable

### Secondary (MEDIUM confidence)
- `.venv/bin/pytest tests/ -q` run — confirmed baseline: 1 pre-existing failure (test_cli), 788 passing, 1 skipped

---

## Metadata

**Confidence breakdown:**
- Deletion targets: HIGH — all verified by direct source inspection with exact line numbers
- Zero-caller status: HIGH — verified by grep across all src/ and tests/
- Test impact: HIGH — test_pipeline.py import and test functions confirmed by direct file read
- Import cleanup: HIGH — ruff baseline run confirms which imports are newly orphaned vs pre-existing

**Research date:** 2026-03-04
**Valid until:** Stable — no external dependencies, pure code archaeology
