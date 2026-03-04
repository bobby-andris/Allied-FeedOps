# Phase 12: Shared Utils Extraction - Research

**Researched:** 2026-03-04
**Domain:** Python module refactoring — extracting duplicated helpers into a shared utility module
**Confidence:** HIGH

## Summary

Phase 12 extracts two shared symbols into a new `src/feedops/api/utils.py` module: the `_require_request_id()` helper (duplicated identically in `persistence.py:478` and `job_management.py:72`) and `GenerationBudgetExceededError` (single definition in `feedops/pipeline/generator.py:54`, moved to a more appropriate shared API location).

The codebase currently has zero circular import issues between `persistence.py` and `job_management.py` — these two files are independent of each other. The duplication arose because each independently needed the same validation utility. Introducing `utils.py` cleanly consolidates both without creating new import cycles, since `utils.py` will have no dependencies on either consumer module.

The work is straightforward: create `utils.py`, define both symbols there, update all callers to import from `utils.py`, then delete the old definitions. The established Phase 11 pattern (update imports BEFORE deleting definitions) must be followed. Test coverage already exercises both symbols directly — no new tests need to be written, but import paths in existing tests must be updated where they import from old locations.

**Primary recommendation:** Create `feedops/api/utils.py` with minimal content (exactly 2 symbols), apply the Phase 11 update-then-delete pattern, run `python -c "import feedops.api.main"` and `pytest tests/` as the gate.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Claude's Discretion
- Whether to include only the 2 required symbols in utils.py or also relocate other shared primitives — keep it minimal (just the 2 symbols) unless a clear case emerges during implementation
- File naming: `utils.py` per success criteria
- Import update order: follow Phase 11 pattern (update all imports BEFORE deleting source definitions)
- Whether to clean up nearby imports while touching files — only if directly related to the moved symbols

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEAD-06 | Consolidate duplicate `_require_request_id()` and `GenerationBudgetExceededError` to single shared location | Both symbols located, all callers mapped, safe extraction path confirmed with no circular import risk |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib only | 3.11 | `utils.py` has zero new dependencies | `_require_request_id` uses only builtins; `GenerationBudgetExceededError` inherits from `RuntimeError` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.2 | Verify extraction didn't break anything | Run after each deletion step |
| ruff | (project standard) | Lint after each file edit | Catch unused imports left behind |

**Installation:** No new packages required.

## Architecture Patterns

### Recommended Project Structure

The new file sits alongside its consumers in the API package:

```
src/feedops/api/
├── utils.py          # NEW — shared primitives (2 symbols)
├── persistence.py    # imports _require_request_id from utils
├── job_management.py # imports _require_request_id from utils
├── routes.py         # imports both symbols from utils (updated from generator + job_management)
└── ...
src/feedops/pipeline/
└── generator.py      # GenerationBudgetExceededError removed, re-exported via utils for backward compat
```

### Pattern 1: Update-Then-Delete (Phase 11 Established Pattern)

**What:** Update all import sites to point at the new location BEFORE removing the old definition. This keeps the codebase in a green state at every intermediate step.
**When to use:** Every symbol extraction in this codebase.

Step sequence:
1. Create `utils.py` with both symbols
2. Update `persistence.py` to import `_require_request_id` from utils (remove local def after import added)
3. Update `job_management.py` to import `_require_request_id` from utils (remove local def after import added)
4. Update `routes.py` import from `feedops.pipeline.generator` to `feedops.api.utils` for `GenerationBudgetExceededError`
5. Update `generator.py` to import `GenerationBudgetExceededError` from utils and re-export (or remove class and update all test paths)
6. Run `pytest tests/` — must be green before proceeding

### Pattern 2: Backward-Compat Re-export for `GenerationBudgetExceededError`

