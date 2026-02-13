# 2026-02-13: Manual Base Description Override (Google/Bing)

## Goal

Allow operators to manually set exact base descriptions for Google/Bing when regenerate-with-feedback cannot converge, while preserving finish-token safety and deterministic variant behavior.

## Scope

- SKU review page (`/review/[sku]`) description block only.
- Platforms: `google`, `bing`.
- Content type: `description`.

Shopify is out of scope for this override because this flow is intended for variant description propagation.

## UX behavior

New action: `Edit Base Description`

- Opens dialog with:
  - editable `Description Prefix`
  - locked `{FINISH_SENTENCE}` token (non-editable)
  - editable `Description Suffix`
  - live preview
- Save action: `Save and Apply to All Variants`

Legacy templates using `[FINISH_SENTENCE]` are normalized to `{FINISH_SENTENCE}` on open/save.

## Validation

Manual template must:

1. contain exactly one `{FINISH_SENTENCE}` token
2. contain no hardcoded finish names
3. be non-empty

Validation implemented in:

- `dashboard/src/lib/review/manual-description.ts`

Helper behavior:

- If current description already contains token, split into editable prefix/suffix.
- If current description uses legacy `[FINISH_SENTENCE]`, normalize to canonical token.
- If current description contains a hardcoded finish, auto-convert first match to token for editing.
- If no token/finish exists, inject token after the first sentence.

## Persistence behavior

Endpoint:

- `POST /api/review/manual-description`

Payload:

```json
{
  "master_sku": "CS-1",
  "platform": "google",
  "description": "Solid brass shower bracket with precision mounting. {FINISH_SENTENCE} Built for long-term durability."
}
```

On success:

- updates `generated_content.candidate_content` for `content_type='description'`
- bumps `version`
- stamps `generation_model='manual_description_override'`
- clears `approved_content`, `approved_at`, `approved_version`
  - forces explicit re-approval before publish
- appends best-effort audit row to `regeneration_history`

## Variant propagation

No direct variant row writes are required.

Variant description previews and publish expansion already derive from the platform base description template via existing variant-content expansion logic.

## Files

- UI:
  - `dashboard/src/components/review/ManualDescriptionEditor.tsx`
  - `dashboard/src/components/review/SkuReviewClient.tsx`
- API:
  - `dashboard/src/app/api/review/manual-description/route.ts`
- Validation helpers:
  - `dashboard/src/lib/review/manual-description.ts`
- Tests:
  - `dashboard/src/lib/review/__tests__/manual-description.test.ts`
  - `dashboard/src/components/review/__tests__/ManualDescriptionEditor.test.tsx`

## API/schema impact

- No schema changes.
- One additive API route only (`/api/review/manual-description`).
- Existing generation/publish contracts remain unchanged.
