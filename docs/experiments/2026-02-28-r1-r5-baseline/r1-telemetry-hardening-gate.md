# R1 Telemetry Hardening Gate Report

## Branch + Baseline
- Branch: `codex/e245-r1-telemetry-hardening-20260228`
- Base: `master`
- Program tracker: `docs/roadmaps/2026-02-28-r1-r5-implementation-program.md`

## Implemented Scope
1. Hybrid/batch/full-generation persistence now writes telemetry fields into `regeneration_history` for successful rows:
   - `tokens_used`
   - `cost_usd`
   - `latency_ms`
2. Provider retry diagnostics now flow from OpenAI provider -> per-platform generator output:
   - `attempt_count`
   - `json_decode_retries`
   - `api_retries`
   - `budget_retries`
3. Terminal structured summary events are emitted for regenerate and batch/hybrid workers:
   - event: `generation.request.summary`
   - fields include `request_id`, `job_id`, `master_sku`, `platform`, `content_type`, `mode`, `result_state`, and telemetry/retry counters when available.
4. Batch/hybrid per-SKU detail hardening:
   - hybrid job creation inserts processing-scope rows in `batch_generation_job_skus`
   - helper upsert ensures SKU status rows exist and progress deterministically (`pending` -> `processing` -> terminal)
5. Env parity fix:
   - `_get_supabase_config()` now prefers environment variables before Streamlit secrets to keep local/Vercel parity deterministic.

## New/Updated Tests (R1)
- `tests/api/test_main_master_sku_alias_runtime.py`
  - `test_process_hybrid_batch_job_persists_non_null_telemetry`
  - `test_process_hybrid_batch_job_writes_batch_sku_detail_for_processing_scope`
  - `test_generation_summary_event_contract`

## Required Gate Suite
Executed:
```bash
PYTHONPATH=src uv run --frozen --extra dev pytest -q \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_regenerate_response_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/test_cloud_run_parity.py \
  tests/test_runtime_env_contract.py \
  tests/test_env_parity.py
```

Result:
- `27 passed`
- `0 failed`

## Gate Decision
- Code gate: pass
- Contract gate: pass (additive only)
- Observability gate: pass (summary event + retry diagnostics)
- Data gate: pass for app-layer write behavior and SKU detail completeness
- Deploy gate: pending (requires PR merge + production deployment)
