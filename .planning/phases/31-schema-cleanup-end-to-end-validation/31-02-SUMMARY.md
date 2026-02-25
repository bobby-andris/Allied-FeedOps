---
phase: 31-schema-cleanup-end-to-end-validation
plan: 02
subsystem: ui
tags: [react, next.js, sku-review, coming-soon, sidebar, gmc-badge, prompt-lineage]

# Dependency graph
requires:
  - phase: 31-01
    provides: Schema cleanup and orphan analysis identifying disconnected components
provides:
  - GmcDisapprovalBadge wired into main SkuReviewClient with live GMC status fetch
  - PromptLineagePanel wired into main SkuReviewClient with lazy-load on expand
  - Coming Soon pages replacing broken empty-table Optimization and Intent Control Centers
  - Sidebar badges indicating DEFER'd pages
affects: [v1.3c-optimization, v1.3c-intent]

# Tech tracking
tech-stack:
  added: []
  patterns: [coming-soon-pattern, sidebar-badge-pattern]

key-files:
  created: []
  modified:
    - dashboard/src/components/review/SkuReviewClient.tsx
    - dashboard/src/app/(dashboard)/optimization-control-center/page.tsx
    - dashboard/src/app/(dashboard)/intent-control-center/page.tsx
    - dashboard/src/components/shared/Sidebar.tsx

key-decisions:
  - "GmcDisapprovalBadge placed inline next to SKU title in header for immediate visibility"
  - "PromptLineagePanel placed between content blocks and approval actions for logical flow"
  - "DEFER'd pages converted from client to server components since no interactivity needed"

patterns-established:
  - "Coming Soon pattern: Card with Construction icon, version target, and description for unreleased features"
  - "Sidebar badge pattern: NavItem interface with optional badge field rendered as small muted tag"

requirements-completed: [MIGR-02, MIGR-03]

# Metrics
duration: 4min
completed: 2026-02-25
---

# Phase 31 Plan 02: Wire Orphaned Components and Coming Soon States Summary

**Wired GmcDisapprovalBadge and PromptLineagePanel into SKU Review, replaced DEFER'd pages with Coming Soon cards, added sidebar badges**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-25T14:29:47Z
- **Completed:** 2026-02-25T14:33:39Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- GmcDisapprovalBadge now renders inline near SKU title when GMC issues exist (invisible otherwise)
- PromptLineagePanel renders below content section with lazy-load on expand (self-contained)
- Optimization Control Center and Intent Control Center show clear "Coming in v1.3c" messaging instead of broken empty-table queries
- Sidebar shows "Soon" badges on DEFER'd pages for polished user experience
- 1,442 lines of dead client-side code removed from DEFER'd pages

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire GmcDisapprovalBadge and PromptLineagePanel into main SkuReviewClient** - `7ad22bfa` (feat)
2. **Task 2: Replace DEFER'd pages with Coming Soon states and update sidebar** - `1ccf782c` (feat)

## Files Created/Modified
- `dashboard/src/components/review/SkuReviewClient.tsx` - Added GMC status fetch, GmcDisapprovalBadge inline, PromptLineagePanel below content
- `dashboard/src/app/(dashboard)/optimization-control-center/page.tsx` - Replaced with Coming Soon server component
- `dashboard/src/app/(dashboard)/intent-control-center/page.tsx` - Replaced with Coming Soon server component
- `dashboard/src/components/shared/Sidebar.tsx` - Added NavItem interface with badge support, "Soon" badges on DEFER'd pages

## Decisions Made
- GmcDisapprovalBadge placed inline next to SKU title in header for immediate visibility
- PromptLineagePanel placed between content blocks and approval actions for logical content flow
- DEFER'd pages converted from client to server components (no interactivity needed for static Coming Soon cards)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing TypeScript errors in `funnel-snapshots/__tests__/trends.test.ts` (from Phase 30.1) -- out of scope, did not affect build

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All orphaned components are now wired and visible in the SKU Review page
- DEFER'd pages clearly communicate v1.3c timeline to users
- Build and lint pass cleanly

## Self-Check: PASSED

All 4 modified files verified on disk. Both task commits (7ad22bfa, 1ccf782c) verified in git log.

---
*Phase: 31-schema-cleanup-end-to-end-validation*
*Completed: 2026-02-25*