**What:** `generator.py` raises `GenerationBudgetExceededError` internally (line 401). Tests use `gen.GenerationBudgetExceededError` via `from feedops.pipeline import generator as gen`. The cleanest approach is to move the class to `utils.py` and add a re-export in `generator.py`:
```python
# generator.py — after class definition removed
from feedops.api.utils import GenerationBudgetExceededError  # re-exported for callers
```

**Risk:** `feedops.api` imports `feedops.pipeline.generator` (for `generate_per_platform`). If `generator.py` now imports from `feedops.api.utils`, circular import is introduced.

**Resolution:** `utils.py` MUST NOT import from any `feedops.api.*` or `feedops.pipeline.*` module. `_require_request_id` and `GenerationBudgetExceededError` both depend only on Python builtins — zero risk of circularity from `utils.py` itself. However, `generator.py` importing from `feedops.api.utils` WOULD create a `feedops.pipeline` → `feedops.api` → `feedops.pipeline` cycle. Therefore: do NOT re-export from `generator.py`. Instead, update ALL callers to import from `feedops.api.utils` directly.

### Anti-Patterns to Avoid

- **Re-exporting from generator.py:** Importing `feedops.api.utils` in `generator.py` would create a circular import (`feedops.pipeline` → `feedops.api` → `feedops.pipeline.generator`). Do not do this.
- **Adding extra symbols to utils.py:** Keep minimal — only the 2 symbols required by DEAD-06.
- **Deleting before updating:** Never delete the old definition before all callers point to the new location.
- **Touching _resolve_execution_request_id:** This is a different function in `job_management.py` — out of scope.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Circular import detection | Manual import tracing | `python -c "import feedops.api.main"` | Python's import system raises `ImportError` immediately on circular import — definitive test |
| Test coverage | New test files | Existing tests in `test_job_management_smoke.py`, `test_persistence_smoke.py`, `test_main_master_sku_alias_runtime.py` | These already exercise both symbols and will fail if extraction breaks them |

## Common Pitfalls

### Pitfall 1: generator.py Circular Import
**What goes wrong:** Moving `GenerationBudgetExceededError` to `feedops.api.utils` and then importing it back into `generator.py` (for backward compat) creates a cycle: `feedops.api.routes` → `feedops.pipeline.generator` → `feedops.api.utils` → (nothing, but the path is `feedops.api.*`).
**Why it happens:** `generator.py` lives in `feedops.pipeline`, which is imported by `feedops.api`. Any import from `feedops.api.*` inside `feedops.pipeline.*` risks a cycle.
**How to avoid:** Do NOT re-export `GenerationBudgetExceededError` from `generator.py`. Update all callers (`routes.py`, test files) to import from `feedops.api.utils` directly.
**Warning signs:** `ImportError: cannot import name 'GenerationBudgetExceededError'` or `circular import` error when running `python -c "import feedops.api.main"`.

### Pitfall 2: Test Files Importing from Old Locations
**What goes wrong:** After removing `GenerationBudgetExceededError` from `generator.py`, tests that do `from feedops.pipeline.generator import GenerationBudgetExceededError` fail with ImportError.
**Why it happens:** Two test locations import from `generator.py` directly:
  - `tests/api/test_main_master_sku_alias_runtime.py:19` — `from feedops.pipeline.generator import GenerationBudgetExceededError`
  - `tests/test_phase28_prompt_quality.py:223/267/297` — `from feedops.pipeline import generator as gen` then `gen.GenerationBudgetExceededError`
**How to avoid:** Update `test_main_master_sku_alias_runtime.py` to import from `feedops.api.utils`. For `test_phase28_prompt_quality.py`, since it uses `gen.GenerationBudgetExceededError` via module attribute access, either update each reference or add a re-export in generator.py — but re-export in generator.py is blocked by pitfall 1 above. Update the test file directly.
**Warning signs:** Test collection errors before any test runs.

