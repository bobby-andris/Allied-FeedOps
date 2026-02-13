# Allied FeedOps Dashboard

Next.js operator UI for SKU review, approvals, publishing, and performance monitoring.

## Canonical authority

- Python remains canonical for prompt logic and generation authority.
- Dashboard manages review, approval state transitions, and platform publish orchestration.
- Prompt authority is **not** moved into the dashboard.

## Approval and publish model (2026-02-11)

### Explicit approval scopes

- Platform scope:
  - One explicit action per platform tab (`Approve Google/Bing/Shopify Content for Publishing`).
  - Writes through `PATCH /api/approvals`.
- Variant scope:
  - Variant table actions are explicitly variant-scoped (`Approve All Google/Bing Variant Content`).
  - Writes through `POST /api/variants/approvals/bulk`.

### Deterministic readiness

Readiness is computed from persisted data in `src/lib/publishing/platform-readiness.ts`:

- `generated_content.approved_content` title+description per platform
- `variant_approvals` finish coverage for Google/Bing
- `variant_lifestyle_images` approved+selected coverage per finish for Bing
- Shopify master image is optional and not a readiness blocker

### Publish gating by selected platform(s)

`POST /api/publish/sku`:

- Accepts requested platform subset (`platforms: ['google']`, `['shopify']`, `['google','bing']`, etc.).
- Validates only requested platforms via `validateRequestedPlatformsReady`.
- Returns `409` with actionable readiness blockers when requested platform(s) are not ready:
  - `code: publish_platform_not_ready`
  - `readiness_errors[]` with platform-scoped blocker data

## Review progress visibility (2026-02-13)

The review UX now shows platform completion state in both queue and detail views.

### Review Queue (`/review`)

Each SKU card includes per-platform badges:

- `Published` (with date) when latest successful production publish exists
- `Ready` when readiness checks pass but publish has not occurred
- `Needs action` when readiness blockers remain

### SKU Detail (`/review/[sku]`)

The page includes a platform progress panel that shows:

- state (`Published`, `Ready to publish`, `Needs action`)
- first actionable blocker for blocked states
- latest published timestamp/version
- latest published title and description snapshot per platform

### Data source and determinism

Status is computed from persisted data only:

- `generated_content.approved_content`
- `variant_approvals`
- `variant_lifestyle_images`
- successful production `publish_events`

No API contract or schema changes were required.

## Lifestyle image behavior

### Google

- Variant image approval + user selection remains available at finish-level.
- Google publish readiness does not require variant image coverage.

### Bing

- Variant image approval + user selection remains finish-level.
- Bing readiness requires one approved+selected variant image per finish.

### Shopify

- Shopify publish readiness does not require a master image selection.
- Selecting a Shopify master image from variant candidates still supports cloning an approved+selected variant image into `product_lifestyle_images` in the same flow (`/api/review/images/select` + `master-selection.ts`).

### Default variant image selection fallback

When multiple approved variant images exist for the same `gmc_offer_id`, publish selection is deterministic:

1. `user_selected = true` wins
2. else `ai_selected = true` wins (Google Ads-driven generation default)
3. else most recent generated image wins

This fallback keeps publish behavior deterministic even before manual image selection.

### Idempotent image generation writes

Cloud Run lifestyle generation reruns are idempotent to avoid duplicate-key failures:

- `product_lifestyle_images` upsert on `(master_sku, variation_index)`
- `variant_lifestyle_images` upsert on `(gmc_offer_id, variation_index)`

This prevents `duplicate key value violates unique constraint product_lifestyle_images_master_sku_variation_index_key` on reruns.

## Key files

- UI
  - `src/components/review/SkuReviewClient.tsx`
  - `src/components/review/ApprovalActions.tsx`
  - `src/components/review/VariantContentGrid.tsx`
  - `src/components/review/LifestyleImageReview.tsx`
  - `src/components/review/ImageApprovalCard.tsx`
  - `src/components/review/PublishButton.tsx`
  - `src/components/review/approval-copy.ts`
- API
  - `src/app/api/approvals/route.ts`
  - `src/app/api/variants/approvals/bulk/route.ts`
  - `src/app/api/publish/sku/route.ts`
  - `src/app/api/review/images/select/route.ts`
  - `src/app/api/review/images/select/master-selection.ts`

## Test coverage

Vitest is configured in `vitest.config.ts`.

- Platform readiness acceptance matrix:
  - `src/lib/publishing/__tests__/platform-readiness.test.ts`
- Variant image fallback selection:
  - `src/lib/publishing/__tests__/variant-image-selection.test.ts`
- Approval copy/scope clarity regression:
  - `src/components/review/__tests__/approval-copy.test.ts`
- Lifestyle review default finish selection:
  - `src/components/review/__tests__/lifestyle-image-selection.test.ts`
- Master image selection semantics:
  - `src/app/api/review/images/select/__tests__/master-selection.test.ts`

Run tests:

```bash
cd dashboard
npm test
```

Targeted:

```bash
cd dashboard
npx vitest run src/lib/publishing/__tests__/platform-readiness.test.ts src/components/review/__tests__/approval-copy.test.ts src/app/api/review/images/select/__tests__/master-selection.test.ts
```

## Production operations

Use the root-level runbook for live troubleshooting and rollback:

- `../docs/troubleshooting/2026-02-11-platform-readiness-ops-runbook.md`
