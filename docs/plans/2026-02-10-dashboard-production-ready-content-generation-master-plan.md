# Dashboard + Content Generation Production Readiness — Master Implementation Plan

> **For Codex/Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` (or equivalent) to implement this plan task-by-task.

**Goal:** Make the content generation + review + publishing workflow production-ready so we can scale from 1 published SKU to 72,000+ SKUs while generating policy-safe, evidence-grounded titles/descriptions that maximize Shopping CTR and Shopify conversion (revenue).

**Architecture (target):** Python (Cloud Run) is the single source of truth for prompt + generation + validation + scoring. The dashboard becomes a thin UI + orchestration layer that proxies to Python and renders results/review state from Supabase.

**Tech stack:** Python 3.11 + FastAPI (`src/feedops/api/`), pipeline modules (`src/feedops/pipeline/`), Supabase (content + evidence + review queue), Next.js dashboard (`dashboard/`).

---

## How To Use This Master Plan

This file is the “north star” list of phases and acceptance criteria.

Execution cadence:
1. Before starting a phase, create a *phase plan* in `docs/plans/` that breaks that phase into small tasks with test-first steps (TDD where feasible).
2. Implement the phase plan task-by-task.
3. Run all verification commands listed in the phase before marking it complete.
4. Only then, move to the next phase.

Definition of “phase complete” is explicit under each phase.

## Implementation Status Protocol (Required)

After each completed task, update this file immediately in the relevant phase section and append a row to the execution log below.

Required per-task status update format:
1. Mark task as `DONE` / `BLOCKED` / `IN PROGRESS`.
2. Record date (`YYYY-MM-DD`), owner/model, and changed file paths.
3. Record verification command(s) run and pass/fail result.
4. If blocked, record exact blocker and next unblocking action.

## Execution Log

| Date | Phase | Task/Change | Status | Verification |
|------|-------|-------------|--------|--------------|
| 2026-02-10 | Phase 0 | Baseline gate script + baseline test/doc updates | DONE | `bash scripts/verify_phase_0.sh` (pass) |
| 2026-02-10 | Phase 2 | Route/proxy unification status documented | DONE | `bash scripts/verify_phase_0.sh` (pass) |
| 2026-02-10 | Phase 2 | `middleware.ts` migrated to `proxy.ts`; workspace root + lockfile warning cleanup | DONE | `cd dashboard && npm run lint && npm run build -- --webpack` (pass) |
| 2026-02-10 | Phase 1 | Prompt parity checklist + prompt contract artifacts created | DONE | `docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`, `docs/architecture/prompt-contract.md` (present) |
| 2026-02-10 | Phase 1 | Prompt-source/prompt-hash verification test suite | DONE | `.venv/bin/pytest -q tests/test_prompt_title_guidance.py tests/test_prompts_finish.py` + `.venv/bin/pytest -q tests/test_prompt_loader.py tests/test_hybrid_generation_prompt.py tests/test_keyword_placement.py` (pass) |
| 2026-02-10 | Phase 1 | Unified generator prompt retrieval via `prompt_loader.get_system_prompt()` | DONE | `.venv/bin/pytest -q tests/test_pipeline.py::test_build_prompt_uses_canonical_prompt_loader tests/test_pipeline.py::test_build_split_prompt_uses_canonical_prompt_loader tests/test_pipeline.py::test_build_variant_prompt_uses_canonical_prompt_loader` (pass) |
| 2026-02-10 | Phase 1 | Post-refactor full Phase 1 verification rerun | DONE | `.venv/bin/pytest -q tests/test_prompt_title_guidance.py tests/test_prompts_finish.py tests/test_prompt_loader.py tests/test_hybrid_generation_prompt.py tests/test_keyword_placement.py tests/test_pipeline.py::test_build_prompt_uses_canonical_prompt_loader tests/test_pipeline.py::test_build_split_prompt_uses_canonical_prompt_loader tests/test_pipeline.py::test_build_variant_prompt_uses_canonical_prompt_loader` (pass) |
| 2026-02-10 | Phase 2 | Regeneration route audit confirms Python pipeline proxy path | DONE | `rg` audit of `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/app/api/regenerate/batch/route.ts`, `dashboard/src/app/api/sku-selection/generate/route.ts`, `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts` |
| 2026-02-10 | Phase 2 | Phase 2 verification gates rerun | DONE | `.venv/bin/pytest -q tests/api` + `cd dashboard && npm run lint && npm run build -- --webpack` (pass) |
| 2026-02-10 | Phase 0 | Added live Supabase canary gate script + integrated optional canary mode into baseline verify script | DONE | `bash scripts/verify_phase_0.sh` (pass, default offline mode), `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (fails in this environment: DNS resolution for Supabase host) |
| 2026-02-10 | Phase 0 | Verification scripts standardized on `.env.local` (`dashboard/.env.local` fallback only) | DONE | `bash scripts/verify_phase_0.sh` (pass), `RUN_SUPABASE_CANARY=auto bash scripts/verify_phase_0.sh` (canary invoked, DNS failure in this environment) |
| 2026-02-10 | Phase 3 | Added Python finish sentence validation module and test suite | DONE | `.venv/bin/pytest -q tests/test_finish_sentence_validation.py tests/test_hybrid_generation_prompt.py tests/api/test_regenerate_response_contract.py` (pass) |
| 2026-02-10 | Phase 3 | Enforced finish sentence validation + canonical persistence in `/regenerate` and hybrid generation flows | DONE | `bash scripts/verify_phase_0.sh` (pass) |
| 2026-02-10 | Phase 0 | Fixed live canary fixture probe parsing (`eval-skus` object entries) and validated live Supabase canary end-to-end | DONE | `bash scripts/verify_live_supabase_canary.sh` (pass), `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass) |
| 2026-02-10 | Phase 4 | Implemented search-query-first keyword plan + Bing anti-stuffing validators + keyword-alignment retry/scoring integration | DONE | `.venv/bin/pytest -q tests/test_keyword_placement.py tests/test_quality.py tests/test_title_validators.py tests/test_selection.py tests/test_pipeline.py::test_generate_candidates_fetches_image_once_and_generates_n tests/test_pipeline.py::test_generate_candidates_skips_failed_attempts` (pass) |
| 2026-02-10 | Phase 4 | Added speculative-competitor-claim guardrails in Python validators and sanitized enrichment/prompt comparative phrasing | DONE | `.venv/bin/pytest -q tests/test_keyword_placement.py tests/test_quality.py tests/test_title_validators.py tests/test_pipeline.py::test_validate_candidate_content_rejects_catalog_csv_references tests/test_pipeline.py::test_validate_candidate_content_rejects_speculative_competitive_claims tests/test_pipeline.py::test_validate_candidate_content_allows_evidence_style_comparison_language` (pass) |
| 2026-02-10 | Phase 4 | Full end-to-end verification with live Supabase canary and dashboard production build after guardrail changes | DONE | `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass; Python `350 passed, 1 skipped`, canary `SUPABASE_CANARY_OK`, dashboard lint/build pass) |
| 2026-02-10 | Phase 5 | Wire gold standard examples into generator prompts (master + variant) | DONE | `.venv/bin/pytest -q tests/test_prompt_loader.py::test_format_gold_standard_examples_bundle_formats_cross_platform_examples tests/test_pipeline.py::test_build_split_prompt_includes_gold_examples_when_available tests/test_pipeline.py::test_build_split_prompt_omits_gold_examples_when_unavailable tests/test_pipeline.py::test_build_variant_prompt_includes_gold_examples_when_available` (pass) |
| 2026-02-10 | Phase 5 | Raise gold example description cap to 5000 chars (avoid misleading truncation) | DONE | `.venv/bin/pytest -q tests/test_prompt_loader.py tests/test_pipeline.py::test_build_split_prompt_includes_gold_examples_when_available tests/test_pipeline.py::test_build_split_prompt_omits_gold_examples_when_unavailable tests/test_pipeline.py::test_build_variant_prompt_includes_gold_examples_when_available` (pass) |
| 2026-02-10 | Phase 5 | Wire keyword gap evidence into `src/feedops/pipeline/evidence.py` using `src/feedops/pipeline/keyword_gaps.py` with category-relevance + finish exclusion filtering | DONE | `.venv/bin/pytest -q tests/test_pipeline.py::test_build_evidence_table_keyword_gaps_are_category_relevant_and_finish_excluded` (pass) |
| 2026-02-10 | Phase 5 | Wire competitor evidence into `src/feedops/pipeline/evidence.py` via safe row builder in `src/feedops/pipeline/competitor_evidence.py` (filters speculative comparative language) | DONE | `.venv/bin/pytest -q tests/test_pipeline.py::test_build_evidence_table_competitor_rows_filter_speculative_language` (pass) |
| 2026-02-10 | Phase 5 | Add integration tests validating keyword-gap category relevance + finish exclusion and competitor evidence language safety (`tests/test_pipeline.py`) | DONE | `.venv/bin/pytest -q tests/test_pipeline.py::test_build_evidence_table_keyword_gaps_are_category_relevant_and_finish_excluded tests/test_pipeline.py::test_build_evidence_table_competitor_rows_filter_speculative_language` (pass) |
| 2026-02-10 | Phase 5 | Required verification gate: full test suite after evidence integration changes | DONE | `.venv/bin/pytest -q` (pass: `362 passed, 1 skipped`) |
| 2026-02-10 | Phase 5 | Required verification gate: `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` | BLOCKED | Python tests pass inside gate; live canary failed with `Supabase table probe failed: [Errno 8] nodename nor servname provided, or not known` (environment DNS/network blocker). Next action: rerun canary in an environment with Supabase DNS/network access. |
| 2026-02-10 | Phase 5 | Required verification gate rerun in network-enabled environment (`RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh`) | DONE | pass: Python `362 passed, 1 skipped`; canary `SUPABASE_CANARY_OK` (`catalog_count=75770`, `probe_sku=1031/30`, `probe_variant_count=28`); dashboard `npm run lint` + `next build --webpack` pass |
| 2026-02-10 | Phase 6 | Converted Phase 6 bullets into executable dashboard subtasks with file/test targets | DONE | Plan-only update (`docs/plans/2026-02-10-dashboard-production-ready-content-generation-master-plan.md`) |
| 2026-02-10 | Phase 6 | 6.1 Idempotent regeneration state handling + structured validation/actionable error payloads across API/UI | DONE | `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build` (fails in sandbox Turbopack with OS error 1), `cd dashboard && npm run build -- --webpack` (pass), `.venv/bin/pytest -q tests/api/test_regenerate_response_contract.py tests/api/test_dashboard_regenerate_route_contract.py` (pass) |
| 2026-02-10 | Phase 6 | 6.2 Idempotent review/approval transitions + source-content gating for approval writes | DONE | `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build` (fails in sandbox Turbopack with OS error 1), `cd dashboard && npm run build -- --webpack` (pass), `.venv/bin/pytest -q tests/api/test_dashboard_approval_state_contract.py tests/api/test_dashboard_regenerate_route_contract.py` (pass) |
| 2026-02-10 | Phase 6 | 6.3 Idempotent publish no-op detection + configurable publish RBAC guard + actionable publish failure codes | DONE | `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build` (fails in sandbox Turbopack with OS error 1), `cd dashboard && npm run build -- --webpack` (pass), `.venv/bin/pytest -q tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py` (pass) |
| 2026-02-10 | Phase 6 | 6.4 Batch status model + retry safety + per-SKU failure visibility (`publish/batch` assignment state writes, batch status normalization in list/detail pages) | DONE | `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build` (fails in sandbox Turbopack with OS error 1), `cd dashboard && npm run build -- --webpack` (pass), `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py` (pass) |
| 2026-02-10 | Phase 6 | 6.5 Validation/policy remediation surfaced in API + review/batch UIs (actionable next-step messaging) | DONE | `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build` (fails in sandbox Turbopack with OS error 1), `cd dashboard && npm run build -- --webpack` (pass), `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py tests/api/test_dashboard_regenerate_route_contract.py tests/api/test_dashboard_validation_surface_contract.py tests/test_review_dashboard.py tests/test_reporter_google_patch_structured_only_env.py` (pass) |
| 2026-02-11 | Phase 6 | Full-access verification rerun confirms dashboard build + Phase 6 tests outside sandbox | DONE | `cd dashboard && npm run lint && npm run build` (pass with Turbopack), `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py tests/api/test_dashboard_regenerate_route_contract.py tests/api/test_dashboard_validation_surface_contract.py tests/test_review_dashboard.py tests/test_reporter_google_patch_structured_only_env.py` (pass: `48 passed`) |
| 2026-02-11 | Phase 7 | Structured request-scoped logging + request ID propagation across generation paths | DONE | `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py::test_structured_log_event_includes_request_id` (pass) |
| 2026-02-11 | Phase 7 | Added generation/provider metrics for latency, retries, validation failures, and provider errors | DONE | `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py::test_metrics_registry_tracks_latency_retry_and_errors tests/test_phase7_observability_reliability.py::test_regenerate_description_skips_finish_sentence_path_when_killed` (pass) |
| 2026-02-11 | Phase 7 | Hardened provider retry behavior with exponential backoff + circuit breaker protection | DONE | `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py::test_openai_provider_applies_backoff_on_retryable_error tests/test_phase7_observability_reliability.py::test_openai_provider_circuit_breaker_blocks_after_threshold` (pass) |
| 2026-02-11 | Phase 7 | Added generation/finish-sentence kill switches and forced provider fallback toggle | DONE | `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py tests/test_providers.py` (pass) |
| 2026-02-11 | Phase 7 | Required verification: full Python test suite rerun after observability/reliability changes | DONE | `.venv/bin/pytest -q` (pass: `389 passed, 1 skipped`) |
| 2026-02-11 | Phase 7 | Required verification: Supabase canary gate via Phase 0 script | BLOCKED | `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (Python tests pass, canary fails in this environment: `Supabase table probe failed: [Errno 8] nodename nor servname provided, or not known`) |
| 2026-02-11 | Phase 7 | Required verification rerun in full-access environment (`RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh`) | DONE | pass: Python `389 passed, 1 skipped`; canary `SUPABASE_CANARY_OK` (`catalog_count=75770`, `probe_sku=1031/30`, `probe_variant_count=28`, `prompt_hash=530a11ec32d54c46`); dashboard `npm run lint` + `next build --webpack` pass; script finished `OK` |
| 2026-02-11 | Phase 6 | Production dashboard validation run (login, generate, regenerate with/without feedback, batch/readiness) using real SKUs `920D-6` and `SB-16`; verified Python prompt-source traceability and finish sentence behavior | DONE (issues found) | Browser routes exercised: `/login`, `/review`, `/generate`, `/review/920D-6`, `/batches`, `/batches/test-workflow-1770569844`. SOT checks: `generated_content.generation_prompt_hash=530a11ec32d54c46`, `regeneration_history.prompt_hash=530a11ec32d54c46`, `generation_model=openai/gpt-5.2`; finish evidence: `variant_finish_sentences` refreshed for `920D-6` Google path. Required gates rerun: `.venv/bin/pytest -q` (pass: `389 passed, 1 skipped`) and `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass, `SUPABASE_CANARY_OK`, dashboard lint/build pass). Defects observed: batch status/remediation visibility mismatch in UI vs `publish_events`/`publish_batches` data. |
| 2026-02-11 | Phase 6 | Batch/readiness hotfix for legacy DB schemas: added `batch_sku_assignments` read fallback when `status/error_message` columns are missing (`42703`) and wired batches list/detail/API to shared assignment store | DONE | Code: `dashboard/src/lib/batches/assignment-store.ts`, `dashboard/src/app/(dashboard)/batches/page.tsx`, `dashboard/src/app/(dashboard)/batches/[batchId]/page.tsx`, `dashboard/src/app/api/batches/route.ts`. Verification: `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_regenerate_route_contract.py tests/test_hybrid_generation_prompt.py` (pass: `14 passed`), `.venv/bin/pytest -q` (pass: `394 passed, 1 skipped`), `cd dashboard && npm run lint` (pass), `cd dashboard && npm run build -- --webpack` (pass). Live stream browser recheck (`prephase8-fixes`, viewer `ws://localhost:9223`): `/batches` and `/batches/batch-ft16-uppercase-mpn-test` reload clean with no `batch_sku_assignments.status` console error after clear. Note: `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` currently blocked in this environment (`nodename nor servname provided, or not known`). |
| 2026-02-11 | Phase 8 | 8.1 Batch sizing strategy finalized for 72k rollout (100 SKU hard cap, wave ramp, throughput-based capacity estimates) | DONE | `curl -sS "$FEEDOPS_PIPELINE_URL/health" | jq '{status,service,supabase_connected,product_catalog_count}'` (pass), `POST /batch-optimize` dry-run (`SB-16`,`107`) completed (`job_id=74ab0472-28c1-4237-b2ee-e8117b00fc70`, `2/2`) and throughput sampled (`~1.55 SKU/min`) |
| 2026-02-11 | Phase 8 | 8.2 Operator runbook blocks for Generate -> Review -> Publish finalized and aligned to current dashboard + Cloud Run paths/tables | DONE | `GET /api/sku-selection`, `GET /api/sku-selection/jobs`, `GET /api/sku-selection/generate/{jobId}`, `GET /api/approvals`, `GET /api/batches` checks (pass); non-dry run `POST /batch-optimize` for SKU `1098` completed (`job_id=210b995c-2623-4843-a37e-096bd9408e36`, `1/1`) and `generated_content` prompt-hash/model spot-check (pass) |
| 2026-02-11 | Phase 8 | 8.3 Stop-condition thresholds + rollback instructions finalized with verified query/CLI commands | DONE | `.venv/bin/python` threshold checks on `batch_generation_job_skus`, `publish_events`, `sku_approvals` (pass); `.venv/bin/feedops publish-history --limit 3` (pass); `.venv/bin/feedops rollback --sku FT-16 --platform shopify --dry-run` and non-dry-run rollback command execution path validated (no patch found, expected) |
| 2026-02-11 | Phase 8 | 8.4 Dry-run + spot-check verification bundle documented and command-validated in this environment | DONE | `docs/plans/2026-02-11-phase8-72k-scale-up-runbook.md` command set executed; local unauthenticated `POST /api/sku-selection/generate` guard check returned `307` with `/login` (expected), confirming write-route auth behavior |
| 2026-02-11 | Phase 7 | Shopify generation-path parity audit + full-generation history linkage fix across platforms | DONE | `.venv/bin/pytest -q` (pass: `401 passed, 1 skipped`), `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass: `SUPABASE_CANARY_OK`, dashboard lint/build `OK`), live `SB-16` run via `optimize_single_sku` with DB verification (Google/Bing placeholder + finish sentence persistence + Shopify outputs + linked history IDs + model/prompt hash) |
| 2026-02-11 | Phase 7 + Phase 6 | Production parity hardening + publish safety gates + review queue remediation pass | DONE | commit `23e1cfd6` pushed to `origin/master`; `.venv/bin/pytest -q` (pass: `434 passed, 1 skipped`), `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass: `SUPABASE_CANARY_OK`, `catalog_count=75770`, `probe_sku=1031/30`, `probe_variant_count=28`, `prompt_hash=530a11ec32d54c46`), production smoke (`/health`, `/optimize-sku` dry run, `/regenerate`, `/hybrid-generate`, `/batch-status`) all returned expected success/processing states |
| 2026-02-11 | Phase 7 | Hybrid requested-vs-expanded counter split to prevent progress overflow in hybrid jobs and dashboard history | DONE | commit `1b2dd79d` pushed to `origin/master`; tests: `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py::test_process_hybrid_batch_job_full_generation_matches_regenerate_finish_rules tests/test_phase7_observability_reliability.py::test_process_hybrid_batch_job_tracks_requested_and_expanded_counters tests/test_phase7_observability_reliability.py::test_process_batch_job_never_writes_partial_status` (pass), `.venv/bin/pytest -q` (pass: `436 passed, 1 skipped`), `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` (pass: `SUPABASE_CANARY_OK`, dashboard lint/build `OK`), production batch `38c55dae` final status `completed` with requested `2/2` and expanded `3/3`; `/generate` -> `Past Jobs` shows `2/2 (+3/3 expanded)` while historical failed jobs still show legacy overflow values |

