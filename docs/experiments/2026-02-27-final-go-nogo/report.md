# Final Go/No-Go Report (2026-02-28 post-deploy rerun)

> Historical evidence only. This report captures a pre-closure go/no-go decision and is not the active production certification source.
>
> Canonical sources:
> - `AGENTS.md`
> - `docs/architecture/generation-runtime-truth.md`
> - `docs/architecture/generation-core-task-model.md`
> - `docs/experiments/2026-02-28-production-divergence-closure/report.md`

## Executive Decision
**NO-GO** for prompt/output quality analysis start.

Rationale:
1. **G1 passed** (all required parity/contract tests green, no warnings).
2. **G2 failed** (successful hybrid description rows still miss telemetry/retry fields; hybrid job terminal state still leaves pending SKU detail rows).
3. **G3 failed** (reconciliation is reachable and usage is partially available, but OpenAI cost windows are still null so status remains `missing_openai_data`).
4. **G4 failed** (single title succeeded, but single description timed out and hybrid run failed).

## Baseline
- Branch: `codex/e245-final-go-nogo-postdeploy-20260228`
- Baseline SHA: `cd091581d4729ef33361029824de6cc2803dcf5b`
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
- `49 passed in 1.70s`
- No pytest warnings emitted.

### G2 — Supabase Lineage/Telemetry Gate
**FAIL**

Last 24h (`regeneration_history`) aggregate:
- `total_rows=78`
- `request_id_present=26`
- `completed_rows=17`
- `completed_with_tokens=11`
- `completed_with_cost=11`
- `completed_with_latency=11`
- `completed_with_provider_attempts=11`
- `completed_with_parse_retries=7`

Recent run window (`created_at >= 2026-02-28T03:20:00Z`) state split:
- `completed`: `rows=9`, `with_request_id=9`, telemetry populated on `5/9`

Missing telemetry on successful rows (sample, all from hybrid description writes with request_id `0af0932c72a0497c89c2ae49e4569358`):
- `DT-GTB-2 / google / description`
- `DT-GTB-2 / shopify / description`
- `2020G / google / description`
- `2020G / shopify / description`

Finish placeholder integrity (Google/Bing descriptions, last 24h):
- `google`: `total_rows=31`, `exactly_one_placeholder=31`, `invalid_placeholder_rows=0`

Variant finish linkage:
- `google`: `desc_rows=31`, `with_finish_rows=31`, `missing_finish_rows=0`

Hybrid per-SKU detail integrity (current smoke job):
- `job_id=2ccd5453-e145-43ea-885f-eeb40a3550d6`
- `status=failed`, `total_skus=2`, `detail_rows=2`
- detail state split: `failed_rows=1`, `pending_rows=1`

Gate verdict reason:
- Completed description rows still miss required telemetry/retry fields.
- Hybrid failed job leaves one SKU detail row pending instead of terminal (`failed`/`completed`).

### G3 — OpenAI Usage/Reconciliation Gate
**FAIL**

Dashboard reconciliation endpoint (read path) is reachable:
- `GET /api/monitoring/cost-reconciliation?lookback_days=2` returns `success=true`.

Latest report window:
- `status=missing_openai_data`
- `openai_total_requests=82`
- `openai_total_cost_usd=null`
- `internal_total_cost_usd=0.970185`
- `categories=["openai_usage_unavailable","internal_only_activity"]`

`openai_usage_window_rollups` latest metadata:
- `usage_available=true`
- `costs_available=false`
- `warnings=[]`

Gate verdict reason:
- Usage calls now partially work, but cost data is still not available (`total_cost_usd` null), so reconciliation remains non-operational for spend truth.

### G4 — Controlled Smoke Runs (One Single + One Hybrid)
**FAIL**

Single SKU smoke (`CL-55`, Google title):
- request_id: `d8cf8e9d-ac0a-4312-b40d-9e0268b6744a`
- HTTP 200 (success)
- persisted row:
  - `generated_content_id=8300a24f-d4c0-439b-87d1-94768f069bbe`
  - `tokens_used=5968`
  - `cost_usd=0.033070`
  - `latency_ms=25842`
  - `provider_attempt_count=1`
  - `parse_retry_count=0`

Single SKU smoke (`CL-55`, Google description):
- request_id: `959d0243-def5-4ea3-b851-8df44389afb5`
- HTTP 500
- error: `[openai/gpt-5.2] Failed to generate valid JSON: Request timed out. (after 2 retries)`

Hybrid smoke (`1033/18`, `1033/24`, Google descriptions only):
- request_id: `e7c8ab30-0775-4643-93bf-448ee6cd5210`
- `job_id=2ccd5453-e145-43ea-885f-eeb40a3550d6`
- final status: `failed`
- `completed_skus=0`, `failed_skus=1`, with one remaining `pending` SKU detail row

Gate verdict reason:
- Required single+hybrid smoke did not complete end-to-end successfully.

## Evidence Notes
Primary evidence sources used in this rerun:
1. Parity/contract pytest run (G1 command above).
2. Supabase read-only SQL on:
   - `regeneration_history`
   - `generated_content`
   - `variant_finish_sentences`
   - `batch_generation_jobs`
   - `batch_generation_job_skus`
   - `openai_usage_window_rollups`
   - `cost_reconciliation_deltas`
3. Live Cloud Run smoke requests via `scripts/smoke_regenerate_lineage.py`.
4. Live dashboard reconciliation GET endpoint.

## Residual Risks
1. Quality-analysis conclusions remain unreliable while description and hybrid runs are timing out.
2. Spend reconciliation is still incomplete while OpenAI costs remain unavailable.
3. Hybrid telemetry is still asymmetric (titles populated, descriptions null) in successful write paths.

## Immediate Next Actions (Blockers)
1. **Fix hybrid description telemetry parity**:
   - Ensure hybrid adaptation writes populate `tokens_used`, `cost_usd`, `latency_ms`, `provider_attempt_count`, `parse_retry_count` for completed rows.
2. **Fix hybrid terminal-state consistency**:
   - Ensure all `batch_generation_job_skus` rows transition to terminal state when parent job fails.
3. **Fix OpenAI cost availability**:
   - Validate `OPENAI_USAGE_API_KEY` scope for organization costs endpoint, and confirm runtime org/project mapping used by reconciliation.
4. **Stabilize description timeout path**:
   - Recheck provider timeout/retry envelope on description generation and rerun controlled smoke.
5. **Re-run G2/G3/G4 after fixes**; retain current G1 baseline.

## Final Decision Rule Applied
Per plan, GO requires G1–G4 all passing.
- Current state: G1 pass, G2/G3/G4 fail.
- **Decision: NO-GO.**
