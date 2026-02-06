# Prompt 23: Publishing Enhancements — Structured Content, Lifestyle Images & Shopify Strategy

## Objective

Enhance the publishing pipeline with three improvements:
1. **GMC AI content disclosure**: Add `structured_title` and `structured_description` columns to the Google Sheets supplemental feed for proper AI-generated content compliance
2. **Lifestyle image publishing**: Wire approved lifestyle images through the publish pipeline to Google Sheets (and optionally Shopify)
3. **Shopify publishing strategy**: Decide and document how Shopify product-level vs variant-level content should work

## IMPORTANT: Use Superpowers Skills

You MUST use the following skills during this work:
- `superpowers:brainstorming` — BEFORE starting any implementation, to explore the approach for each task
- `superpowers:writing-plans` — To create a detailed implementation plan before writing code
- `superpowers:test-driven-development` — Write tests before implementation code
- `superpowers:verification-before-completion` — Run verification before claiming any task is done
- `superpowers:systematic-debugging` — If any bugs or test failures are encountered

## CRITICAL: Read Before Changing

Before modifying ANY file, you MUST read it first. The publishing system was recently fixed for a data corruption bug — do NOT introduce regressions. Key constraint: the `buildColumnMap` function in `google-sheets.ts` builds the column map PURELY from sheet headers (no defaults). Do not reintroduce hardcoded default column positions.

## Context & Current State

### What exists today

**Google Sheets supplemental feed** (spreadsheet ID in env `GOOGLE_SHEETS_SPREADSHEET_ID`):
- 11 columns: `id`, `mpn`, `product_type`, `pattern`, `custom_label_0`, `custom_label_1`, `custom_label_2`, `title`, `google_product_category`, `description`, `custom_label_4`
- ~59,589 rows (one per variant/offer ID)
- Offer ID format: `shopify_US_{product_id}_{variant_id}` (uppercase US)
- Connected to live Merchant Center feed — changes here affect production Shopping ads

**Publishing code** (`dashboard/src/lib/publishing/`):
- `google-sheets.ts` — Google Sheets API client, `publishExpandedVariantsToGoogleSheets()`, `buildColumnMap()` (builds from headers only), `ensureLifestyleImageColumn()` (auto-adds column if missing), `rowDataToValues()` (skips fields with `undefined` column indices)
- `shopify.ts` — Shopify GraphQL Admin API, `publishToShopify()` updates product-level title + description + tracking tag
- `expand-variants.ts` — Expands `{FINISH_NAME}` templates to 28 variant-specific titles/descriptions
- `types.ts` — `GoogleSheetsRow`, `SheetColumnMap`, `PublishEventInsert`

**Publish routes** (`dashboard/src/app/api/publish/`):
- `sku/route.ts` — Single SKU publish (validates approval → expands variants → writes to Google Sheets / Shopify)
- `batch/route.ts` — Batch publish (same flow for multiple SKUs)
- Neither route currently passes lifestyle image URLs through

**Lifestyle images in Supabase**:
- `generated_images` table has `image_url`, `approval_status`, `ai_selected`, `user_selected`, `use_for_master`, `gmc_offer_id`
- Images are approved through the review UI but never published to any platform

**Environment variable**: `FEEDOPS_GMC_STRUCTURED_ONLY` — when set to `1`, the code already omits standard `title`/`description` and only writes `structured_title`/`structured_description` fields. Currently NOT enabled.

### GMC Policy (from official Product Data Specification)

**Structured title/description** — compound attributes for AI-generated content:
- Feed format: `trained_algorithmic_media:"Your title text here"`
- Sub-attributes: `digital_source_type` (trained_algorithmic_media or default) + `content` (the text)
- Google says: "For titles created using generative AI, use the `structured_title` attribute"
- **If both `title` AND `structured_title` are submitted, Google ignores `structured_title`** — so structured-only mode must omit plain title/description

**Lifestyle image link** — real GMC attribute:
- Feed column name: `lifestyle_image_link`
- Only shown on "browsy surfaces" (Discover, Shopping tab browsing)
- AI-generated images MUST have IPTC `DigitalSourceType: TrainedAlgorithmicMedia` metadata embedded in the image file
- URL must be publicly crawlable by Google
- Does NOT require Shopify publishing — GMC fetches the URL directly

## Task 1: Add structured_title / structured_description to Google Sheets

### Requirements

1. Add two new columns to the END of the Google Sheet: `structured_title` and `structured_description`
   - MUST be added at the end (after column K) to avoid shifting existing columns
   - Use a function similar to `ensureLifestyleImageColumn()` — check if column exists, add if not
   - Column values use compound format: `trained_algorithmic_media:"content text"`

2. Enable structured-only mode by default:
   - Set `FEEDOPS_GMC_STRUCTURED_ONLY=1` in Vercel environment variables
   - When enabled, `rowDataToValues` should write `structured_title` and `structured_description` but NOT plain `title`/`description`
   - Keep writing plain `title`/`description` as a fallback when `FEEDOPS_GMC_STRUCTURED_ONLY` is not set

3. The `GoogleSheetsRow` type already has `structured_title`, `structured_description`, and `digital_source_type` fields — but they need to be populated with the compound format value, not as separate columns

4. **Important**: In a supplemental feed (Google Sheets), `structured_title` is a SINGLE column with format `trained_algorithmic_media:"content"` — it is NOT two separate columns. The `digital_source_type` field should NOT be a separate column in the sheet. Update the code to build the compound value.

### Files to modify

- `dashboard/src/lib/publishing/google-sheets.ts` — Add `ensureStructuredColumns()`, update `rowDataToValues()` to build compound format
- `dashboard/src/lib/publishing/types.ts` — Update `GoogleSheetsRow` if needed for compound format

