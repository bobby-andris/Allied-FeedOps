# Phase 32: Operational Prerequisites - Research

**Researched:** 2026-02-25
**Domain:** GCP Cloud Scheduler, Supabase schema migrations, Google Ads API backfill, Slack alerting
**Confidence:** HIGH

## Summary

Phase 32 resolves four infrastructure gaps inherited as tech debt from v1.3b so that downstream phases (33-37) operate on real data rather than empty tables or missing columns. The work breaks into four distinct deliverables: (1) activate Cloud Scheduler for daily funnel snapshot capture, (2) re-backfill 30 days of funnel_snapshots_daily using the existing backfill endpoint, (3) extend the existing `query_value_scores` table with new columns for Phase 33's tier scoring, and (4) extend the existing `experiment_outcomes` table with statistical columns for Phase 36's A/B testing.

All four deliverables have existing infrastructure to build on. The capture endpoint (`/api/funnel-snapshots/capture`) and backfill endpoint (`/api/funnel-snapshots/backfill`) are production-ready TypeScript API routes. The scheduler setup script (`scripts/setup-funnel-scheduler.sh`) exists but has never been run. The `query_value_scores` table was created from migration `033b_DEFERRED_optimization_control_plane.sql` (applied out-of-band). The `experiment_outcomes` table was created from migration `035b_DEFERRED_unified_intent_execution_system.sql` (applied out-of-band). Schema extensions are straightforward ALTER TABLE ADD COLUMN operations.

