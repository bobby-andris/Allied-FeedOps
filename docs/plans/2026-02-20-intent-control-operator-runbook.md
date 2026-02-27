# Intent Control Operator Runbook

## Scope
This runbook covers day-to-day operation of the Unified Intent Intelligence & Execution bridge shipped in `c5bd`:
- `/intent-control-center`
- `/search-governance`
- `/experiment-lab`
- Existing high-volume triage in `/shopping-funnel`

It is optimized for safe, high-volume decisioning with human-in-the-loop review.

## Goals
- Increase profitable revenue while protecting margin efficiency.
- Improve query quality and Search/Shopping governance consistency.
- Reduce decision latency without increasing expensive mistakes.

## Daily Workflow (20-40 minutes, 2x/day)
1. Open `/intent-control-center`.
2. Check Guardrail Status first:
   - `GO`: normal operations.
   - `HOLD`: apply only high-confidence, low-risk actions.
   - `BLOCKED`: stop non-essential actions and run rollback protocol.
3. Review top intent decisions:
   - Prioritize terms flagged `REVIEW`.
   - Confirm route, tier, and reason codes align with intent.
4. Review bid policy recommendations:
   - Approve only when confidence and attribution quality are stable.
   - Defer aggressive changes during volatility windows.
5. If warnings appear (missing table/data freshness), switch to conservative mode and log the issue.

## Shopping Funnel + Intent Routing
Use `/shopping-funnel` for bulk triage and staged publish. Use intent signals for consistency:
- `BRAND_CORE` -> branded routes only.
- `PRODUCT_HIGH` -> Shopping `HIGH` (and Search graduation candidates).
- `CATEGORY_MID` -> Shopping `MEDIUM`.
- `DISCOVERY_LOW` -> Shopping `LOW` with tight controls.
- `MISMATCH` / `RISK_POLICY` -> negatives or hold for review.

Operator rule:
- Auto-safe actions are acceptable when confidence is high.
- Borderline confidence or mixed evidence must stay in staged review.

## Search Governance Workflow
1. Open `/search-governance`.
2. Sort and select high-confidence candidates first.
3. Apply selected candidates in controlled batches (start with 20-50 terms).
4. Confirm expected actions:
   - Broad -> Phrase promotion.
   - Phrase -> Exact promotion.
   - Shopping -> Search graduation where justified.
5. Ensure cross-channel conflict prevention is active (negative registry entries created on apply).

## Experiment Workflow
1. Open `/experiment-lab`.
2. Register an experiment before major policy changes:
   - clear initiative
   - explicit hypothesis
   - decision rule
   - success and failure thresholds
3. Do not move from pilot to scale without recorded experiment outcomes.

## Review Queue Prioritization
Prioritize in this order:
1. High spend + weak conversion terms.
2. High confidence promotions with material revenue impact.
3. Brand leakage and competitor terms.
4. Lower confidence discovery terms.

Batch hygiene:
- Use staged publishes.
- Keep batch size smaller during unstable attribution/data windows.

## Operator Calibration Panel (Phase 3 Batch C)
`/intent-control-center` now includes **Operator Calibration & Decision Consistency**.

Use it to monitor:
- **Review actions**: total action volume and 24h velocity.
- **Consistency rate**: queue/entity conflict signal across positive vs negative decisions.
- **Policy alignment**: how often selected actions/tiers match recommended actions/tiers.
- **Queue consistency table**: where drift is happening.
- **Operator calibration table**: which actors are outliers on alignment.

Escalate if:
- Consistency drops below 70% for any queue over a 7-day window.
- Alignment drops below 65% for a high-impact queue.
- A single actor’s alignment is >20 points below team median with comparable volume.

When escalation is triggered:
1. Switch affected queue to staged-only.
2. Pull top conflict entities and review reason codes.
3. Re-calibrate policy thresholds only after confirming data quality/guardrails are healthy.