### 2026-02-11 Production Readiness Verification Log (UTC)

- Timestamp window: `2026-02-11 10:36:44Z` to `2026-02-11 11:03:00Z` (latest run marker captured at `2026-02-11 11:00:57Z` via `date -u`).
- Representative SKUs used for live verification: `SB-16`, `1051`, `920D-6`, `WP-2TB-16-GAL`, plus full review remediation sweep over active queue SKUs.
- Routes and runtime paths validated:
  - Pipeline endpoints: `GET /health`, `POST /optimize-sku`, `POST /regenerate`, `POST /hybrid-generate`, `GET /batch-status/{job_id}`.
  - Dashboard proxy/generation/publish paths touched in this pass: `dashboard/src/app/api/sku-selection/generate/route.ts`, `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`, `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/app/api/publish/sku/route.ts`, `dashboard/src/app/api/publish/batch/route.ts`.
  - Python generation/parity paths touched in this pass: `src/feedops/api/main.py`, `src/feedops/api/hybrid_generation.py`, `src/feedops/pipeline/finish_sentence_placeholder.py`.
- Metadata/linkage fields explicitly checked in live Supabase records:
  - `generated_content.generation_model`, `generated_content.generation_prompt_hash`, `generated_content.generation_timestamp`.
  - `regeneration_history.generated_content_id`, `regeneration_history.prompt_hash`, `regeneration_history.model_version`.
  - `variant_finish_sentences.finish_sentences` cardinality for Google/Bing (`len(json)` expected = `28`).
