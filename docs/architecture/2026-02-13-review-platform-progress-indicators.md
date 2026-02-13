# 2026-02-13: Review Queue + SKU Detail Platform Progress Indicators

## Summary

Added deterministic, per-platform completion indicators to both:

- Review Queue (`/review`) list cards
- SKU detail review page (`/review/[sku]`)

This makes it visible, without drilling into each SKU, which platform is:

- blocked (needs action),
- ready to publish, or
- already published to production.

For SKU detail pages, the latest published title/description snapshot is now shown per platform.

## Why this change

Operators could not quickly answer:

1. what is complete for each SKU,
2. for which platform(s), and
3. what content was last pushed to production.

Readiness/publish state existed in separate tables, but UI did not unify them at queue-level.

## Implementation details

## New deterministic helper

Added `dashboard/src/lib/review/platform-progress.ts`:

- `computePlatformReadinessForSku(...)`
  - Computes platform readiness from persisted state:
    - `generated_content.approved_content` (title + description)
    - `variant_approvals` finish coverage (Google/Bing)
    - `variant_lifestyle_images` approved+selected finish coverage (Bing image requirement)
  - Delegates final platform gate logic to canonical `computePlatformReadiness(...)`.

- `latestProductionPublishSnapshots(...)`
  - Picks latest successful production publish snapshot per platform from `publish_events`.

- `buildPlatformProgress(...)`
  - Produces display-friendly status per platform:
    - `published`
    - `ready`
    - `blocked`

## Review Queue updates (`/review`)

File: `dashboard/src/app/(dashboard)/review/page.tsx`

Queue data fetch now aggregates, per SKU:

- generated content approval state by platform
- variant readiness dependencies
- latest successful production publish events

Each SKU card shows per-platform badges:

- `Google/Bing/Shopify: Published (date)` when a production publish exists
- `...: Ready` when readiness checks pass but not yet published
- `...: Needs action` with blocker tooltip context

## SKU detail updates (`/review/[sku]`)

Files:

- `dashboard/src/app/(dashboard)/review/[sku]/page.tsx`
- `dashboard/src/components/review/SkuReviewClient.tsx`

Detail page now loads latest successful production publish snapshots and passes them to client UI.

New platform summary panel shows per platform:

- current state (`Published`, `Ready to publish`, `Needs action`)
- blocker reason for blocked states
- latest published timestamp
- latest published title/description snapshot (if present)

## Testing

Added tests:

- `dashboard/src/lib/review/__tests__/platform-progress.test.ts`
  - readiness derivation from persisted records
  - latest publish snapshot selection
  - combined progress-state construction

Full dashboard suite passes with this change.

## API/schema impact

- No schema changes.
- No API contract changes.
- Uses existing persisted state and publish event data.
