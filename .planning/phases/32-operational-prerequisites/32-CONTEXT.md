# Phase 32: Operational Prerequisites - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Resolve all data infrastructure gaps so Phase 33 (Tier Scoring Engine) and Phase 36 (Experiments) operate on real data. Activate Cloud Scheduler for daily funnel snapshots, backfill historical data, extend database schemas for scoring and experiment columns. No UI work — pure infrastructure.

</domain>

<decisions>
## Implementation Decisions

### Backfill strategy
- Backfill 30 days of funnel_snapshots_daily data
- Source data from Google Ads API live queries (not reconstructing from existing DB tables)
- Skip days with incomplete/missing data — log which dates were skipped, don't interpolate
- Script must be idempotent (upsert on date+term key) — safe to re-run if issues arise

### Schema extension design
- tier_fit_scores column: JSONB with no fixed structure — Phase 33 decides what to store, JSONB gives flexibility to change scoring model later without migrations
- recommended_tier and net_monthly_impact: nullable, no defaults — NULL means "not yet scored" (clean distinction from "scored as zero")
- Experiment columns (p_value, confidence_interval, minimum_sample_size): extend existing experiment_outcomes table, don't create new table
- All schema changes applied as versioned Supabase migrations (not direct SQL)

### Scheduler & monitoring
- Cloud Scheduler fires daily at 6 AM UTC (after Google Ads finalizes previous day's metrics)
- Retry policy: 2 retries with 5-minute spacing before giving up
- On failure (including zero-row captures): send Slack alert via existing webhook
  - Webhook URL: `(stored in Vercel env var SLACK_WEBHOOK_URL — do not commit)`
- Failures only — no daily success heartbeat messages (reduce noise)

### Validation & gating
- Automated validation script: `scripts/validate_phase32.py`
- Runs the 3 success criteria as SQL checks, prints PASS/FAIL for each
- Hard gate: Phase 33 cannot proceed until all checks pass
- Reusable pattern for future phase prerequisite validation

### Claude's Discretion
- Minimum data threshold for funnel_snapshots_daily (7 vs 14 days) — pick based on what Phase 33 scoring actually needs
- Exact CRON_SECRET configuration approach
- Backfill script error handling details
- Migration file numbering and naming

</decisions>

<specifics>
## Specific Ideas

- Existing Slack webhook already configured for Cloud Run notifications — reuse for scheduler alerts
- Validation script should be runnable anytime as an ad-hoc readiness check, not just at phase completion

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 32-operational-prerequisites*
*Context gathered: 2026-02-25*