- Metadata verification results snapshot:
  - `SB-16` and `1051` latest generation rows show `generation_model=openai/gpt-5.2` and `generation_prompt_hash=530a11ec32d54c46`.
  - `variant_finish_sentences` counts are `28` for `SB-16` (Google/Bing), `1051` (Google/Bing), and `920D-6` (Google/Bing).
  - `regeneration_history` latest rows include non-null `generated_content_id` with current prompt hash/model fields.
- Test/canary outputs for this pass:
  - `.venv/bin/pytest -q` -> `434 passed, 1 skipped`.
  - `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` -> `SUPABASE_CANARY_OK`, `catalog_count=75770`, `probe_sku=1031/30`, `probe_variant_count=28`, `prompt_hash=530a11ec32d54c46`, dashboard lint/build `OK`.
  - Targeted parity tests (new/updated): `tests/test_phase7_observability_reliability.py` and `tests/test_hybrid_generation_parity.py` fallback/placeholder cases pass.
- Production smoke evidence:
  - `GET /health` returned `{status:\"healthy\", service:\"feedops-pipeline\", version:\"1.0.0\", supabase_connected:true}`.
  - `POST /optimize-sku` dry run (`SB-16`) returned success with message `Generated content for 3 platforms`.
  - `POST /regenerate` (`SB-16`, Google description) returned success with `model=openai/gpt-5.2`, `prompt_hash=530a11ec32d54c46`, placeholder present exactly once, and finish sentence count `28`.
  - `POST /hybrid-generate` returned queued `job_id`; `GET /batch-status/{job_id}` returned `processing` with expected counters.
- Review queue remediation evidence:
  - Before remediation (`/tmp/review_quality_audit_before.json`): `strict_ready=9/92`, `not_ready=83`, with widespread missing placeholders/finish-sentence completeness/Shopify title brand violations.
  - After targeted regenerate sweep (`/tmp/review_quality_targeted_regen.json` + `/tmp/review_quality_audit_after.json`): `strict_ready=90/92`, `not_ready=2`, `223` successful operations, `5` failed operations (all `WP-2TB-16-GAL` `404`).
  - Final after stale content correction (`/tmp/review_quality_audit_after_final.json`): `strict_ready=91/92`, `not_ready=1` (`WP-2TB-16-GAL` only remaining blocker; missing slots + finish sentence rows).
  - Generic finish-count claim issue class is absent in final issue counts (remaining issues are slot and finish-sentence completeness for the single blocked SKU).

---

## Non-Negotiable Constraints

