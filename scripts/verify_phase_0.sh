#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Load canonical local environment.
env_file=".env.local"
if [[ ! -f "$env_file" ]] && [[ -f "dashboard/.env.local" ]]; then
  env_file="dashboard/.env.local"
fi

if [[ ! -f "$env_file" ]]; then
  echo "ERROR: .env.local not found (checked .env.local and dashboard/.env.local)."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$env_file"
set +a

echo "== Python tests =="
.venv/bin/pytest -q

echo "== Live Supabase canary =="
canary_mode="${RUN_SUPABASE_CANARY:-0}"
if [[ "$canary_mode" == "1" ]]; then
  bash scripts/verify_live_supabase_canary.sh
elif [[ "$canary_mode" == "0" ]]; then
  echo "Skipped (RUN_SUPABASE_CANARY=0)"
else
  has_supabase_url=0
  has_supabase_key=0

  if [[ -n "${SUPABASE_URL:-}" ]] || [[ -n "${NEXT_PUBLIC_SUPABASE_URL:-}" ]]; then
    has_supabase_url=1
  fi

  if [[ -n "${SUPABASE_KEY:-}" ]] || [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]] || [[ -n "${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}" ]]; then
    has_supabase_key=1
  fi

  if [[ "$has_supabase_url" -eq 1 ]] && [[ "$has_supabase_key" -eq 1 ]]; then
    bash scripts/verify_live_supabase_canary.sh
  else
    echo "Skipped (auto mode; set RUN_SUPABASE_CANARY=1 to require live Supabase canary)"
  fi
fi

echo "== Dashboard lint/build =="
cd dashboard
npm run lint
npm run build -- --webpack

echo "OK"
