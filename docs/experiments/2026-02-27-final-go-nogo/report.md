# Final Go/No-Go Report (2026-02-27)

## Executive Decision
**NO-GO** for prompt/output quality analysis start.

Rationale:
1. Gate G1 (tests) passed.
2. Gate G2 (lineage/telemetry) failed due to incomplete request/telemetry coverage in new `regeneration_history` rows and missing parse retry persistence.
3. Gate G3 (OpenAI usage reconciliation) failed due to persisted 403 usage/cost warnings and `missing_openai_data` reconciliation state.
4. Gate G4 (controlled smoke runs) failed: single-SKU and hybrid generation both timed out via provider path (`[openai/gpt-5.2] ... Request timed out. (after 2 retries)`).

## Baseline
- Branch: `codex/e245-final-go-nogo-20260227`
- Baseline SHA: `5f0569e08b3d39f174f73f19c5f12fa1c0264fb1`
- Baseline lock file: `docs/experiments/2026-02-27-final-go-nogo/baseline.md`

## Gate-by-Gate Status

### G0 — Administrative Cleanup
**PASS**
- Closed PR #36.
- Deleted remote branch `codex/e245-secret-containment-hotfix-20260227`.
- Remaining open PRs are intended Dependabot PRs only.

### G1 — Contract/Parity Test Gate
**PASS**
Command executed:
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
Result: `48 passed, 14 warnings`.

Additional route/lib monitoring tests executed:
```bash
cd dashboard
npm run test -- \
  src/lib/monitoring/__tests__/cost-reconciliation.test.ts \
  src/app/api/monitoring/__tests__/cost-reconciliation.route.test.ts
```
Result: `10 passed`.

### G2 — Supabase Lineage/Telemetry Gate
**FAIL**

Read-only findings (last 24h):
- `regeneration_history` totals:
  - rows: `46`
  - `request_id` present: `13`
  - `tokens_used` present: `11`
  - `cost_usd` present: `11`
  - `latency_ms` present: `13`
  - `provider_attempt_count` present: `3`
  - `parse_retry_count` present: `0`
- `result_state` distribution:
  - `<null>`: `43`
  - `completed`: `3`
- Completed row coverage (`result_state='completed'`):
  - `request_id/tokens/cost/latency/provider_attempt_count`: `3/3`
  - `parse_retry_count`: `0/3`

Finish placeholder consistency (Google/Bing descriptions, last 24h):
- Google description rows: `22`
- Exactly one `{FINISH_SENTENCE}`: `22`
- Zero or multiple placeholders: `0`

Hybrid per-SKU integrity:
- A recent failed hybrid job (`f0469aae-d3b2-48db-a262-c40aba526684`) has per-SKU rows in `batch_generation_job_skus` (2 failed rows), but an earlier failed job in the same 24h window had no SKU rows (`sku_rows=0`) indicating inconsistent coverage across jobs in the window.

Gate verdict reason:
- Critical lineage/telemetry completeness criteria are not met for new rows in the sampled window.

### G3 — OpenAI Usage/Reconciliation Gate
**FAIL**

Rollup state:
- `openai_usage_window_rollups` latest row:
  - `openai_request_count=0`, `total_cost_usd=NULL`
  - metadata warnings: `OpenAI usage API error (403)`, `OpenAI costs API error (403)`
- `cost_reconciliation_deltas` latest row:
  - `status='missing_openai_data'`
  - `mismatch_categories=['openai_usage_unavailable','internal_only_activity']`

Gate verdict reason:
- Reconciliation remains non-operational due to unresolved OpenAI org usage/cost authorization.

### G4 — Controlled Smoke Runs (One Single + One Hybrid)
**FAIL**

Single SKU (`CL-55`, Google title):
- request_id: `ce778f65-36e3-4412-8306-90bf863aba06`
- HTTP 500
- detail: `[openai/gpt-5.2] Failed to generate valid JSON: Request timed out. (after 2 retries)`

Single SKU (`CL-55`, Google description):
- request_id: `85503ff5-613b-42bd-a28f-f225879af3c5`
- HTTP 500
- detail: `[openai/gpt-5.2] Failed to generate valid JSON: Request timed out. (after 2 retries)`

Hybrid family run (`1033/18`, `1033/24`, Google title+description):
- `job_id=f0469aae-d3b2-48db-a262-c40aba526684`
- final status: `failed`
- `completed_skus=0`, `failed_skus=2`
- per-SKU errors: timeout after 2 retries for both SKUs.

Gate verdict reason:
- Required smoke runs did not complete successfully; no usable generation outputs were produced.

## Evidence Tables and Query Notes

### Key SQL checks used
1. `regeneration_history` 24h coverage and result-state distribution.
2. Placeholder cardinality check for Google/Bing descriptions.
3. `batch_generation_jobs` + `batch_generation_job_skus` integrity checks.
4. `openai_usage_window_rollups` + `cost_reconciliation_deltas` latest state and metadata warnings.

### Notable error signature
- Repeated runtime failure:
  - `[openai/gpt-5.2] Failed to generate valid JSON: Request timed out. (after 2 retries)`

## Residual Risks
1. Prompt/output quality analysis would produce non-trustworthy conclusions while generation attempts are timing out.
2. Cost reconciliation cannot be trusted while OpenAI org usage APIs return 403.
3. Partial telemetry/null lineage rows can obscure root-cause attribution for failures.

## Immediate Next Actions (Blockers to clear)
1. **Provider timeout/retry tuning (P0):** reduce effective wall time and isolate retry layer behavior in production pipeline.
2. **OpenAI org usage auth (P0):** validate key/org linkage for usage/cost endpoints until rollups stop reporting 403 and `missing_openai_data`.
3. **Lineage write consistency (P0):** enforce request/telemetry field population contract (including `parse_retry_count` defaulting to `0` when absent).
4. **Re-run G2–G4 only** after fixes; if green, flip decision to GO and begin quality analysis.

## Final Decision Rule Applied
Per plan: GO only if G1–G4 all pass.
- G1 passed, G2/G3/G4 failed.
- **Decision: NO-GO.**
