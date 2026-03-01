# Generation Change Checklist

Use this checklist for every generation-affecting branch before merge.

## Branch Hygiene

- `git fetch origin --prune`
- `git switch master`
- `git pull --ff-only origin master`
- create a fresh `codex/<topic>-<yyyymmdd>` branch or worktree
- run `scripts/dev_session_preflight.sh`

## Source Review

- identify the affected route or routes
- identify the intended task graph
- identify the prompt-building path
- identify the persistence path
- identify the dashboard readback path

## Host Verification

- compile touched Python modules
- run targeted tests for the change
- run required generation regression suite
- add a failing regression test first when fixing a bug

## Required Generation Regression Suite

- `tests/test_generation_runtime_scope_contract.py`
- `tests/test_hybrid_generation_parity.py`
- `tests/api/test_hybrid_generation_telemetry_contract.py`
- `tests/test_cloud_run_parity.py`
- `tests/test_runtime_env_contract.py`
- `tests/test_env_parity.py`
- `tests/test_finish_sentence_validation.py`
- `tests/test_finish_injection.py`
- `tests/api/test_dashboard_regenerate_route_contract.py`
- `tests/api/test_regenerate_response_contract.py`
- `tests/api/test_main_master_sku_alias_runtime.py`

## Container Certification

- run `ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh`
- inspect `summary.json`
- inspect `container.log`
- confirm container behavior matches intended task graph

## Live Certification

- choose the correct deploy mode before certifying:
  - pre-PR exact-branch certification: `scripts/deploy_tagged_revision.sh <revision-tag>`
  - post-merge production deploy: GitHub-connected Cloud Build on `origin/master`
- deploy the exact tested commit to Cloud Run
- capture image ref and Cloud Run revision
- capture Cloud Build ID only when the post-merge production path is used
- record the deploy mode in the report
- run the six-scenario certification matrix

### Required live scenarios

1. single Google title-only
2. single Google description-only
3. batch Google title-only
4. batch Google description-only
5. hybrid Google title-only
6. hybrid Google description-only

## Supabase Proof

Verify fresh rows in:

- `generated_content`
- `regeneration_history`
- `variant_finish_sentences`
- `batch_generation_jobs`
- `batch_generation_job_skus`

## Prompt Lineage Proof

- run the prompt lineage audit against the fresh live request IDs
- verify every provider-backed prompt row matches source exactly
- include finish generation rows

## Dashboard Proof

- log into the dashboard with the automation user
- verify review-page readback for the proof SKUs
- confirm visible content matches fresh persisted rows
- confirm no unintended placeholder leaks

## Documentation Gate

- update the dated experiment report
- record commit SHA
- record deploy mode
- record image ref
- record Cloud Run revision
- record Cloud Build ID when applicable
- record request IDs and job IDs
- record final GO/NO-GO decision

## Merge Blockers

Do not merge if any of the following are true:

- host and container differ
- container and Cloud Run differ
- Cloud Run and Supabase differ
- Supabase and dashboard readback differ
- prompt lineage cannot be proven
- runtime still depends on legacy hardcoded pipeline URLs
