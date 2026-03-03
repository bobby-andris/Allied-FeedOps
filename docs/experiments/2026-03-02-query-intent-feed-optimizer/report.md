# 2026-03-02 Query-Intent Feed Optimizer V1 Certification Recovery

## Summary

This report closes the prior NO-GO by completing the missing operational evidence and validating the same tested code path across source, host tests, local container runtime, deployed Cloud Run runtime, Supabase lineage, and dashboard readback.

Release decision in this report: **GO (controlled rollout)**.

## Scope And Intent

- Feature under test: Query-Intent Feed Optimizer V1 (`QUERY_INTENT_BRIEF_V1`)
- Runtime contract: additive, bounded query-intent brief for Google/Bing title+description only
- Non-negotiables preserved:
  - no public route contract changes
  - no new task kinds
  - no provider-backed subcall widening
  - no dashboard routing bypass of `FEEDOPS_PIPELINE_URL`
  - prompt lineage persistence maintained

## Root Cause Closure

The prior blocking NO-GO condition was an operational verification gap (not a functional regression in query-intent behavior). This pass completed the previously missing certification layers and hardened persistence parity checks used by smoke workflows.

### Hardening implemented

- Updated parity verifier:
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/scripts/verify_generation_persistence_parity.py`
- Outcome:
  - verifier now reconciles prompt/persistence correctly for superseded rows and candidate/approved content evolution
  - avoids false negatives from later overwrites in repeated smoke cycles

## Tested Source Revision And Deployment

- Branch: `codex/go-recovery-hardening-20260302`
- Commit SHA tested/deployed: `a88331fedb455802a66cb9fb6bdb4a67874d158e`
- Image ref:
  - `us-east1-docker.pkg.dev/bobbys-project-346400/cloud-run-source-deploy/feedops-pipeline:a88331fedb455802a66cb9fb6bdb4a67874d158e-amd64`
- Cloud Run revision:
  - `feedops-pipeline-00299-gap`
- Tagged revision URL:
  - `https://cert-qi-v1-20260302---feedops-pipeline-3b43yg32oa-ue.a.run.app`

## Verification Evidence

## 1) Host tests

Command set (required suite + query-intent tests) executed via project venv.

Result:
- `113 passed`

## 2) Local container smoke (flag OFF)

Command:

```bash
VERIFY_PERSISTENCE_PARITY=1 ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh
```

Artifacts:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-generation-core-simplification/container-smoke/20260302-081433/summary.json`

Result:
- all six scenarios `200`
- persistence parity PASS

## 3) Local container smoke (flag ON)

Command:

```bash
VERIFY_PERSISTENCE_PARITY=1 ENV_FILE=<temp_overlay_with_QUERY_INTENT_BRIEF_V1=1> PORT=18080 scripts/container_generation_smoke.sh
```

Artifacts:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-generation-core-simplification/container-smoke/20260302-081709/summary.json`

Result:
- all six scenarios `200`
- persistence parity PASS
- positive and self-disable paths both observed as designed

## 4) Cloud Run six-scenario certification (flag ON)

Artifacts:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/cloud-run-smoke/20260302-082314/summary.json`

Request IDs and job IDs:

1. `single-google-title`
   - request_id: `1b61fbf0-47c6-4c06-a964-8684a7251a1d`
2. `single-google-description`
   - request_id: `0182f817-726b-469c-9b79-78bfd28d8c3e`
3. `batch-google-title`
   - request_id: `4f653caf-fead-4e36-bfbf-b02945e1432b`
   - job_id: `d35d3ff8-0c58-4097-8fda-67e634af9592`
4. `batch-google-description`
   - request_id: `2d72ff98-0813-4567-b918-16a90263f6ec`
   - job_id: `5a0047ac-44cd-48b3-b5d3-2e9f21c526bd`
5. `hybrid-google-description`
   - request_id: `1f5f23a8-64a9-4145-9c5c-e4fb77595fc4`
   - job_id: `fa33e7ab-7f12-499b-8745-4d91f35054a8`
6. `hybrid-google-title`
   - request_id: `1b646959-6cc8-4a32-b102-226d9f47c9da`
   - job_id: `e9e88d2b-6847-4a1b-8525-f67ff2339c14`

Result:
- all scenarios `200`
- no task graph widening observed

## 5) Supabase lineage proof

Dashboard API readback artifacts (fresh live rows):
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/cl55-cloudrun-proof.json`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/1033-18-cloudrun-proof.json`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/1033-24-cloudrun-proof.json`

Key checks:

- `CL-55` (positive path):
  - `QUERY_INTENT_BRIEF_V1=true`
  - `query_intent_brief_enabled=true`
  - `query_intent_data_sufficiency=true`
  - `query_intent_source_query_count=120`
  - prompt hashes present per provider-backed row
- `1033/18` (self-disable path):
  - `QUERY_INTENT_BRIEF_V1=true`
  - `query_intent_disabled_reason=no_master_queries`
  - `query_intent_source_query_count=0`
  - no forced brief injection
