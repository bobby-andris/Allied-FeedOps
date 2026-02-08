# Hybrid Generation Testing & Fixes (2026-02-08)

**Status:** ✅ Core functionality working, 🔄 Testing in progress

## Summary

Successfully implemented and deployed hybrid multi-SKU generation to Cloud Run. Discovered and fixed several bugs during initial testing. Currently awaiting deployment of final fixes.

## What Was Tested

### ✅ Successful Tests

1. **Endpoint Availability** ✅
   - `/hybrid-generate` endpoint responds correctly
   - Returns proper job structure with job_id

2. **Family Detection** ✅
   - Correctly identifies multi-SKU families by product_id
   - Test: 3 SKUs → detected 3 families with 9 variants
   - Strategy calculation correct: 3 base + 9 variants = 12 total

3. **Job Creation** ✅
   - Creates `batch_generation_jobs` record
   - Returns immediately with job_id (no timeout)
   - Status updates to "processing"

### ❌ Bugs Found & Fixed

#### Bug #1: Supabase Method Name (FIXED)
**Error:** `'SyncSelectRequestBuilder' object has no attribute 'maybeSingle'`

**Root Cause:** Python Supabase client uses `maybe_single()` (snake_case), not `maybeSingle()` (camelCase)

**Fix:** Changed `.maybeSingle()` → `.maybe_single()` in 2 places
- Line 163: Base content query
- Line 189: Current content query

**Commit:** b79953d9

#### Bug #2: Missing Fields in regeneration_history (FIXED)
**Error:** `null value in column "master_sku" of relation "regeneration_history" violates not-null constraint`

**Root Cause:** `regeneration_history` insert was missing required fields

**Fix:** Added 3 required fields to insert:
```python
supabase.table("regeneration_history").insert({
    "generated_content_id": content_id_result.data["id"],
    "master_sku": variant_sku,           # ADDED
    "platform": platform,                 # ADDED
    "content_type": content_type,         # ADDED
    "system_prompt": system_prompt,
    "user_prompt": user_prompt,
    "model_version": model,
    "prompt_hash": prompt_hash,
    "mode": "variant-adaptation",
})
```

**Commit:** f9003462

#### Bug #3: Google Ads Yaml Warning (FIXED)
**Warning:** `Google Ads API enabled but client could not be loaded ([Errno 2] No such file or directory: '/root/google-ads.yaml'); returning []`

**Root Cause:** Code tried `load_from_storage()` first, which looks for yaml file

**Fix:** Updated to try `load_from_env()` before falling back to yaml:
```python
def _load_client():
    # Try loading from environment variables (Cloud Run)
    try:
        return GoogleAdsClient.load_from_env()
    except Exception:
        # Fall back to yaml file (local development)
        return GoogleAdsClient.load_from_storage()
```

**Commit:** f9003462

**Note:** Other Google Ads files (`google_ads_performance.py`, `google_ads_search_terms.py`) already handle env vars properly by manually building config dict.

#### Bug #4: NoneType Error on Failed Queries (NEEDS FIX)
**Error:** `'NoneType' object has no attribute 'data'`

**Occurs When:** Supabase returns "406 Not Acceptable" error

**Root Cause:** Code doesn't check if `current_result` is valid before accessing `.data`

**Proposed Fix:**
```python
# Get current content for version tracking
current_result = (
    supabase.table("generated_content")
    .select("*")
    .eq("master_sku", variant_sku)
    .eq("platform", platform)
    .eq("content_type", content_type)
    .maybe_single()
    .execute()
)

# Check if query was successful
if not current_result or not hasattr(current_result, 'data'):
    return {
        "success": False,
        "error": f"Failed to query existing content for {variant_sku}/{platform}/{content_type}",
    }
```

**Status:** NOT YET COMMITTED

#### Issue #5: Supabase 406 Not Acceptable (INVESTIGATING)
**Error:** `HTTP/2 406 Not Acceptable` from Supabase API

**Occurs When:** Querying `generated_content` table

**Possible Causes:**
1. Missing `Accept` header in request
2. Content negotiation issue with Supabase client
3. API version mismatch

**Status:** NEEDS INVESTIGATION

## Deployment Timeline

| Time | Event | Commit | Status |
|------|-------|--------|--------|
| 16:07 | Initial hybrid generation deployment | d0052f38 | ✅ SUCCESS |
| 16:10 | Model fix (gpt-4o → gpt-5.2) + client | 4ba2bbc3 | ✅ SUCCESS |
| 16:21 | Fix maybeSingle → maybe_single | b79953d9 | ✅ SUCCESS |
| 16:36 | Fix regeneration_history + Google Ads | f9003462 | 🔄 DEPLOYING |

## Test Results

### Test Job #1: 83e4fd3c-65da-4bed-ba9c-1f7333cd4870
- **SKUs:** 16 partial content families (51 total SKUs)
- **Started:** 16:18 UTC
- **Status:** Failed after base SKU generation
- **Failures:** 18 (due to maybeSingle bug)
- **Completed:** 6

### Test Job #2: 1be74eb4-8cb6-4e1f-b382-142b40582340
- **SKUs:** 3 families (12 total SKUs)
- **Started:** 16:28 UTC
- **Status:** Processing
- **Issue:** Stuck at 0 completions (using buggy code)

