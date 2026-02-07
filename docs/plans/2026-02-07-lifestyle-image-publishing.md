# Lifestyle Image Publishing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire approved lifestyle images from the `generated_images` table through the publish pipeline to populate the `lifestyle_image_link` column in Google Sheets.

**Architecture:** Add image querying logic to `expandVariantsForPublish()` that fetches approved images from `generated_images` using variant-specific lookup with master-level fallback. Pass image URLs through expanded variants to Google Sheets, which already supports the `lifestyle_image_link` column via `ensureLifestyleImageColumn()`.

**Tech Stack:** TypeScript, Next.js, Supabase (PostgreSQL), Google Sheets API

---

## Task 1: Add image_url to ExpandedVariant type

**Files:**
- Modify: `dashboard/src/lib/publishing/expand-variants.ts:16-22`
- Modify: `dashboard/src/lib/publishing/types.ts:1-150`

**Step 1: Add image_url field to ExpandedVariant interface**

In `dashboard/src/lib/publishing/expand-variants.ts`, update the interface:

```typescript
export interface ExpandedVariant {
  gmc_offer_id: string
  finish: string
  finish_code: string | null
  title: string
  description: string
  image_url?: string  // Add this field
}
```

**Step 2: Commit type update**

```bash
git add dashboard/src/lib/publishing/expand-variants.ts
git commit -m "feat: add image_url field to ExpandedVariant type"
```

---

## Task 2: Create image query helper function

**Files:**
- Modify: `dashboard/src/lib/publishing/expand-variants.ts:89-108`

**Step 1: Add queryApprovedImages function before expandVariantsForPublish**

Add this function after the imports and interfaces section (around line 30):

