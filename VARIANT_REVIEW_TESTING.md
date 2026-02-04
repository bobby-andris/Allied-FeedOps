# Variant Review Page Testing Checklist

## Code Review Summary

✅ **All files exist and are tracked in git:**

- `dashboard/src/components/review/VariantSelector.tsx`
- `dashboard/src/components/review/VariantApprovalGrid.tsx`
- `dashboard/src/components/review/SkuReviewClient.tsx`
- `dashboard/src/app/api/variants/approvals/route.ts`
- `dashboard/src/app/(dashboard)/review/[sku]/page.tsx`

✅ **Code handles type differences:**

- Approval fields checked for both `boolean` and `number` types (`=== true || === 1`)
- Conditional rendering based on `hasVariants` flag

## Potential Issues to Check

### 1. Database Tables Missing in Production

The variant review requires two tables:

- `variant_index` - Maps GMC offer IDs to master SKUs with finish info
- `variant_approvals` - Per-finish approval tracking

**Check:** Verify these tables exist in production Supabase:

```sql
SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_schema = 'public'
  AND table_name = 'variant_index'
);

SELECT EXISTS (
  SELECT FROM information_schema.tables
  WHERE table_schema = 'public'
  AND table_name = 'variant_approvals'
);
```

### 2. No Variants for Test SKU

If a SKU has no variants in `variant_index`, the variant selector won't appear (by design).

**Check:** Query for a SKU that should have variants:

```sql
SELECT * FROM variant_index WHERE master_sku = '1051' LIMIT 5;
```

### 3. Build/Deployment Issues

The build failed due to missing `OPENAI_API_KEY` in the regenerate route, but this shouldn't affect the variant review page.

**Check:** Verify the variant review page builds successfully:

```bash
cd dashboard
npm run build
```

### 4. Runtime Errors

Check browser console for errors when loading `/review/[sku]` page.

## Manual Testing Steps

1. **Navigate to Review Page**

   - Go to `https://allied-feed-ops.vercel.app/review`
   - Sign in
   - Click on a SKU (preferably SKU 1051 which should have variants)

2. **Check for Variant Selector**

   - Look for "Variant Selection" section below the header
   - Should see tabs: "All Variants" + individual finish tabs
   - If no variants exist, selector won't appear (this is expected)

3. **Test Variant Selection**

   - Click on a finish tab (e.g., "Polished Chrome")
   - Header should show the selected finish badge
   - Approval status should update to show variant-specific approval

4. **Test Approval Actions**

   - Click "Approve" on a title/description/image
   - Should call `/api/variants/approvals` when finish is selected
   - Should call `/api/approvals` when "All Variants" is selected

5. **Check Variant Approval Grid**
   - Scroll to bottom of page
   - Should see "Variant Approval Status" table
   - Shows all variants with title/desc/image approval indicators
   - Test "Approve All Variants" button
   - Test "Copy Master to All" button (if master approval exists)

## Expected Behavior

### When SKU Has Variants:

- ✅ Variant selector appears below header
- ✅ "All Variants" tab selected by default
- ✅ Individual finish tabs show approval status indicators
- ✅ Variant approval grid appears at bottom
- ✅ Clicking variant row selects that variant
- ✅ Approval actions work for selected variant

### When SKU Has No Variants:

- ✅ Page loads normally (no variant selector)
- ✅ Master SKU approval works as before
- ✅ No variant grid shown

## Debugging Steps

1. **Check Browser Console**

   - Open DevTools → Console
   - Look for errors related to:
     - `variant_index` table
     - `variant_approvals` table
     - Component imports

2. **Check Network Tab**

   - Verify API calls to `/api/variants/approvals`
   - Check for 404 or 500 errors

3. **Check Supabase Tables**

   - Verify `variant_index` has data for test SKU
   - Verify `variant_approvals` table exists and is accessible

4. **Check Build Logs**
   - Review Vercel deployment logs
   - Look for TypeScript errors or build failures

## Quick Fixes

If variant selector doesn't appear:

1. Check if `variant_index` table has data for the SKU
2. Check browser console for errors
3. Verify the page component is using `SkuReviewClient` (not old code)

If approval actions don't work:

1. Check network tab for API errors
2. Verify `/api/variants/approvals` route is deployed
3. Check Supabase RLS policies allow reads/writes
