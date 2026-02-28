#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"
PYTHON_BIN="python"
if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

echo "Running Cloud Run parity contract suite..."
"$PYTHON_BIN" -m pytest -q \
  tests/test_generation_runtime_scope_contract.py \
  tests/test_generator_task_prompt_contract.py \
  tests/test_hybrid_generation_parity.py \
  tests/test_cloud_run_parity.py \
  tests/test_env_parity.py \
  tests/test_runtime_env_contract.py \
  tests/api/test_hybrid_generation_telemetry_contract.py \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_dashboard_generation_routes_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/test_phase28_prompt_quality.py \
  tests/api/test_regenerate_response_contract.py \
  tests/test_v1_path_regression.py

echo "Cloud Run parity suite passed."
