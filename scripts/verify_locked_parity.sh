#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for locked parity checks. Install uv first." >&2
  exit 1
fi

echo "Running frozen parity suite (UV_FROZEN=1)..."
UV_FROZEN=1 uv run --frozen pytest -q \
  tests/test_cloud_run_parity.py \
  tests/test_env_parity.py \
  tests/test_runtime_env_contract.py \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/test_phase28_prompt_quality.py \
  tests/api/test_regenerate_response_contract.py \
  tests/test_v1_path_regression.py

echo "Checking uv.lock immutability..."
if ! git diff --exit-code uv.lock >/dev/null; then
  echo "ERROR: uv.lock changed during frozen parity run. Revert or isolate dependency changes in a separate PR." >&2
  git --no-pager diff -- uv.lock
  exit 1
fi

echo "Frozen parity suite passed and uv.lock remained unchanged."
