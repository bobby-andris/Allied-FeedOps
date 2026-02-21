---
phase: 09-sku-review-revamp
plan: 03
subsystem: ui
tags: [next.js, typescript, react, tailwind, optimistic-ui, supabase-rpc]

# Dependency graph
requires:
  - 09-01 (ReviewListClient with 4-state platform badges and platform_progress data)
  - 09-02 (stats bar + filter controls wired to URL params)
provides:
  - Inline expand/collapse row preview panel with per-platform Mark Approved action
  - POST /api/review/approve-platform API route
  - ImageRowBadge compact 4-state image lifecycle column in list rows
  - LifestyleImageBadge full-detail image lifecycle display in preview panel
  - get_catalog_thumbnails RPC call replacing product_catalog table query (bypasses 1000-row limit)
affects:
  - Vercel production deploy (pushed to master, auto-deploy triggered)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Optimistic UI update with rollback on failure (useState + fetch + catch)
    - useRef + useEffect for auto-scroll to expanded panel (scrollIntoView)
    - expandedSku toggle pattern (one-open-at-a-time: setExpandedSku prev => prev === sku ? null : sku)
    - e.stopPropagation() on button clicks inside clickable row div
    - Supabase RPC call via .rpc('get_catalog_thumbnails', { sku_list }) to bypass PostgREST 1000-row limit
    - LifestyleImageLifecycle interface (total/approved/published) from variant_lifestyle_images

key-files:
  created:
    - dashboard/src/app/api/review/approve-platform/route.ts
  modified:
    - dashboard/src/components/review/ReviewListClient.tsx
    - dashboard/src/app/(dashboard)/review/page.tsx

key-decisions:
  - "Optimistic approval update with rollback: badge changes instantly on click; reverts if API call fails"
  - "expandedSku as single string (not array) enforces one-row-open-at-a-time without extra logic"
  - "approve-platform uses fetch-then-loop pattern (not column-to-column Supabase update) since JS client cannot reference columns in update values"
  - "get_catalog_thumbnails RPC replaces direct product_catalog table query to bypass PostgREST 1000-row default limit"
  - "LifestyleImageLifecycle added to SkuRow: shopify_media_id IS NOT NULL = published, approval_status = approved = approved, any row = generated"
  - "ImageRowBadge follows same 4-state color convention as platform badges (gray/yellow/blue/green)"
  - "Preview panel restructured: prominent Open Full Review button top-right (primary color) replaces plain text link at bottom"

# Metrics
duration: 47min
completed: 2026-02-18
---

# Phase 9 Plan 03: Inline Expand, Quick Approve, and Image Lifecycle Summary

**Inline expand/collapse row preview with per-platform Mark Approved action (optimistic update, no navigation), ImageRowBadge 4-state image lifecycle column, and product_catalog RPC fix for 1000-row limit**

## Performance

- **Duration:** 47 min (includes human verification checkpoint)
- **Started:** 2026-02-18T23:00:23Z
- **Completed:** 2026-02-18T23:48:19Z
- **Tasks:** 2 (Task 1 auto, Task 2 human-verify checkpoint)
- **Files created:** 1
- **Files modified:** 2

## Accomplishments

**Task 1 — Inline expand/collapse + approve-platform API:**
- `expandedSku` useState(null) toggles one row at a time; clicking open row closes it
- ChevronRight icon rotates 90deg on open via `transition-transform` + conditional `rotate-90`
- `SkuPreviewPanel` component: per-platform badges + Mark Approved buttons, LifestyleImageBadge, Close
- `handleQuickApprove` with optimistic update and rollback on fetch failure
- `POST /api/review/approve-platform`: fetches unapproved candidate_content rows, copies to approved_content, upserts sku_approvals — proper error handling throughout
- Auto-scroll to expanded panel via `useRef` + `scrollIntoView({ behavior: 'smooth', block: 'nearest' })`
- Build pass + TypeScript zero errors on first attempt

**Human checkpoint verification — extra fixes applied:**
- `get_catalog_thumbnails` RPC replaces direct `product_catalog` table query — fixes 1000-row PostgREST limit that caused thumbnail/title data to silently truncate at 1000 SKUs
- `LifestyleImageLifecycle` interface added to `page.tsx` and exported for use in `ReviewListClient`
- `shopify_media_id` added to `variant_lifestyle_images` select — enables published count
- `ImageRowBadge` added to each list row (inline 4-state: None/Generated/Approved/Published)
- `LifestyleImageBadge` added to preview panel with counts and guidance text
- Preview panel restructured: product title + quality score on left, prominent "Open Full Review" button (primary color) on right in header row

## Task Commits

