# R1-R5 Baseline Snapshot

This directory captures immutable pre-R1 baseline evidence.

## Captured
- Git/worktree/branch inventory under `meta/`
- SQL snapshots under `sql/`
- Test logs under `tests/`

## Baseline summary
- Head SHA: `080f7508`
- Baseline parity/regression run status: `FAILED (1)`
- Failing test at baseline: `tests/test_env_parity.py::test_supabase_config_accepts_vercel_env_names`

## Interpretation
Baseline test output is captured as-is and is treated as starting-state evidence. R1 implementation may proceed, but gatekeeping for merge will use phase-specific pass criteria and remediations where needed.