## Search Buildout Briefs (Phase 3 Batch D)
`/search-governance` now includes **Search Buildout Briefs** to turn mined query clusters into actionable Search campaign structure.

What this panel now provides:
- `cluster_key` groupings (for example: `towel bar`, `robe hook`) from query mining.
- Structured recommendations:
  - `suggested_campaign`
  - `suggested_ad_group`
  - `recommended_tier`
- Cluster-level volume and confidence indicators to prioritize execution.

Operator usage:
1. Start with the top 3-5 clusters by priority/confidence.
2. Validate campaign/ad-group naming against current account conventions.
3. Use candidate selection + apply flow only after cluster sanity check.
4. Keep rollout batched (20-50 terms) and monitor guardrail status between batches.

Escalate/review required when:
- Cluster confidence is below 60%.
- Cluster intent mix includes `MISMATCH` or `RISK_POLICY`.
- Buildout recommendation conflicts with active branded/competitor controls.

Batch D objective:
- Increase new profitable Search coverage while minimizing cross-channel cannibalization.
- Ensure every buildout recommendation is traceable to intent + reason codes.

## Experiment Holdouts and Weekly Governance (Phase 3 Batch E)
`/experiment-lab` now supports holdout assignment workflows and weekly checkpoint decisioning so experiment rollouts stay evidence-driven.

What changed:
- Added **Assign Holdouts** workflow to create deterministic treatment/control cohort assignments by experiment key.
- Added weekly governance checkpoint table with:
  - `weekly_status` recommendation (`promote_to_scale`, `hold`, `observe_more_data`, `rollback_or_pause`, `needs_data`)
  - Holdout mix visibility (`holdout_share`, control/treatment counts)
  - Latest metric/lift/sample context
  - Checkpoint due flag (`Due` vs `On track`)

Operator usage:
1. Register experiment as before (`name`, `initiative`, `hypothesis`, `decision rule`, thresholds).
2. Assign holdouts to candidate entities before major rollout:
   - Provide `experiment_key`.
   - Provide entity keys (comma/newline format).
   - Set holdout percent (default `20`).
3. Run weekly checkpoint review:
   - `promote_to_scale`: candidate for controlled expansion.
   - `hold`: continue current run and collect more periods.
   - `observe_more_data`: sample too small; keep experiment active.
   - `rollback_or_pause`: trigger incident-aware rollback/hold procedures.
4. Keep decisions logged and aligned with guardrail state before any scale action.

Escalate/review required when:
- Weekly status is `rollback_or_pause`.
- Checkpoint is `Due` for more than one cycle.
- Holdout share is near 0% or 100% (assignment imbalance).
- Attribution/data quality warnings are present during checkpoint review.

## Guardrails and Rollback Protocol
Trigger rollback if any of these occur:
- Spend spike with margin/revenue degradation.
- Attribution quality collapse.
- Critical guardrail incidents.
- Data staleness beyond acceptable threshold.

Steps:
1. Set operational mode to hold (or blocked as needed).
2. Call rollback flow (`/api/intent/rollback`) to restore last known-good snapshot if available.
3. Pause new promote/demote and bid policy changes.
4. Re-check guardrails and incident counts before resuming.

Exit criteria:
- Metrics stabilize for consecutive windows.
- No open critical incidents.
- Operator sign-off logged.

## Weekly Governance Cadence (45-60 minutes)
1. Audit intent/tier drift and negative coverage.
2. Reassess Search graduation quality and overlap risk.
3. Review experiment outcomes and apply decision rules.
4. Tune thresholds only with evidence; avoid broad threshold shifts without holdout support.

## Operational Constraints
- Preserve current tracking stack (including Analyzify and existing GA4 setup).
- Treat missing tables/data as a safety signal: reduce automation, increase manual review.
- Prefer reversible, incremental changes over large one-shot rollouts.