- **No hallucination:** Titles/descriptions must only state claims supported by the evidence pipeline. If unknown, omit.
- **Policy-first:** If a copy technique conflicts with platform policy, policy wins.
- **One prompt source of truth:** A single canonical system prompt must be used for every generation call (no drift between TS/Python/DB).
- **Methodology validation (not A/B testing):** Verification is via rule compliance, offline evaluations, sampled human review, and regression tests—*not* traffic experiments.

---

## Current State (Repo Truth, Feb 10 2026)

This plan assumes we’re starting from the current split-brain implementation:

- Dashboard still contains legacy regeneration logic and (at least some) LLM calls.
- Python API endpoints exist but do not always use the same prompt builder / pipeline path.
- Supabase `prompt_templates` has examples/guidance, and there is code that can incorrectly treat DB `system_prompt` as authoritative.

Files that will matter early:
- `src/feedops/api/main.py`
- `src/feedops/api/prompt_loader.py`
- `src/feedops/pipeline/prompts.py`
- `src/feedops/pipeline/generator.py`
- `src/feedops/pipeline/finish_injection.py`
- `src/feedops/quality/scoring.py`
- `dashboard/src/app/api/regenerate/route.ts`
- `dashboard/src/lib/regeneration/prompts.ts` (legacy TS prompt source)

---

## Baseline Architecture And Known Gaps (Approved)

**Reviewed research inputs**
- `docs/research/google-shopping-research-2026-02-10.md`
- `docs/research/shopify-cro-research-2026-02-10.md`
- `docs/research/prompt-scoring-audit-2026-02-10.md`
- `docs/research/content-optimization-synthesis-2026-02-10.md`

**Why TS changes were proposed while Python remained unchanged**
- Historical prompt/scoring improvements were drafted around dashboard code paths (`dashboard/src/lib/regeneration/*` and `dashboard/src/lib/quality-scoring.ts`).
- Runtime generation is being shifted to Cloud Run Python (`src/feedops/api/main.py`), which uses its own prompt/evidence/provider stack.
- Result: TS prompt edits can fail to affect production generation if Python does not consume the same canonical prompt/version.

**Known high-risk gaps (must be addressed early)**
- Prompt source-of-truth drift risk in `src/feedops/api/prompt_loader.py`.
- Thin Cloud Run prompt assembly in `src/feedops/api/main.py` if category guidance/examples are not consistently injected.
- Finish list/key integrity drift risk in `src/feedops/api/hybrid_generation.py`.
- Enrichment language policy risk (unverifiable or banned marketing language) in `src/feedops/pipeline/enrichment.py`.
- Provider structural safety risk (JSON parse without strict schema validation/repair) in `src/feedops/providers/openai_provider.py`.
- Policy mismatch risk for Shopify title rules in `src/feedops/pipeline/keyword_placement.py`.

**Supabase schema reality check (validated on `qezuszwufortkiutlhym`, Feb 2026)**
- Core generation/evidence tables exist and are populated: `product_catalog` (~75,770 rows), `prompt_templates` (1 row), `generated_content` (~400), `regeneration_history` (~177), `variant_finish_sentences` (~35), `search_queries_by_master_sku` (~894), `keyword_metrics` (~714).
- Operational routing/index tables are present and populated for scaled rollout: `variant_index` (~72,023 rows), `search_queries` (~2,147), `publish_events` (~29), `publish_batches` (~6), `performance_baselines` (~166).
- `prompt_templates.system_prompt` is present in schema, but architectural policy remains: code-owned canonical prompt only; DB prompt text is data and must not override runtime system prompt.
- `generated_content.generation_prompt_hash` and `regeneration_history.prompt_hash` are present; Phase 1 uses these for prompt-version traceability.
- Phase 4/5 target tables already exist but are currently empty: `keyword_coverage_master`, `keyword_coverage_variant`, `finish_search_patterns`; implementation work should write to these rather than creating new duplicate tables.

**Fixture source strategy (why samples still exist)**
- Offline regression must be deterministic and runnable without network credentials; fixture SKU baskets in `samples/eval-skus*.json` provide stable coverage for repeatable checks.
- Runtime generation and evidence are Supabase-first via `product_catalog` and search insight tables; sample CSV data is only a local/demo fallback for tests and developer onboarding.
- Phase 1+ work keeps both layers: deterministic offline fixtures for CI confidence, plus periodic live Supabase snapshot refresh for realism.