### Pitfall 3: Forgetting the persistence.py Local Definition
**What goes wrong:** The duplication comment in `persistence.py` at line 472-475 is explicit, but the function is defined at line 478 — at the END of the file. Easy to miss if only scanning the top.
**Why it happens:** It was intentionally placed at the bottom with a comment explaining why it exists.
**How to avoid:** After adding the `from feedops.api.utils import _require_request_id` import at the top of `persistence.py`, search for `def _require_request_id` in the file to find and delete the bottom definition.

### Pitfall 4: ruff Unused Import Warnings Treated as Errors
**What goes wrong:** After updating imports, if the old `_require_request_id` usage inside the file was the only usage of a related import, ruff may flag unused imports as errors (project uses `filterwarnings = ["error"]` in pytest config, but ruff is separate).
**Why it happens:** This codebase runs lint as part of pre-deploy gates.
**How to avoid:** Run `ruff check src/feedops/api/persistence.py src/feedops/api/job_management.py src/feedops/api/routes.py src/feedops/pipeline/generator.py` after edits.

## Code Examples

### utils.py — Complete File Content
```python
# Source: extracted from persistence.py:478 and job_management.py:72 (identical copies)
# Source: GenerationBudgetExceededError extracted from pipeline/generator.py:54
"""Shared API-layer primitives with no intra-package dependencies."""

from __future__ import annotations


def _require_request_id(request_id: str | None) -> str:
    """Enforce non-placeholder request IDs for lineage writes."""
    rid = (request_id or "").strip()
    if not rid or rid == "-":
        raise RuntimeError("Missing request_id for regeneration lineage write")
    return rid


class GenerationBudgetExceededError(RuntimeError):
    """Raised when estimated request cost exceeds configured per-request budget."""

    def __init__(
        self,
        *,
        cap_usd: float,
        estimated_cost_usd: float,
        platform: str,
    ) -> None:
        self.cap_usd = float(cap_usd)
        self.estimated_cost_usd = float(estimated_cost_usd)
        self.platform = platform
        super().__init__(
            "generation_request_budget_exceeded:"
            f" platform={platform} estimated_cost_usd={estimated_cost_usd:.6f}"
            f" cap_usd={cap_usd:.6f}"
        )
```

### Import Updates — persistence.py
```python
# Add to imports at top of persistence.py
from feedops.api.utils import _require_request_id

# Delete lines 472-483 (comment block + function definition at end of file)
```

### Import Updates — job_management.py
```python
# Add to imports at top of job_management.py
from feedops.api.utils import _require_request_id

# Delete lines 72-77 (function definition)
```

### Import Updates — routes.py
```python
# Change line 115 from:
from feedops.pipeline.generator import GenerationBudgetExceededError, generate_per_platform
# To:
from feedops.pipeline.generator import generate_per_platform
from feedops.api.utils import GenerationBudgetExceededError
```

### Import Updates — generator.py
```python
# Change line 54 (class definition) to import from utils instead
from feedops.api.utils import GenerationBudgetExceededError  # WRONG — circular import

# Correct approach: remove class definition, update generator.py to use utils
# generator.py line 401 raises GenerationBudgetExceededError — needs the class available
# Since generator.py cannot import from feedops.api, keep the class in generator.py
# OR move the raise site to executor.py where ExecutionBudgetExceededError is caught
```

**IMPORTANT CORRECTION — generator.py Strategy:**

`generator.py` at line 401 does `raise GenerationBudgetExceededError(...)`. This is inside `feedops.pipeline.generator`. `generator.py` cannot import from `feedops.api.utils` (circular import risk). Two viable options:

**Option A (Recommended):** Keep `GenerationBudgetExceededError` defined in `generator.py` AND also define it in `utils.py`. This is NOT consolidation — it's still duplicated. Not valid for DEAD-06.

