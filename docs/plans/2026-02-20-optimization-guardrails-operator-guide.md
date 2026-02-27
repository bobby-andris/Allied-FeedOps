# Optimization Guardrails Operator Guide

## Purpose
This guide explains how to read and operate the optimization guardrails output for the Google Ads optimization system. It is a runbook for analysts/reviewers, not a development spec.

This system is intentionally **Google Ads-first**. GA4 and Shopify signals are supplemental confidence gates, not the primary source of optimization decisions.

## Scope and safety boundaries
- This workflow does **not** edit storefront tracking code or Analyzify-managed integrations.
- Guardrails provide **decision safety** for rollout states: `go`, `hold`, `blocked`.
- Guardrails persistence writes to internal Supabase telemetry tables only:
  - `guardrail_incidents`
  - `optimization_experiment_snapshots`

## Endpoints
- Read current evaluation:
  - `GET /api/optimization/guardrails`
- Evaluate + optionally persist incidents/snapshot:
  - `POST /api/optimization/guardrails?persist=true`
- Useful query params:
  - `start_date`, `end_date`, `custom_label_0`, `min_impressions`, `limit`
- `POST` authorization:
  - In non-dev, `x-internal-token` must match `INTERNAL_API_TOKEN`.

## Response decoder (field-by-field)
### `pipeline`
- Source decomposition metadata from the needs-decision read path.
- Example fields:
  - `enabled`: decomposition pipeline feature flag state
  - `pairs_total`, `pairs_cached`, `pairs_recomputed`
  - `warnings`: pipeline-level issues
- If `enabled=false`, guardrails still run using available response data, but recommendations are less mature.

### `supplemental_confidence`
- Confidence gate from GA4 + Shopify read-only diagnostics.
- Key fields:
  - `multiplier`: confidence down-weight (lower means higher risk)
  - `reasons`: machine-readable penalty reasons
  - `warnings`: human-readable signal degradation messages
- Critical threshold in current rules:
  - `multiplier <= 0.85` triggers high-severity incident `opt_supplemental_confidence_degraded`.

### `guardrail_decision`
- Final rollout directive:
  - `status`: `go | hold | blocked`
  - `confidence`: risk-adjusted confidence score
  - `rationale`: operator-facing reason
- Decision logic summary:
  - `blocked`: any high/critical incident
  - `hold`: 2+ medium incidents and no high/critical
  - `go`: no blocking pattern

### `incidents`
- List of active rule breaches for the evaluation window.
- Important fields:
  - `ruleId`, `severity`, `message`, `suggestedAction`, `metadata`
- Typical rule IDs in this phase:
  - `opt_supplemental_confidence_degraded`
  - `opt_high_impact_low_confidence`
  - `opt_roas_low_actionable_share`
  - `opt_high_overlap_opportunity_share`
  - `opt_audience_risk_concentration`
  - `opt_supplemental_signal_unavailable`

### `metrics`
- Aggregated features used by guardrail rules.
- High-signal fields:
  - `queue_total`
  - `queue_high_impact_count`
  - `queue_low_confidence_high_impact_count`
  - `roas_total`
  - `roas_actionable_count`
  - `opportunities_total`
  - `opportunities_high_overlap_count`
  - `audience_high_priority_count`
  - derived shares:
    - `low_confidence_high_impact_share`
    - `roas_actionable_share`
    - `high_overlap_cluster_share`

### `persistence` (POST only)
- Indicates what was written this run:
  - `incidentsInserted`
  - `experimentSnapshotsInserted`
- `incidentsInserted=0` can be expected due to dedupe (same `rule_id + report_date` already open/acknowledged).

### `warnings` and `available`
- `warnings`: non-fatal issues (missing supplemental signal, missing relation, etc.).
- `available`: `true` only when warnings array is empty.
- Treat `available=false` as "actionable with caution," not automatic failure.

## Decision matrix (operator action)
| Decision | Meaning | Operator action |
|---|---|---|
| `go` | Guardrails healthy | Continue planned rollout with normal monitoring |
| `hold` | Medium-risk concentration | Pause automation expansion, continue manual review, re-evaluate next cycle |
| `blocked` | High/critical risk present | Stop rollout changes immediately; resolve incident root causes first |

## Real example (captured from current environment)
```json
{
  "guardrail_decision": {
    "status": "blocked",
    "confidence": 0.65
  },
  "supplemental_confidence": {
    "multiplier": 0.82
  },
  "incidents": [
    {
      "ruleId": "opt_supplemental_confidence_degraded",
      "severity": "high"
    },
    {
      "ruleId": "opt_roas_low_actionable_share",
      "severity": "medium"
    }
  ],
  "metrics": {
    "queue_total": 3000,
    "roas_total": 160,
    "roas_actionable_count": 0,
    "roas_actionable_share": 0,
    "high_overlap_cluster_share": 0.3151
  },
  "persistence": {
    "incidentsInserted": 0,
    "experimentSnapshotsInserted": 1
  }
}
```

### How to interpret this exact example
- `blocked` is expected because a high-severity incident exists.
- `multiplier=0.82` crossed the `<=0.85` threshold, so supplemental data quality is degraded.
- `roas_actionable_share=0` means tROAS recommendations are present but none are currently actionable.
- `incidentsInserted=0` is normal when the same incident/day key already exists.
- `experimentSnapshotsInserted=1` confirms telemetry logging is still running.

## On-call checklist
1. Run `GET /api/optimization/guardrails` for the active window.
2. If `status=blocked`, stop rollout changes and read `incidents[*].suggestedAction`.
3. Confirm if issue is data quality (`supplemental_confidence`) vs recommendation readiness (`roas_actionable_share`).
4. Run `POST /api/optimization/guardrails?persist=true` (authorized) to snapshot current state.
5. Check latest `guardrail_incidents` and `optimization_experiment_snapshots` rows.
6. Track until decision returns to `hold` or `go`.

## Common failure patterns
- Missing table warnings:
  - `"optimization_experiment_snapshots" is missing` -> apply migration `035`.
  - `"guardrail_incidents" is missing` -> apply migration `033`.
- Supplemental signal outages:
  - GA4/Shopify fetch failures degrade confidence; keep Google Ads-first manual mode active.
- Pipeline not enabled:
  - If decomposition `pipeline.enabled=false`, recommendations still run but maturity is limited.

## Recommended operating cadence
- Daily:
  - Evaluate guardrails and persist snapshot.
  - Triage any `blocked` state within same business day.
- Weekly:
  - Review rule frequency and false-positive patterns.
  - Adjust rollout velocity only when stable `go/hold` trend is observed.
