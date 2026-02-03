# Task: Add Variant-Level Review Support

## Objective

Enhance the SKU detail page to show and approve content at the variant (finish) level, not just the master SKU level.

## Current State

- SKU detail page shows content by platform (Google, Bing, Shopify)
- Approval is tracked at master SKU level in `sku_approvals`
- Variant-level approvals exist in `variant_approvals` table but aren't used in UI
- Content in `generated_content` may have variant-specific variations

## Business Context

Allied Brass products have multiple finishes (e.g., Polished Chrome, Oil Rubbed Bronze, Satin Nickel). Each finish is a separate GMC offer ID. Content may need per-variant approval for:

- Finish-specific title variations
- Variant-specific images
- Quality differences between variants

## Files to Modify

1. `dashboard/src/app/(dashboard)/review/[sku]/page.tsx` - Add variant tabs/sections
2. `dashboard/src/app/api/approvals/route.ts` - Support variant-level approvals
3. `dashboard/src/components/review/VariantSelector.tsx` - NEW component
4. `dashboard/src/components/review/ApprovalActions.tsx` - Support variant context

## Supabase Tables

### `variant_index`

```sql
-- Maps GMC offer IDs to master SKUs with finish info
CREATE TABLE variant_index (
  id uuid PRIMARY KEY,
  gmc_offer_id text UNIQUE,
  master_sku text NOT NULL,
  shopify_product_id text,
  shopify_variant_id text,
  finish text,      -- e.g., "Oil Rubbed Bronze"
  finish_code text, -- e.g., "ORB"
  dimensions text
);
```

### `variant_approvals`

```sql
CREATE TABLE variant_approvals (
  id uuid PRIMARY KEY,
  master_sku text NOT NULL,
  variant_id text, -- Can be finish_code or gmc_offer_id
  finish text,
  title_approved boolean,
  description_approved boolean,
  image_approved boolean,
  approval_status text, -- derived from above
  approved_by text,
  approved_at timestamptz,
  notes text
);
```

## Requirements

### 1. Fetch Variant Data

Update `getSkuData()` to also fetch:

- Variants from `variant_index` for this master SKU
- Variant-level approvals from `variant_approvals`

```typescript
const { data: variants } = await supabase
  .from("variant_index")
  .select("*")
  .eq("master_sku", sku)
  .order("finish");
```

### 2. Variant Selector Component

Show variants as tabs or a dropdown:

- "All Variants" (master SKU level)
- Individual finishes (e.g., "Polished Chrome", "Oil Rubbed Bronze")

```tsx
<VariantSelector
  variants={variants}
  selectedVariant={selectedVariant}
  onSelect={setSelectedVariant}
/>
```

### 3. Filter Content by Variant

If content has variant-specific versions (stored with finish info), filter the display:

- When "All Variants" selected: Show master SKU content
- When specific finish selected: Show finish-specific content (if exists) or fall back to master

### 4. Variant-Level Approval Actions

Update `ApprovalActions` to support variant context:

```tsx
<ApprovalActions
  sku={sku}
  variantId={selectedVariant?.finish_code}
  type="title"
/>
```

API calls should include variant info:

```typescript
PATCH /api/approvals
{
  master_sku: "1051",
  variant_id: "ORB", // Optional - if null, applies to master SKU
  title_approved: true
}
```

### 5. Approval Status Display

Show approval status per variant:

- Grid or table showing all variants with their approval status
- Quick visual: green check for approved, yellow for pending, red for rejected
- Count: "3/12 variants approved"

### 6. Batch Approval

"Approve All Variants" button that:

1. Copies master SKU approval to all variants
2. Or applies current approval to selected variants

## UI Design Suggestions

Option A: Tabs above content

```
[All Variants] [Polished Chrome] [Oil Rubbed Bronze] [Satin Nickel] ...
```

Option B: Sidebar with variant list

```
| Variants (12)    |  Content Area
| ☑ Polished Chrome|  [Title comparison]
| ☐ Oil Rubbed...  |  [Description comparison]
| ☑ Satin Nickel   |  [Images]
```

## Reference Data

- Finish codes: See `data/finish-metadata.json` for full list
- Example finishes for SKU 1051: Check `variant_index` table

## Success Criteria

1. Can see all variants for a SKU
2. Can switch between variants to see variant-specific content (if exists)
3. Can approve/reject at variant level
4. Variant approval status is persisted to Supabase
5. UI clearly shows which variants are approved vs pending
6. Master SKU approval still works as before (applies to "all")

## Notes

- Not all SKUs will have variant-specific content initially
- If no variant-specific content exists, show master SKU content with note
- Consider performance: Don't fetch all variant images unless needed