## Next Steps

### Immediate (After Current Deployment)

1. **Wait for build 4df33bdb to complete** (ETA: ~3-5 minutes)
2. **Test with small batch** (3 SKUs):
   ```bash
   python3 /tmp/test-hybrid.py
   ```
3. **Monitor logs** for:
   - ✅ No maybeSingle errors
   - ✅ No regeneration_history constraint violations
   - ✅ No Google Ads yaml warnings
   - ⚠️  Check for 406 errors

### If 406 Errors Persist

4. **Investigate Supabase client configuration:**
   - Check if `postgrest-py` version is compatible
   - Test with direct SQL queries vs PostgREST
   - Add explicit `Accept` headers if needed

5. **Add comprehensive error handling:**
   - Validate Supabase responses before accessing `.data`
   - Log full error details for debugging
   - Graceful degradation for query failures

### Full Integration Test

6. **Run complete 16-family batch** once 406 issue is resolved:
   ```bash
   bash /tmp/backfill-test.sh
   ```

7. **Verify results:**
   ```sql
   -- Check content generation tags
   SELECT
     CASE WHEN generation_model LIKE '%variant-adaptation%' THEN 'Variant' ELSE 'Base' END as type,
     COUNT(*) as count,
     COUNT(DISTINCT master_sku) as unique_skus
   FROM generated_content
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY type;

   -- Expected: 16 base + 35 variants = 51 total
   ```

## Google Ads Configuration Verification

**Environment Variables in Cloud Run:**
- ✅ `GOOGLE_ADS_CUSTOMER_ID`: 6253381786
- ✅ `GOOGLE_ADS_API_ENABLED`: 1
- ✅ All secrets bound: DEVELOPER_TOKEN, CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, LOGIN_CUSTOMER_ID

**Code Updates:**
- ✅ `google_ads.py`: Now tries `load_from_env()` first
- ✅ `google_ads_performance.py`: Already handles env vars via `load_from_dict()`
- ✅ `google_ads_search_terms.py`: Already handles env vars via `load_from_dict()`

**Expected Result:** No more yaml file warnings in logs after deployment

## Model Configuration Verified

- ✅ All code using `gpt-5.2` as default
- ✅ Variant adaptations tagged as `gpt-5.2-variant-adaptation`
- ✅ Temperature: 0.6 for variants (vs 0.7 for base)

## Key Learnings

1. **Supabase Python Client Syntax:**
   - Always use snake_case: `maybe_single()`, `single()`, etc.
   - Check response validity before accessing `.data`
   - Handle HTTP errors gracefully (406, 404, etc.)

2. **Database Schema Constraints:**
   - Always verify required fields when inserting
   - `regeneration_history` requires: `master_sku`, `platform`, `content_type`, `generated_content_id`

3. **Google Ads Library Configuration:**
   - `load_from_env()` method exists and should be preferred for Cloud Run
   - Fallback to `load_from_storage()` for local development
   - `load_from_dict()` approach (used in other files) is also valid

4. **Cloud Build Performance:**
   - Typical build time: 3-5 minutes
   - Large commits with images: 5-10 minutes
   - Auto-deploy triggers immediately on push to master

## Documentation Updates Needed

After successful testing:

1. ✅ Update `docs/architecture/hybrid-generation-architecture.md` with bug fixes
2. ✅ Add troubleshooting section for common errors
3. ✅ Document Supabase client gotchas
4. ✅ Add verification queries for post-deployment testing

## Success Criteria (Not Yet Met)

- ⏳ Complete batch job with 0 errors
- ⏳ All 51 SKUs have content generated
- ⏳ Database shows correct generation_model tags
- ⏳ No warnings in Cloud Run logs
- ⏳ Google Ads client loads successfully from env vars

## Files Modified

**Python (Cloud Run):**
- `src/feedops/api/hybrid_generation.py` - Fixed maybeSingle → maybe_single, added regeneration_history fields
- `src/feedops/integrations/google_ads.py` - Added load_from_env() fallback

**Tests:**
- `tests/api/test_multi_sku_detection.py` - Unit tests for detection logic

**Documentation:**
- `docs/audit/hybrid-generation-cloud-run-2026-02-08.md` - Implementation details
- `docs/architecture/hybrid-generation-architecture.md` - Architecture decision

**Test Scripts:**
- `/tmp/test-hybrid.py` - Python script for endpoint testing
- `/tmp/backfill-test.sh` - Full 16-family batch test
- `/tmp/hybrid-generation-verification.sql` - Database verification queries

## References

**Commits:**
- d0052f38: Initial hybrid generation implementation
- 4ba2bbc3: Model fix (gpt-5.2) + dashboard client
- b79953d9: Fix maybeSingle → maybe_single
- f9003462: Fix regeneration_history + Google Ads

**Build IDs:**
- b767cba2: Initial deployment (SUCCESS)
- 71959beb: Model fix deployment (SUCCESS)
- 691cf823: maybeSingle fix deployment (SUCCESS)
- 4df33bdb: Final fixes deployment (WORKING)

**Cloud Run:**
- Service: `feedops-pipeline`
- URL: `https://feedops-pipeline-623866089882.us-east1.run.app`
- Region: `us-east1`
- Project: `bobbys-project-346400`
