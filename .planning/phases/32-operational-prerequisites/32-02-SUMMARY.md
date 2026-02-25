---
plan: 32-02
title: Cloud Scheduler Activation — Capture Endpoint + Slack Alerting + Scheduler Setup
status: complete
started: 2026-02-25
completed: 2026-02-25
---

## What Was Built

Added Slack failure alerting to the funnel capture endpoint and updated the Cloud Scheduler job to 6 AM UTC with 2 retries / 5-minute spacing. Scheduler is live and configured in GCP.

## Key Files

### Modified
- `dashboard/src/app/api/funnel-snapshots/capture/route.ts` — Added `sendSlackAlert` helper, wired to error and zero-row cases
- `scripts/setup-funnel-scheduler.sh` — Updated schedule, retry config, added update-vs-create handling

## Decisions Made
- Used `--update-headers` for gcloud scheduler update (different flag than `--headers` used by create)
- Split COMMON_ARGS and HEADERS to handle create vs update flag differences
- Slack alert recomputes yesterday's date in catch block (original `d` variable may not be in scope)

## Deviations
- None

## Self-Check: PASSED
- [x] Slack alert fires on endpoint error
- [x] Slack alert fires on zero-row capture
- [x] No alert on successful capture
- [x] SLACK_WEBHOOK_URL in Vercel env vars (not in source code)
- [x] Scheduler job updated: 6 AM UTC, 2 retries, 300s backoff
- [x] npm run build passes