**Baseline architecture (today)**
```mermaid
flowchart TD
  subgraph DASH["Dashboard (Next.js)"]
    UI["Review UI"] --> ROUTE["`/api/regenerate` route.ts"]
    ROUTE --> CLOUD["POST `/regenerate` (Cloud Run)"]
    ROUTE --> DBWRITE["Supabase writes (`generated_content`, `regeneration_history`, `variant_finish_sentences`)"]
  end

  subgraph CLOUDRUN["Cloud Run (Python FastAPI)"]
    CLOUD --> MAIN["`src/feedops/api/main.py`"]
    MAIN --> LOADSKU["Load product row(s) from Supabase"]
    LOADSKU --> EVIDENCE["Build evidence table (`src/feedops/pipeline/evidence.py`)"]
    EVIDENCE --> INPUTS["Inputs: catalog fields, variant dimensions, finishes, search query insights, enrichment signals"]
    INPUTS --> PROMPT["Load system prompt (`src/feedops/api/prompt_loader.py`)"]
    PROMPT --> PROVIDER["LLM provider (`src/feedops/providers/*`)"]
    PROVIDER --> RESP["Structured JSON response"]
  end

  RESP --> DBWRITE
```

## Prompt Logic Inventory To Consolidate In Python (Phase 1 Scope)

The previous system used three prompt-generation logic paths in TypeScript. Phase 1 must preserve the useful logic and remove duplication by consolidating it in Python.

1. `dashboard/src/lib/regeneration/prompts.ts` (static prompt logic)
   - Canonical system prompt text, platform context blocks, finish list/reference, hard validation rules.
2. `dashboard/src/lib/regeneration/core.ts` (dynamic prompt assembly)
   - Evidence-table-based user prompt construction, simple fallback prompt, variant-adaptation prompt, JSON parsing/validation expectations, finish sentence persistence behavior.
3. `dashboard/src/app/api/regenerate/route.ts` (route-level prompt behavior)
   - Regeneration mode handling, feedback injection, and TS-side finish sentence generation call flow.

Phase 1 migration requirement:
- Document each TS rule as one of: `adopt`, `adapt`, or `drop`.
- Re-implement adopted/adapted rules in Python prompt builder/validators.
- Remove TS runtime prompt decisions from production execution paths once parity is verified.

## Platform And Entity Behavior Matrix (Must Stay Explicit)

Generation behavior must remain intentionally different by platform and by entity type:

- Google/Bing + Variant context
  - Variant-aware listing output.
  - Finish is part of title/description context.
  - Must support finish-specific content injection and channel-specific anti-stuffing constraints.
- Shopify + Master context
  - Master SKU storefront copy across finishes.
  - Finish-agnostic base title/description for product page clarity.
  - Channel-specific constraints (`no finish name`, `no Allied Brass` in Shopify title rules where defined by policy).

All Phase 1 tasks must preserve this matrix while moving prompt authority to Python.

---

## Global Acceptance Criteria (End State)

By the time we complete all phases:

1. **Consistency**
   - Every generation call uses the same canonical system prompt and the same platform-specific rules.
   - Generated records store a `prompt_version` (or hash) so we can trace exactly what produced any output.

2. **Compliance**
   - Google Shopping: AI-generated text is delivered using `structured_title` / `structured_description` and `digital_source_type=trained_algorithmic_media` where applicable.
   - No disallowed formatting (ALL CAPS, promo text, finish names in Shopify base copy, etc.) slips through validation.

3. **Quality**
   - Titles front-load the product type + primary dimension + key modifier within the first ~70 characters (channel-specific rules).
   - Descriptions follow benefits → features → trust structure and are scanner-friendly (bullets, short paragraphs).
   - Bing descriptions never keyword-dump (no slash-separated synonym lists, no parenthetical dumps).
   - Competitive positioning is allowed only when evidence supports it, and is expressed in qualified, non-speculative language.

4. **Operational**
   - Batch generation is idempotent, resumable, and rate-limit safe.
   - Dashboards show generation status, validation failures, and “why this scored the way it did.”
   - We can safely scale generation (and review) without manual firefighting.

---

## Phase 0 — Baseline, Guardrails, And Dev Environment

**Objective:** Freeze a reliable baseline, define gating tests, and ensure local dev can run the full pipeline deterministically.

**Key tasks**
- Document the canonical “generate single SKU end-to-end” workflow (local + Cloud Run parity).
- Create a small, curated SKU fixture set (10–30 master SKUs) covering key categories: towel bars, hooks, shelves, grab bars, paper holders, mirrors.
- Add regression fixtures for validators (known-bad strings that must fail).
- Ensure the repo has a single obvious command set for: lint, typecheck, unit tests, “generate sample”.

**Verification commands**
- Python unit tests: `.venv/bin/pytest -q`
- Targeted pipeline tests: `.venv/bin/pytest -q tests/test_pipeline.py tests/test_finish_injection.py tests/test_quality.py`
- Live Supabase runtime canary: `bash scripts/verify_live_supabase_canary.sh`
- Dashboard build sanity: `cd dashboard && npm run lint && npm run build`
- Phase 0 unified gate: `bash scripts/verify_phase_0.sh`
- Phase 0 unified gate with required Supabase canary: `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh`

**Definition of done**
- Every developer can run the commands above locally and get a clean pass.
- We have a committed SKU fixture list and a written “how to validate outputs without traffic.”

---

## Phase 1 — Single Source Of Truth For Prompts (Python Canonical)

**Objective:** Ensure the Python pipeline always uses the best system prompt (single canonical source) and that Supabase examples do not cause prompt drift.

**Implementation status (current)**
- `DONE` TS-to-Python parity checklist created: `docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`.
- `DONE` Prompt contract created: `docs/architecture/prompt-contract.md`.
- `DONE` Canonical prompt source in Python prompt loader (`src/feedops/api/prompt_loader.py` returns code-owned prompt, not DB `system_prompt`).
- `DONE` Prompt hash traceability active via `get_system_prompt_hash()` and persisted to `generated_content.generation_prompt_hash` / `regeneration_history.prompt_hash`.
- `DONE` Runtime prompt retrieval in `src/feedops/pipeline/generator.py` now uses `prompt_loader.get_system_prompt()` for `build_prompt`, `build_split_prompt`, and `build_variant_prompt`.
- `DONE` Phase 1 verification commands currently green as of 2026-02-10.

**Decisions (explicit)**
- Canonical prompt lives in Python code (recommend `src/feedops/pipeline/prompts.py`).
- Supabase `prompt_templates` remains **examples/guidance only**.
- Dashboard never supplies its own system prompt to the generator; it only requests “generate X”.

**Key tasks**
- Create a TS-to-Python prompt logic parity checklist covering:
  - static prompt rules (`prompts.ts`)
  - dynamic prompt assembly (`core.ts`)
  - route-level regeneration behavior (`route.ts`)
  - each item marked `adopt` / `adapt` / `drop` with rationale.
- Phase 1 artifact path: `docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`
- Fix `src/feedops/api/prompt_loader.py` so it **never** treats DB `system_prompt` as authoritative.
- Introduce prompt versioning (hash or semver) and store it with generated outputs in Supabase.
- Move all runtime prompt composition decisions to Python (including platform and master/variant branching).
- Create a “prompt contract” doc that explains: where prompt lives, what is data-only, how to safely iterate.
- Phase 1 artifact path: `docs/architecture/prompt-contract.md`

**Verification commands**
- `.venv/bin/pytest -q tests/test_prompt_title_guidance.py tests/test_prompts_finish.py`
- `.venv/bin/pytest -q tests/test_prompt_loader.py tests/test_hybrid_generation_prompt.py tests/test_keyword_placement.py`

**Definition of done**
- For any generation call, logs show the same prompt version regardless of whether prompt templates exist in Supabase.
- There is one and only one code path to retrieve the canonical system prompt.
- Phase 1 artifact docs exist and are current:
  - `docs/plans/2026-02-10-phase-1-ts-to-python-prompt-parity-checklist.md`
  - `docs/architecture/prompt-contract.md`

---

## Phase 2 — Unify Generation Path (Dashboard Proxies, Python Generates)

**Objective:** Eliminate any remaining LLM calls from the dashboard and route all title/description generation through Python for consistency and auditability.

**Implementation status (current)**
- Dashboard regeneration route no longer imports or calls OpenAI directly.
- Python `/regenerate` now returns optional `finish_sentences` for Google/Bing descriptions.
- Dashboard persists Python-returned `finish_sentences` into `variant_finish_sentences`.
- Dashboard batch regeneration and hybrid generation routes now proxy to Python pipeline endpoints.
- Next.js middleware deprecation warning is resolved by moving dashboard auth middleware to `dashboard/src/proxy.ts`.
- Workspace-root/package-lock ambiguity is addressed by aligning Next root settings in `dashboard/next.config.ts` and keeping the dashboard lockfile authoritative (`dashboard/package-lock.json`).
- Route audit confirms regeneration API paths proxy to Python endpoints (`/regenerate`, `/batch-optimize`, `/hybrid-generate`) and do not instantiate TS OpenAI clients.
- `dashboard/src/lib/regeneration/core.ts` still contains legacy OpenAI helper code but is currently unreferenced by dashboard API routes (safe but removable cleanup).

**Key tasks**
- Remove or disable any TS-side OpenAI usage for regeneration endpoints.
- Make dashboard regeneration strictly call Python endpoints and persist returned results (including finish sentences) into Supabase.
- Ensure dashboard and Python agree on schemas for:
  - Base content (title/description per platform)
  - Finish sentences storage (`variant_finish_sentences`)
  - Validation + scoring breakdowns

**Verification commands**
- `.venv/bin/pytest -q tests/api`
- Dashboard build: `cd dashboard && npm run lint && npm run build -- --webpack`
- Manual smoke: regenerate one SKU via dashboard and confirm no TS LLM call occurs (phase plan should define how to confirm via logs).

**Definition of done**
- The dashboard contains **zero** code paths that call LLM providers directly.
- Regeneration button results match Python output 1:1 and include finish sentences where required.

---

## Phase 3 — Finish Sentences: Generate + Store In Python

**Objective:** Ensure the “28 finish sentence moat” is generated consistently, validated, and stored in `variant_finish_sentences` from Python.

**Implementation status (current)**
- `DONE` Python finish sentence validation module added: `src/feedops/pipeline/finish_sentence_validation.py`.
- `DONE` `/regenerate` flow validates finish sentence payload and persists only complete canonical finish maps.
- `DONE` Hybrid generation path validates finish sentence payload with the same shared validator.
- `DONE` Dedicated tests added and green:
  - `tests/test_finish_sentence_validation.py`
  - `tests/test_hybrid_generation_prompt.py`
  - `tests/api/test_regenerate_response_contract.py`

**Key tasks**
- Make finish sentence generation a first-class pipeline step in Python.
- Remove any hardcoded/duplicated finish lists across the repo; unify finish definitions in one module.
- Add validators for finish sentence quality:
  - No “designer finishes” boilerplate.
  - Must be product-specific (not generic one-liners).
  - Must not introduce unverified material/design claims.

**Verification commands**
- `.venv/bin/pytest -q tests/test_finish_injection.py tests/test_google_short_title_finish_injection.py`
- Add tests for “finish list correctness” and “no banned boilerplate.”

**Definition of done**
- `variant_finish_sentences` is always produced by Python and is stable across runs for the same evidence (unless prompt version changes).

---

## Phase 4 — Tier 1 Methodology Improvements (Search Alignment + Anti-Stuffing + Scoring)

**Objective:** Improve the *determinism* and *measurability* of title/description quality before scaling.

**What we are porting into Python**
The repo already has a Tier-1 plan drafted in TS form; we will implement the same intent in Python:
- `docs/plans/2026-02-10-content-generation-tier1-improvements.md`

**Key tasks**
- `DONE` Implement a deterministic per-SKU keyword plan derived from Search Query Insights:
  - Pick a title anchor phrase.
  - Pick 1–2 support terms for title.
  - Pick a small set of description terms.
- `DONE` Enforce keyword alignment via validation + auto-retry:
  - Titles can’t “look good” while missing the anchor.
  - Descriptions must include minimum term coverage *without stuffing*.
- `DONE` Add Bing anti-stuffing rules (prompt + validators).
- `DONE` Add competitive positioning guardrails:
  - Only allow comparisons when we have evidence (materials, warranties, capacities, etc.).
  - Ban speculative “better than competitors” language.
- `DONE` Recalibrate scoring so “high score” correlates with “search aligned + readable + policy-safe.”

**Verification commands**
- `.venv/bin/pytest -q tests/test_keyword_placement.py tests/test_quality.py tests/test_title_validators.py`
- Add new tests:
  - Keyword plan builder (anchor selection logic).
  - Keyword-alignment validator (title + description).
  - Bing anti-stuffing validator (slash/parenthetical dumps).

**Definition of done**
- We can run the SKU fixture set through generation and observe:
  - No keyword dumping.
  - Consistent anchor usage across titles.
  - Lower variance in quality scores (less score inflation).

---

## Phase 5 — Evidence Pipeline Upgrades (Keyword Gaps + Competitors + Gold Examples)

**Objective:** Give the model better evidence so it can differentiate and prioritize without guessing.

**Key tasks**
- Gold standard examples are injected into generator prompts (DONE; 2026-02-10; files: `src/feedops/api/prompt_loader.py`, `src/feedops/pipeline/generator.py`, `src/feedops/pipeline/prompts.py`; tests: `tests/test_prompt_loader.py`, `tests/test_pipeline.py`).
- `DONE` Add “keyword gap” evidence: high-volume terms missing from the current title (or missing from generated candidate). (2026-02-10; files: `src/feedops/pipeline/evidence.py`, `src/feedops/pipeline/keyword_gaps.py`, `tests/test_pipeline.py`)
- `DONE` Add competitor title pattern evidence for the product category:
  - Separate **direct competitors** (brand owners like Kingston Brass, Signature Hardware) from **marketplaces** (Wayfair, Amazon, Lowe’s, Houzz).
  - Use direct competitors for positioning patterns; use marketplaces mainly for query language and merchandising norms.
  - Safety rule enforced in row serialization: speculative comparative phrasing is dropped before prompt injection.
- Expand and diversify gold examples (`prompt_templates`) so examples cover:
  - Multiple styles (modern, transitional, traditional).
  - Multiple opening strategies (quality-first default, pain-point-first when natural).
  - Multiple categories (not just towel bars).

**Verification commands**
- `.venv/bin/pytest -q tests/test_evidence_multisize.py tests/test_pipeline.py`
- Add tests asserting:
  - Keyword gap evidence only includes terms relevant to the SKU category.
  - Competitor evidence never injects unverifiable claims.

**Definition of done**
- Evidence tables produced for fixture SKUs clearly show keyword plan + gaps + safe competitor context.

---

## Phase 6 — Dashboard Production Readiness (Review + Batch + Safety)

**Objective:** Make the dashboard safe, reliable, and fast for daily use by operators reviewing and publishing content.

**Executable subtasks (dashboard scope only)**
- `DONE` 6.0 Convert Phase 6 bullets into executable subtasks with code/test targets (this section).
- `DONE` 6.1 Idempotent regeneration state handling. (2026-02-10; files: `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/app/api/regenerate/batch/route.ts`, `dashboard/src/components/review/RegenerateButton.tsx`, `dashboard/src/components/review/BatchRegenerateButton.tsx`, `tests/api/test_dashboard_regenerate_route_contract.py`; verification: `cd dashboard && npm run lint` pass, `cd dashboard && npm run build -- --webpack` pass, `.venv/bin/pytest -q tests/api/test_regenerate_response_contract.py tests/api/test_dashboard_regenerate_route_contract.py` pass)
  - Target: `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/components/review/RegenerateButton.tsx`
  - Requirements:
    - No-op-safe retry when generated output equals current candidate content.
    - Explicit response state: `completed` | `failed` | `no_change`.
    - Return structured validation details for UI rendering.
  - Tests/verification: dashboard lint/build + API contract tests.
- `DONE` 6.2 Idempotent review/approval state handling. (2026-02-10; files: `dashboard/src/app/api/approvals/route.ts`, `dashboard/src/app/api/variants/approvals/route.ts`, `tests/api/test_dashboard_approval_state_contract.py`; verification: `cd dashboard && npm run lint` pass, `cd dashboard && npm run build -- --webpack` pass, `.venv/bin/pytest -q tests/api/test_dashboard_approval_state_contract.py tests/api/test_dashboard_regenerate_route_contract.py` pass)
  - Target: `dashboard/src/app/api/approvals/route.ts`, `dashboard/src/app/api/variants/approvals/route.ts`
  - Requirements:
    - Repeated approve/reject requests are no-op safe.
    - `approved_content`/`approved_version` only change on state transition (not duplicate requests).
    - Actionable API errors when required source content is missing.
  - Tests/verification: dashboard lint/build + relevant approval tests.
- `DONE` 6.3 Idempotent publish state handling + RBAC guard. (2026-02-10; files: `dashboard/src/lib/auth/publish-guard.ts`, `dashboard/src/app/api/publish/sku/route.ts`, `dashboard/src/app/api/publish/batch/route.ts`, `tests/api/test_dashboard_publish_safety_contract.py`; verification: `cd dashboard && npm run lint` pass, `cd dashboard && npm run build -- --webpack` pass, `.venv/bin/pytest -q tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py` pass)
  - Target: `dashboard/src/app/api/publish/sku/route.ts`, `dashboard/src/app/api/publish/batch/route.ts`, shared auth helper(s)
  - Requirements:
    - Repeat publish calls for already-published same content return idempotent success/no-op.
    - Publishing routes return actionable failure codes/messages.
    - Publishing endpoints enforce configurable role-based guardrails.
  - Tests/verification: dashboard lint/build + publish-related Python tests.
- `DONE` 6.4 Batch safety and retry semantics. (2026-02-10; files: `dashboard/src/app/api/publish/batch/route.ts`, `dashboard/src/app/api/batches/route.ts`, `dashboard/src/app/(dashboard)/batches/page.tsx`, `dashboard/src/app/(dashboard)/batches/[batchId]/page.tsx`, `dashboard/src/components/batches/BatchesClient.tsx`, `dashboard/src/components/batches/BatchDetailClient.tsx`, `dashboard/src/lib/supabase/types.ts`, `dashboard/src/lib/supabase/queries.ts`, `tests/api/test_dashboard_batch_readiness_contract.py`; verification: `cd dashboard && npm run lint` pass, `cd dashboard && npm run build -- --webpack` pass, `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py` pass)
  - Target: `dashboard/src/app/api/batches/route.ts`, `dashboard/src/components/batches/BatchesClient.tsx`, `dashboard/src/components/batches/BatchDetailClient.tsx`, `dashboard/src/lib/supabase/types.ts`
  - Requirements:
    - Consistent batch status model (`draft/pending/executing/published/partial/failed`) across API + UI.
    - Safe retry path for failed/partial batches without duplicate success writes.
    - Per-SKU failure reason visibility in batch detail.
  - Tests/verification: dashboard lint/build.
- `DONE` 6.5 Validation and policy errors surfaced clearly in UI/API. (2026-02-10; files: `dashboard/src/app/api/regenerate/route.ts`, `dashboard/src/app/api/regenerate/batch/route.ts`, `dashboard/src/components/review/RegenerateButton.tsx`, `dashboard/src/components/review/BatchRegenerateButton.tsx`, `dashboard/src/components/batches/BatchesClient.tsx`, `dashboard/src/components/batches/BatchDetailClient.tsx`, `tests/api/test_dashboard_validation_surface_contract.py`; verification: `cd dashboard && npm run lint` pass, `cd dashboard && npm run build -- --webpack` pass, `.venv/bin/pytest -q tests/api/test_dashboard_batch_readiness_contract.py tests/api/test_dashboard_publish_safety_contract.py tests/api/test_dashboard_approval_state_contract.py tests/api/test_dashboard_regenerate_route_contract.py tests/api/test_dashboard_validation_surface_contract.py tests/test_review_dashboard.py tests/test_reporter_google_patch_structured_only_env.py` pass)
  - Target: review and batch UI components + API response payloads.
  - Requirements:
    - UI renders human-actionable remediation text from API errors (not generic “failed” alerts).
    - Policy/validation violations are explicit in API payloads and visible to operators.
    - No prompt-source changes; Python remains generation authority.
  - Tests/verification: dashboard lint/build + `tests/test_reporter_google_patch_structured_only_env.py`.

**Verification commands**
- Dashboard: `cd dashboard && npm run lint && npm run build`
- Python: `.venv/bin/pytest -q tests/test_review_dashboard.py tests/test_reporter_google_patch_structured_only_env.py`

**Definition of done**
- An operator can safely:
  - Regenerate content.
  - Review + approve.
  - Publish a batch.
  - Understand why something failed and how to fix it.

---

## Phase 7 — Observability, Reliability, And Performance

**Objective:** Production-hardening so we can scale without silent failures or “mystery regressions.”

**Key tasks**
- Add structured logs and request IDs for every generation call.
- Emit metrics (counts, latency, retry rate, validation-failure rate, provider error rate).
- Add circuit breakers / backoff for provider rate limits.
- Add a “kill switch” configuration:
  - Disable generation.
  - Disable finish sentence regeneration.
  - Force fallback behavior when providers are down.

**Execution updates**
- `DONE` 7.1 Structured request-scoped logging + request ID propagation.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Files: `src/feedops/observability/__init__.py`, `src/feedops/api/main.py`, `src/feedops/providers/factory.py`, `src/feedops/api/hybrid_generation.py`, `tests/test_phase7_observability_reliability.py`.
  - Notes:
    - Added HTTP request middleware assigning/propagating `X-Request-ID`.
    - Added structured JSON log events with request context across generation/provider/fallback paths.
    - Background generation threads inherit request IDs.
  - Verification: `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py` (pass).
- `DONE` 7.2 Reliability metrics (latency, retries, validation failures, provider errors).
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Files: `src/feedops/observability/metrics.py`, `src/feedops/api/main.py`, `src/feedops/api/hybrid_generation.py`, `src/feedops/providers/openai_provider.py`, `src/feedops/providers/gemini_provider.py`, `tests/test_phase7_observability_reliability.py`.
  - Notes:
    - Added in-memory metrics registry with counters/timers.
    - Instrumented provider latency/retry/error metrics.
    - Instrumented generation latency and finish sentence validation-failure metrics.
  - Verification: `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py tests/test_providers.py` (pass).
- `DONE` 7.3 Provider backoff + circuit breaker hardening.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Files: `src/feedops/providers/reliability.py`, `src/feedops/providers/openai_provider.py`, `src/feedops/providers/gemini_provider.py`, `tests/test_phase7_observability_reliability.py`.
  - Notes:
    - Added retryable-error classification, exponential backoff, and process-wide circuit breaker registry.
    - Added circuit-open protection + metrics/logging.
  - Verification: `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py::test_openai_provider_applies_backoff_on_retryable_error tests/test_phase7_observability_reliability.py::test_openai_provider_circuit_breaker_blocks_after_threshold` (pass).
- `DONE` 7.4 Kill switches and fallback control.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Files: `src/feedops/api/runtime_controls.py`, `src/feedops/api/main.py`, `src/feedops/api/hybrid_generation.py`, `src/feedops/providers/factory.py`, `tests/test_phase7_observability_reliability.py`, `tests/test_providers.py`.
  - Notes:
    - Added generation kill switch for optimize/regenerate/batch/hybrid APIs.
    - Added finish-sentence regeneration kill switch for regenerate + variant adaptation flows.
    - Added fallback force-toggle to instantiate provider chain when both providers are available.
  - Verification: `.venv/bin/pytest -q tests/test_phase7_observability_reliability.py tests/test_providers.py` (pass).
- `DONE` 7.5 Generation-path parity fix (Generate + Hybrid == Regenerate finish handling).
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - SKU verification target: `SB-16`.
  - Routes/code paths touched:
    - `POST /optimize-sku` full generation path.
    - `process_hybrid_batch_job` full-generation branch (`generate_full_content`).
    - `POST /regenerate` kept aligned through shared parity helper.
    - Hybrid variant adaptation path (`adapt_variant_content`) for sanitization parity.
  - Files: `src/feedops/api/main.py`, `src/feedops/api/hybrid_generation.py`, `src/feedops/pipeline/finish_sentence_placeholder.py`, `tests/test_phase7_observability_reliability.py`.
  - What was fixed:
    - Added shared parity helper that enforces Google/Bing description finish flow:
      - strips generic finish-count claims from base description;
      - generates + validates canonical finish sentences (28);
      - injects `{FINISH_SENTENCE}` exactly once when complete.
    - Wired helper into full Generate and Hybrid full-generation flows.
    - Persisted `variant_finish_sentences` for Generate and Hybrid full-generation descriptions.
    - Kept `generation_model` + `generation_prompt_hash` writes unchanged in `generated_content`.
  - Metadata/traceability fields checked (live):
    - `generated_content.generation_model`
    - `generated_content.generation_prompt_hash`
    - `generated_content.generation_timestamp/updated_at`
    - `variant_finish_sentences.finish_sentences` (count == 28 for Google + Bing)
    - `regeneration_history.prompt_hash`, `regeneration_history.model_version` (existing SB-16 rows confirmed intact)
  - Validation run:
    - `.venv/bin/pytest -q` → `398 passed, 1 skipped`.
    - `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` → `SUPABASE_CANARY_OK`, dashboard lint/build `OK`.
    - Live SB-16 checks:
      - `google_description` and `bing_description` contain `{FINISH_SENTENCE}` exactly once.
      - No `available in 28 designer finishes` phrase remained in final base descriptions.
      - `variant_finish_sentences` persisted with 28 entries for Google and Bing.
- `DONE` 7.6 Shopify generation-path alignment + cross-platform linkage hardening.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - SKU verification target: `SB-16`.
  - Routes/code paths touched:
    - `POST /optimize-sku` (full generation persistence + linkage).
    - `process_batch_job` (full generation persistence + linkage).
    - `process_hybrid_batch_job` full-generation branch (`generate_full_content`) (full generation persistence + linkage).
    - `POST /regenerate` (now attempts `generated_content_id` linkage when a row exists).
    - Hybrid variant adaptation prompt builder for Shopify descriptions (`build_variant_adaptation_prompt`).
  - Files: `src/feedops/api/main.py`, `src/feedops/api/hybrid_generation.py`, `tests/test_phase7_observability_reliability.py`.
  - What was fixed:
    - Added canonical helper to persist `generated_content` and immediately write linked `regeneration_history` with:
      - `generated_content_id`
      - `model_version`
      - `prompt_hash`
      - truncated `system_prompt` / `user_prompt`
      - `mode="full_generation"`.
    - Wired helper into all full-generation paths so linkage is consistent across Google/Bing/Shopify.
    - Added best-effort `generated_content_id` linkage in `/regenerate` history writes.
    - Fixed Shopify hybrid adaptation prompt drift: `shopify/description` now uses description-specific adaptation instructions (no title fallback), including explicit finish-agnostic guardrail.
  - Metadata/traceability fields checked (live):
    - `generated_content.generation_model`
    - `generated_content.generation_prompt_hash`
    - `regeneration_history.generated_content_id`
    - `regeneration_history.model_version`
    - `regeneration_history.prompt_hash`
    - `variant_finish_sentences.finish_sentences` cardinality for Google/Bing.
  - Validation run:
    - `.venv/bin/pytest -q` → `401 passed, 1 skipped`.
    - `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` → `SUPABASE_CANARY_OK`, dashboard lint/build `OK`.
    - Live `SB-16` checks:
      - Google/Bing descriptions contain `{FINISH_SENTENCE}` exactly once.
      - Google/Bing base descriptions do not contain prohibited generic finish-count claims.
      - Google/Bing `variant_finish_sentences` persisted with 28 entries each.
      - Shopify title/description generated and persisted with prompt/model metadata.
      - All six full-generation rows (Google/Bing/Shopify × title/description) have linked `regeneration_history.generated_content_id`.

### 2026-02-11 Hybrid Counter Remediation Verification Log (UTC)

- Timestamp window: `2026-02-11 17:42:00Z` to `2026-02-11 18:03:00Z`.
- SKUs used: `SB-16`, `1031/30`.
- Routes touched:
  - Cloud Run: `POST /hybrid-generate`, `GET /batch-status/{job_id}`, `GET /health`, `POST /optimize-sku` (dry run), `POST /regenerate`.
  - Dashboard: `/generate` (`Generate` and `Past Jobs` tabs), `/login`.
- Metadata fields checked:
  - `batch_generation_jobs.total_skus`, `batch_generation_jobs.completed_skus`, `batch_generation_jobs.failed_skus`.
  - `batch_generation_jobs.options.expanded_total_skus`, `batch_generation_jobs.options.expanded_completed_skus`, `batch_generation_jobs.options.expanded_failed_skus`.
- Test and canary outputs:
  - `.venv/bin/pytest -q` -> `436 passed, 1 skipped`.
  - `RUN_SUPABASE_CANARY=1 bash scripts/verify_phase_0.sh` -> `SUPABASE_CANARY_OK` and dashboard lint/build `OK`.
- Deployment verification results:
  - Cloud Build `4f1e9034-22a6-4504-9422-eb3f9eb10696` -> `SUCCESS`.
  - Active Cloud Run image: `gcr.io/bobbys-project-346400/feedops-pipeline:1b2dd79d2252757b951e7ce5f184bab6bd55c412`.
- Live hybrid job `38c55dae-8b43-47cd-a3e5-06c92cf7ca78` completed with requested `2/2` and expanded `3/3`, no requested-counter overflow.

### 2026-02-11 Review Queue Blocker Remediation (UTC)

- Timestamp window: `2026-02-11 18:10:00Z` to `2026-02-11 19:05:00Z`.
- Objective: clear active review blockers without legacy tagging or broad destructive cleanup.
- SKUs audited as blockers: `1031/18`, `1031/24`, `1031/30`, `1031/36`, `CL-28-30`, `WP-2TB-16-GAL`.
- Routes/processes touched:
  - Cloud Run: `POST /regenerate` (targeted bing title/description regeneration only for required SKUs).
  - Supabase data maintenance: deterministic row updates/copies for alias normalization (`WP-2TB/16-GAL` -> `WP-2TB-16-GAL`) and placeholder cleanup.
- Metadata and policy fields checked:
  - Readiness: review queue strict policy checks (`google_missing_finish_sentence_placeholder`, `google_missing_finish_sentence_rows`, `shopify_title_has_brand`, slot completeness).
  - Variant data: `variant_finish_sentences` row presence/cardinality for Google/Bing descriptions.
  - Regeneration metadata on successful calls: `model`, `prompt_hash`, `finish_sentences_count`.
- Evidence artifacts:
  - Before audit: `/private/tmp/review_quality_audit_current.json` (`strict_ready=86`, `not_ready=6` on `active_review_skus=92`).
  - Remediation plan split: `/private/tmp/review_quality_remediation_plan.json` (`db_only=1`, `regeneration_required=5`).
  - Targeted regeneration results: `/private/tmp/review_quality_targeted_regen_round2.json` (`total=14`, `ok=8`, `failed=6`), where all six failures were `404 SKU not found` for alias `WP-2TB-16-GAL`.
  - After audit: `/private/tmp/review_quality_audit_current_after.json` (`strict_ready=92`, `not_ready=0` on `active_review_skus=92`).
- Deterministic fixes applied (no model calls):
  - `CL-28-30` Shopify description placeholder cleanup to remove finish placeholder drift in base content.
  - `WP-2TB-16-GAL` alias normalization by copying canonical slash-SKU content/finish-sentence rows from `WP-2TB/16-GAL`.
- Regeneration results summary:
  - `1031/18`, `1031/24`, `1031/30`, `1031/36`: bing title+description regenerated successfully.
  - All regenerated bing descriptions recorded `finish_sentences_count=28`.
  - No blocker required broad backfill; only targeted repairs/regeneration were used.
- Outcome:
  - Active review queue strict-ready quality moved from `86/92` to `92/92`.
  - Remaining blockers in active review queue: `0`.
  - Legacy tagging/UI badge work was intentionally deferred in favor of canonical data correctness.

**Runtime toggles (safe defaults)**
- `FEEDOPS_DISABLE_GENERATION` (default: unset/`false`): when `true`, generation endpoints return `503` and background generation is not started.
- `FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN` (default: unset/`false`): when `true`, finish-sentence generation/adaptation paths are skipped.
- `FEEDOPS_FORCE_PROVIDER_FALLBACK` (default: unset/`false`): when `true` and both API keys are set, provider factory returns primary+fallback chain.
- `FEEDOPS_PROVIDER_CIRCUIT_BREAKER_ENABLED` (default: `true`): enables provider circuit protection.
- `FEEDOPS_PROVIDER_CIRCUIT_FAILURE_THRESHOLD` (default: `5`): consecutive failed requests before circuit opens.
- `FEEDOPS_PROVIDER_CIRCUIT_COOLDOWN_SECONDS` (default: `30`): circuit-open cooldown window.
- `FEEDOPS_PROVIDER_BACKOFF_BASE_SECONDS` (default: `0.25`), `FEEDOPS_PROVIDER_BACKOFF_MAX_SECONDS` (default: `8`), `FEEDOPS_PROVIDER_BACKOFF_JITTER_SECONDS` (default: `0.1`): retry backoff tuning.

**Verification commands**
- `.venv/bin/pytest -q`
- Load test (phase plan should define a safe local load test that does not hit real providers; use mocks).

**Definition of done**
- We can detect regressions quickly and roll back by prompt version or config toggles.

---

## Phase 8 — Scale-Up Runbook (72k SKUs)

**Objective:** Execute the scale-up in a controlled, reviewable way.

**Implementation status**
- `DONE` 8.1 Concrete batch sizing strategy.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Output: `docs/plans/2026-02-11-phase8-72k-scale-up-runbook.md` section `1) Concrete Batch Sizing Strategy`.
  - Notes:
    - Encodes hard API cap (`100` SKUs/job) and wave progression (`2` dry-run -> `25` pilot -> `100` steady-state).
    - Uses observed throughput sample from live validated run (`~1.55 SKU/min`) for capacity planning.
- `DONE` 8.2 Operator runbook for generate -> review -> publish.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Output: `docs/plans/2026-02-11-phase8-72k-scale-up-runbook.md` section `2) Operator Runbook (Generate -> Review -> Publish)`.
  - Notes:
    - Steps are mapped to current API routes and Supabase tables.
    - Includes exact commands and expected outcomes for each stage.
- `DONE` 8.3 Stop-condition thresholds and rollback instructions.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Output: `docs/plans/2026-02-11-phase8-72k-scale-up-runbook.md` section `3) Stop Conditions and Rollback Instructions`.
  - Notes:
    - Threshold checks use row-level status data (`batch_generation_job_skus`) and `publish_events` to avoid counter drift issues.
    - Rollback path references existing CLI (`feedops rollback`) and publish event snapshots.
- `DONE` 8.4 Dry-run and spot-check verification commands.
  - Date: `2026-02-11`; owner/model: `Codex GPT-5`.
  - Output: `docs/plans/2026-02-11-phase8-72k-scale-up-runbook.md` section `4) Dry-Run and Spot-Check Verification Bundle`.
  - Notes:
    - Every listed command was executed at least once in this environment.
    - Includes explicit expected outcomes for pass/fail triage.

**Definition of done**
- A documented and command-validated process exists to progress from 1 -> 72,000 SKUs with explicit stop/rollback controls and no ad-hoc operational steps.

---

## Optional: JavaScript Test Runner (Vitest vs Jest)

If we keep meaningful non-trivial logic in the dashboard (beyond rendering + proxying), add a JS unit test runner.

Recommendation: **Vitest** for fast unit tests of pure TS helpers (validators, formatters). If we need deeper Next.js integration tests, consider Jest + `next/jest`.

We will decide this in Phase 0 based on how much logic remains in the dashboard after Phase 2.
