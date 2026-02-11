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
- `variant_lifestyle_images` approved+selected coverage per finish for Google/Bing
- `product_lifestyle_images` approved+selected master image for Shopify

### Publish gating by selected platform(s)

`POST /api/publish/sku`:

- Accepts requested platform subset (`platforms: ['google']`, `['shopify']`, `['google','bing']`, etc.).
- Validates only requested platforms via `validateRequestedPlatformsReady`.
- Returns `409` with actionable readiness blockers when requested platform(s) are not ready:
  - `code: publish_platform_not_ready`
  - `readiness_errors[]` with platform-scoped blocker data

## Lifestyle image behavior

### Google / Bing

- Variant image approval + user selection remains finish-level.
- Readiness requires one approved+selected variant image per finish.

### Shopify

- Shopify publish readiness requires one approved+selected product-level master image.
- Selecting a Shopify master image from variant candidates now supports cloning an approved+selected variant image into `product_lifestyle_images` in the same flow (`/api/review/images/select` + `master-selection.ts`).

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
- Approval copy/scope clarity regression:
  - `src/components/review/__tests__/approval-copy.test.ts`
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