```typescript
/**
 * Query approved lifestyle images for a master SKU.
 * Returns a map of finish_code -> image_url for variant-specific images,
 * plus a master image URL if use_for_master is true.
 *
 * Strategy:
 * - Fetch all approved images for the SKU
 * - Build a map of finish-specific images (keyed by finish_code)
 * - Extract master image (use_for_master = true) as fallback
 */
async function queryApprovedImages(
  supabase: Awaited<ReturnType<typeof createClient>>,
  master_sku: string
): Promise<{
  finishImages: Map<string, string>
  masterImageUrl: string | null
}> {
  const { data: images, error } = await supabase
    .from('generated_images')
    .select('finish_code, image_url, use_for_master')
    .eq('master_sku', master_sku)
    .eq('approval_status', 'approved')

  if (error) {
    console.error('Error fetching approved images:', error)
    return { finishImages: new Map(), masterImageUrl: null }
  }

  if (!images || images.length === 0) {
    return { finishImages: new Map(), masterImageUrl: null }
  }

  const finishImages = new Map<string, string>()
  let masterImageUrl: string | null = null

  for (const img of images) {
    // Extract master image (applies to all variants)
    if (img.use_for_master && img.image_url) {
      masterImageUrl = img.image_url
    }

    // Extract finish-specific images
    if (img.finish_code && img.image_url && !img.use_for_master) {
      finishImages.set(img.finish_code, img.image_url)
    }
  }

  return { finishImages, masterImageUrl }
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit image query helper**

```bash
git add dashboard/src/lib/publishing/expand-variants.ts
git commit -m "feat: add queryApprovedImages helper for lifestyle image lookup"
```

---

## Task 3: Integrate image lookup into expandVariantsForPublish

**Files:**
- Modify: `dashboard/src/lib/publishing/expand-variants.ts:39-88`

**Step 1: Add image query to expandVariantsForPublish**

Update the `expandVariantsForPublish` function to query images and apply them to variants:

```typescript
export async function expandVariantsForPublish(
  options: ExpandVariantsOptions
): Promise<ExpandedVariant[]> {
  const { master_sku, platform, approved_title, approved_description } = options
  const supabase = await createClient()

  // Get all variants for this SKU from variant_index
  const { data: variants, error: variantError } = await supabase
    .from('variant_index')
    .select('gmc_offer_id, finish, finish_code')
    .eq('master_sku', master_sku)

  if (variantError) {
    console.error('Error fetching variants:', variantError)
    return []
  }

  if (!variants?.length) {
    console.warn(`No variants found for master_sku: ${master_sku}`)
    return []
  }

  // Get finish sentences for this SKU/platform (product-specific finish descriptions)
  const { data: finishData, error: finishError } = await supabase
    .from('variant_finish_sentences')
    .select('finish_sentences')
    .eq('master_sku', master_sku)
    .eq('platform', platform)
    .single()

  if (finishError && finishError.code !== 'PGRST116') {
    // PGRST116 = no rows found, which is OK (we'll use generic fallback)
    console.error('Error fetching finish sentences:', finishError)
  }

  const finishSentences = (finishData?.finish_sentences as Record<string, string>) || {}

  // Query approved lifestyle images for this SKU
  const { finishImages, masterImageUrl } = await queryApprovedImages(supabase, master_sku)

  // Expand each variant
  return variants.map((v) => {
    // Determine image URL: finish-specific takes precedence, then master fallback
    const imageUrl = v.finish_code
      ? finishImages.get(v.finish_code) || masterImageUrl || undefined
      : masterImageUrl || undefined

    return {
      gmc_offer_id: v.gmc_offer_id,
      finish: v.finish || 'Unknown',
      finish_code: v.finish_code,
      title: generateVariantTitle(approved_title, v.finish || 'Unknown', platform),
      description: generateVariantDescription(
        approved_description,
        v.finish || 'Unknown',
        finishSentences
      ),
      image_url: imageUrl,
    }
  })
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit image integration**

```bash
git add dashboard/src/lib/publishing/expand-variants.ts
git commit -m "feat: integrate lifestyle image lookup into variant expansion"
```

---

## Task 4: Update SKU publish route to pass images

**Files:**
- Modify: `dashboard/src/app/api/publish/sku/route.ts:156-173`

**Step 1: Update publishExpandedVariantsToGoogleSheets call**

The expanded variants already contain `image_url`, and `publishExpandedVariantsToGoogleSheets` already supports it via `ExpandedVariantRow.image_url`. Verify the mapping is correct:

```typescript
// Around line 166 in sku/route.ts
const googleResult = await publishExpandedVariantsToGoogleSheets(
  expandedVariants.map((v) => ({
    gmc_offer_id: v.gmc_offer_id,
    title: v.title,
    description: v.description,
    image_url: v.image_url,  // Add this line
  })),
  environment
)
```

**Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit SKU route update**

```bash
git add dashboard/src/app/api/publish/sku/route.ts
git commit -m "feat: pass image_url through SKU publish route to Google Sheets"
```

---

## Task 5: Update batch publish route to pass images

**Files:**
- Modify: `dashboard/src/app/api/publish/batch/route.ts:298-305`

**Step 1: Update publishExpandedVariantsToGoogleSheets call**

Similar to the SKU route, add `image_url` to the mapped variants:

```typescript
// Around line 298 in batch/route.ts
const googleResult = await publishExpandedVariantsToGoogleSheets(
  expandedVariants.map((v) => ({
    gmc_offer_id: v.gmc_offer_id,
    title: v.title,
    description: v.description,
    image_url: v.image_url,  // Add this line
  })),
  environment
)
```

**Step 2: Verify TypeScript compiles**

Run: `cd dashboard && npm run build`
Expected: Build succeeds with no errors

**Step 3: Commit batch route update**

```bash
git add dashboard/src/app/api/publish/batch/route.ts
git commit -m "feat: pass image_url through batch publish route to Google Sheets"
```

---

## Task 6: Verification - Test with real data

**Files:**
- Test: Manual verification via Supabase and Google Sheets

**Step 1: Query for test data**

Use Supabase MCP to find a SKU with approved images:

```sql
SELECT master_sku, finish_code, image_url, use_for_master, approval_status
FROM generated_images
WHERE approval_status = 'approved'
LIMIT 5
```

Expected: Returns at least one SKU with an approved image

**Step 2: Verify SKU has approved content**

```sql
SELECT master_sku, platform, content_type,
       approved_content IS NOT NULL as has_approved_content
FROM generated_content
WHERE master_sku = '<test_sku_from_step_1>'
  AND platform = 'google'
```

Expected: Shows approved title and description

**Step 3: Test publish via API**

Use curl or Postman to call the SKU publish endpoint:

```bash
curl -X POST http://localhost:3000/api/publish/sku \
  -H "Content-Type: application/json" \
  -d '{
    "master_sku": "<test_sku>",
    "platforms": ["google"],
    "environment": "staging"
  }'
```

Expected: Returns success response with `updated_count` or `appended_count` > 0

**Step 4: Verify Google Sheets was updated**

Query the Google Sheet (via Google Sheets UI or API) to check:
- The `lifestyle_image_link` column exists
- The test SKU's variants have image URLs populated
- URLs match the approved image from `generated_images`

Expected: All variants for the test SKU show the same `lifestyle_image_link` value (if `use_for_master=true`)

**Step 5: Verify image URL is accessible**

Test the URL from the sheet:

```bash
curl -I <image_url_from_sheet>
```

Expected: Returns `200 OK` (for Supabase Storage public bucket or Shopify CDN)

**Step 6: Document test results**

Record findings in this plan or a separate test results file

---

## Task 7: Final build and commit

**Files:**
- All modified files

**Step 1: Run final build check**

Run: `cd dashboard && npm run build && npm run lint`
Expected: Both commands succeed with no errors or warnings

**Step 2: Review git diff**

Run: `git diff --stat`
Expected: Shows modifications to 3 files:
- `dashboard/src/lib/publishing/expand-variants.ts`
- `dashboard/src/app/api/publish/sku/route.ts`
- `dashboard/src/app/api/publish/batch/route.ts`

**Step 3: Final commit (if needed)**

If there are uncommitted changes:

```bash
git add -A
git commit -m "feat: complete lifestyle image publishing integration

- Add image_url to ExpandedVariant type
- Query approved images with finish-specific + master fallback logic
- Pass image URLs through SKU and batch publish routes
- Verified integration with Google Sheets lifestyle_image_link column

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Summary

This implementation adds lifestyle image publishing by:

1. **Type safety**: Added `image_url` field to `ExpandedVariant` interface
2. **Image querying**: Created `queryApprovedImages()` helper that fetches approved images with variant-specific + master fallback logic
3. **Integration**: Wired image lookup into `expandVariantsForPublish()` to resolve images per variant
4. **Publishing**: Updated both SKU and batch publish routes to pass `image_url` through to Google Sheets
5. **Existing infrastructure**: Leveraged existing `ensureLifestyleImageColumn()` and `ExpandedVariantRow.image_url` support in google-sheets.ts

**Key design decisions:**

- **Variant-specific with master fallback**: Images are resolved per-variant by `finish_code`, falling back to `use_for_master` images
- **Single query optimization**: One database query fetches all images, then processes in memory
- **Graceful degradation**: Missing images don't block publishing - variants without images simply have `undefined` image_url
- **No breaking changes**: Existing publish flows work unchanged - images are additive

**Testing strategy:**

- Manual verification via Supabase queries + publish API + Google Sheets inspection
- URL accessibility check via curl
- TypeScript build validation at each step
