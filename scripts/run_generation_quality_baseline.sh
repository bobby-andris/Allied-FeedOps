#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env.vercel" ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.vercel
  set +a
fi

RUN_ID="${RUN_ID:-gq-baseline-$(date -u +%Y%m%d-%H%M%S)}"
SAMPLE_FILE="${SAMPLE_FILE:-samples/eval-skus-google-ads-90d.json}"
VARIANTS="${VARIANTS:-control}"
PLATFORMS="${PLATFORMS:-google,bing,shopify}"
REPLICATES="${REPLICATES:-2}"
REASONING_EFFORT="${REASONING_EFFORT:-high}"
MAX_COMPLETION_TOKENS="${MAX_COMPLETION_TOKENS:-16000}"
OUTPUT_ROOT="${OUTPUT_ROOT:-artifacts/prompt-quality}"
REPORT_PATH="${REPORT_PATH:-docs/experiments/${RUN_ID}-report.md}"
DRY_RUN="${DRY_RUN:-0}"

mkdir -p "$(dirname "$REPORT_PATH")"

echo "Running generation quality baseline"
echo "  run_id: $RUN_ID"
echo "  sample_file: $SAMPLE_FILE"
echo "  variants: $VARIANTS"
echo "  platforms: $PLATFORMS"
echo "  replicates: $REPLICATES"
echo "  report: $REPORT_PATH"
echo "  dry_run: $DRY_RUN"

cmd=(uv run --frozen --extra dev python scripts/phase28_root_cause_eval.py \
  --run-id "$RUN_ID" \
  --sample-file "$SAMPLE_FILE" \
  --variants "$VARIANTS" \
  --platforms "$PLATFORMS" \
  --replicates "$REPLICATES" \
  --reasoning-effort "$REASONING_EFFORT" \
  --max-completion-tokens "$MAX_COMPLETION_TOKENS" \
  --output-root "$OUTPUT_ROOT" \
  --report-path "$REPORT_PATH")

if [[ "$DRY_RUN" == "1" ]]; then
  cmd+=(--dry-run)
fi

UV_FROZEN=1 "${cmd[@]}"
