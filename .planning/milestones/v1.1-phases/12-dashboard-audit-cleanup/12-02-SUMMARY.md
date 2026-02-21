---
phase: 12-dashboard-audit-cleanup
plan: "02"
subsystem: dashboard
tags: [ux, bugfix, cleanup, monitoring, settings, overview]
dependency_graph:
  requires: [12-01]
  provides: [fixed-monitoring-page, fixed-settings-page, fixed-overview-stats]
  affects: [dashboard/src/app/(dashboard)/monitoring/page.tsx, dashboard/src/app/(dashboard)/settings/page.tsx, dashboard/src/app/api/stats/route.ts, dashboard/src/app/(dashboard)/page.tsx]
tech_stack:
  added: []
  patterns: [inline-alert-feedback, contextual-empty-states, env-var-display]
key_files:
  created: []
  modified:
    - dashboard/src/app/(dashboard)/monitoring/page.tsx
    - dashboard/src/app/(dashboard)/settings/page.tsx
    - dashboard/src/app/api/stats/route.ts
    - dashboard/src/app/(dashboard)/page.tsx
decisions:
  - "Monitoring page split into two snapshot buttons (Search vs Performance) to make the endpoint distinction explicit — users previously expected one button to refresh both tabs"
  - "Settings notification switches removed entirely (not replaced with functional ones) — deferred wiring as out-of-scope; static description explains Slack webhook config instead"
  - "Danger Zone buttons removed in favor of text guidance — no click handlers existed, misleading UI worse than no UI"
  - "pendingReview in stats API now uses generated_content count minus approved count — sku_approvals.status=pending was misleading since many SKUs never get a pending row"
  - "Platform breakdown fallback removed — zeros are now returned when no variant_approvals exist for a platform, making empty state explicit"
metrics:
  duration_minutes: 3
  completed_date: "2026-02-19"
  tasks_completed: 2
  files_changed: 4
---

# Phase 12 Plan 02: Fix BROKEN and STALE Pages Summary

Fixed every FIX-action page identified in 12-AUDIT.md: replaced alert() in the monitoring page with inline feedback, split snapshot buttons by endpoint, added navigation links to empty states, removed non-functional settings UI, and corrected misleading overview stats.

## Fixes Applied

### 1. Post-Publish Monitoring (`/monitoring`) — BROKEN → FIXED

**File:** `dashboard/src/app/(dashboard)/monitoring/page.tsx`

| Issue | Fix |
|-------|-----|
| `alert()` on line 107 for snapshot feedback | Replaced with `SnapshotResult` state + `Alert` component from `@/components/ui/alert` with `CheckCircle2` / `XCircle` icons |
| "Capture Snapshots" button called search endpoint only | Split into two buttons: "Capture Search Snapshots" (`/api/monitoring/snapshot-capture`) and "Capture Performance Snapshots" (`/api/performance/capture-snapshot`) |
| Performance delta empty state: generic "wait 7+ days" | Contextual message + link: "View performance snapshots →" to `/performance` |
| Search delta empty state: "Run search insights sync first" | Contextual message + link: "Go to Search Insights to sync →" to `/search-insights` |

New imports added: `Alert`, `AlertDescription` from `@/components/ui/alert`; `CheckCircle2`, `XCircle` from `lucide-react`; `Link` from `next/link`.

---

### 2. Settings (`/settings`) — STALE → FIXED

**File:** `dashboard/src/app/(dashboard)/settings/page.tsx`

| Issue | Fix |
|-------|-----|
| Notification `Switch` components with no state/persistence | Removed switches entirely; replaced with static description explaining `SLACK_WEBHOOK_URL` env var config |
| Danger Zone "Clear" buttons with no click handlers | Removed buttons; replaced with text guidance directing users to Supabase dashboard |
| Hardcoded Supabase URL `https://qezuszwufortkiutlhym.supabase.co` | Replaced with `process.env.NEXT_PUBLIC_SUPABASE_URL` |

Removed unused import: `Switch` from `@/components/ui/switch`.

---

### 3. Overview (`/`) — STALE → FIXED

**Files:** `dashboard/src/app/api/stats/route.ts` + `dashboard/src/app/(dashboard)/page.tsx`

| Issue | Fix |
|-------|-----|
| `pendingReview` used `sku_approvals.status = 'pending'` — SKUs with generated content but no approval row showed as 0 pending | Changed to `Math.max(0, totalGenerated - totalApproved)` — counts generated_content rows minus approved rows |
| Platform breakdown fell back to overall sku_approvals totals when variant_approvals empty — triplicate display of same numbers | Removed fallback; platform breakdown now returns zeros when no variant_approvals exist for a platform |
| Quality Distribution "No scores yet" shown when `average === 0` (valid score) | Changed condition from `average > 0` to `distribution.reduce((sum, d) => sum + d.count, 0) > 0` |

---

## Build Status

| Check | Before | After |
|-------|--------|-------|
| `npm run build` | N/A (fixes applied) | PASS — 56 pages, 0 errors |
| `npm run lint` | N/A | PASS — 0 errors (2 pre-existing warnings in unrelated files) |
| TypeScript | N/A | PASS (implicit via build) |

---

## Deviations from Plan

None — plan executed exactly as written. All four root-cause issues from each audit section were resolved.

---

## Commits

- `211053b9` — fix(12-02): resolve broken and stale pages from audit

## Self-Check: PASSED

- `dashboard/src/app/(dashboard)/monitoring/page.tsx` exists and no longer contains `alert(`
- `dashboard/src/app/(dashboard)/settings/page.tsx` exists and no longer imports `Switch`
- `dashboard/src/app/api/stats/route.ts` no longer contains `fallback` comment with sku_approvals override
- `dashboard/src/app/(dashboard)/page.tsx` condition updated to use distribution count
- Commit `211053b9` in git log
- Build passes, push to master succeeded — Vercel deployment triggered
