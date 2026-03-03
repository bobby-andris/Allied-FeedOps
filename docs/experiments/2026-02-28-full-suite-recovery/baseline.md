# Full Suite Recovery Baseline

- Date: 2026-02-28
- Repo: /Users/bobby/Documents/GitHub/Allied-FeedOps
- Branch: codex/e245-full-suite-recovery-20260228
- Base SHA: dc041ed1
- Master SHA: dc041ed1
- Origin/master SHA: dc041ed1

## Commands

```bash
PYTHONPATH=src uv run --frozen --extra dev pytest -q
./scripts/verify_cloud_run_parity.sh
```

## Objective

- Restore full-suite health to 0 failures and 0 warnings.
- Preserve parity subset pass for Cloud Run deploy contract.

## Recovery Validation (2026-02-28)

- `PYTHONPATH=src uv run --frozen --extra dev pytest -q`
  - `653 passed, 1 skipped in 35.94s`
- `./scripts/verify_cloud_run_parity.sh`
  - `52 passed in 5.12s`

Artifacts:

- `docs/experiments/2026-02-28-full-suite-recovery/artifacts/full-pytest-baseline.txt` (original failing baseline)
- `docs/experiments/2026-02-28-full-suite-recovery/artifacts/full-pytest-recovery.txt` (post-fix recovery run)