**Primary recommendation:** Execute in order: (1) CRON_SECRET + Scheduler activation, (2) backfill 30 days, (3) schema migrations, (4) validation script. The scheduler must run first because the success criteria require 7 days of data from the scheduler (not from backfill).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Backfill 30 days of funnel_snapshots_daily data
- Source data from Google Ads API live queries (not reconstructing from existing DB tables)
- Skip days with incomplete/missing data -- log which dates were skipped, don't interpolate
- Script must be idempotent (upsert on date+term key) -- safe to re-run if issues arise
- tier_fit_scores column: JSONB with no fixed structure -- Phase 33 decides what to store, JSONB gives flexibility to change scoring model later without migrations
- recommended_tier and net_monthly_impact: nullable, no defaults -- NULL means "not yet scored" (clean distinction from "scored as zero")
- Experiment columns (p_value, confidence_interval, minimum_sample_size): extend existing experiment_outcomes table, don't create new table
- All schema changes applied as versioned Supabase migrations (not direct SQL)
- Cloud Scheduler fires daily at 6 AM UTC (after Google Ads finalizes previous day's metrics)
- Retry policy: 2 retries with 5-minute spacing before giving up
- On failure (including zero-row captures): send Slack alert via existing webhook
  - Webhook URL: `(stored in Vercel env var SLACK_WEBHOOK_URL — do not commit)`
- Failures only -- no daily success heartbeat messages (reduce noise)
- Automated validation script: `scripts/validate_phase32.py`
- Runs the 3 success criteria as SQL checks, prints PASS/FAIL for each
- Hard gate: Phase 33 cannot proceed until all checks pass
- Reusable pattern for future phase prerequisite validation

### Claude's Discretion
- Minimum data threshold for funnel_snapshots_daily (7 vs 14 days) -- pick based on what Phase 33 scoring actually needs
- Exact CRON_SECRET configuration approach
- Backfill script error handling details
- Migration file numbering and naming

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OPS-01 | Cloud Scheduler activated for funnel_snapshots_daily capture (CRON_SECRET configured, setup script run) | Existing `scripts/setup-funnel-scheduler.sh` creates the GCP Cloud Scheduler job. Needs CRON_SECRET set in Vercel env vars. User wants 6 AM UTC schedule (differs from existing script's 5 AM ET -- need to update). Capture endpoint at `/api/funnel-snapshots/capture` is fully implemented. Slack alerting on failure is new (add to capture endpoint or create wrapper). |
| OPS-02 | funnel_snapshots_daily table re-backfilled with historical data and verified non-empty | Existing `/api/funnel-snapshots/backfill` endpoint handles day-by-day backfill with upsert. Call with `start_date` = 30 days ago, `end_date` = yesterday. Run against localhost to avoid Vercel timeout (route comment says this explicitly). Existing data from Phase 30.1 backfill (4,093 rows) may already be in table but could be stale. |
| OPS-03 | query_value_scores table schema extended with tier_fit_scores JSONB, recommended_tier, net_monthly_impact, scored_at columns | Table exists in production (created from 033b migration applied out-of-band). Current schema has: search_term, custom_label_0, score_version, expected_clicks, expected_cvr, expected_conversion_value, expected_profit_proxy, uncertainty, impact_score, model_inputs, created_at. Need ALTER TABLE to add 4 new columns. |
| OPS-04 | experiment_outcomes table schema extended with p_value, confidence_interval, and minimum_sample_size columns | Table exists in production (created from 035b migration). Current schema has: experiment_key, metric_name, observed_lift, sample_size, status, measured_at, metadata. Need ALTER TABLE to add 3 new columns. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| GCP Cloud Scheduler | N/A | Daily cron trigger for funnel capture | Already used in project (setup scripts exist), GCP project configured |
| Supabase Migrations | Postgres 15 | Schema changes via versioned SQL | Project standard for all DDL changes |
| google-ads-api | 23.0 | Data source for backfill (via `getLabelTierPerformance()`) | Already wired in `service.ts`, proven in production |
| Next.js API Routes | 16.x | Capture and backfill endpoints | Both endpoints already exist and are tested |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| curl / node-fetch | N/A | Slack webhook POST for failure alerts | Simple HTTP POST, no library needed |
| gcloud CLI | latest | Cloud Scheduler job creation | Human-run setup script |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GCP Cloud Scheduler | Vercel Crons | Vercel crons already have 1 entry (ga4 snapshot). vercel.json supports it, but GCP Cloud Scheduler gives more control (retry policy, timeout, header auth). User decision locks GCP Cloud Scheduler. |
| Slack webhook for alerts | GCP Cloud Monitoring | Cloud Monitoring would need extra setup. Slack webhook is a single HTTP POST -- simpler for failure-only alerts. |
| Python backfill script | Existing TS backfill endpoint | User decision locks Google Ads API live queries. The existing `/api/funnel-snapshots/backfill` endpoint already does exactly this. Use it. |

## Architecture Patterns

### Existing Infrastructure Map

```
ALREADY EXISTS (from Phase 30):
  dashboard/src/app/api/funnel-snapshots/
    capture/route.ts        # POST - captures yesterday's data, auth via CRON_SECRET
    backfill/route.ts       # POST - backfills date range, auth via CRON_SECRET
    trends/route.ts         # GET - returns 7d vs prev-7d trends
  scripts/setup-funnel-scheduler.sh  # Creates GCP Cloud Scheduler job

ALREADY EXISTS (from 033b/035b migrations):
  supabase/migrations/033b_DEFERRED_optimization_control_plane.sql  # query_value_scores table
  supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql  # experiment_outcomes table

NEEDS CREATION (Phase 32):
  supabase/migrations/037_extend_scoring_and_experiment_columns.sql  # ALTER TABLE x2
  scripts/validate_phase32.py  # Validation script
  Modified: scripts/setup-funnel-scheduler.sh OR new script with updated schedule
  Modified: capture/route.ts OR wrapper for Slack alerting
```

### Pattern 1: Cloud Scheduler + Bearer Token Auth
**What:** GCP Cloud Scheduler calls Vercel-hosted API route with Bearer token matching CRON_SECRET env var.
**When to use:** Scheduled tasks that need to call the Next.js dashboard API.
**Key details:**
- CRON_SECRET is set in Vercel environment variables (all environments: Production, Preview, Development)
- Cloud Scheduler sends `Authorization: Bearer <CRON_SECRET>` header
- The capture endpoint already validates this token (lines 17-33 of `capture/route.ts`)
- Existing script uses 5 AM ET schedule; user wants 6 AM UTC (= 1 AM ET in winter, 2 AM ET in summer)

**Example (from existing setup script):**
```bash
gcloud scheduler jobs create http "feedops-funnel-snapshot-daily" \
  --project="bobbys-project-346400" \
  --location="us-east1" \
  --schedule="0 6 * * *" \
  --time-zone="UTC" \
  --uri="https://allied-feed-ops.vercel.app/api/funnel-snapshots/capture" \
  --http-method=POST \
  --headers="Content-Type=application/json,Authorization=Bearer ${CRON_SECRET}" \
  --message-body='{}' \
  --attempt-deadline="120s" \
  --max-retry-attempts=2 \
  --min-backoff="300s" \
  --max-backoff="300s"
```

### Pattern 2: Idempotent Supabase Schema Extension
**What:** ALTER TABLE ADD COLUMN IF NOT EXISTS for extending existing tables.
**When to use:** Adding columns to tables that already exist in production.
**Key details:**
- Use `ADD COLUMN IF NOT EXISTS` for idempotency
- Nullable columns with no default -- NULL means "not yet scored"
- Versioned migration files in `supabase/migrations/`

**Example:**
```sql
ALTER TABLE query_value_scores
  ADD COLUMN IF NOT EXISTS tier_fit_scores JSONB,
  ADD COLUMN IF NOT EXISTS recommended_tier TEXT,
  ADD COLUMN IF NOT EXISTS net_monthly_impact NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;
```

### Pattern 3: Slack Webhook Failure Alert
**What:** HTTP POST to Slack webhook URL on capture failure or zero-row capture.
**When to use:** Failure-only alerting (no success heartbeats).
**Key details:**
- Webhook URL is provided in CONTEXT.md
- Simple JSON payload with text field
- Can be done inline in capture endpoint or as a wrapper

**Example:**
```typescript
async function sendSlackAlert(message: string): Promise<void> {
  const webhookUrl = process.env.SLACK_WEBHOOK_URL
  if (!webhookUrl) return
  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: message }),
    })
  } catch (err) {
    console.error('[slack-alert] Failed to send:', err)
  }
}
```

### Anti-Patterns to Avoid
- **Hardcoding Slack webhook URL in source code:** Store in Vercel env var `SLACK_WEBHOOK_URL`, never commit the URL.
- **Running backfill against production Vercel:** The backfill endpoint iterates day-by-day synchronously. Vercel functions have a 60s timeout (Pro) or 10s (Hobby). Run against `localhost:3000` instead.
- **Overwriting existing scheduler job without checking:** The existing `setup-funnel-scheduler.sh` creates job `feedops-funnel-snapshot-daily`. If it already exists, `gcloud scheduler jobs create` will fail. Use `--quiet` flag or delete-then-create pattern.
- **Using DEFAULT values on new columns:** User explicitly wants NULL (not default 0) to distinguish "not yet scored" from "scored as zero."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Daily funnel capture | New capture logic | Existing `capture/route.ts` | Already tested, proven, handles upsert and 90-day retention cleanup |
| Historical backfill | New backfill script | Existing `backfill/route.ts` | Already handles day-by-day iteration, error logging per day, 90-day safety limit |
| Cloud Scheduler setup | Manual GCP console clicks | Modified `setup-funnel-scheduler.sh` | Reproducible, version-controlled, includes retry and auth config |
| Schema changes | Direct SQL in production | Versioned migration file | Matches project convention (supabase/migrations/*.sql) |
| Validation checks | Manual SQL queries | `scripts/validate_phase32.py` | Reusable, automated, prints PASS/FAIL per criterion |

**Key insight:** 90% of this phase is activating and configuring existing infrastructure, not building new code. The capture endpoint, backfill endpoint, and scheduler script all exist. The new work is: update scheduler config, add Slack alerting, write 2 ALTER TABLE migrations, and write a validation script.

## Common Pitfalls

### Pitfall 1: Scheduler Time Zone Mismatch
**What goes wrong:** Existing script uses `America/New_York` (5 AM ET), user wants 6 AM UTC. These are different times and shift with DST.
**Why it happens:** UTC is fixed; ET shifts between UTC-5 (EST) and UTC-4 (EDT). 6 AM UTC = 1 AM ET in winter, 2 AM ET in summer.
**How to avoid:** Use `--time-zone="UTC"` and `--schedule="0 6 * * *"` exactly as user specified. Do NOT convert to ET.
**Warning signs:** Data captured at inconsistent times after DST change.

### Pitfall 2: Vercel Function Timeout on Backfill
**What goes wrong:** Calling `/api/funnel-snapshots/backfill` on production Vercel hits the function timeout (10-60s depending on plan) when iterating 30 days.
**Why it happens:** Each day makes a Google Ads API call (~2-5s), so 30 days takes 60-150s.
**How to avoid:** Run backfill against `localhost:3000` as stated in the endpoint's own documentation (line 12 of backfill/route.ts). Or break into smaller batches (10 days each).
**Warning signs:** HTTP 504 Gateway Timeout or partial backfill results.

### Pitfall 3: 033b Table May Not Exist
**What goes wrong:** `query_value_scores` was in a DEFERRED migration (033b). The existing code uses `isMissingRelationError()` to handle the case where the table doesn't exist. The migration triage only audited 034b and 035b tables -- 033b was not in scope.
**Why it happens:** The schema verification report (31-01) only verified 034b and 035b tables. 033b tables were not verified against production.
**How to avoid:** Before writing the ALTER TABLE migration, verify the table exists in production using a simple SQL query: `SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'query_value_scores')`. If it doesn't exist, create it first (from 033b SQL).
**Warning signs:** ALTER TABLE fails with "relation does not exist" error.

### Pitfall 4: CRON_SECRET Not in Vercel Env
**What goes wrong:** Cloud Scheduler sends the Bearer token, but Vercel returns 401 because CRON_SECRET env var is missing or doesn't match.
**Why it happens:** CRON_SECRET must be manually added to Vercel environment variables before the scheduler can work.
**How to avoid:** Check Vercel env vars before activating scheduler. The validation script should verify this.
**Warning signs:** All scheduler runs return 401 Unauthorized.

### Pitfall 5: Slack Webhook URL Committed to Git
**What goes wrong:** The webhook URL from CONTEXT.md is sensitive -- if committed to source code, anyone with repo access can spam the Slack channel.
**Why it happens:** Tempting to hardcode the URL from the decision document.
**How to avoid:** Store as `SLACK_WEBHOOK_URL` env var in Vercel. Reference `process.env.SLACK_WEBHOOK_URL` in code.
**Warning signs:** URL appears in git diff.

### Pitfall 6: Existing Funnel Data Already Stale
**What goes wrong:** Phase 30.1 backfilled 4,093 rows, but if the scheduler was never activated, those rows are getting older every day. The backfill endpoint has 90-day retention cleanup that deletes rows older than 90 days.
**Why it happens:** The capture endpoint runs cleanup inline (lines 79-92 of capture/route.ts). If called during backfill or re-backfill, it won't clean up old data because backfill/route.ts does NOT run cleanup.
**How to avoid:** The re-backfill just needs to upsert 30 fresh days. Old data from Phase 30.1 will eventually be cleaned by the daily capture job's retention logic. No conflict.
**Warning signs:** None -- this is actually fine.

## Code Examples

### Migration: Extend query_value_scores
```sql
-- Migration: 037_extend_scoring_and_experiment_columns.sql
-- Phase 32: OPS-03 and OPS-04

-- OPS-03: Extend query_value_scores for Phase 33 tier scoring
ALTER TABLE query_value_scores
  ADD COLUMN IF NOT EXISTS tier_fit_scores JSONB,
  ADD COLUMN IF NOT EXISTS recommended_tier TEXT,
  ADD COLUMN IF NOT EXISTS net_monthly_impact NUMERIC(14,4),
  ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;

-- Optional: constraint on recommended_tier
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'query_value_scores_recommended_tier_check'
  ) THEN
    ALTER TABLE query_value_scores
      ADD CONSTRAINT query_value_scores_recommended_tier_check
      CHECK (recommended_tier IS NULL OR recommended_tier IN ('HIGH', 'MEDIUM', 'LOW'));
  END IF;
END $$;

-- Index for scored_at queries (Phase 33 will query recent scores)
CREATE INDEX IF NOT EXISTS idx_query_value_scores_scored_at
  ON query_value_scores (scored_at DESC NULLS LAST);

-- OPS-04: Extend experiment_outcomes for Phase 36 experiments
ALTER TABLE experiment_outcomes
  ADD COLUMN IF NOT EXISTS p_value NUMERIC(10,8),
  ADD COLUMN IF NOT EXISTS confidence_interval JSONB,
  ADD COLUMN IF NOT EXISTS minimum_sample_size BIGINT;
```

### Validation Script Pattern
```python
#!/usr/bin/env python3
"""
Validate Phase 32 operational prerequisites.
Usage: python scripts/validate_phase32.py
Requires: SUPABASE_URL and SUPABASE_KEY env vars (or sourced from .env.vercel)
"""
import os
import sys
from datetime import datetime, timedelta
# Uses supabase-py or direct HTTP to run SQL checks
```

### Slack Alert in Capture Endpoint
```typescript
// Add to capture/route.ts after the catch block
const webhookUrl = process.env.SLACK_WEBHOOK_URL
if (webhookUrl) {
  await fetch(webhookUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text: `:warning: Funnel snapshot capture failed for ${yesterday}\nError: ${error instanceof Error ? error.message : 'Unknown'}`,
    }),
  })
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No daily capture (live queries only) | Write-behind to funnel_snapshots_daily | Phase 30 (v1.3b) | Enables trend analysis, historical comparisons |
| Hardcoded ROAS thresholds (3.6/3.1/2.6) | Distribution-based scoring (Phase 33) | Planned v1.3c | Requires query_value_scores columns from OPS-03 |
| No experiment statistical rigor | p-value + confidence intervals (Phase 36) | Planned v1.3c | Requires experiment_outcomes columns from OPS-04 |

## Open Questions

1. **Does query_value_scores actually exist in production?**
   - What we know: Migration 033b was marked DEFERRED but states "Tables created out-of-band." Existing code uses `isMissingRelationError()` guard, which suggests the table might NOT exist. The Phase 28/31 triage only verified 034b and 035b tables, not 033b.
   - What's unclear: Whether the 033b migration was ever run against production Supabase.
   - Recommendation: First task in implementation should be to query `information_schema.tables` for `query_value_scores`. If it doesn't exist, create it from 033b SQL before running ALTER TABLE. The migration should use `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS` to be safe either way.

2. **Minimum data threshold: 7 or 14 days?**
   - What we know: Phase 33 computes tier distributions from funnel_snapshots_daily. More data = more stable distributions. The success criteria says "7 days."
   - Recommendation: 7 days minimum for validation. Phase 33's scoring uses percentiles across all terms within a tier -- 7 days of ~60 rows/day = ~420 data points per tier, which is sufficient for percentile computation. 14 days would be better for trend analysis but is not required for scoring to function.

3. **CRON_SECRET value -- generate or reuse?**
   - What we know: The env var `CRON_SECRET` is referenced in capture and backfill routes. It may already be set in Vercel (from Phase 30 development/testing) or may need to be created.
   - Recommendation: Check Vercel env vars first. If not set, generate a secure random string (32+ chars) and add to both Vercel and the Cloud Scheduler setup command.

4. **Vercel plan tier for cron slots**
   - What we know: STATE.md has a blocker: "Verify Vercel plan tier -- v1.3c needs 4 cron entries (Hobby: 2, Pro: 40)." Currently `vercel.json` has 1 cron entry (`ga4/snapshot-capture`).
   - What's unclear: Whether this phase needs Vercel Crons at all. Cloud Scheduler is used for funnel capture (not Vercel Crons). The blocker may be about future phases.
   - Recommendation: Phase 32 uses GCP Cloud Scheduler (not Vercel Crons), so the plan tier question doesn't block this phase. Note for future phases that may add Vercel Crons.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) for validation script; vitest for existing TS tests |
| Config file | `pyproject.toml` ([tool.pytest.ini_options], testpaths = ["tests"]) |
| Quick run command | `python scripts/validate_phase32.py` |
| Full suite command | `cd dashboard && npx vitest run src/app/api/funnel-snapshots/` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | Cloud Scheduler running, funnel_snapshots_daily has rows from last 7 days | smoke (SQL query) | `python scripts/validate_phase32.py` | Wave 0 |
| OPS-02 | funnel_snapshots_daily re-backfilled and non-empty | smoke (SQL count) | `python scripts/validate_phase32.py` | Wave 0 |
| OPS-03 | query_value_scores has tier_fit_scores, recommended_tier, net_monthly_impact, scored_at | smoke (information_schema query) | `python scripts/validate_phase32.py` | Wave 0 |
| OPS-04 | experiment_outcomes has p_value, confidence_interval, minimum_sample_size | smoke (information_schema query) | `python scripts/validate_phase32.py` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd dashboard && npm run build` (TypeScript compile check for any modified TS files)
- **Per wave merge:** `python scripts/validate_phase32.py` (runs all 3 success criteria checks)
- **Phase gate:** All 3 checks PASS before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scripts/validate_phase32.py` -- covers OPS-01 through OPS-04 (all checks in one script)
- [ ] Requires `SUPABASE_URL` and `SUPABASE_KEY` env vars (already available in `.env.vercel`)
- [ ] Python `requests` or `supabase` package for HTTP calls to Supabase REST API

## Sources

### Primary (HIGH confidence)
- Existing codebase: `dashboard/src/app/api/funnel-snapshots/capture/route.ts` (capture endpoint implementation)
- Existing codebase: `dashboard/src/app/api/funnel-snapshots/backfill/route.ts` (backfill endpoint implementation)
- Existing codebase: `scripts/setup-funnel-scheduler.sh` (Cloud Scheduler setup pattern)
- Existing codebase: `supabase/migrations/033b_DEFERRED_optimization_control_plane.sql` (query_value_scores schema)
- Existing codebase: `supabase/migrations/035b_DEFERRED_unified_intent_execution_system.sql` (experiment_outcomes schema)
- Existing codebase: `dashboard/vercel.json` (current Vercel cron configuration)
- Phase 30 research: `.planning/milestones/v1.3b-phases/30-historical-funnel-persistence/30-RESEARCH.md`

### Secondary (MEDIUM confidence)
- Schema verification: `docs/database/schema-verification-31-01.md` (confirms 035b tables exist, does not verify 033b)
- Migration triage: `docs/architecture/migration-triage.md` (034b + 035b only, not 033b)

### Tertiary (LOW confidence)
- Whether `query_value_scores` table exists in production (033b not verified in any audit)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools already exist in the project
- Architecture: HIGH -- extending existing proven infrastructure, not building new
- Pitfalls: HIGH -- identified from direct codebase audit (timeout issue, missing table guard, etc.)

**Research date:** 2026-02-25
**Valid until:** 2026-03-25 (infrastructure research, stable domain)
