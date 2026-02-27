# R1-R5 Implementation Program

## Program Scope
Execute R1-R5 sequentially with hard phase gates, one PR per phase, and deploy only after each merged phase passes post-deploy smoke checks.

## Baseline Lock
- Baseline branch: `master`
- Baseline SHA: `ac539a87`
- Baseline captured at (UTC): `2026-02-27T08:16:16Z`
- RCA baseline artifacts:
  - `docs/experiments/2026-02-27-single-sku-hybrid-as-is-trace/`
  - `docs/experiments/2026-02-27-google-4sku-eval/`

## Phase Status Tracker
| Phase | Branch | Status | PR | Deploy | Exit Gate |
|---|---|---|---|---|---|
| R0 Program Controls | `master` | completed | n/a | n/a | Baseline docs + SQL + tests captured |
| R1 Telemetry Hardening | `codex/e245-r1-telemetry-hardening-20260228` | merged | [#25](https://github.com/bobby-andris/Allied-FeedOps/pull/25) | verified | Hybrid telemetry non-null + batch detail completeness |
| R2 Lineage/Idempotency/Placeholder | `codex/e245-r2-lineage-idempotency-20260228` | merged | [#26](https://github.com/bobby-andris/Allied-FeedOps/pull/26) | verified | Lineage fields + deterministic dedupe + write-time placeholder gate |
| R3 Cost Reconciliation | `codex/e245-r3-cost-reconciliation-20260228` | merged | [#27](https://github.com/bobby-andris/Allied-FeedOps/pull/27) | verified | Daily reconciliation artifacts + retry attribution |
| R4 Lineage Bridge + Change Packages | `codex/e245-r4-lineage-bridge-change-packages-20260228` | merged | [#29](https://github.com/bobby-andris/Allied-FeedOps/pull/29) | verified | Generation->outcome linkage + package-governed rollback |
| R5 Prioritization + Experiment Lifecycle | `codex/e245-r5-prioritization-experiment-lifecycle-20260228` | merged | [#31](https://github.com/bobby-andris/Allied-FeedOps/pull/31) | verified | Closed-loop queue->experiment->outcome lifecycle |
| R6 Pilot Generation Ops | `codex/e245-r6-pilot-generation-ops-20260227` | in-progress | pending | pending | Flagged canary live on pilot cohort with gate checkpoints |

## Cross-Phase Gates (must pass before merge)
1. Code gate: required tests green for phase scope.
2. Data gate: SQL verification checks pass.
3. Contract gate: no breaking API changes.
4. Observability gate: required logs/metrics emitted.
5. Security gate: env/secret contract checks pass.
6. Deploy gate: production smoke checks pass.
7. Rollback gate: executable rollback path documented and validated.

## Baseline Evidence
- SQL snapshots: `docs/experiments/2026-02-28-r1-r5-baseline/sql/`
- Test outputs: `docs/experiments/2026-02-28-r1-r5-baseline/tests/`
- Topology/meta snapshot: `docs/experiments/2026-02-28-r1-r5-baseline/meta/`
- Program closeout report: `docs/experiments/2026-02-28-r1-r5-closeout/report.md`