## API Surface Reference
- Intent decision queue: `GET /api/intent/decisions`
- Route application planning: `POST /api/intent/route`
- Promotion/demotion evaluation: `POST /api/intent/promote-demote`
- Bid policy evaluation: `POST /api/intent/bid-policy`
- Guardrail status: `GET /api/intent/guardrails`
- Rollback: `POST /api/intent/rollback`
- Operator calibration analytics: `GET /api/intent/review-analytics`
- Search candidates: `GET /api/search/governance/candidates`
- Search buildout briefs: `GET /api/search/governance/buildouts`
- Search apply: `POST /api/search/governance/apply`
- Experiment register/results:
  - `POST /api/experiments/register`
  - `GET /api/experiments/results`
  - `POST /api/experiments/assignments`

## Cross-Channel Input Hardening (Phase 4 Batch A)

All policy decision entry points (`routeIntentDecision`, `evaluatePromotionDemotion`, `evaluateSearchGovernance`, `recommendBidPolicy`, `evaluateShoppingToSearchGraduation`) now apply input sanitization before evaluation.

### What changed
- **Input validation layer** (`input-validation.ts`): Sanitizes `TermMetrics` (NaN→0, negative→0, Infinity→0, fractional counts floored), clamps score fields to 0-1 range, rejects empty search terms/keys.
- **GA4/Shopify value consistency checker** (`value-consistency.ts`): Compares GA4 conversion values against Shopify order values, producing a consistency score (0-1) with divergence flags and severity levels (`none`, `warning`, `critical`).
- **Policy hardening**: Every policy function validates inputs at entry. Invalid or out-of-range values are corrected with warnings rather than causing silent incorrect decisions.

### Operator impact
- **No behavior change for clean data**: If inputs are already valid, decisions are identical.
- **Dirty data handling**: NaN, negative, or Infinity metrics no longer produce unpredictable confidence scores or phantom promotions/demotions. They are safely clamped and logged.
- **Value consistency checks**: Use `checkValueConsistency()` to audit GA4 vs Shopify value alignment before trusting conversion-based decision signals.

### Thresholds
| Divergence | Severity | Action |
|---|---|---|
| < 15% | `none` | Values consistent — normal operations |
| 15-50% | `warning` | Flag for review — possible tracking gap |
| > 50% | `critical` | Do not trust value signals — investigate tracking setup |

### When to escalate
- Value consistency score drops below 0.5 for the account during weekly governance.
- Multiple input validation warnings appear in API responses (suggests upstream data quality issue).
- Attribution quality score + value consistency both degraded simultaneously.

## Incident Automation + Rollback Playbook (Phase 4 Batch B)

### What changed
- **Auto-detect + auto-persist incidents**: `GET /api/intent/guardrails` now automatically creates `guardrail_incidents` rows for newly detected issues. Existing open incidents (by `rule_id`) are deduped — no duplicate incidents.
- **Rollback readiness endpoint**: `GET /api/intent/rollback/readiness` evaluates pre-flight checks before rollback: guardrail status, snapshot availability, open incident counts, and active cross-channel negatives.
- **Incident automation library** (`incident-automation.ts`): Pure functions for `autoDetectIncidents()` and `evaluateRollbackReadiness()`.

### Operator impact
- Guardrail evaluation now **automatically creates incidents** without manual intervention. Operators see `auto_created_incidents` and `auto_skipped_incidents` counts in the guardrail response.
- Before executing rollback, call `GET /api/intent/rollback/readiness` for a structured pre-flight checklist.

### Rollback readiness recommendations
| Recommendation | Meaning | Action |
|---|---|---|
| `rollback_recommended` | Guardrails blocked, snapshots available | Execute rollback immediately |
| `rollback_optional` | Guardrails on hold, snapshots available | Review incidents first, rollback if needed |
| `no_rollback_needed` | Guardrails clear | No action required |
| `no_snapshots_available` | No policy snapshots to restore | Cannot rollback — investigate manually |

