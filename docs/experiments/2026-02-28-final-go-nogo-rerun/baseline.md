# Final Go/No-Go Rerun Baseline

> Historical evidence only. This rerun baseline remains useful for forensic comparison, but it is not the active operational truth.
>
> Canonical sources:
> - `AGENTS.md`
> - `docs/architecture/generation-runtime-truth.md`
> - `docs/architecture/generation-core-task-model.md`
> - `docs/experiments/2026-02-28-production-divergence-closure/report.md`

- Timestamp: `2026-02-28 05:00:18 EST`
- Repository: `/Users/bobby/Documents/GitHub/Allied-FeedOps`
- Branch: `codex/e245-final-go-nogo-rerun-20260228`
- Baseline SHA: `1a6cb07e`
- Environment mode: `local parity (uv --frozen, PYTHONPATH=src)`

## Gate Commands

### G1 Contract + Parity Tests

```bash
PYTHONPATH=src uv run --frozen --extra dev pytest -q \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/api/test_regenerate_response_contract.py \
  tests/api/test_hybrid_generation_telemetry_contract.py \
  tests/api/test_finish_prompt_source_contract.py \
  tests/test_cloud_run_parity.py \
  tests/test_runtime_env_contract.py \
  tests/test_env_parity.py \
  tests/test_finish_sentence_validation.py \
  tests/test_finish_injection.py \
  tests/test_hybrid_generation_parity.py
```

### G2 Supabase Lineage + Telemetry Checks

- Validate request lineage, telemetry population, finish sentence linkage, and hybrid row integrity for recent rows.

### G3 OpenAI Usage Reconciliation Checks

- Validate `openai_usage_window_rollups` and `cost_reconciliation_deltas` population and no auth warning path.

### G4 Controlled Smoke Runs

- Single SKU: `CL-55` (Google title + description path)
- Hybrid family: `1033` family
