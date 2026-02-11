# Platform-Scoped Approval And Publish Readiness (2026-02-11)

## Summary

This change removes publish confusion and global gating mismatch by introducing explicit platform approval language and deterministic platform readiness checks.

It keeps existing architecture intact:

- Python remains canonical generation authority.
- Dashboard remains review/publish orchestration layer.
- No prompt-authority shift to dashboard.

## Problems addressed

1. Approval UX ambiguity:
   - Users saw overlapping “approve” actions without clear scope.
2. Global publish gate mismatch:
   - `sku_approvals.approval_status='approved'` blocked valid partial platform publishes.
3. Lifestyle image approval confusion:
   - Shopify master image path felt like a hidden second approval.

## Design

## Approval scopes

- Platform approval (Google/Bing/Shopify):
  - Explicit label: `Approve <Platform> Content for Publishing`
  - Endpoint: `PATCH /api/approvals`
  - Behavior: transitions approved content snapshot for the specified platform.
- Variant approval (Google/Bing):
  - Explicit label: `Approve All <Platform> Variant Content`
  - Endpoint: `POST /api/variants/approvals/bulk`
  - Behavior: bulk updates variant title/description approval flags by finish.

## Deterministic readiness function

Implemented in `dashboard/src/lib/publishing/platform-readiness.ts`.

Inputs:

- Content approval:
  - `generated_content.approved_content` by `{platform, content_type in [title, description]}`
- Variant readiness (Google/Bing):
  - `variant_approvals` complete finish coverage with approved title+description
  - `variant_lifestyle_images` complete finish coverage with approved+selected image
- Shopify readiness:
  - `product_lifestyle_images` has approved+selected master image

Outputs:

- `readiness[platform].ready: boolean`
- `readiness[platform].blockers[]` with machine-readable `code` and actionable messages

## Publish gating behavior

Endpoint: `POST /api/publish/sku`

- Previous behavior:
  - required global `sku_approvals.approval_status='approved'` for all publishes.
- New behavior:
  - computes readiness and validates only requested `platforms[]`.
  - allows independent subset publish when subset is ready.
  - fails closed for unready requests.

Error contract for readiness failures:

- HTTP `409`
- `code: "publish_platform_not_ready"`
- `step: "platform_readiness"`
- `readiness_errors[]`: `{ platform, code, reason, actionableMessage }`

## Lifestyle image semantics

Google/Bing:

- Variant image readiness remains finish-scoped and required.

Shopify:

- Master readiness is product-scoped.
- `/api/review/images/select` can resolve a selected approved variant image and upsert it into `product_lifestyle_images` for Shopify master selection using:
  - `dashboard/src/app/api/review/images/select/master-selection.ts`

This removes the user-facing “mystery second approval” path by making the flow coherent and explicit.

## API changes

These are additive/minimal and required for scope clarity:

1. `PATCH /api/approvals`
   - accepts optional `platform`.
   - reason: platform-scoped snapshot transitions must occur even when global booleans are already true.
2. `POST /api/variants/approvals/bulk`
   - accepts optional `platform` (`google|bing`).
   - reason: explicit variant scope and platform-specific user messaging.
3. `POST /api/publish/sku`
   - readiness-gated by requested platform subset.
   - returns readiness errors for unready platform requests.

No schema migrations are required.

## Rollback strategy

If needed, rollback is code-only:

1. Revert `platform-readiness` usage in `POST /api/publish/sku`.
2. Re-enable global `sku_approvals` gate in publish route.
3. Keep additive API parameters harmlessly ignored.

No data migration rollback is needed.

## Tests

- `dashboard/src/lib/publishing/__tests__/platform-readiness.test.ts`
  - Includes acceptance matrix:
    - Google ready only
    - Shopify ready only
    - Google+Bing ready, Shopify not ready
    - none ready
- `dashboard/src/components/review/__tests__/approval-copy.test.ts`
  - Guards against ambiguous scope wording regressions.
- `dashboard/src/app/api/review/images/select/__tests__/master-selection.test.ts`
  - Verifies variant-to-master image payload semantics.

## Operations

For production troubleshooting, deterministic DB checks, and rollback playbook, see:

- `docs/troubleshooting/2026-02-11-platform-readiness-ops-runbook.md`
