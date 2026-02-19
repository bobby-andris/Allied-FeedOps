# 2026-02-19: Shopify Manual Overrides + Lifestyle Generation Retry/Debugging

## Summary

This update closes two operator gaps in review:

1. Shopify review content can now be manually edited directly (title + description), with platform-safe validation.
2. Lifestyle image generation failures are now more resilient and debuggable:
   - transient Gemini quota errors are retried with backoff
   - all-failed runs return actionable per-variation error details instead of a generic message

No architecture redesign was introduced. Python remains the canonical generation runtime and prompt authority.

## Root Causes

### 1) Shopify manual edit parity gap

Google/Bing already had manual override tools for title/description templates. Shopify did not.
When regenerate-with-feedback failed to match exact business intent, operators could not directly correct Shopify content in review with the same workflow.

### 2) Lifestyle generation “all attempts failed” ambiguity

The `POST /generate-images` flow returned `success=false` with:

`"All image generation attempts failed"`

without variation-level diagnostics. In addition, variation generation had no retry/backoff for transient `429 RESOURCE_EXHAUSTED` conditions, which made intermittent provider bursts look like hard failures.

## Code Changes

### Shopify manual title/description overrides

- `dashboard/src/components/review/ManualTitleEditor.tsx`
  - Added Shopify mode (freeform input, no `{FINISH_NAME}` token lock UI).
- `dashboard/src/components/review/ManualDescriptionEditor.tsx`
  - Added Shopify mode (freeform textarea, no `{FINISH_SENTENCE}` token lock UI).
- `dashboard/src/components/review/SkuReviewClient.tsx`
  - Exposes manual editor controls for Shopify candidates.

- `dashboard/src/lib/review/manual-title.ts`
  - Added `validateManualTitleForPlatform(...)`.
  - Added Shopify-specific validation (finish-agnostic + no `Allied Brass` + no hardcoded finishes).
- `dashboard/src/lib/review/manual-description.ts`
  - Added `validateManualDescriptionForPlatform(...)`.
  - Added Shopify-specific validation (finish placeholders/hardcoded finish restrictions).

- `dashboard/src/app/api/review/manual-title/route.ts`
  - Expanded platform support to `google | bing | shopify`.
  - Uses platform-aware validator.
- `dashboard/src/app/api/review/manual-description/route.ts`
  - Expanded platform support to `google | bing | shopify`.
  - Uses platform-aware validator.

### Lifestyle generation resilience + diagnostics

- `src/feedops/pipeline/lifestyle_images.py`
  - Added `_generate_image_content_with_retry(...)`:
    - retries transient `RESOURCE_EXHAUSTED`/`429` failures with exponential backoff + jitter
    - controlled by env vars:
      - `LIFESTYLE_GENERATION_MAX_ATTEMPTS` (default `4`)
      - `LIFESTYLE_GENERATION_RETRY_BASE_SECONDS` (default `1.0`)
  - `generate_single_variation(...)` now uses retry helper for both:
    - multi-reference call
    - single-reference fallback call
  - Added `build_generation_failure_message(...)` to aggregate per-variation errors.
  - `generate_lifestyle_images_for_sku(...)` now returns aggregated failure details in `message` when no variation succeeds.

## API Contract Notes

No endpoint shape change was required:

- `POST /api/review/manual-title` and `POST /api/review/manual-description`
  - request field `platform` now accepts `shopify` in addition to `google` and `bing`
  - response format unchanged

- `POST /generate-images`
  - response schema unchanged
  - `message` content is now more actionable on all-failed runs

## Testing

### Dashboard (Vitest)

- `dashboard/src/lib/review/__tests__/manual-title.test.ts`
- `dashboard/src/lib/review/__tests__/manual-description.test.ts`
- `dashboard/src/components/review/__tests__/ManualTitleEditor.test.tsx`
- `dashboard/src/components/review/__tests__/ManualDescriptionEditor.test.tsx`

Added Shopify-mode coverage for manual editing and platform-aware validation behavior.

### Python (pytest)

- `tests/test_lifestyle_image_generation_retries.py` (new)
  - validates retry/backoff path for transient `429 RESOURCE_EXHAUSTED`
  - validates all-failed summary message includes variation-level details
- `tests/test_lifestyle_image_generation_writes.py`
  - hardened import shims to avoid cross-test module pollution

## Operational Troubleshooting

If operators report “Generate Lifestyle Images” failure:

1. Re-run the request and inspect returned `message` details (now includes `varN: ...` failure snippets).
2. Confirm Cloud Run has valid `GEMINI_API_KEY`.
3. If failures are quota bursts, tune:
   - `LIFESTYLE_GENERATION_MAX_ATTEMPTS`
   - `LIFESTYLE_GENERATION_RETRY_BASE_SECONDS`
4. If failures are persistent model errors (non-429), investigate provider availability/permissions for `gemini-3-pro-image-preview`.

## Rollback

If rollback is required:

1. Revert Shopify platform additions in manual title/description validators, editors, and API routes.
2. Revert retry helper usage in `generate_single_variation(...)`.
3. Revert all-failed message aggregation in `generate_lifestyle_images_for_sku(...)`.

No schema/data rollback is required.
