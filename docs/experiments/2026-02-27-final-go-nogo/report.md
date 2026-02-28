# Final Go/No-Go Report (2026-02-27 rerun)

## Executive Decision
**NO-GO** for prompt/output quality analysis start.

Rationale:
1. **G1 passed** (all required tests green with no warnings in this run).
2. **G2 failed** (lineage/telemetry completeness still below gate expectations).
3. **G3 failed** (OpenAI org usage/cost reconciliation still returns persisted `403` warnings).
4. **G4 failed** (controlled smoke did not complete successfully for description/hybrid).

## Baseline
- Branch: `codex/e245-final-go-nogo-rerun-20260227`
- Baseline SHA: `376a238ec8da6a2aa3e7ce3cc4eadd0e60be7855`
- Baseline lock file: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-02-27-final-go-nogo/baseline.md`

## Gate-by-Gate Status

### G0 — Administrative Cleanup
**PASS**
- PR #36 remains closed.
- Remote secret-hotfix branch remains deleted.

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

Result:
- `49 passed in 1.76s`
- No pytest warnings emitted in this rerun.

### G2 — Supabase Lineage/Telemetry Gate
**FAIL**

Read-only checks (last 24h, `regeneration_history`):
- `total_rows=70`
- `request_id_present=18`
- `completed_rows=8`
- Completed rows with populated telemetry:
  - `tokens_used=6`
  - `cost_usd=6`
  - `latency_ms=6`
  - `provider_attempt_count=6`
  - `parse_retry_count=2`
- `result_state` distribution:
  - `<null>=62`
  - `completed=8`
- Completed rows with missing required fields (request/telemetry/retry set): `6`

Finish placeholder integrity (Google/Bing description outputs, last 24h):
- `google`: `total_rows=3`, `exactly_one_placeholder=3`, `invalid_placeholder_rows=0`

Variant finish linkage:
- `google`: `desc_sku_pairs=3`, `with_finish_row=3`, `missing_finish_row=0`, `min_finish_count=28`, `max_finish_count=28`

Hybrid per-SKU detail integrity:
- Recent failed job with full detail coverage:
  - `job_id=5b384d4f-53d2-4f72-8a26-4de9c4dd79fc`
  - `total_skus=2`, `detail_rows=2` (both failed)
- Historical failed job in window with missing details:
  - `job_id=0c52acdc-ac07-4437-8731-40432ec47a1a`
  - `total_skus=2`, `detail_rows=0`

Gate verdict reason:
- New completed rows still do not consistently populate telemetry and retry counters.
- A failed hybrid job within the observation window has zero per-SKU detail rows.

### G3 — OpenAI Usage/Reconciliation Gate
**FAIL**

Rollup presence:
- `openai_usage_window_rollups` rows in last 7 days: `1`
- `cost_reconciliation_deltas` rows in last 7 days: `1`

Latest reconciliation evidence:
- `status=missing_openai_data`
- `mismatch_categories=["openai_usage_unavailable","internal_only_activity"]`
- `metadata.warnings` includes:
  - `OpenAI usage API error (403)`
  - `OpenAI costs API error (403)`

Gate verdict reason:
- Reconciliation remains non-operational due to unresolved OpenAI org usage/cost permissions.

### G4 — Controlled Smoke Runs (One Single + One Hybrid)
**FAIL**

Single SKU smoke (`CL-55`, Google title):
- request_id: `70b2e9c5-c8e2-4784-a809-478703af53c2`
- HTTP 200 (success)
- DB lineage row persisted:
  - `generated_content_id=8300a24f-d4c0-439b-87d1-94768f069bbe`
  - `tokens_used=6156`, `cost_usd=0.034221`, `latency_ms=30966`

Single SKU smoke (`CL-55`, Google description):
- request_id: `c1eeba4d-c5b4-4e51-932e-b8529c15ee4c`
- HTTP 500
- Error: `[openai/gpt-5.2] Failed to generate valid JSON: Request timed out. (after 2 retries)`

Hybrid smoke (`1033/18`, `1033/24`, Google descriptions only):
- request_id: `a64cb19a-7c99-40fd-b5b4-a901973507af`
- `job_id=5b384d4f-53d2-4f72-8a26-4de9c4dd79fc`
- Final status: `failed`
- `completed_skus=0`, `failed_skus=2`
- Both SKU rows failed with timeout after 2 retries.

Gate verdict reason:
- Required single+hybrid smoke did not complete end-to-end successfully.

## Evidence Notes
Key SQL checks used:
1. 24h `regeneration_history` completeness aggregates.
2. 24h completed-row missing-field check.
3. Placeholder cardinality check on `generated_content.candidate_content`.
4. `variant_finish_sentences` linkage and finish-count check.
5. `batch_generation_jobs` / `batch_generation_job_skus` detail-count integrity.
6. `openai_usage_window_rollups` + `cost_reconciliation_deltas` latest status/warnings.

## Residual Risks
1. Quality-analysis conclusions would be unreliable while description/hybrid runs are timing out.
2. Spend reconciliation cannot be trusted until OpenAI usage/cost APIs stop returning `403`.
3. Telemetry gaps on completed rows reduce confidence in root-cause attribution.

## Immediate Next Actions (Blockers)
1. **Rerun OpenAI permissions validation in production runtime**:
   - Verify `OPENAI_USAGE_API_KEY` is org-level with usage+cost scope.
   - Verify `OPENAI_ORG_ID` matches key’s organization.
2. **Backfill/normalize telemetry defaults on completed rows**:
   - Ensure `parse_retry_count` and `provider_attempt_count` persist as `0` when absent.
3. **Resolve timeout instability for description/hybrid paths**:
   - Tighten model call latency envelope and observe retries by request_id.
4. **Re-run G2/G3/G4 only** after fixes; keep G1 baseline as-is.

## Final Decision Rule Applied
Per plan, GO requires G1–G4 all passing.
- Current state: G1 pass, G2/G3/G4 fail.
- **Decision: NO-GO.**
