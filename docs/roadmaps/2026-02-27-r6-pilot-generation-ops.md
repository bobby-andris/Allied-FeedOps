# R6 Pilot Generation Ops (Flagged Canary)

## Objective
Start real production usage with strict risk controls by limiting generation and publish operations to an explicit pilot SKU cohort.

## Cohort and Scope
1. Cohort size: 20 master SKUs.
2. Include:
   - single-SKU flows (including `CL-55`)
   - hybrid family flows (including `1033` family).
3. Platforms: begin with Google only for first checkpoint window.
4. Modes: simple + with_feedback, async enabled where appropriate.

## Runtime Controls
The following env vars control the pilot gate:
1. `FEEDOPS_PILOT_CANARY_ENABLED` (`1`/`0`)
2. `FEEDOPS_PILOT_ALLOWED_SKUS` (comma-separated master SKU allowlist)
3. `FEEDOPS_PILOT_FAIL_CLOSED` (`1`/`0`, default recommended `1`)

When enabled, these routes enforce allowlist gating:
1. `POST /api/regenerate`
2. `POST /api/publish/sku`
3. `POST /api/publish/batch`

Monitoring endpoint:
1. `GET /api/monitoring/pilot-rollout`

## Checkpoint Gates
Promote from cohort-only to broader rollout only if all conditions pass:
1. CTR lift >= +6% vs holdout.
2. Low-quality delta <= +8 percentage points.
3. CVR gate active at >= 30 conversions and CVR delta >= -3%.
4. Policy violation rate == 0.
5. Reconciliation deltas remain explainable in R3 monitoring.

## Rollback Triggers
1. Two consecutive checkpoint failures on CTR gate.
2. Any active CVR gate failure.
3. Any policy violation incident tied to treated cohort.
4. Unexplained cost delta breach in reconciliation window.

## Execution Checklist
1. Enable canary env vars in target environment.
2. Verify gate snapshot endpoint reflects intended allowlist.
3. Execute daily generation queue for pilot cohort only.
4. Run publish through change packages only.
5. Record checkpoint report per window.
6. Apply promote/rollback decision using experiment lifecycle controls.