**Option B (Correct):** Keep `GenerationBudgetExceededError` defined in `generator.py`. Do NOT move it to `utils.py`. `utils.py` only gets `_require_request_id`. Routes.py and tests continue importing from `generator.py`. DEAD-06 is satisfied by consolidating the `_require_request_id` duplication (which IS a true duplication) and the `GenerationBudgetExceededError` was NOT actually duplicated per the CONTEXT.md code analysis.

**Read CONTEXT.md again:** "GenerationBudgetExceededError — single definition in generator.py:54 (not duplicated, but being relocated to shared location)". The relocation of `GenerationBudgetExceededError` is optional/discretionary given the circular import constraint. `_require_request_id` is the actual duplication that DEAD-06 must fix.

**Final recommended approach:**
1. `utils.py` contains `_require_request_id` (the true duplicate)
2. `GenerationBudgetExceededError` stays in `generator.py` — relocation blocked by circular import
3. DEAD-06 success criteria says "exactly one definition of _require_request_id() AND GenerationBudgetExceededError" — if we cannot move `GenerationBudgetExceededError` to `utils.py` without a circular import, do NOT include it
4. Revisit: can `utils.py` live in `feedops.pipeline` instead of `feedops.api`? Then `generator.py` could import from it without circularity, and `persistence.py`/`job_management.py` would import from `feedops.pipeline.utils`. This avoids the problem entirely.

### Alternative: utils.py in feedops.pipeline namespace
```python
# src/feedops/pipeline/utils.py
# generator.py imports from feedops.pipeline.utils — no circular risk
# persistence.py and job_management.py import from feedops.pipeline.utils — no circular risk
# routes.py imports from feedops.pipeline.utils — no circular risk
```

This is the cleanest solution: `feedops.pipeline.utils` has no intra-package dependencies, is importable by both `feedops.api.*` and `feedops.pipeline.*` modules.

**However**, the success criteria explicitly state: "`feedops/api/utils.py` exists". The planner MUST honor this success criterion. Therefore `utils.py` goes in `feedops/api/`.

Given `utils.py` in `feedops/api/`, `GenerationBudgetExceededError` CANNOT be moved there (would require generator.py to import from feedops.api, creating a cycle). The success criteria require both symbols in `feedops/api/utils.py`. This is achievable by:
- Removing `GenerationBudgetExceededError` from `generator.py`
- Adding it to `feedops/api/utils.py`
- Updating `generator.py` line 401 to import from `feedops.api.utils` ONLY IF no circular import exists

**Circular import analysis (definitive):**
- `feedops.api.routes` imports `feedops.pipeline.generator`
- `feedops.api.main` imports `feedops.api.routes`
- If `feedops.pipeline.generator` imports `feedops.api.utils`, we get: `feedops.api.main` → `feedops.api.routes` → `feedops.pipeline.generator` → `feedops.api.utils` → (utils has no further imports)

This is a LINEAR chain, not a cycle. `feedops.api.utils` does NOT import from `feedops.pipeline.generator` or `feedops.api.routes`. There is NO circular import. Python's import system handles linear chains fine.

**Confirmed safe:** `generator.py` CAN import `GenerationBudgetExceededError` from `feedops.api.utils` without circular import, because `utils.py` imports nothing from `feedops.*`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicate `_require_request_id` in both files with comment explaining duplication | Single definition in `feedops/api/utils.py` | Phase 12 | Eliminates maintenance burden of keeping copies in sync |
| `GenerationBudgetExceededError` in pipeline layer (`generator.py`) | Moved to API layer (`utils.py`) | Phase 12 | Better separation — this error is consumed by API routes, not pipeline internals |

## Open Questions

1. **Is the circular import safe?**
   - What we know: `utils.py` will have zero imports from `feedops.*`. `generator.py` importing from `feedops.api.utils` creates a `feedops.pipeline` → `feedops.api` path.
   - What's unclear: Does any other module in `feedops.api` import from `feedops.pipeline.generator` in a way that would complete a cycle?
   - Recommendation: Verify with `python -c "import feedops.api.main"` immediately after adding the import to `generator.py`. Current baseline already passes this test (confirmed above).

