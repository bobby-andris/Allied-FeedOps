---
phase: 32-operational-prerequisites
verified: 2026-02-25T00:00:00Z
status: passed
score: 3/3 success criteria verified
re_verification: false
---

# Phase 32: Operational Prerequisites — Verification Report

**Phase Goal:** Resolve all data infrastructure gaps so Phase 33+ operate on real data. Activate Cloud Scheduler, backfill funnel data, extend scoring and experiment table schemas.
**Verified:** 2026-02-25
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Cloud Scheduler running and `funnel_snapshots_daily` has rows from last 7 days | VERIFIED | `validate_phase32.py` OPS-01: 936 rows in last 7 days; GCP job confirmed at 6 AM UTC, 2 retries, 300s backoff |
| 2 | `query_value_scores` has `tier_fit_scores`, `recommended_tier`, `net_monthly_impact`, `scored_at` | VERIFIED | `validate_phase32.py` OPS-03: all 4 columns confirmed via PostgREST probe; migration 037 applied |
| 3 | `experiment_outcomes` has `p_value`, `confidence_interval`, `minimum_sample_size` | VERIFIED | `validate_phase32.py` OPS-04: all 3 columns confirmed via PostgREST probe; migration 037 applied |

**Score:** 3/3 truths verified

`python3 scripts/validate_phase32.py` exits 0 — hard gate for Phase 33 cleared.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/037_extend_scoring_and_experiment_columns.sql` | ALTER TABLE for both `query_value_scores` (4 cols) and `experiment_outcomes` (3 cols); CHECK constraints; index | VERIFIED | File exists, 135 lines, substantive. Contains CREATE TABLE IF NOT EXISTS for both tables (safety), all 7 ALTER TABLE ADD COLUMN IF NOT EXISTS, CHECK constraints via DO $$ idempotent blocks, `idx_query_value_scores_scored_at` index. Applied to production via commit `0efd522e`. |
| `dashboard/src/app/api/funnel-snapshots/capture/route.ts` | `sendSlackAlert` helper wired to error and zero-row cases; comment updated to 6 AM UTC | VERIFIED | File exists, 144 lines. `sendSlackAlert` at line 21 uses `process.env.SLACK_WEBHOOK_URL`, wrapped in try/catch. Fires on catch (line 134) and on `rows.length === 0` (line 101). No hardcoded webhook URL. Comment at line 8 reads "6 AM UTC". |
| `scripts/setup-funnel-scheduler.sh` | Schedule `0 6 * * *` UTC, 2 retries, 300s backoff, create-or-update handling | VERIFIED | File exists. `COMMON_ARGS` contains `--schedule="0 6 * * *"`, `--time-zone="UTC"`, `--max-retry-attempts=2`, `--min-backoff="300s"`, `--max-backoff="300s"`. Update vs create handled via `gcloud scheduler jobs describe` check. `bash -n` syntax OK. |
| `scripts/validate_phase32.py` | Phase gate validation script, 3 SQL checks (OPS-01/03/04), PASS/FAIL, exits 0/1 | VERIFIED | File exists, 172 lines. Uses PostgREST (no exec_sql RPC dependency). All 3 checks run independently. Exits 0 on all pass. Confirmed: runs and exits 0 with all PASS. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `capture/route.ts` sendSlackAlert | `process.env.SLACK_WEBHOOK_URL` | `process.env` lookup at line 22 | WIRED | Webhook URL read from env, never hardcoded. Silently skips if unset. |
| `capture/route.ts` error path | `sendSlackAlert` | catch block at line 134 | WIRED | `await sendSlackAlert(...)` called before returning 500 response |
| `capture/route.ts` zero-row path | `sendSlackAlert` | `if (rows.length === 0)` at line 100 | WIRED | Alert fires before 90-day cleanup on zero-row captures |
| `setup-funnel-scheduler.sh` | GCP Cloud Scheduler job `feedops-funnel-snapshot-daily` | `gcloud scheduler jobs` create/update | WIRED | Job confirmed live: `gcloud scheduler jobs describe` returns schedule=`0 6 * * *`, timeZone=UTC, retryCount=2, minBackoff=300s |
| `validate_phase32.py` OPS-01 check | `funnel_snapshots_daily` | PostgREST `GET /rest/v1/funnel_snapshots_daily?select=snapshot_date&snapshot_date=gte.{7 days ago}&limit=1` with `Prefer: count=exact` | WIRED | Returns Content-Range header; confirmed 936 rows |
| `validate_phase32.py` OPS-03/04 checks | `query_value_scores` / `experiment_outcomes` columns | PostgREST `GET /rest/v1/{table}?select={col}&limit=0` per column | WIRED | 200 = column exists, HTTPError = missing. All 7 columns return 200. |
| Migration 037 | Production Supabase | Applied via MCP during phase execution | WIRED | `validate_phase32.py` column probes confirm columns exist in production |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| OPS-01 | 32-02 | Cloud Scheduler activated for `funnel_snapshots_daily` capture (CRON_SECRET configured, setup script run) | SATISFIED | GCP job `feedops-funnel-snapshot-daily` confirmed live. CRON_SECRET set in Vercel (human action per 32-02 Task 3, documented in SUMMARY). `capture/route.ts` auth check uses `process.env.CRON_SECRET`. |
| OPS-02 | 32-03 | `funnel_snapshots_daily` re-backfilled with historical data, verified non-empty | SATISFIED | `validate_phase32.py` OPS-01 check: 936 rows in last 7 days. SUMMARY 32-03 documents 3,953 rows backfilled (Jan 26 – Feb 24). Human action per 32-03 Task 1. |
| OPS-03 | 32-01 | `query_value_scores` extended with `tier_fit_scores`, `recommended_tier`, `net_monthly_impact`, `scored_at` | SATISFIED | Migration 037 applied. `validate_phase32.py` OPS-03: all 4 columns confirmed. CHECK constraint on `recommended_tier` (HIGH/MEDIUM/LOW). Index `idx_query_value_scores_scored_at` created. |
| OPS-04 | 32-01 | `experiment_outcomes` extended with `p_value`, `confidence_interval`, `minimum_sample_size` | SATISFIED | Migration 037 applied. `validate_phase32.py` OPS-04: all 3 columns confirmed. CHECK constraint on `p_value` (0-1). |

All 4 requirement IDs (OPS-01, OPS-02, OPS-03, OPS-04) from REQUIREMENTS.md are accounted for across plans 32-01, 32-02, and 32-03. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `scripts/validate_phase32.py` | 56 | `raise NotImplementedError(...)` in `run_sql_via_postgrest` | Info | Dead code path — `run_sql()` is never called by the three check functions (they use direct PostgREST queries). Script ran and exited 0 confirming this path is unreachable. No operational impact. |

No blockers or warnings. The `NotImplementedError` is in an unreachable fallback function.

### Human Verification Required

#### 1. Slack Alert Delivery

**Test:** Trigger the capture endpoint with an invalid CRON_SECRET so it returns 500, then check that a Slack alert arrives in the configured channel.
**Expected:** A `:warning: FunnelCapture FAILED` message appears in the Slack channel within ~30 seconds.
**Why human:** Cannot verify webhook delivery programmatically — the webhook URL is a Vercel env var not exposed to this session, and Slack delivery confirmation requires checking the channel.

#### 2. Scheduler First Automatic Execution

**Test:** Wait for 6 AM UTC and confirm a new row appears in `funnel_snapshots_daily` with `snapshot_date = yesterday`, OR check Vercel function logs for `[funnel-capture] Upserted N rows`.
**Expected:** The scheduler fires automatically, captures data, and logs a successful upsert.
**Why human:** Scheduler has not yet fired autonomously (job was configured 2026-02-25). Verifying automatic execution requires waiting for the next 6 AM UTC window and checking logs.

### Gaps Summary

No gaps. All success criteria verified, all requirements satisfied, all artifacts are substantive and wired.

The one `NotImplementedError` in `validate_phase32.py` is dead code (unreachable at runtime) and does not affect the script's correctness — confirmed by the script running to completion with exit code 0.

Human verification items (Slack delivery and first automatic scheduler run) are informational checks. They do not block Phase 33 — the hard gate script (`validate_phase32.py`) has already exited 0.

---

_Verified: 2026-02-25_
_Verifier: Claude (gsd-verifier)_
