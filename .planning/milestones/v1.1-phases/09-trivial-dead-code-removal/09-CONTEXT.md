# Phase 9: Trivial Dead Code Removal - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Delete all zero-caller orphan functions (DEAD-01) and the never-enabled `FEEDOPS_VARIANT_AT_LLM_TIME` feature flag block (DEAD-05) from the codebase. Tests and linting must stay green after each deletion. No test changes required — these are truly dead code paths.

Phase 11 handles the related but riskier work: test-import updates (DEAD-02), main.py re-export block removal (DEAD-03), and generator.py duplicate function cleanup (DEAD-04). This phase only touches code with zero callers.

</domain>

<decisions>
## Implementation Decisions

### Deletion ordering
- Delete in separate atomic commits per logical group — easier to bisect if something breaks
- DEAD-01 orphan functions first (lower risk), then DEAD-05 feature flag block (larger change)
- Run `pytest tests/` and `ruff check src/` after each commit to confirm green

### Feature flag cleanup scope
- Delete the flag check, dead code branches, and all comments/docstrings that reference `FEEDOPS_VARIANT_AT_LLM_TIME`
- Clean removal — no vestigial references should remain in the codebase
- Spans 3 files: generator.py, finish_injection.py, reporter.py

### Re-export removal boundary
- Remove `_provider_label` re-export from finish_processing.py (it re-exports from generation_telemetry.py — callers should import directly)
- Remove finish processing re-exports from generation.py (lines 26-30)
- Do NOT touch main.py re-exports — that's Phase 11 (DEAD-03)

### Claude's Discretion
- Exact ordering of individual function deletions within DEAD-01
- Whether to combine small deletions in the same file into one commit
- How to handle any docstring references to deleted functions in other files

</decisions>

<specifics>
## Specific Ideas

No specific requirements — the success criteria are explicit function/block deletions with green tests.

</specifics>

<code_context>
## Existing Code Insights

### DEAD-01 Targets (generator.py)
- `_payload_value_lengths` (line 138) — zero callers
- `_schema_hash` (line 184) — zero callers
- `_prompt_hash` (line 190) — zero callers
- `_generate_with_provider_compat` (line 151) — dead copy; live copies exist in executor.py:111 and hybrid_generation.py:52

### DEAD-01 Targets (re-exports)
- `finish_processing.py:7` — `_provider_label` re-exported from generation_telemetry via noqa comment
- `generation.py:26` — finish processing symbols re-exported via noqa comment

### DEAD-05 Target (feature flag block)
- `generator.py` — `FEEDOPS_VARIANT_AT_LLM_TIME` env var check (line 752), ~500 lines of variant generation code
- `finish_injection.py` — 3 references (docstring line 11, usage line 619, error message line 643)
- `reporter.py` — 2 references (env check line 38, docstring line 817)

### File sizes
- generator.py: 936 lines — will shrink substantially (~500 lines from DEAD-05 alone)

### Established Patterns
- Atomic commits with `pytest` + `ruff` verification after each (from Phase 8 pattern)
- Re-exports use `# noqa: F401` comments — removal means also removing noqa annotations

### Integration Points
- No new code connects to anything — this is purely subtractive
- executor.py and hybrid_generation.py have their own copies of `_generate_with_provider_compat` — those are live and untouched

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-trivial-dead-code-removal*
*Context gathered: 2026-03-03*
