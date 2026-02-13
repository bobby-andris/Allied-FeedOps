# 2026-02-13: Manual Base Title Override (Google/Bing)

## Goal

Allow operators to manually set exact base titles for Google/Bing when regenerate-with-feedback cannot converge, while preserving finish-token safety and deterministic variant behavior.

## Scope

- SKU review page (`/review/[sku]`) title block only.
- Platforms: `google`, `bing`.
- Content type: `title`.

Shopify is out of scope because this override is intended for variant-title propagation flows.

## UX behavior

New action: `Edit Base Title`

- Opens dialog with:
  - editable `Title Prefix`
  - locked `{FINISH_NAME}` token (non-editable)
  - editable `Title Suffix`
  - live preview
- Save action: `Save and Apply to All Variants`

## Validation

Manual template must:

1. contain exactly one `{FINISH_NAME}` token
2. contain no hardcoded finish names
3. be non-empty

Validation implemented in:

- `dashboard/src/lib/review/manual-title.ts`

Helper behavior:

- If current title already contains token, split into editable prefix/suffix.
- If current title contains a hardcoded finish, auto-convert first match to token for editing.
- If no token/finish exists, seed template as `<current title> - {FINISH_NAME}`.

## Persistence behavior

Endpoint:

- `POST /api/review/manual-title`

Payload:

```json
{
  "master_sku": "CS-1",
  "platform": "google",
  "title": "Designer Rod Brackets {FINISH_NAME} - Carolina Collection"
}
```

On success:

- updates `generated_content.candidate_content` for `content_type='title'`
- bumps `version`
- stamps `generation_model='manual_title_override'`
- clears `approved_content`, `approved_at`, `approved_version`
  - forces explicit re-approval before publish
- appends best-effort audit row to `regeneration_history`

## Variant propagation

No direct variant row writes are required.

Variant title previews and publish expansion already derive from platform base title template via existing variant-content expansion logic.

## Files

- UI:
  - `dashboard/src/components/review/ManualTitleEditor.tsx`
  - `dashboard/src/components/review/SkuReviewClient.tsx`
- API:
  - `dashboard/src/app/api/review/manual-title/route.ts`
- Validation helpers:
  - `dashboard/src/lib/review/manual-title.ts`
- Tests:
  - `dashboard/src/lib/review/__tests__/manual-title.test.ts`
  - `dashboard/src/components/review/__tests__/ManualTitleEditor.test.tsx`

## API/schema impact

- No schema changes.
- One additive API route only (`/api/review/manual-title`).
- Existing generation/publish contracts remain unchanged.

Related:

- `docs/architecture/2026-02-13-manual-base-description-override.md`
