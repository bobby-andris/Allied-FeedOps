# Critical Fix: Offer ID Case Mismatch (2026-02-08)

## Problem

Performance baseline capture returned ZERO data for ALL SKUs, even though products were active in Google Ads campaigns with thousands of impressions.

## Root Cause

**Offer ID case mismatch between database and Google Ads:**

- **Database (`variant_index`)**: `shopify_US_*` (uppercase "US")
- **Google Ads API**: `shopify_us_*` (lowercase "us")

When querying Google Ads with `shopify_US_7721863643362_42804912849122`, it returned no matches because Google Ads stores it as `shopify_us_7721863643362_42804912849122`.

## Investigation Process

1. **Initial symptoms**: Baseline capture returned 0 data for ~60 SKUs
2. **Added campaign.advertising_channel_type**: Still returned 0 rows
3. **Created diagnostic endpoints**: `/performance/diagnose-query` and `/performance/diagnose-products`
4. **Direct Google Ads query**: Found 42 products with impressions, all using lowercase "us"
5. **Database check**: Confirmed all 72,023 rows used uppercase "US"

## Solution

Updated all offer IDs in `variant_index` table to use lowercase "us":

```sql
UPDATE variant_index
SET gmc_offer_id = REPLACE(gmc_offer_id, 'shopify_US_', 'shopify_us_')
WHERE gmc_offer_id LIKE 'shopify_US_%';
```

**Result**: 72,023 rows updated (0 uppercase → 72,023 lowercase)

## Verification

### Before Fix
```bash
curl .../performance/capture-baseline -d '{"master_skus": ["DMF-2/2X"]}'
# Result: 0 rows returned from Google Ads API
```

### After Fix
```bash
# Test with diagnostic script
python3 scripts/test_google_ads_raw.py
# Result: Found 42 products with impressions, both SHOPPING and PERFORMANCE_MAX
```

## Impact

- **Before**: 0% of SKUs could capture baseline data
- **After**: All active products in campaigns can now capture data
- **Root issue**: Not the query, not the campaign type filter - just a case mismatch

## Additional Fixes

1. Removed `updated_at` field from baseline data (column doesn't exist in table)
2. Added diagnostic endpoints for future troubleshooting:
   - `/performance/diagnose-query` - Test queries with specific SKUs
   - `/performance/diagnose-products` - See what products exist in Google Ads

## Lessons Learned

1. **Test with real data first**: The fix to add `campaign.advertising_channel_type` was correct in theory but didn't help because of the case mismatch
2. **Check assumptions**: The documentation said offer IDs should be `shopify_US_*` but Google Ads actually uses `shopify_us_*`
3. **Direct API testing**: Running a Python script locally with real API calls revealed the issue immediately
4. **Database vs API mismatch**: Always verify the exact format of identifiers between systems

## Files Changed

- `src/feedops/integrations/google_ads_performance.py` - Added `campaign.advertising_channel_type` (correct but not the main issue)
- `src/feedops/api/performance_baseline.py` - Removed `updated_at` field, added diagnostic endpoints
- `variant_index` table - Updated 72,023 rows from uppercase to lowercase

## Related Documentation

- Original issue: `docs/prompts/investigate-google-ads-pmax-query.md`
- Performance Max query fix: `docs/audit/critical-blocker-fixed-2026-02-08.md` (superseded by this fix)
- Test script: `scripts/test_google_ads_raw.py` (for direct API testing)
