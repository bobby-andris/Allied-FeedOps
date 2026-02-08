# GMC Feed Investigation - 2026-02-08

## Objective
Investigate whether Google Merchant Center (GMC) feed contains the variant IDs reported by Google Ads search terms.

## Context
Google Ads search terms query returned `shopify_us_4539975336068_32103134298244` (lowercase 'us'), but our database `variant_index` table only has different variant IDs for product `4539975336068`.

## Investigation Method

1. **Attempted:** Query GMC Reports API directly
   - **Result:** 401 Unauthorized - credentials don't have proper access
   - **Note:** Both Reports API and Products API require proper OAuth/service account setup

2. **Successful:** Examined cached GMC snapshot
   - **Location:** `/Users/bobby/.cache/feedops/merchant_center/items.jsonl`
   - **Method:** Parsed JSONL file to extract all offer IDs for product `4539975336068`

## Findings

### Key Result
✅ **Google Ads variant ID `32103134298244` DOES EXIST in GMC**

### GMC Data for Product `4539975336068`

**Total variants found:** 102 variants

**Variant ID ranges:**
- First: `32103132364932`
- Last: `43099045658850`
- Includes: `32103134298244` ← The Google Ads variant

**Specific variant details** (`shopify_US_4539975336068_32103134298244`):
```json
{
  "offerId": "shopify_US_4539975336068_32103134298244",
  "customLabel0": "Free Standing Make-Up Mirrors",
  "customLabel1": "low",
  "customLabel2": "500+",
  "productTypes": [
    "Make-Up Mirrors > Allied Brass > Adjustable Height Freestanding Make-Up Mirror 8 Inch Diameter - Polished Chrome / 5X"
  ],
  "destinationStatuses": [
    {
      "reportingContext": "SHOPPING_ADS",
      "approvedCountries": ["US"]
    },
    ...
  ]
}
```

**Status:** Approved for Shopping Ads, Display Ads, Free Listings, etc.

### Database Comparison

**GMC/Google Ads variant IDs** (sample):
- `32103132364932`
- `32103134298244` ← Google Ads reported this
- `32103134331012`
- `43099044577506`
- `43099045658850`

**Our database variant IDs** (sample from `variant_index`):
- `43099044577506` ← Matches GMC
- `43099044610274` ← Matches GMC
- `43099044643042` ← Matches GMC
- But **missing** older variant IDs like `32103134298244`

## Conclusion

### Root Cause Location
❌ **NOT a GMC feed issue** - GMC has correct variant IDs
✅ **Sync issue in `variant_index` table** - Database is missing older variant IDs

### Data Mismatch Details
1. **GMC contains TWO sets of variant IDs:**
   - Older IDs: `321031323xxxxx` range (likely original Shopify variants)
   - Newer IDs: `430990445xxxxx` range (likely replacement variants)

2. **Our database only has:**
   - Newer IDs: `430990445xxxxx` range
   - Missing: Older `321031323xxxxx` range

3. **Google Ads reports performance for:**
   - Both old and new variant IDs
   - We can't match old IDs to our database records

### Impact
- Search terms from Google Ads referencing old variant IDs cannot be matched to products in our database
- This causes `item_ids` arrays in `search_queries` table to contain variants that don't exist in `variant_index`
- Performance metrics for old variants cannot be attributed correctly

## Recommendations

1. **Immediate:** Sync all historical variant IDs from GMC into `variant_index` table
2. **Investigation:** Determine why Shopify product has two sets of variant IDs
3. **Architecture:** Implement continuous sync to catch variant ID changes
4. **Monitoring:** Add alerts when Google Ads reports variant IDs not in our database

## Files Created
- Investigation script: `/Users/bobby/Documents/GitHub/Allied-FeedOps/scripts/query_gmc_offer_ids.py`
- This audit report: `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/audit/gmc-feed-investigation-2026-02-08.md`
