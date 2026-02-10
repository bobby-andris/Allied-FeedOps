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

# Support service-role key fallback for canary checks
if [[ -z "${SUPABASE_KEY:-}" ]] && [[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  export SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY}"
fi

# Support NEXT_PUBLIC fallbacks used by dashboard env files
if [[ -z "${SUPABASE_URL:-}" ]] && [[ -n "${NEXT_PUBLIC_SUPABASE_URL:-}" ]]; then
  export SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL}"
fi

if [[ -z "${SUPABASE_KEY:-}" ]] && [[ -n "${NEXT_PUBLIC_SUPABASE_ANON_KEY:-}" ]]; then
  export SUPABASE_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY}"
fi

if [[ -z "${SUPABASE_URL:-}" ]]; then
  echo "ERROR: SUPABASE_URL is not set."
  exit 1
fi

if [[ -z "${SUPABASE_KEY:-}" ]]; then
  echo "ERROR: SUPABASE_KEY is not set (or SUPABASE_SERVICE_ROLE_KEY fallback missing)."
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "ERROR: .venv/bin/python not found. Create/activate the project venv first."
  exit 1
fi

echo "== Supabase canary =="
PYTHONPATH=./src .venv/bin/python - <<'PY'
import json
from pathlib import Path

from feedops.api.prompt_loader import get_system_prompt_hash
from feedops.api.supabase_loader import get_product_catalog_count, load_parent_sku_from_supabase
from feedops.db.supabase_client import get_client, is_supabase_available

if not is_supabase_available():
    raise SystemExit("Supabase is not available from current environment variables")

try:
    client = get_client()
except Exception as exc:
    raise SystemExit(f"Failed to initialize Supabase client: {exc}") from exc

tables = [
    "product_catalog",
    "prompt_templates",
    "variant_index",
    "search_queries_by_master_sku",
    "keyword_metrics",
]

table_counts = {}
try:
    for table_name in tables:
        result = client.table(table_name).select("*", count="exact").limit(1).execute()
        table_counts[table_name] = result.count or 0
except Exception as exc:
    raise SystemExit(f"Supabase table probe failed: {exc}") from exc

required_non_empty = ["product_catalog", "prompt_templates", "variant_index"]
empty_required = [name for name in required_non_empty if table_counts.get(name, 0) <= 0]
if empty_required:
    raise SystemExit(f"Required Supabase tables are empty: {', '.join(empty_required)}")

try:
    catalog_count = get_product_catalog_count()
except Exception as exc:
    raise SystemExit(f"Failed to read product_catalog count: {exc}") from exc

if catalog_count <= 0:
    raise SystemExit("product_catalog appears empty")

fixture_path = Path("samples/eval-skus.json")
fixture_skus = json.loads(fixture_path.read_text())
if not fixture_skus:
    raise SystemExit("samples/eval-skus.json has no SKUs for probe")

def _extract_master_sku(entry):
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        candidate = (entry.get("master_sku") or entry.get("sku") or "").strip()
        return candidate
    return ""

probe_sku = None
probe_parent = None
probe_errors = []

for entry in fixture_skus:
    candidate_sku = _extract_master_sku(entry)
    if not candidate_sku:
        continue
    try:
        parent = load_parent_sku_from_supabase(candidate_sku)
    except Exception as exc:
        probe_errors.append(f"{candidate_sku}: {exc}")
        continue
    if parent is not None:
        probe_sku = candidate_sku
        probe_parent = parent
        break

if probe_parent is None:
    if probe_errors:
        raise SystemExit(
            "No probe SKU could be loaded from product_catalog. Sample errors: "
            + "; ".join(probe_errors[:3])
        )
    raise SystemExit("No valid probe SKU candidates found in samples/eval-skus.json")

try:
    prompt_hash = get_system_prompt_hash()
except Exception as exc:
    raise SystemExit(f"Prompt hash lookup failed: {exc}") from exc

if not prompt_hash or len(prompt_hash) < 8:
    raise SystemExit("Prompt hash lookup returned an invalid value")

print("SUPABASE_CANARY_OK")
print(f"catalog_count={catalog_count}")
print(f"probe_sku={probe_sku}")
print(f"probe_variant_count={len(probe_parent.variants)}")
print(f"prompt_hash={prompt_hash}")
print("table_counts=" + json.dumps(table_counts, sort_keys=True))
PY

echo "OK"
