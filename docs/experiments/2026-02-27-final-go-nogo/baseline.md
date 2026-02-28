# Final Go/No-Go Baseline (2026-02-27 rerun)

- Timestamp (ET): 2026-02-27
- Repository: `bobby-andris/Allied-FeedOps`
- Canonical path: `/Users/bobby/Documents/GitHub/Allied-FeedOps`
- Branch: `codex/e245-final-go-nogo-rerun-20260227`
- Baseline SHA: `376a238ec8da6a2aa3e7ce3cc4eadd0e60be7855`
- Upstream baseline: `origin/master`
- Environment mode: local parity (`uv`, `PYTHONPATH=src`)

## Planned G1 test command

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

Result:
- `49 passed` (no warnings emitted by pytest in this rerun).
