---
phase: 30-historical-funnel-persistence
verified: 2026-02-25T11:10:00Z
status: human_needed
score: 5/6 must-haves verified
re_verification: false
human_verification:
  - test: "Confirm funnel_snapshots_daily table has 7+ days of data in production Supabase"
    expected: "SELECT count(DISTINCT snapshot_date) FROM funnel_snapshots_daily returns >= 7"
    why_human: "Cloud Scheduler has not yet been configured (user_setup item from Plan 01). Table was created and migration applied, but daily capture requires manual CRON_SECRET setup + scheduler job creation before data accumulates. This is a known pending action, not a code defect."
---

# Phase 30: Historical Funnel Persistence Verification Report

**Phase Goal:** Shopping Funnel dashboard shows historical trends instead of only live ephemeral data
**Verified:** 2026-02-25T11:10:00Z
**Status:** human_needed (all code verified; one success criterion requires accumulated runtime data)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | funnel_snapshots_daily table exists with correct schema and unique constraint | VERIFIED | Migration `20260225105102_create_funnel_snapshots_daily.sql` applied; Plan 01 SUMMARY confirms production Supabase verification |
| 2 | POST /api/funnel-snapshots/capture authenticates, upserts, and runs 90-day retention | VERIFIED | `capture/route.ts` (106 lines): Bearer auth check, `getLabelTierPerformance` call, upsert with `onConflict`, `.delete().lt().select('id')` chain; 7/7 capture.test.ts tests pass |
| 3 | Re-running capture for the same day upserts without duplicates | VERIFIED | `onConflict: 'snapshot_date,custom_label_0,tier'` wired in route.ts line 70; test "handles re-run for same day via upsert" passes |
| 4 | GET /api/funnel-snapshots/trends returns 7d vs prev-7d aggregates for all 6 metrics | VERIFIED | `trends/route.ts` (138 lines): 15-day query window, period split, CTR/ROAS with division-by-zero guards, Cache-Control header; 6/6 trends.test.ts tests pass |
| 5 | FunnelTrendCards renders 6 cards above the Tabs with up/down/flat arrows | VERIFIED | `FunnelTrendCards.tsx` (218 lines): 6 METRIC_CARDS (Impressions, Clicks, CTR, Ad Spend, Conversions, ROAS), TrendArrow with 5% threshold, Ad Spend invertColor; 8/8 FunnelTrendCards.test.tsx tests pass |
| 6 | funnel_snapshots_daily table contains at least 7 days of accumulated data | NEEDS HUMAN | Table created and capture endpoint working, but Cloud Scheduler not yet configured (user_setup item). Data accumulation requires CRON_SECRET in Vercel + scheduler job creation. |

**Score:** 5/6 truths verified (automated); 1 requires human confirmation of Cloud Scheduler setup

---

### Required Artifacts

| Artifact | Min Lines | Actual Lines | Status | Details |
|----------|-----------|-------------|--------|---------|
| `dashboard/src/app/api/funnel-snapshots/__tests__/capture.test.ts` | 40 | 199 | VERIFIED | 7 test cases: auth rejection, upsert, retention cleanup, error handling |
| `dashboard/src/app/api/funnel-snapshots/__tests__/trends.test.ts` | 40 | 176 | VERIFIED | 6 test cases: aggregation, CTR/ROAS guards, has_data/has_previous edge cases, Cache-Control |
| `dashboard/src/app/(dashboard)/shopping-funnel/__tests__/FunnelTrendCards.test.tsx` | 40 | 326 | VERIFIED | 8 test cases: render-nothing, 6 cards, arrows, threshold, invertColor, formatting |
| `dashboard/src/app/api/funnel-snapshots/capture/route.ts` | 40 | 106 | VERIFIED | POST handler with auth, getLabelTierPerformance call, upsert, 90-day cleanup |
| `scripts/setup-funnel-scheduler.sh` | 15 | 66 | VERIFIED | 5 AM ET schedule, retry config, --delete option, data settlement advisory comment |
| `dashboard/src/app/api/funnel-snapshots/trends/route.ts` | 30 | 138 | VERIFIED | GET handler, 15-day window, period split, CTR/ROAS computation, Cache-Control |
| `dashboard/src/app/(dashboard)/shopping-funnel/FunnelTrendCards.tsx` | 60 | 218 | VERIFIED | 6 cards, TrendArrow, invertColor for Ad Spend, skeleton loading, null on no data |
| `supabase/migrations/20260225105102_create_funnel_snapshots_daily.sql` | — | 21 | VERIFIED | TABLE DDL, UNIQUE constraint, index, RLS enabled |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `capture/route.ts` | `service.ts` | `import getLabelTierPerformance` | WIRED | Line 13: `import { getLabelTierPerformance } from '@/lib/shopping-funnel/service'`; line 44: called with startDate/endDate |
| `capture/route.ts` | `funnel_snapshots_daily` | `supabase.from('funnel_snapshots_daily').upsert()` | WIRED | Line 69-70: `.from('funnel_snapshots_daily').upsert(rows, { onConflict: ... })` |
| `trends/route.ts` | `funnel_snapshots_daily` | `supabase.from('funnel_snapshots_daily').select()` | WIRED | Lines 86-90: `.from('funnel_snapshots_daily').select('*').gte().lte()` |
| `FunnelTrendCards.tsx` | `trends/route.ts` | `fetch('/api/funnel-snapshots/trends')` | WIRED | Line 150: `fetch('/api/funnel-snapshots/trends')` in useEffect |
| `page.tsx` | `FunnelTrendCards.tsx` | `import and render above Tabs` | WIRED | Line 47: import; line 1350: `<FunnelTrendCards />` — git diff f5c781e5 confirms exactly 2 additive lines |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| HIST-01 | 30-00, 30-01 | funnel_snapshots_daily table with 90-day retention | SATISFIED | Table DDL applied to production; retention DELETE in capture/route.ts line 84-90; capture.test.ts "deletes rows older than 90 days" passes |
| HIST-02 | 30-00, 30-01 | Daily capture endpoint triggered by Cloud Scheduler | SATISFIED (code) / PENDING (scheduler) | capture/route.ts fully implemented and tested; setup-funnel-scheduler.sh exists and is syntactically valid; user_setup action pending (CRON_SECRET + scheduler job creation) |
| HIST-03 | 30-00, 30-02 | 7d vs prev-7d trend indicators on Shopping Funnel page | SATISFIED | trends/route.ts + FunnelTrendCards.tsx wired into page.tsx; all 14 tests pass; build passes |

