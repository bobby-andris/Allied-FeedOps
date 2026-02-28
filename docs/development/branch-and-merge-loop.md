# Branch And Merge Loop

## Goal
Keep development predictable: every change starts from synced `master`, lands on a single feature branch, and merges back cleanly.

## Start A New Work Session
```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps
git fetch origin --prune
git switch master
git pull --ff-only origin master
git switch -c codex/<topic>-<yyyymmdd>
scripts/dev_session_preflight.sh
```

## During Development
1. Keep scope limited to one branch/PR.
2. Run targeted tests early, then full required suites before merge.
3. Commit logically grouped changes with clear messages.

## Pre-Merge Checklist
```bash
git status -sb
scripts/dev_session_preflight.sh
```

Run required suites for this project phase:
```bash
PYTHONPATH=src uv run --frozen --extra dev pytest -q \
  tests/api/test_dashboard_regenerate_route_contract.py \
  tests/api/test_main_master_sku_alias_runtime.py \
  tests/api/test_regenerate_response_contract.py \
  tests/test_cloud_run_parity.py \
  tests/test_runtime_env_contract.py \
  tests/test_env_parity.py
```

## Merge And Reset Loop
```bash
git push -u origin codex/<topic>-<yyyymmdd>
# open PR, review, merge
git switch master
git pull --ff-only origin master
# optional cleanup
git branch -d codex/<topic>-<yyyymmdd>
git push origin --delete codex/<topic>-<yyyymmdd>
```

## Invariants
1. No implementation commits on `master`.
2. No stale-branch development after `master` moves.
3. No skipped preflight.
4. No merge without passing required tests for the active phase.
