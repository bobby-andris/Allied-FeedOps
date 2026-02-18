---
created: 2026-02-18T21:19:28.262Z
title: Backfill performance snapshots and improve Performance page
area: ui
files:
  - dashboard/src/app/(dashboard)/performance/page.tsx
  - dashboard/src/app/api/performance/route.ts
  - dashboard/src/app/api/performance/capture-snapshot/route.ts
---

## Problem

~35 SKUs have already been published to Google Ads but the Performance page (`/performance`) shows no useful data because:
1. `performance_snapshots` table only has 1 row (a test entry) — no real post-publish snapshots captured yet
2. `performance_baselines` has 181 rows across 89 SKUs — pre-publish data is there
3. The nightly Cloud Scheduler job (`feedops-daily-snapshot-capture`, 3am PT) was just created today (2026-02-18) so won't have history

The Performance page compares `performance_baselines` (pre-publish) vs `performance_snapshots` (post-publish) to show CTR/CVR/impressions/clicks delta. Without snapshots, every SKU shows "no data."

## Solution

**Two quick tasks in order:**

### Quick Task A: Backfill snapshots for published SKUs
- Query `publish_events` for all SKUs with `platform = 'google'` — expect ~35 rows
- Call `POST /api/performance/capture-snapshot` for each published SKU (or call once without params to capture all)
- The endpoint is at: `https://allied-feed-ops.vercel.app/api/performance/capture-snapshot`
- Check `dashboard/src/app/api/performance/capture-snapshot/route.ts` for exact API contract
- After backfill, verify `performance_snapshots` has rows with real `days_since_publish` values

### Quick Task B: Audit and fix Performance page API
- Check `dashboard/src/app/api/performance/route.ts` — verify it correctly JOINs `performance_baselines` + `performance_snapshots`
- The page fetches `/api/performance?dateRange=30d&platform=all`
- If snapshot data exists after Task A but page still shows nothing, the API query logic may need fixing
- Key schema facts:
  - `performance_snapshots`: master_sku, platform, days_since_publish, impressions, clicks, ctr, cvr, captured_at (NOTE: executor found column may be `fetched_at` not `captured_at` — CHECK SCHEMA.md first)
  - `performance_baselines`: master_sku, platform, avg_impressions, avg_clicks, avg_ctr, avg_cvr, captured_at
  - Published SKUs: query `SELECT DISTINCT master_sku FROM publish_events WHERE platform = 'google'`

## Context from conversation (2026-02-18)

- Monitoring endpoints now working after Phase 08 gap closure
- Slack notifications configured (SLACK_WEBHOOK_URL set on Cloud Run)
- Backfill Monitoring added to sidebar nav in Quick Task 1
- Cloud Scheduler: 2am PT = incremental refresh, 3am PT = snapshot capture (both just set up)
- ~35 SKUs published to Google, baselines exist for 89 SKUs
