---
phase: 09-sku-review-revamp
plan: 02
subsystem: ui
tags: [next.js, typescript, react, tailwind, url-state]

# Dependency graph
requires:
  - 09-01 (ReviewListClient with 4-state platform badges and platform_progress data)
provides:
  - Stats summary bar with per-platform 4-state counts (Needs Review/Partial/Approved/Published)
  - Filter controls wired to URL search params (?status=...&platform=...)
  - filteredSkus useMemo filtering by status + platform
  - applyFilter shared by stats bar buttons and filter dropdowns
affects:
  - 09-03-inline-approval (ReviewListClient is the list; plan 09-03 adds inline approve actions)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - URL param-based filter state via useSearchParams + router.replace (scroll: false)
    - useMemo for both stats aggregation and filtered list derivation
    - useCallback for applyFilter to avoid unnecessary re-renders
    - Stats computed client-side from already-fetched platform_progress data (no extra API calls)

key-files:
  created: []
  modified:
    - dashboard/src/components/review/ReviewListClient.tsx

key-decisions:
  - "Single applyFilter function shared by stats bar and dropdowns ensures identical filter behavior from both interaction paths"
  - "Stats computed via useMemo over platform_progress.state — no new data fetching needed"
  - "Suspense boundary not needed — /review is already a dynamic server route; no build error"
  - "Removed Input search field from filter bar (not in plan spec, replaced with select-only controls)"

# Metrics
duration: 3min
completed: 2026-02-18
---

# Phase 9 Plan 02: Stats Bar and Filter Wiring Summary

**4-state stats summary bar (Google/Bing/Shopify) with clickable counts, filter dropdowns wired to URL search params, and filteredSkus useMemo — all computed from existing platform_progress data without additional API calls**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-18T22:54:36Z
- **Completed:** 2026-02-18T22:57:36Z
- **Tasks:** 2 (implemented in single pass per plan spec)
- **Files modified:** 1

## Accomplishments

- Stats summary bar: 3-column grid (Google / Bing / Shopify), each with 4 clickable count buttons (Needs Review gray, Partial yellow, Approved blue, Published green)
- Stats computed from `platform_progress.state` via `useMemo` — maps `blocked` → Needs Review, `partial` → Partial, `ready` → Approved, `published` → Published
- Filter controls: Status dropdown (all/needs-review/partial/approved/published) + Platform dropdown (all/google/bing/shopify)
- `applyFilter(status, platform)` shared by both stats bar buttons and dropdowns — updates URL params via `router.replace` (scroll: false) for persistence
- `filteredSkus` useMemo filters `skus` by `activeStatus` and `activePlatform` from URL params
- Clear filters button appears when any filter is active — resets both params
- Filtered count label: "N of M SKUs" aligned right in filter bar
- Build and TypeScript: zero errors

## Task Commits

Tasks 1 and 2 implemented in one pass per plan spec (applyFilter forward reference required both tasks in same file):

1. **Tasks 1 + 2: Stats bar + filter controls wired with URL persistence** - `2b00d309` (feat)

## Files Modified

- `dashboard/src/components/review/ReviewListClient.tsx` — Added:
  - `useMemo`, `useCallback` imports from react
  - `useSearchParams`, `useRouter`, `usePathname` imports from next/navigation
  - `stats` useMemo: per-platform 4-state counts
  - `filteredSkus` useMemo: filters by activeStatus + activePlatform
  - `applyFilter` useCallback: URL param updates via router.replace
  - Stats summary bar JSX: 3-column grid with 4 clickable buttons per platform
  - Filter bar JSX: status select + platform select + clear button + count label
  - Renders `filteredSkus` instead of `skus` in the list

## Filter URL Param Scheme

- `?status=needs-review` — maps to `platform_progress.state === 'blocked'`
- `?status=partial` — maps to `platform_progress.state === 'partial'`
- `?status=approved` — maps to `platform_progress.state === 'ready'`
- `?status=published` — maps to `platform_progress.state === 'published'`
- `?platform=google|bing|shopify` — filters to specific platform progress entries
- Absent params = "all" (no filter applied)
- Both params can be combined (e.g., `?status=partial&platform=google`)

## Stats Computation Approach (4-state)

Stats are computed client-side from the `platform_progress` array already present on each `SkuRow`. No additional API calls or DB queries. For each platform:

```
needsReview = skus where platform_progress[platform].state === 'blocked'
partial     = skus where platform_progress[platform].state === 'partial'
approved    = skus where platform_progress[platform].state === 'ready'
published   = skus where platform_progress[platform].state === 'published'
```

State mapping reflects 09-01's priority: published > ready > partial > blocked.

## Edge Cases Handled

- Platform not found in `platform_progress`: `find()` returns `undefined`, filtered out before count
- Filtered list empty: Shows "No SKUs found" message (existing handler)
- Both filters at 'all': "Clear filters" button hidden (conditional render)
- Stats bar click on a count that is 0: Still applies filter (results in empty list with "No SKUs found")

## Deviations from Plan

### Auto-removed: Search Input field

The placeholder filter bar in Plan 09-01 included an `<Input placeholder="Search SKUs..." readOnly />` element that was purely visual. The Plan 09-02 spec for the filter bar does not include a search input — only the two Select dropdowns and the count label. The search input was removed as part of replacing the placeholder with the wired implementation. This matches the plan spec exactly.

No other deviations.

## Issues Encountered

None. Build passed on first attempt. TypeScript check returned zero errors. No Suspense boundary needed (dynamic route already).

## Next Phase Readiness

- ReviewListClient is ready for Plan 09-03 (inline approval actions)
- `per_platform_approval` field on each SkuRow is still available for 09-03's approve/reject buttons
- URL filter state is now established — 09-03 can extend params if needed

---
*Phase: 09-sku-review-revamp*
*Completed: 2026-02-18*

## Self-Check: PASSED

- FOUND: dashboard/src/components/review/ReviewListClient.tsx
- FOUND: .planning/phases/09-sku-review-revamp/09-02-SUMMARY.md
- FOUND commit: 2b00d309 (Tasks 1 + 2)
