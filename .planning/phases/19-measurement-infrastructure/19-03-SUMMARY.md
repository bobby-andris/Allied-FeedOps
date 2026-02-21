---
phase: 19-measurement-infrastructure
plan: 03
subsystem: dashboard-ui
tags: [bottleneck-classifier, prompt-lineage, dashboard, typescript, components, measurement]

# Dependency graph
requires:
  - phase: 19-02
    provides: POST /api/bottleneck/classify, GET /api/bottleneck/status, GET /api/prompt-lineage
provides:
  - dashboard/src/components/bottleneck/BottleneckBadge.tsx
  - dashboard/src/components/lineage/PromptLineagePanel.tsx
  - dashboard/src/app/(dashboard)/monitoring/bottleneck/page.tsx
  - Bottleneck summary section in monitoring/page.tsx
affects:
  - 19-04 (GMC disapproval badge can follow same pattern as BottleneckBadge)
  - SKU review pages (BottleneckBadge + PromptLineagePanel ready for integration into ReviewListClient/SkuReviewClient)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Collapsible shadcn/ui component for optional-detail panels (PromptLineagePanel)"
    - "Feature flag badges: green=on, gray=off using Badge className variants"
    - "Override form inline in table rows — no modal needed for simple classification overrides"
    - "Delete-then-insert handled by API (Plan 02); UI just calls POST with override params"

key-files:
  created:
    - dashboard/src/components/bottleneck/BottleneckBadge.tsx
    - dashboard/src/components/lineage/PromptLineagePanel.tsx
    - dashboard/src/app/(dashboard)/monitoring/bottleneck/page.tsx
  modified:
    - dashboard/src/app/(dashboard)/monitoring/page.tsx

key-decisions:
  - "BottleneckBadge: inline badge with confidence % shown as muted sub-text within the badge; override shown as separate dashed-border tag"
  - "PromptLineagePanel: collapsible (collapsed by default) to avoid visual clutter on SKU review pages"
  - "Compare Versions is opt-in (hidden behind button) per plan spec — not default view"
  - "Bottleneck diagnostic page uses /monitoring/bottleneck route (not a tab in monitoring page) — category grouping + override forms need dedicated space"
  - "Do NOT modify SkuReviewClient variants (3 variants per CLAUDE.md) — badge/panel ready for future integration task"

metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 3
  files_modified: 1
  completed_date: "2026-02-21"
---

# Phase 19 Plan 03: Dashboard UI for Measurement Visibility Summary

**Three new UI artifacts making measurement instrumentation data from Plans 01-02 visible and actionable: color-coded BottleneckBadge, collapsible PromptLineagePanel, and /monitoring/bottleneck diagnostic page with reclassify/override workflow**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-21T04:13:37Z
- **Completed:** 2026-02-21T04:17:09Z
- **Tasks:** 2
- **Files created:** 3 (+ 1 modified)

## Accomplishments

- Created `BottleneckBadge` — 5 color-coded categories (gray/purple/yellow/orange/blue), optional confidence %, isOverride indicator
- Created `PromptLineagePanel` — collapsible section with prompt hash (8-char truncated), alias, model version, 3 feature flag badges (green on/gray off), tokens, latency, published/generated dates
- `PromptLineagePanel` includes opt-in "Compare Versions" button that fetches `/api/prompt-lineage?compare=true&hash_a=X&hash_b=Y` for side-by-side prompt analysis
- Created `/monitoring/bottleneck` diagnostic page with:
  - Summary bar: 5 category cards with count + percentage
  - Collapsible category sections with SKU-level table
  - Reclassify button per SKU (POST /api/bottleneck/classify)
  - Override form per SKU (classification dropdown + note field → is_override=true)
  - "Reclassify All" button at top (batch=true mode with loading spinner)
- Updated monitoring page with bottleneck summary card (counts by category, link to /monitoring/bottleneck)
- Dashboard builds and lints clean (0 errors, 1 pre-existing unrelated warning)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create BottleneckBadge and PromptLineagePanel components** - `41826281` (feat)
2. **Task 2: Create bottleneck diagnostic page and wire monitoring page** - `a2810c8b` (feat)

## Files Created/Modified

- `dashboard/src/components/bottleneck/BottleneckBadge.tsx` — Inline badge with 5 category colors + optional confidence and override indicator
- `dashboard/src/components/lineage/PromptLineagePanel.tsx` — Collapsible lineage section with flag badges, cost data, opt-in compare mode
- `dashboard/src/app/(dashboard)/monitoring/bottleneck/page.tsx` — Dedicated diagnostic view, grouped by category, with reclassify + override controls
- `dashboard/src/app/(dashboard)/monitoring/page.tsx` — Added bottleneck summary card with category counts and link to diagnostic view

## Decisions Made

- BottleneckBadge renders confidence as muted sub-text inside the badge; override uses a separate dashed-border indicator to clearly distinguish manual from auto
- PromptLineagePanel defaults to collapsed state — avoids cluttering SKU review pages with technical metadata that most users don't need daily
- Compare Versions is strictly opt-in (hidden behind button) per plan requirement
- `/monitoring/bottleneck` is a dedicated route, not a third tab — the override form complexity warrants its own page
- SkuReviewClient.tsx not modified (3 variants per CLAUDE.md convention) — BottleneckBadge and PromptLineagePanel are ready for integration into SkuReviewClient and ReviewListClient in a future task

## Integration Path (Future Task)

Both components are designed for drop-in integration:

**BottleneckBadge in ReviewListClient** (when bottleneck data is available per-SKU):
```typescript
import { BottleneckBadge } from '@/components/bottleneck/BottleneckBadge'
// In SKU row:
<BottleneckBadge classification={sku.bottleneck_classification} confidence={sku.bottleneck_confidence} />
```

**PromptLineagePanel in SkuReviewClient** (below content display for published SKUs):
```typescript
import { PromptLineagePanel } from '@/components/lineage/PromptLineagePanel'
// In detail view:
<PromptLineagePanel masterSku={sku} platform={selectedPlatform} />
```

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: dashboard/src/components/bottleneck/BottleneckBadge.tsx
- FOUND: dashboard/src/components/lineage/PromptLineagePanel.tsx
- FOUND: dashboard/src/app/(dashboard)/monitoring/bottleneck/page.tsx
- FOUND: dashboard/src/app/(dashboard)/monitoring/page.tsx (modified)
- Commit 41826281 (Task 1) - verified
- Commit a2810c8b (Task 2) - verified
- Build: PASSED (npm run build — /monitoring/bottleneck appears in route list)
- Lint: PASSED (0 errors, 1 pre-existing warning in unrelated file)

---
*Phase: 19-measurement-infrastructure*
*Completed: 2026-02-21*