| Task | Description | Commit | Type |
| ---- | ----------- | ------ | ---- |
| 1 | Inline expand/collapse + approve-platform API route | fca7282a | feat |
| 2 | Human checkpoint: image lifecycle, RPC fix, UX improvements | 4f8ac6c0 | feat |

## Files Modified

- `dashboard/src/app/api/review/approve-platform/route.ts` (created):
  - POST handler with input validation
  - Fetch-then-loop to copy candidate_content → approved_content
  - Upsert sku_approvals with title_approved/description_approved/image_approved/approval_status
  - Full try/catch with proper error responses

- `dashboard/src/components/review/ReviewListClient.tsx` (modified):
  - Added `useState`, `useRef`, `useEffect` imports
  - Added `LifestyleImageLifecycle` import from page.tsx
  - `SkuRow` extended with `lifestyle_images: LifestyleImageLifecycle`
  - `getPlatformLabel()` helper added
  - `ImageRowBadge` component (4-state: None/Generated/Approved/Published)
  - `LifestyleImageBadge` component with counts and guidance text
  - `SkuPreviewPanel` restructured with header row (title + Open Full Review button)
  - `expandedSku` and `optimisticApprovals` state in `ReviewListClient`
  - `handleQuickApprove` with optimistic update + rollback
  - Row `onClick` toggle, `ref={expandedRef}` on panel div
  - Image column added to column headers

- `dashboard/src/app/(dashboard)/review/page.tsx` (modified):
  - `LifestyleImageLifecycle` interface exported
  - `SkuWithContent` gains `lifestyle_images` field
  - `VariantImageRow` gains `shopify_media_id: string | null`
  - Catalog query replaced: `supabase.rpc('get_catalog_thumbnails', { sku_list: skuList })` (was: `.from('product_catalog').select(...)`)
  - `lifestyleImages` computed from `skuVariantImages` and included in each result row

## Deviations from Plan

### Auto-applied during human checkpoint

**1. [Rule 1 - Bug] Fixed product_catalog 1000-row PostgREST limit**
- **Found during:** Human checkpoint verification
- **Issue:** Direct `product_catalog` table query silently truncated at 1000 rows, causing missing thumbnails/titles for SKUs beyond position 1000
- **Fix:** Replaced with `get_catalog_thumbnails` RPC (migration 026 applied via MCP; returns DISTINCT ON master_sku rows)
- **Files modified:** `dashboard/src/app/(dashboard)/review/page.tsx`
- **Commit:** 4f8ac6c0

**2. [Rule 2 - Enhancement] Added image lifecycle tracking (not in original plan)**
- **Found during:** Human checkpoint review — user added LifestyleImageLifecycle to provide image status visibility in list without needing to open full review
- **Fix:** Added `LifestyleImageLifecycle` interface, `ImageRowBadge`, `LifestyleImageBadge`, `shopify_media_id` column
- **Files modified:** `dashboard/src/app/(dashboard)/review/page.tsx`, `dashboard/src/components/review/ReviewListClient.tsx`
- **Commit:** 4f8ac6c0

**3. [Rule 2 - UX] Preview panel restructured with prominent Open Full Review button**
- **Found during:** Human checkpoint review
- **Fix:** Header row with title left, primary-colored "Open Full Review" button right (was: plain text link at bottom)
- **Files modified:** `dashboard/src/components/review/ReviewListClient.tsx`
- **Commit:** 4f8ac6c0

## Phase 9 Complete — All Success Criteria Verified

- [x] Stats bar at top with per-platform counts broken out by 4 statuses (Needs Review/Partial/Approved/Published)
- [x] SKUs render in compact rows — no per-SKU vertical scrolling
- [x] Per-platform status badges (Google/Bing/Shopify) with 4-state colors visible inline per row
- [x] Image lifecycle column (None/Generated/Approved/Published) visible inline per row
- [x] Row click expands inline preview with "Mark Approved" button and "Open Full Review" escape hatch
- [x] "Mark Approved" updates approval state without full-page navigation (optimistic update)
- [x] Filter by status (4 states) and platform works immediately with URL persistence
- [x] Stats bar click = same as setting filters manually
- [x] All 3 SkuReviewClient variants unaffected (detail page still works — verified, not modified)
- [x] Build verified locally before pushing; human-approved before commit
- [x] Pushed to master — Vercel auto-deploy triggered (commit 4f8ac6c0)

## Self-Check: PASSED

- FOUND: dashboard/src/app/api/review/approve-platform/route.ts
- FOUND: dashboard/src/components/review/ReviewListClient.tsx
- FOUND: dashboard/src/app/(dashboard)/review/page.tsx
- FOUND: .planning/phases/09-sku-review-revamp/09-03-SUMMARY.md
- FOUND commit: fca7282a (Task 1)
- FOUND commit: 4f8ac6c0 (Task 2 + human fixes)
