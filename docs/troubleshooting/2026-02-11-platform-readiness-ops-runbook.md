# Platform Readiness Ops Runbook (2026-02-11)

## Purpose

This runbook is for operating, troubleshooting, and rolling back the platform-scoped approval + publish readiness changes introduced on 2026-02-11.

Use this when:

- publish requests fail with readiness blockers
- operators report "approved content but not publish-ready"
- Google/Bing/Shopify readiness appears inconsistent in UI
- you need a safe rollback path under production pressure

## Scope of change

Core behavior changes:

1. Approval actions are explicitly scoped:
   - platform scope: `PATCH /api/approvals`
   - variant scope: `POST /api/variants/approvals/bulk`
2. Publish gate is deterministic and platform-specific:
   - `POST /api/publish/sku` validates only requested `platforms[]`
3. Lifestyle semantics are aligned by platform:
   - Google does not require variant image coverage
   - Bing requires variant image coverage by finish
   - Shopify requires one selected master product image

No schema migration is required for this release.

## Source files (release-critical)

### UI

- `dashboard/src/components/review/SkuReviewClient.tsx`
- `dashboard/src/components/review/ApprovalActions.tsx`
- `dashboard/src/components/review/VariantContentGrid.tsx`
- `dashboard/src/components/review/LifestyleImageReview.tsx`
- `dashboard/src/components/review/ImageApprovalCard.tsx`
- `dashboard/src/components/review/PublishButton.tsx`
- `dashboard/src/components/review/approval-copy.ts`

### API

- `dashboard/src/app/api/approvals/route.ts`
- `dashboard/src/app/api/variants/approvals/bulk/route.ts`
- `dashboard/src/app/api/publish/sku/route.ts`
- `dashboard/src/app/api/review/images/select/route.ts`
- `dashboard/src/app/api/review/images/select/master-selection.ts`

### Readiness logic

- `dashboard/src/lib/publishing/platform-readiness.ts`

### Tests

- `dashboard/src/lib/publishing/__tests__/platform-readiness.test.ts`
- `dashboard/src/components/review/__tests__/approval-copy.test.ts`
- `dashboard/src/components/review/__tests__/PublishButton.test.tsx`
- `dashboard/src/app/api/review/images/select/__tests__/master-selection.test.ts`

## Deterministic readiness model

Readiness is computed from persisted state only.

### Content readiness (all platforms)

Data source:

- `generated_content`

Required:

- `approved_content` exists and is non-empty for:
  - `{ platform: google, content_type: title }`
  - `{ platform: google, content_type: description }`
  - same pattern for `bing` and `shopify`

### Google/Bing variant content readiness

Data source:

- `variant_approvals`

Required per finish:

- `approval_status = 'approved'`
- `title_approved = true`
- `description_approved = true`

### Bing variant image readiness

Data source:

- `variant_lifestyle_images`

Required per finish:

- at least one row with:
  - `approval_status = 'approved'`
  - `user_selected = true`

### Shopify master image readiness

Data source:

- `product_lifestyle_images`

Required:

- at least one row with:
  - `approval_status = 'approved'`
  - `user_selected = true`

## Production verification checklist

Run these in order before claiming a publish issue is fixed.

1. Verify dashboard tests

```bash
cd dashboard
npm test
```

2. Verify dashboard build

```bash
cd dashboard
npm run build
```

3. Verify DB state for a SKU (example `CS-1`)

```sql
-- platform title/description approval snapshot
select platform, content_type, approved_version, approved_at
from public.generated_content
where master_sku = 'CS-1'
  and is_current = true
  and platform in ('google','bing','shopify')
  and content_type in ('title','description')
order by platform, content_type;

-- required finishes
select count(*) as required_finishes
from public.variant_index
where master_sku = 'CS-1'
  and finish is not null;

-- variant content approvals by finish
select count(distinct finish) as approved_variant_finishes
from public.variant_approvals
where master_sku = 'CS-1'
  and approval_status = 'approved'
  and title_approved = true
  and description_approved = true;

-- bing variant image approvals by finish
select count(distinct finish) as approved_selected_variant_image_finishes
from public.variant_lifestyle_images
where master_sku = 'CS-1'
  and approval_status = 'approved'
  and user_selected = true;

-- shopify master image presence
select count(*) as approved_selected_master_images
from public.product_lifestyle_images
where master_sku = 'CS-1'
  and approval_status = 'approved'
  and user_selected = true;
```

4. Verify publish API behavior from authenticated dashboard session

Expected failure contract for unready platform(s):

- HTTP `409`
- `code = publish_platform_not_ready`
- `step = platform_readiness`
- `readiness_errors[]` populated

Expected success contract for ready platform(s):

- HTTP `200`
- `success = true`
- per-platform `results[]` entries

## Common symptoms and resolution

### Symptom: "I approved Google content but publish still fails"

Most common causes:

- variant content coverage is incomplete across finishes

How to confirm:

- readiness error includes `google_variant_content_not_approved`

Fix:

- bulk approve variant content per finish

### Symptom: "Shopify says not ready even though variant image is approved"

Cause:

- Shopify checks `product_lifestyle_images` (master), not variant image rows

Fix:

- in review UI, select an approved Shopify master image
- or re-run master selection flow via `/api/review/images/select`

### Symptom: "Bing publish fails while Google succeeds"

Cause:

- platform approvals are independent; Bing title/description may not be approved
- Bing also requires variant image coverage

Fix:

- use `Approve Bing Content for Publishing`
- approve/select one variant image per required finish for Bing
- verify `generated_content` rows for `platform='bing'` are approved

### Symptom: "Publish button enabled, but request fails"

Cause:

- button availability is request-selection driven; server remains authoritative

Fix:

- inspect `readiness_errors[]` in response and resolve blockers

## Rollback and mitigation

## Option A: Fast mitigation (preferred first)

If failures are operational (data state), do not roll back code.

1. Keep current release.
2. Resolve missing readiness data for affected SKU(s).
3. Re-test publish endpoint.

## Option B: Code rollback to previous global gate

Use only if there is a confirmed logic regression in readiness gating.

1. Revert readiness-gate changes in:
   - `dashboard/src/app/api/publish/sku/route.ts`
2. Restore prior global gate check (`sku_approvals.approval_status='approved'`).
3. Keep additive API parameters in place (they are backward-compatible).
4. Deploy and verify publish endpoint.

No data rollback is needed.

## Option C: Full commit revert

If needed, revert the release commit(s) and redeploy.

```bash
git revert <commit_sha>
git push origin master
```

Then validate:

- `npm test`
- `npm run build`
- publish smoke checks for one known ready and one known unready SKU

## Post-incident checklist

1. Capture failing request payload + response JSON.
2. Capture readiness DB snapshots for affected SKU.
3. Document exact blocker code frequency.
4. Add/adjust test cases if a new edge case was discovered.
5. Update this runbook with concrete reproduction steps.
