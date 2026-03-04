# Phase 11: Test-Import Cleanup and Re-export Removal - Research

**Researched:** 2026-03-04
**Domain:** Python test refactoring — import migration, backward-compat re-export removal, dead code cleanup
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Test migration ordering:**
- Migrate test files one at a time with `pytest` + `ruff` verification after each commit
- Start with a smaller file to validate the approach, then tackle the heavy alias runtime test (42 refs)
- Order: `test_finish_prompt_source_contract.py` (4 refs) → `test_generation_runtime_scope_contract.py` (8 refs) → `test_phase7_observability_reliability.py` (21 refs) → `test_main_master_sku_alias_runtime.py` (42 refs)
- For monkeypatching: patch where the code under test resolves the symbol at runtime — as imports move to canonical modules, update patches to canonical when applicable, but keep `api_main.*` patches if that remains the lookup point

**Re-export block removal:**
- After all test imports are migrated, remove the entire re-export block in a single commit
- `feedops.api.main` must remain importable — smoke tests just do `import feedops.api.main` and must keep passing
- Leave minimal surface if needed (the FastAPI app, middleware, startup — the actual main.py code stays)
- Fallback: if single-commit removal breaks in unexpected ways, remove group-by-group with verification after each group

**generator.py duplicate cleanup:**
- Remove the duplicates that actually exist now: `_platform_reasoning_effort` and `_platform_completion_cap` (both exist in `generator.py` AND `executor.py`)
- Do a verification search for any remaining duplicates between the two files before declaring DEAD-04 complete
- If DEAD-04's original "6 functions" count is outdated, update the requirement note to match current reality
- `generate_per_platform` and `GenerationBudgetExceededError` in generator.py are NOT duplicates

### Claude's Discretion
- Exact ordering of individual import rewrites within each test file
- Whether to combine the generator.py duplicate removal with a test migration commit or keep it separate
- How to handle any docstring references to the re-export pattern in test files

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEAD-02 | Update 5 test files to import from actual extracted module locations instead of main.py re-exports | Full canonical module map built; 4 migration files verified passing; 1 pre-existing file (test_prompt_sanitization_contract.py) already imports directly from canonical module |
| DEAD-03 | Remove ~130-line backward-compat re-export block from main.py after test imports updated | Block is lines 174-304 of main.py (131 lines, 23 import groups); 5 smoke tests confirm main.py importability is the only contract |
| DEAD-04 | Remove generator.py duplicate functions already copied to executor.py | Confirmed: exactly 2 duplicates remain (`_platform_reasoning_effort` line 75, `_platform_completion_cap` line 82); test_prompt_sanitization_contract.py imports them from generator.py — that test also needs updating |
</phase_requirements>

---

## Summary

Phase 11 is a pure Python refactoring phase with no logic changes. The work splits into three sequential streams: (1) migrate four test files off `feedops.api.main` re-exports to canonical module imports, (2) delete the 131-line backward-compat re-export block from main.py, and (3) delete two duplicate helper functions from generator.py.

