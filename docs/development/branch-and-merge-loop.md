# Branch And Merge Loop

## Goal
Keep development predictable: every change starts from synced `master`, lands on a single feature branch, and merges back cleanly.

## Canonical Generation References

For generation-affecting work, this loop must be used together with:

1. `AGENTS.md`
2. `docs/architecture/generation-runtime-truth.md`
3. `docs/architecture/generation-core-task-model.md`
4. `docs/development/generation-change-checklist.md`
5. `docs/operations/deploy-and-certify-generation.md`

## Start A New Work Session
```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
git fetch origin --prune
git switch master
git pull --ff-only origin master
scripts/dev_session_preflight.sh
git switch -c codex/<topic>-<yyyymmdd>
```

## During Development
1. Keep scope limited to one branch/PR.
2. Run targeted tests early, then full required suites before merge.
3. Commit logically grouped changes with clear messages.
4. For generation changes, no merge is allowed without source review, container proof, Cloud Run proof, Supabase proof, and dashboard readback proof.

## Pre-Merge Checklist
```bash
git status -sb
scripts/dev_session_preflight.sh
```

Run required suites for this project phase:
```bash
PYTHONPATH=src uv run --frozen --extra dev pytest -q \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_dashboard_generation_routes_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/api/test_regenerate_response_contract.py \
  tests/test_cloud_run_parity.py \
  tests/test_generation_runtime_scope_contract.py \
  tests/test_runtime_env_contract.py \
  tests/test_env_parity.py
```

For generation-affecting work, also run:
```bash
ENV_FILE=.env.vercel PORT=18080 scripts/container_generation_smoke.sh
```

Then capture the deployed Cloud Run revision and certify the required live scenarios before merge.

## Merge And Reset Loop
```bash
git push -u origin codex/<topic>-<yyyymmdd>
# open PR, review, merge
git switch master
git pull --ff-only origin master
# cleanup after verifying the branch is merged
git branch -d codex/<topic>-<yyyymmdd>
git push origin --delete codex/<topic>-<yyyymmdd>
```

## Invariants
1. No implementation commits on `master`.
2. No stale-branch development after `master` moves.
3. No skipped preflight.
4. No merge without passing required tests for the active phase.
5. No generation-affecting merge without a dated experiment report and explicit evidence links.