- `1033/24` (variant adaptation path):
  - model version `deterministic-variant-adapter`
  - no hidden provider-backed base regeneration behavior introduced

## 6) Dashboard readback proof (UI + API)

Artifacts:
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/cl55-review-history.png`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/1033-18-review-history.png`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/1033-24-alias-review-history.png`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/alias-route-url.txt`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/dashboard-readback/20260302-082951/alias-route-heading.txt`

Confirmed:
- Review pages load and display fresh regeneration history rows matching cloud-run request windows.
- Alias route `/review/1033-24` resolves to SKU heading `1033/24`.
- API readback rows match persisted Supabase lineage for certified request IDs.

## 7) Production rollout execution (post-certification)

Traffic cutover:

- Service URL: `https://feedops-pipeline-3b43yg32oa-ue.a.run.app`
- Latest ready revision: `feedops-pipeline-00299-gap`
- Final traffic state: `100%` to `feedops-pipeline-00299-gap`

Post-cutover smoke artifacts:

- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/production-rollout-smoke/20260302-090013/summary-final.json`
- `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/production-rollout-smoke/20260302-090013/hybrid-rerun-summary.json`

Post-cutover request IDs / job IDs:

1. `single-google-title`
   - request_id: `67e39e76-a750-4720-b940-2e14c804265b`
2. `single-google-description`
   - request_id: `4886deaf-aefc-4e7a-960b-02a9b8c0afcd`
3. `batch-google-title`
   - request_id: `4a5db85b-2fe2-4bda-8e3c-32c74a5567c8`
   - job_id: `648cf0b3-7f31-4236-a2eb-1561b5680098`
4. `batch-google-description`
   - request_id: `bb3539b0-2347-4792-b3bf-a4ec777067c3`
   - job_id: `e66163c1-b76e-4815-a3b5-c30ee3c99bfd`
5. `hybrid-google-description`
   - request_id: `31a0ae83-a11e-4fdd-bf83-d10270393322`
   - job_id: `31268417-92a8-4114-a942-856edf9e1cb8`
6. `hybrid-google-title`
   - request_id: `509848ae-a320-46b8-b60c-f9d22b855e76`
   - job_id: `f042e22a-6663-4a5b-bb1e-c9090e9d74ec`

Parity verification:

- Command:
  - `python3 scripts/verify_generation_persistence_parity.py --env-file .env.vercel /Users/bobby/Documents/GitHub/Allied-FeedOps/docs/experiments/2026-03-02-query-intent-feed-optimizer/production-rollout-smoke/20260302-090013`
- Result:
  - `Parity check passed for 9 request artifact(s)`

Note:
- Initial post-cutover hybrid calls returned `422` due a malformed verifier payload (missing required `options` object for `/hybrid-generate`), not a runtime regression.
- Hybrid scenarios were immediately rerun with contract-correct payload and passed (`200` with completed jobs).

## Revenue-Oriented Output Analysis (Unbiased)

Sampled generated copy from certified runs and OFF/ON comparison (CL-55):

- Titles improved toward higher-intent phrasing by explicitly foregrounding `paper towel holder` and freestanding/countertop utility.
- Descriptions improved demand-match language (e.g., `freestanding paper towel holder`, `brass paper towel holder`, `under cabinet paper towel holder` as comparative anchor) while preserving factual grounding.
- Self-disable behavior correctly avoided forcing query-intent language on low-signal SKU family (`1033/18`), reducing risk of unnatural copy.

Commercial judgment:

- These outputs are **more likely** to improve qualified traffic capture for Shopping/PMax/Bing than the non-intent baseline, especially where query data is strong (CL-55 pattern).
- They are not keyword-stuffed and remain readable enough for conversion-stage trust.
- There are still occasional phrasing opportunities to tighten elegance/readability, but no blockers were found that would justify withholding launch.

Net: expected directional lift in CTR and query-match coverage is positive; CVR risk appears low due to preserved factuality and compliance guardrails.

## Residual Risks

1. Revenue impact is still a forward hypothesis until post-publish performance accrues.
2. Some generated long descriptions can become verbose; readability tuning should continue via offline rubric review.
3. Low-signal SKUs remain dependent on self-disable behavior quality (already validated in this run).

## GO / NO-GO Decision

## **GO (controlled rollout)**

Rationale:
- source/host/local/deployed/persistence/dashboard layers are all aligned on the same tested commit/revision
- no unexplained divergence remains
- feature behaves correctly on both activation and self-disable paths
- task-model and prompt-lineage invariants remained intact throughout certification

## Recommended Next Steps

1. Roll out `QUERY_INTENT_BRIEF_V1` to production traffic in stages:
   - start with top paid-converting SKUs (CL-55-like signal profile)
   - keep self-disable thresholds unchanged during first window
2. Run a two-week paid impact checkpoint:
   - compare CTR, CVR, and revenue per click vs pre-window baseline on matched SKU cohorts
3. Queue a V1.1 copy refinement pass:
   - tighten verbosity in long descriptions while preserving natural keyword coverage
4. Keep persistence parity checks enabled in smoke/cert workflows to prevent future false NO-GO from supersession effects.