All source of truth for canonical locations has been verified against the live codebase. Every symbol accessed via `api_main.*` in the four migration target files resolves to one of: `feedops.api.routes`, `feedops.api.schemas`, `feedops.api.job_management`, `feedops.api.persistence`, `feedops.api.prompt_loader`, `feedops.api.telemetry`, `feedops.api.runtime_controls`, `feedops.api.sku_alias`, `feedops.api.finish_processing`, `feedops.pipeline.generator`, `feedops.db.supabase_client`, or `feedops.observability`. `fastapi.HTTPException` is used in tests via `api_main.HTTPException` but is NOT in the re-export block — it is an import on line 39 of main.py that stays (it is used elsewhere in main.py's actual code). Tests using `api_main.HTTPException` should switch to `from fastapi import HTTPException` directly.

One critical discovery: `test_prompt_sanitization_contract.py` (not in the four-file DEAD-02 list) already imports `_platform_reasoning_effort` and `_platform_completion_cap` directly from `feedops.pipeline.generator`. When DEAD-04 removes these from generator.py, that test must be updated to import from `feedops.generation.executor` instead.

**Primary recommendation:** Work in strict sequence — migrate the four test files first, then delete the re-export block, then delete the two generator.py duplicate functions (updating test_prompt_sanitization_contract.py in that same commit).

---

## Standard Stack

### Core Tools
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| pytest | 9.0.2 (in use) | Test runner for verification after each commit | Already configured; all tests use it |
| ruff | in use | Linting + import unused detection | Project-standard linter; noqa annotations need removal with re-exports |

### Established Project Patterns
| Pattern | Location | Notes |
|---------|----------|-------|
| Atomic commits with green tests | Phases 8/9 precedent | One file per commit, pytest + ruff after each |
| `# noqa: F401` on re-exports | main.py lines 184-304 | Must be removed together with the import lines |
| PYTHONPATH=./src test invocation | Makefile/dev docs | Required for all test runs in this project |

---

## Architecture Patterns

### DEAD-02: Test Import Migration

Each test file currently does:
```python
import feedops.api.main as api_main
# then accesses: api_main.get_finish_list(), api_main.RegenerateRequest, etc.
```

After migration, the test should import each symbol from its canonical home directly, while still aliasing `feedops.api.main` for `api_main.*` calls that patch at the `api_main` namespace (route handler monkeypatching).

**Critical nuance for monkeypatching:** `monkeypatch.setattr(api_main, "get_request_id", ...)` patches the name in the `feedops.api.main` namespace. After removing re-exports, `api_main.get_request_id` will no longer exist. Those patches need to move to the module that actually executes the lookup — e.g., if `regenerate_content` in `routes.py` calls `get_request_id`, the patch must be `monkeypatch.setattr(api_routes, "get_request_id", ...)`.

### DEAD-03: Re-export Block Deletion

The block is lines 174-304 of main.py (131 lines). After deletion:
- main.py shrinks from 304 to ~173 lines (well under the 500-line guard in `test_main_line_count.py`)
- The `HTTPException` import on line 39 is NOT part of the re-export block; ruff currently flags it as F401 (`imported but unused` after re-exports are gone) — must either remove it from line 39 or confirm it is used elsewhere in actual main.py code
- The 5 smoke tests (`test_telemetry_smoke.py`, `test_persistence_smoke.py`, `test_schemas_smoke.py`, `test_job_runner_smoke.py`, `test_job_management_smoke.py`) just execute `import feedops.api.main` — they will keep passing as long as the file is importable

### DEAD-04: Generator.py Duplicate Removal

Exactly 2 functions are confirmed duplicate (verified by grep against both files):

| Function | generator.py line | executor.py line | Callers in generator.py |
|----------|-------------------|------------------|------------------------|
| `_platform_reasoning_effort` | 75 | 74 | None (not called internally) |
| `_platform_completion_cap` | 82 | 80 | None (not called internally) |

`test_prompt_sanitization_contract.py` imports both functions from `feedops.pipeline.generator` (line 11-15). When the generator.py copies are deleted, that test's import line must change to `from feedops.generation.executor import _platform_completion_cap, _platform_reasoning_effort`.

---

## Canonical Module Map (Complete)

This is the verified truth for every `api_main.*` symbol used across the 4 migration target files:

| Symbol | Canonical Module |
|--------|----------------|
| `get_finish_list` | `feedops.api.prompt_loader` |
| `get_platform_system_prompt_hash` | `feedops.api.prompt_loader` |
| `_enforce_finish_sentence_parity` | `feedops.api.finish_processing` |
| `_assembled_prompt_hash` | `feedops.api.persistence` |
| `_enforce_write_time_finish_placeholder_contract` | `feedops.api.persistence` |
| `_emit_generation_summary` | `feedops.api.telemetry` |
| `get_request_id` | `feedops.observability` |
| `regenerate_content` | `feedops.api.routes` |
| `process_regenerate_job` | `feedops.api.routes` |
| `optimize_single_sku` | `feedops.api.routes` |
| `batch_optimize` | `feedops.api.routes` |
| `hybrid_generate` | `feedops.api.routes` |
| `RegenerateRequest` | `feedops.api.schemas` |
| `RegenerateJobResponse` | `feedops.api.schemas` |
| `HybridGenerateRequest` | `feedops.api.schemas` |
| `OptimizeRequest` | `feedops.api.schemas` |
| `BatchOptimizeRequest` | `feedops.api.schemas` |
| `_require_request_id` | `feedops.api.job_management` |
| `_regeneration_idempotency_key` | `feedops.api.job_management` |
| `_hybrid_generation_idempotency_key` | `feedops.api.job_management` |
| `ensure_generation_enabled` | `feedops.api.runtime_controls` |
| `resolve_canonical_master_sku` | `feedops.api.sku_alias` |
| `get_client` | `feedops.db.supabase_client` |
| `generate_per_platform` | `feedops.pipeline.generator` |
| `GenerationBudgetExceededError` | `feedops.pipeline.generator` |
| `HTTPException` | `fastapi` (NOT in re-export block — import directly) |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Verifying no test imports from api_main remain | Custom script | `grep -rn "api_main\." tests/` | Immediate, no dependencies |
| Checking re-export block is fully gone | Line number tracking | `ruff check src/feedops/api/main.py` | F401 on any leftover noqa annotations |
| Verifying generator.py duplicates removed | Manual diff | `grep -n "_platform_reasoning_effort\|_platform_completion_cap" src/feedops/pipeline/generator.py` | Shows line numbers instantly |

---

## Common Pitfalls

### Pitfall 1: Monkeypatch Namespace Confusion
**What goes wrong:** A test patches `api_main.get_request_id` but after re-export removal `api_main.get_request_id` no longer exists — the monkeypatch is silently a no-op or raises `AttributeError`.
**Why it happens:** pytest monkeypatch sets attributes on the specified module object. If the name doesn't exist in that namespace, the patch doesn't intercept the real call.
**How to avoid:** For each `monkeypatch.setattr(api_main, "X", ...)`, determine which module actually executes `X` at call time, and patch there instead. For route handlers (e.g., `regenerate_content` in `api_routes`), the lookup is typically in the `api_generation` or `api_job_runner` modules.
**Warning signs:** Test passes during migration (re-exports still present) but fails after re-export block removal despite seemingly correct canonical imports.

### Pitfall 2: HTTPException Not in Re-export Block
**What goes wrong:** Developer expects removing the re-export block removes `api_main.HTTPException` — but `HTTPException` is on line 39 as a regular import, not in the block.
**Why it happens:** `HTTPException` is imported at line 39 and ruff currently flags it as F401 because nothing in main.py's actual code uses it (it got there to support test access). After re-export removal, it needs to be removed from line 39 too.
**How to avoid:** After removing the re-export block, run `ruff check src/feedops/api/main.py` and remove the flagged `HTTPException` import from line 39. Tests using `api_main.HTTPException` must add `from fastapi import HTTPException` directly.

### Pitfall 3: test_prompt_sanitization_contract.py (Not in DEAD-02 List)
**What goes wrong:** The phase description lists "5 test files" for DEAD-02, but the CONTEXT.md lists 4. Meanwhile `test_prompt_sanitization_contract.py` imports directly from `feedops.pipeline.generator` — it is NOT currently using api_main re-exports, so it is not part of DEAD-02. However DEAD-04 (removing the duplicates from generator.py) will break its imports.
**How to avoid:** When executing DEAD-04, include an update to `test_prompt_sanitization_contract.py` changing its import from `feedops.pipeline.generator` to `feedops.generation.executor` for `_platform_completion_cap` and `_platform_reasoning_effort`.

### Pitfall 4: Smoke Tests Are the Only Contract After Re-export Removal
**What goes wrong:** Assuming that removing the re-export block means main.py no longer needs any imports at all from those modules.
**How to avoid:** The smoke tests only care that `import feedops.api.main` exits 0. As long as main.py's actual code (lifespan, app, middleware, routers) doesn't import anything broken, the smoke tests pass. The re-export block itself has no effect on main.py's functional code.

### Pitfall 5: noqa Comments Left Orphaned
**What goes wrong:** Re-export imports use `# noqa: E402,F401`. After deletion, any missed line is flagged by ruff.
**How to avoid:** The entire block from line 174 to 304 is deleted as a unit. No individual line should be left behind. After deletion, `ruff check` should show zero errors on main.py.

---

## Code Examples

### Typical Import Rewrite Pattern (DEAD-02)

Before (any migration target file):
```python
import feedops.api.main as api_main

# data access
finish_list = api_main.get_finish_list()
req = api_main.RegenerateRequest(...)

# monkeypatching
monkeypatch.setattr(api_main, "get_request_id", lambda: "req-test")
```

After (using canonical modules):
```python
import feedops.api.main as api_main  # retained only if needed for route handler calls
import feedops.api.routes as api_routes
import feedops.api.schemas as api_schemas
from feedops.api.prompt_loader import get_finish_list

# data access — direct import
finish_list = get_finish_list()
req = api_schemas.RegenerateRequest(...)

# monkeypatching — patch at the module that actually resolves the name
# e.g., if regenerate_content (in routes.py) calls get_request_id,
# patch api_routes, not api_main:
monkeypatch.setattr(api_routes, "get_request_id", lambda: "req-test")
```

### Verification Commands After Each Commit

```bash
# Run the specific migrated test file
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_finish_prompt_source_contract.py -q

# Verify linting
.venv/bin/ruff check src/feedops/api/main.py tests/api/test_finish_prompt_source_contract.py

# Full suite sanity (run before and after each DEAD-03 step)
PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q --tb=short

# Confirm smoke tests pass after re-export block removal
PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_telemetry_smoke.py tests/api/test_persistence_smoke.py tests/api/test_schemas_smoke.py tests/api/test_job_runner_smoke.py tests/api/test_job_management_smoke.py -q

# Confirm main.py is importable (python -c check)
PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main; print('OK')"

# Verify no api_main.* refs remain after full DEAD-02 migration
grep -rn "api_main\." tests/ | grep -v "test_generation_runtime_scope_contract\|test_phase7\|test_main_master_sku" || echo "CLEAN"
```

### DEAD-04 Import Update for test_prompt_sanitization_contract.py

Before:
```python
from feedops.pipeline.generator import (
    _platform_completion_cap,
    _platform_reasoning_effort,
    generate_per_platform,
)
```

After:
```python
from feedops.generation.executor import (
    _platform_completion_cap,
    _platform_reasoning_effort,
)
from feedops.pipeline.generator import generate_per_platform
```

---

## Baseline Test State (Verified 2026-03-04)

| Test Suite | Count | Status |
|-----------|-------|--------|
| Full suite | 791 | 790 passed, 1 failed (`test_cli.py::test_optimize_pipeline_integration`) |
| 4 migration target files | 52 | All passing |
| 5 smoke tests | 31 | All passing |
| test_prompt_sanitization_contract.py | 23 | All passing |

The `test_cli.py::test_optimize_pipeline_integration` failure is pre-existing (unrelated to this phase).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/ -q` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEAD-02 | No test imports from `feedops.api.main` for symbol access | unit | `grep -rn "api_main\." tests/` should return empty | ✅ (post-migration) |
| DEAD-03 | Re-export block deleted; main.py remains importable | smoke | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_telemetry_smoke.py tests/api/test_persistence_smoke.py tests/api/test_schemas_smoke.py tests/api/test_job_runner_smoke.py tests/api/test_job_management_smoke.py -q` | ✅ |
| DEAD-04 | No duplicate functions in generator.py vs executor.py | unit | `PYTHONPATH=./src .venv/bin/python -m pytest tests/test_prompt_sanitization_contract.py -q` | ✅ |

### Sampling Rate
- **Per task commit:** Run the specific test file(s) modified + smoke tests
- **Per wave merge:** Full suite: `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q --tb=short`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — existing test infrastructure covers all phase requirements.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/feedops/api/main.py` lines 174-304 (re-export block), line 39 (HTTPException import)
- Direct code inspection: `src/feedops/pipeline/generator.py` lines 75-119 (duplicate functions)
- Direct code inspection: `src/feedops/generation/executor.py` lines 74-109 (canonical function location)
- Live test execution: `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -q` — 790 passed baseline confirmed
- Python introspection: `getattr(feedops.api.main, sym).__module__` for all 25 symbols — verified canonical module for each

### Secondary (MEDIUM confidence)
- pytest monkeypatch documentation: patching semantics (patch at the module that imports the name, not the module where it's defined)
- ruff F401 behavior on `# noqa: F401` — standard Python linting behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — tools (pytest, ruff) are in active use in the project
- Architecture: HIGH — all canonical module locations verified via live Python introspection
- Pitfalls: HIGH — HTTPException and test_prompt_sanitization_contract.py traps discovered via direct code inspection, not inference

**Research date:** 2026-03-04
**Valid until:** Indefinite (code state is stable; these are exact file/line references)