### Rollback playbook (finalized)
1. Call `GET /api/intent/rollback/readiness` — check `ready` and `recommendation`.
2. If `ready: true` and `recommendation: rollback_recommended`:
   - Call `POST /api/intent/rollback` with optional `snapshot_id`.
   - Verify `rollback_applied: true` and `deactivated_negative_count` in response.
3. Resolve/acknowledge triggering incidents via `POST /api/intent/guardrails/incidents`.
4. Monitor guardrail status for at least 2 consecutive evaluation windows before resuming automated actions.
5. Log operator sign-off via incident resolve action.

### API surface additions
- `GET /api/intent/rollback/readiness` — rollback pre-flight evaluation

## Executive Scorecard (Phase 4 Batch C)

`/intent-control-center` now includes an **Executive Scorecard** panel providing at-a-glance profit, efficiency, and decision velocity metrics.

### What changed
- **Scorecard computation library** (`executive-scorecard.ts`): Pure function computing ROAS, CPA, automation rate, pending review rate, action breakdown (promote/demote/negative/hold percentages), and operational health grade.
- **Scorecard API** (`GET /api/intent/scorecard`): Loads action execution logs and guardrail incidents from database, computes scorecard with optional query params (`period_days`, `total_revenue`, `total_cost`, `total_conversions`).
- **UI panel**: Executive Scorecard card on Intent Control Center with 4 KPI tiles (ROAS, CPA, automation rate, decision latency) and 4 action breakdown tiles (promote, demote, negative, hold).

### Metrics reference
| Metric | Formula | Interpretation |
|---|---|---|
| ROAS | total_conversions_value / total_cost | Revenue efficiency; higher is better |
| CPA | total_cost / total_conversions | Cost per acquisition; lower is better |
| Automation rate | auto_applied / total_decisions | Portion running without review |
| Pending review rate | pending / total_decisions | Queue backlog indicator |
| Decision latency | avg hours between decisions | Operational speed |

### Health grade derivation
| Guardrail status | Open incidents | Grade |
|---|---|---|
| `blocked` | any | `critical` |
| `hold` | any | `degraded` |
| `go` | > 0 | `degraded` |
| `go` | 0 | `healthy` |

### API surface additions
- `GET /api/intent/scorecard` — executive scorecard with ROAS, CPA, automation rate, health grade

## Channel Adapter Contracts (Phase 4 Batch D)

The system now defines **standardized adapter contracts** for future multi-channel expansion beyond Google Ads.

### What changed
- **Channel adapter interface** (`channel-adapter.ts`): Defines `ChannelAdapter` contract with `channelId`, `capabilities`, `checkHealth()`, and `executeActions()` methods.
- **Adapter registry** (`ChannelAdapterRegistry`): Register/unregister adapters, health-check all channels, execute actions with guardrail enforcement.
- **Google Ads stub adapter**: Reference implementation satisfying the contract; delegates to existing route handlers.

### Supported channel types
- `google_ads` (active — stub adapter provided)
- `microsoft_ads` (contract ready — no implementation yet)
- `meta_ads` (contract ready — no implementation yet)
- `custom` (extensibility slot)

### Capability flags per adapter
| Capability | Google Ads | Microsoft Ads (future) | Meta Ads (future) |
|---|---|---|---|
| Negative keywords | Yes | Yes | No |
| tROAS | Yes | Yes | Partial |
| tCPA | Yes | Partial | Yes |
| Tier labels | Yes | No | No |
| Experiments | Yes | No | Partial |

### Guardrail enforcement
- `blocked` status prevents all adapter execution (returns failure per action).
- `hold` and `go` statuses are passed through to the adapter for per-action decisions.

### Operator impact
- No behavior change for current Google Ads workflows.
- Future channel onboarding follows: implement `ChannelAdapter` → register in `ChannelAdapterRegistry` → route actions via `executeOnChannel()`.
- All future channels inherit guardrail enforcement automatically.