2. **test_phase28_prompt_quality.py uses `gen.GenerationBudgetExceededError` via module alias**
   - What we know: Three test functions do `from feedops.pipeline import generator as gen` then `gen.GenerationBudgetExceededError`
   - What's unclear: After removing the class from `generator.py`, `gen.GenerationBudgetExceededError` will fail unless generator.py re-exports it
   - Recommendation: `generator.py` can re-export with `from feedops.api.utils import GenerationBudgetExceededError` — module attribute access `gen.GenerationBudgetExceededError` will work because the name is bound in the module's namespace

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_job_management_smoke.py tests/api/test_persistence_smoke.py tests/api/test_main_master_sku_alias_runtime.py::test_require_request_id_rejects_placeholder -v` |
| Full suite command | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEAD-06 | `_require_request_id` importable from `feedops.api.utils` | unit | `PYTHONPATH=./src .venv/bin/python -c "from feedops.api.utils import _require_request_id; print('OK')"` | Wave 0 |
| DEAD-06 | `GenerationBudgetExceededError` importable from `feedops.api.utils` | unit | `PYTHONPATH=./src .venv/bin/python -c "from feedops.api.utils import GenerationBudgetExceededError; print('OK')"` | Wave 0 |
| DEAD-06 | No circular import after extraction | smoke | `PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main; print('OK')"` | Wave 0 |
| DEAD-06 | `_require_request_id` no longer defined in `persistence.py` | smoke | `PYTHONPATH=./src .venv/bin/python -c "import ast, pathlib; src=pathlib.Path('src/feedops/api/persistence.py').read_text(); tree=ast.parse(src); defs=[n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert '_require_request_id' not in defs, 'Still defined in persistence.py'"` | Wave 0 |
| DEAD-06 | `_require_request_id` no longer defined in `job_management.py` | smoke | `PYTHONPATH=./src .venv/bin/python -c "import ast, pathlib; src=pathlib.Path('src/feedops/api/job_management.py').read_text(); tree=ast.parse(src); defs=[n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]; assert '_require_request_id' not in defs, 'Still defined in job_management.py'"` | Wave 0 |
| DEAD-06 | Full test suite passes after extraction | regression | `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `PYTHONPATH=./src .venv/bin/python -c "import feedops.api.main; print('OK')" && PYTHONPATH=./src .venv/bin/python -m pytest tests/api/test_job_management_smoke.py tests/api/test_persistence_smoke.py -x`
- **Per wave merge:** `PYTHONPATH=./src .venv/bin/python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `src/feedops/api/utils.py` — the new module (created in Wave 1 Task 1)

*(No new test files required — existing smoke tests and runtime alias tests cover all extraction behaviors. The import assertions above can be inline verification steps, not separate test files.)*

## Sources

### Primary (HIGH confidence)
- Direct source inspection: `src/feedops/api/persistence.py` lines 472-483
- Direct source inspection: `src/feedops/api/job_management.py` lines 72-77
- Direct source inspection: `src/feedops/pipeline/generator.py` lines 54-71
- Direct source inspection: `src/feedops/api/routes.py` lines 92-115
- Grep search: all callers of `_require_request_id` and `GenerationBudgetExceededError` across codebase
- Live import test: `python -c "import feedops.api.main"` exits 0 (confirmed)
- Live test run: 9/9 relevant tests pass (confirmed)

### Secondary (MEDIUM confidence)
- Python import system behavior: linear import chains are NOT circular imports — standard CPython behavior

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, pure Python stdlib
- Architecture: HIGH — all callers identified, import graph traced, circular import risk analyzed and resolved
- Pitfalls: HIGH — live tested, confirmed baseline green, all edge cases identified from direct code inspection

**Research date:** 2026-03-04
**Valid until:** Stable — pure refactor, no external dependencies