### Verification

- Read back the sheet headers after adding columns to confirm they were added at the END
- Publish one test variant to staging and verify the compound format: `trained_algorithmic_media:"actual title"` appears in the structured_title column
- Verify that when `FEEDOPS_GMC_STRUCTURED_ONLY=1`, the plain `title` and `description` columns are NOT written to
- Verify that columns A-K are completely unchanged

## Task 2: Wire lifestyle image publishing to Google Sheets

### Requirements

1. During publish (both SKU and batch routes), query `generated_images` for approved lifestyle images:
   - Look for images where `approval_status = 'approved'` for the relevant `gmc_offer_id` or master SKU
   - If `use_for_master = true`, apply the same image URL to all variants of that master SKU
   - If variant-specific, match by `gmc_offer_id`

2. Pass `image_url` through the publish pipeline:
   - `expandVariantsForPublish()` should include image URLs in the returned `ExpandedVariant` objects
   - The publish routes should pass these through to `publishExpandedVariantsToGoogleSheets()`
   - `ensureLifestyleImageColumn()` already handles adding the column if it doesn't exist

3. The image URL must be publicly crawlable by Google. Verify that the URLs stored in `generated_images.image_url` are public CDN URLs (they should be Supabase Storage public URLs or Shopify CDN URLs).

### Files to modify

- `dashboard/src/lib/publishing/expand-variants.ts` — Add image URL lookup
- `dashboard/src/app/api/publish/sku/route.ts` — Pass image URLs through
- `dashboard/src/app/api/publish/batch/route.ts` — Pass image URLs through
- `dashboard/src/lib/publishing/types.ts` — Ensure `ExpandedVariant` includes `image_url`

### Verification

- Query `generated_images` to find an approved image for a test SKU
- Publish that SKU and verify `lifestyle_image_link` column gets the image URL
- Verify the URL is publicly accessible (curl it)

## Task 3: Document Shopify variant vs master SKU strategy

### Context

Shopify's data model:
- **Product** = title, description (HTML body), images, tags
- **Variant** = price, SKU, option values (e.g., "Antique Bronze"), inventory — but NO variant-specific title or description

Currently, the publish code:
- Uses `shopify_product_id` (product-level, not variant)
- Strips `{FINISH_NAME}` from content since Shopify is product-level
- Updates title + descriptionHtml via `productUpdate` GraphQL mutation
- Does NOT handle images

### Requirements

1. Research and decide: Should we add variant-specific content to Shopify? Options:
   - **Option A**: Keep product-level only (current behavior) — simplest, Shopify doesn't natively support variant descriptions
   - **Option B**: Use Shopify metafields to store variant-specific titles/descriptions — more complex but enables custom storefront rendering
   - **Option C**: Use Shopify SEO fields (metaTitle, metaDescription) at variant level — available via GraphQL

2. For lifestyle images on Shopify:
   - Research: Can we add images to a specific Shopify product via the Admin API?
   - The `productCreateMedia` or `productAppendImages` GraphQL mutation could work
   - Should we associate images with specific variants using `alt` text or variant media assignment?

3. **Deliverable**: Add a section to CLAUDE.md under "Publishing Workflow" that documents the decided strategy, including reasoning. Also update the Future TODOs section.

### Files to modify

- `CLAUDE.md` — Document the strategy decision
- `dashboard/src/lib/publishing/shopify.ts` — Implement image publishing if decided
- `dashboard/src/app/api/publish/sku/route.ts` — Pass images to Shopify if decided

## Testing Strategy

Use `superpowers:test-driven-development` for each task.

### Test approach

1. **Unit tests** for:
   - Compound format builder (`trained_algorithmic_media:"content"`)
   - `buildColumnMap` still works correctly with new columns
   - `rowDataToValues` correctly populates structured columns and skips title/description in structured-only mode
   - Image URL lookup logic

2. **Integration verification** (manual via Python):
   - Read sheet headers before and after to confirm no column shifts
   - Publish one variant to staging and read back to verify all fields
   - Use the existing Python `get_column_headers()` and row reading pattern

### Safety constraints

- NEVER modify columns A-K in the sheet — only add new columns at the end
- NEVER write to a column position that was determined from a hardcoded default — always use `buildColumnMap()` from actual headers
- Test on staging (`feedops-staging` label) before any production publish
- The Google Sheet is connected to the live merchant feed — any incorrect writes corrupt production data

## Deployment

Both pipelines auto-deploy on push to master:
- **Cloud Run** (Python): Cloud Build trigger `feedops-pipeline-deploy` builds and deploys automatically
- **Vercel** (Next.js dashboard): Auto-deploys on push

DO NOT manually deploy. DO NOT create GCP secrets. DO NOT create Cloud Build triggers. All infrastructure is already set up.

After pushing, set `FEEDOPS_GMC_STRUCTURED_ONLY=1` in Vercel environment variables (Production + Preview + Development).

## Definition of Done

- [ ] `structured_title` and `structured_description` columns added to sheet (at the end)
- [ ] Compound format `trained_algorithmic_media:"content"` verified in sheet
- [ ] Plain title/description NOT written when `FEEDOPS_GMC_STRUCTURED_ONLY=1`
- [ ] Approved lifestyle images flow through publish pipeline to `lifestyle_image_link` column
- [ ] Image URLs are publicly accessible
- [ ] Shopify strategy documented in CLAUDE.md
- [ ] All changes pushed to master, builds green
- [ ] No regressions — existing columns A-K untouched, `buildColumnMap` still header-only
