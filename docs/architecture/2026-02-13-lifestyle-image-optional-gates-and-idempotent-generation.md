# 2026-02-13: Lifestyle Image Optional Gates + Idempotent Generation

## Summary

This change clarifies platform image readiness expectations and removes non-deterministic behavior in lifestyle image generation/publish selection.

Implemented outcomes:

- Google and Shopify image selection are optional for publish readiness.
- Bing image selection remains required (approved + selected image coverage per finish).
- Lifestyle image generation reruns are idempotent (no duplicate-key crash on `(master_sku, variation_index)`).
- Variant image selection for publish is deterministic and testable:
  - `user_selected` first
  - fallback `ai_selected`
  - fallback newest generated row
- Lifestyle review default finish tab selection is deterministic:
  - explicit selected finish (if present)
  - finish with user-selected image
  - finish with AI-selected image
  - first available finish

## Problem Statement

### 1) Duplicate-key generation failure in review UI

The review page empty-state "Generate Lifestyle Images" action calls Cloud Run endpoint `POST /generate-images`.
Rerunning generation for a SKU that already had rows could fail with:

`duplicate key value violates unique constraint "product_lifestyle_images_master_sku_variation_index_key"`

Root cause:

- Python generation path inserted directly into `product_lifestyle_images` and `variant_lifestyle_images`.
- Both tables have unique constraints that are expected to support idempotent generation reruns.
- Plain inserts violated these constraints on rerun for the same SKU + variation.

### 2) Image readiness expectation mismatch

Operators needed to publish content even when Google/Shopify image selection had not been manually completed.
The previous readiness model still blocked Shopify on master image selection.

### 3) Non-deterministic fallback when no explicit image selection exists

When multiple approved variant images existed for one offer, fallback behavior was implicit and not deterministic.
This caused confusing outcomes from an operator perspective.

## Code-Level Changes

## Dashboard readiness + copy

- `dashboard/src/lib/publishing/platform-readiness.ts`
  - Removed Shopify master-image blocker from readiness gating.
  - Kept existing Bing variant-image blocker.
- `dashboard/src/components/review/approval-copy.ts`
  - Updated help text to explicitly document:
    - Google image selection optional
    - Shopify master image optional
    - Bing image readiness required
- `dashboard/src/components/review/LifestyleImageReview.tsx`
  - Updated explanatory text to remove implied Shopify image requirement.
  - Uses deterministic finish default selection helper.
- `dashboard/src/components/review/lifestyle-image-selection.ts` (new)
  - Added pure helper for deterministic default finish selection.

## Deterministic publish image fallback

- `dashboard/src/lib/publishing/expand-variants.ts`
  - Query now loads `user_selected`, `ai_selected`, `generation_timestamp`, `created_at`.
  - Added `selectPreferredVariantImages(...)` and used it in image map resolution.
  - Selection order per `gmc_offer_id`:
    1. `user_selected = true`
    2. `ai_selected = true`
    3. newest `generation_timestamp` / `created_at`

## Python generation idempotency

- `src/feedops/pipeline/lifestyle_images.py`
  - `save_lifestyle_image_to_db(...)` now upserts instead of inserts:
    - `product_lifestyle_images` with `on_conflict="master_sku,variation_index"`
    - `variant_lifestyle_images` with `on_conflict="gmc_offer_id,variation_index"`
  - This makes reruns safe under existing unique constraints.

## Test Coverage Added/Updated

### Dashboard Vitest

- `dashboard/src/lib/publishing/__tests__/platform-readiness.test.ts`
  - Updated for Shopify optional image gate.
- `dashboard/src/lib/publishing/__tests__/variant-image-selection.test.ts` (new)
  - Verifies deterministic selection precedence.
- `dashboard/src/components/review/__tests__/lifestyle-image-selection.test.ts` (new)
  - Verifies deterministic default finish selection in review UI.
- `dashboard/src/components/review/__tests__/approval-copy.test.ts`
  - Updated expected copy semantics for Google optional image language.

### Python pytest

- `tests/test_lifestyle_image_generation_writes.py` (new)
  - Verifies generation DB writes use upsert with expected conflict keys.

## API / Schema Impact

- No schema changes.
- No external API contract changes required.
- Behavior change only: Shopify readiness gate no longer requires master image selection.

## Operational Notes

- Existing `product_lifestyle_images` and `variant_lifestyle_images` data remains valid.
- Rerunning lifestyle generation for already-generated SKUs should now update rows rather than failing.
- Publish behavior for Bing remains strict on image coverage readiness.

## Rollback Plan

If this behavior needs to be reverted:

1. Re-enable Shopify readiness blocker in `platform-readiness.ts`.
2. Revert optional-language copy updates in review components.
3. Revert selection fallback helper usage in `expand-variants.ts`.
4. Revert Python upsert calls back to inserts in `lifestyle_images.py`.

No data migration rollback is required because this release does not alter schema.
