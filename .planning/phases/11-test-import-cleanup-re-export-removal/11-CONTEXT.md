# Phase 11: Test-Import Cleanup and Re-export Removal - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Update test files to import from canonical module locations instead of via main.py re-exports (DEAD-02), then delete the ~130-line backward-compat re-export block from main.py (DEAD-03), and remove duplicated functions from generator.py that already exist in executor.py (DEAD-04). Tests and linting must stay green throughout.

</domain>

<decisions>
## Implementation Decisions

### Test migration ordering
- Migrate test files one at a time with `pytest` + `ruff` verification after each commit
- Start with a smaller file to validate the approach, then tackle the heavy alias runtime test (42 refs)
- Suggested order: `test_finish_prompt_source_contract.py` (4 refs) → `test_generation_runtime_scope_contract.py` (8 refs) → `test_phase7_observability_reliability.py` (21 refs) → `test_main_master_sku_alias_runtime.py` (42 refs)
- For monkeypatching: patch where the code under test resolves the symbol at runtime — as imports move to canonical modules, update patches to canonical when applicable, but keep `api_main.*` patches if that remains the lookup point

### Re-export block removal
- After all test imports are migrated, remove the entire re-export block in a single commit
- `feedops.api.main` must remain importable — smoke tests (`test_telemetry_smoke.py`, `test_persistence_smoke.py`, `test_schemas_smoke.py`, `test_job_runner_smoke.py`, `test_job_management_smoke.py`) just do `import feedops.api.main` and must keep passing
- Leave minimal surface if needed (the FastAPI app, middleware, startup — the actual main.py code stays)
- Fallback: if single-commit removal breaks in unexpected ways, remove group-by-group with verification after each group

### generator.py duplicate cleanup
- Remove the duplicates that actually exist now: `_platform_reasoning_effort` and `_platform_completion_cap` (both exist in `generator.py` AND `executor.py`)
- Do a verification search for any remaining duplicates between the two files before declaring DEAD-04 complete
- If DEAD-04's original "6 functions" count is outdated (Phase 9 already removed `_generate_with_provider_compat`, others may have been cleaned up too), update the requirement note to match current reality rather than chasing the original count
- `generate_per_platform` and `GenerationBudgetExceededError` in generator.py are NOT duplicates — they are canonical and imported by routes.py, generation.py, job_runner.py, and optimize.py

### Claude's Discretion
- Exact ordering of individual import rewrites within each test file
- Whether to combine the generator.py duplicate removal with a test migration commit or keep it separate
- How to handle any docstring references to the re-export pattern in test files

</decisions>

<code_context>
## Existing Code Insights

### Test Files Requiring Migration (DEAD-02)
- `tests/api/test_finish_prompt_source_contract.py` — 4 `api_main.*` refs (imports: `get_finish_list`, `_enforce_finish_sentence_parity`, `_assembled_prompt_hash`)
- `tests/test_generation_runtime_scope_contract.py` — 8 `api_main.*` refs
- `tests/test_phase7_observability_reliability.py` — 21 `api_main.*` refs
- `tests/api/test_main_master_sku_alias_runtime.py` — 42 `api_main.*` refs (schemas, route handlers, persistence, job management, hybrid generation)

### Smoke Tests (import-only, no api_main.* usage)
- `tests/api/test_telemetry_smoke.py`, `test_persistence_smoke.py`, `test_schemas_smoke.py`, `test_job_runner_smoke.py`, `test_job_management_smoke.py`
- These just assert `import feedops.api.main` succeeds — they'll keep working as long as main.py is importable

### Re-export Block (DEAD-03)
- main.py lines 174-305: imports from 15+ modules (routes, schemas, prompt_loader, supabase_loader, generation_telemetry, supabase_client, evidence, prompt_builder, providers, multi_sku_detection, telemetry, persistence, job_management, hybrid_generation, job_runner, sku_alias, runtime_controls, feature_flags, generator, observability, generation, finish_processing, intent_scoring)

### generator.py Duplicates (DEAD-04)
- `_platform_reasoning_effort` — generator.py:75 AND executor.py:74 (identical)
- `_platform_completion_cap` — generator.py:82 AND executor.py:80 (identical)
- `_generate_with_provider_compat` — already removed from generator.py in Phase 9

### Canonical Imports (NOT duplicates)
- `generator.py:generate_per_platform` — imported by routes.py, generation.py, job_runner.py, optimize.py
- `generator.py:GenerationBudgetExceededError` — imported by routes.py, main.py re-export

### Established Patterns
- Atomic commits with `pytest` + `ruff` after each (from Phase 8/9)
- Re-exports use `# noqa: F401` — removal includes removing noqa annotations

### Integration Points
- Removing re-exports from main.py may affect any external code that imports via `feedops.api.main.*` — but production code doesn't do this, only tests do

</code_context>

<specifics>
## Specific Ideas

No specific requirements — the success criteria are explicit import migrations, block deletion, and duplicate removal with green tests throughout.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-test-import-cleanup-re-export-removal*
*Context gathered: 2026-03-04*