**Orphaned requirements check:** REQUIREMENTS.md maps only HIST-01, HIST-02, HIST-03 to Phase 30. All three are claimed by plans and have implementation evidence. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `page.tsx` (pre-existing) | 514 | `react-hooks/exhaustive-deps` warning for `deferredExistingSearch` | Info | Pre-existing lint warning unrelated to Phase 30 changes; zero errors |
| `ReviewListClient.tsx` (pre-existing) | 117 | `<img>` instead of Next.js `<Image />` | Info | Pre-existing warning unrelated to Phase 30; zero errors |

No anti-patterns in Phase 30 production files. Zero TODO/FIXME/PLACEHOLDER comments found in any Phase 30 created files.

---

### Test Results

All 21 tests pass across 3 test files (run: `npx vitest run`):

- `capture.test.ts`: 7 tests — auth rejection (401), upsert behavior, retention cleanup (rows_deleted count), error handling (500)
- `trends.test.ts`: 6 tests — 7d/prev-7d aggregation, CTR/ROAS division-by-zero guards, has_data=false, has_previous=false, Cache-Control header
- `FunnelTrendCards.test.tsx`: 8 tests — render null on no data, 6 metric card names, "No prior data", green/red arrows, 5% flat threshold, Ad Spend color inversion, number formatting

---

### Build Verification

`npm run build` passes with zero errors. `/shopping-funnel` route included in build output. Zero TypeScript compilation errors.

---

### Human Verification Required

#### 1. Cloud Scheduler Configuration

**Test:** Check Vercel env vars for `CRON_SECRET` and verify GCP Cloud Scheduler job exists
**Expected:**
- `gcloud scheduler jobs describe feedops-funnel-snapshot-daily --project=bobbys-project-346400 --location=us-east1` returns job details with schedule `0 5 * * *` and timezone `America/New_York`
- Vercel Dashboard > Settings > Environment Variables contains `CRON_SECRET`
**Why human:** This is a `user_setup` action defined in Plan 01 frontmatter. The script `scripts/setup-funnel-scheduler.sh` exists and is valid, but running it requires a CRON_SECRET value and GCP CLI access. The code is complete; the infrastructure wiring is pending user action.

#### 2. Accumulated Data Verification (depends on scheduler setup)

**Test:** Query `SELECT count(DISTINCT snapshot_date) FROM funnel_snapshots_daily` via Supabase
**Expected:** Returns >= 7 (at least 7 days of data for Success Criterion 1 to be met)
**Why human:** Data accumulates only after the Cloud Scheduler is configured and has run for 7+ days. Success Criterion 1 from ROADMAP.md ("The funnel_snapshots_daily table contains at least 7 days of historical search term tier data") cannot be verified until the scheduler has operated in production.

#### 3. Trend Cards Visual Appearance

**Test:** Navigate to the Shopping Funnel page once data exists
**Expected:** 6 trend summary cards appear above the tabs, showing 7-day totals with green/red/flat trend indicators; cards hidden entirely when no data
**Why human:** Visual layout and responsive grid behavior (1 col mobile / 2 col sm / 3 col lg) requires browser inspection. Component renders null until data exists so currently not visible.

---

### Gaps Summary

No code gaps found. All production code is substantive, wired, and tested. The single human_needed item (Cloud Scheduler setup) is a known pending user action — it is a `user_setup` item explicitly called out in Plan 01 frontmatter and documented in the Plan 01 SUMMARY. The code for automated daily capture is fully implemented; the infrastructure trigger requires one-time manual configuration.

**Recommendation:** Once the user completes the Cloud Scheduler setup (generate CRON_SECRET, add to Vercel, run `bash scripts/setup-funnel-scheduler.sh <SECRET>`), phase goal achievement will be fully confirmed after 7 days of data accumulation.

---

_Verified: 2026-02-25T11:10:00Z_
_Verifier: Claude (gsd-verifier)_
