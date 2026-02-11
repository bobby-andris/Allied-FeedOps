# Codebase Concerns

**Analysis Date:** 2026-02-11

## Tech Debt

### Multi-SKU Product Query Logic

**Issue:** Query logic mismatch between master_sku-specific filtering and Google Ads' product_id-level aggregation. Google Ads returns data at product_id level, but queries filter by specific master_sku variants.

**Files:**
- `src/feedops/integrations/google_ads_performance.py` (fetch_batch_product_performance)
- `src/feedops/api/performance_baseline.py` (_capture_google_baseline)

**Impact:** Only 0.3% match rate for multi-SKU products (e.g., DMF-2/2X, DMF-2/3X, DMF-2/4X sharing product_id 4539975336068). Single variants capture correctly.

**Root Cause:** When Google Ads returns variant data for high-impression variants (e.g., DMF-2/5X), the code only accepts matches for the queried master_sku (DMF-2/2X), causing silent misses.

**Fix Approach:**
- Implement product_id-based matching: accept ANY variant with matching product_id
- Add `extract_product_id()` helper to parse shopify_us_{product_id}_{variant_id} format
- Update `_capture_google_baseline()` to use product_id instead of exact variant matching
- Test with multi-SKU families to verify 95%+ match rate

---

### Missing Platform Support for Performance Baselines

**Issue:** Only Google Ads platform supported for baseline capture; Bing and Shopify return no data.

**Files:** `src/feedops/api/performance_baseline.py` (line 126)

**Impact:** Cannot capture baseline metrics for Bing or Shopify platforms, limiting performance tracking to Google only.

**Fix Approach:** Implement Bing (`src/feedops/integrations/bing_ads_performance.py`) and Shopify performance APIs; add to baseline capture flow.

**Blocking:** Low priority - Google is primary platform.

---

### User Attribution Not Implemented in Dashboard API Routes

**Issue:** Approval/selection endpoints use hardcoded user values instead of authenticated session data.

**Files:**
- `dashboard/src/app/api/images/route.ts` (line 52)
- `dashboard/src/app/api/review/images/select/route.ts` (lines 62, 115)
- `dashboard/src/app/api/review/images/approve/route.ts` (line 43)

**Impact:** Cannot track which user approved content or selected images; audit trail incomplete.

**Fix Approach:** Extract user from session middleware (Supabase auth or NextAuth), pass to database operations.

---

### Category Benchmarks Not Implemented

**Issue:** Placeholder references to category performance benchmarks without actual data source.

**Files:** `dashboard/src/lib/performance-utils.ts` (line 4)

**Impact:** Cannot compare SKU performance against category baselines; feature blocked.

**Fix Approach:** Query `category_performance_benchmarks` table (if it exists) or create from historical data aggregation.

---

## Known Bugs

### Batch Publishing Status Stuck in "executing"

**Issue:** Final batch status UPDATE fails silently, leaving publish batch in "executing" state instead of final "published"/"partial"/"failed" status.

**Files:**
- `dashboard/src/components/batches/BatchesClient.tsx` (status display logic)
- `dashboard/src/app/api/publish/batch/route.ts` (status update)

**Symptoms:** Batch operations complete but UI shows "Executing..." indefinitely. User has no indication of success/failure.

**Trigger:** Long-running batch operations (Google Sheets + Shopify updates) may timeout or error on final UPDATE operation.

**Workaround:** Manually update via Supabase:
```sql
UPDATE publish_batches
SET status = 'published', success_count = N
WHERE batch_id = 'batch-id'
```

**Fix Approach:**
1. Add error handling to final status UPDATE in `/api/publish/batch/route.ts`
2. Log completion status regardless of update success
3. Consider retry logic for status persistence
4. Add database constraints to prevent stuck states

**Priority:** High - impacts production publishing workflow.

---

### Background Task Container Lifecycle Termination

**Issue:** Despite threading fix (2026-02-08), long-running jobs still fail during container deployments.

**Files:** `src/feedops/api/main.py` (run_async_in_thread, /hybrid-generate endpoint)

**Symptoms:** Job progresses to 50-75% completion then stops mid-execution when new container deploys.

**Trigger:** Deployment of new Cloud Run revision while background job running.

**Current Mitigation:** Threading enables jobs to survive scale-to-zero, but not deployments. Job status UPDATE fails silently.

**Fix Approach:**
- Option 1: Implement external task queue (Cloud Tasks, Pub/Sub) with persistent job state
- Option 2: Add deployment-aware job checkpointing to resume on container restart
- Option 3: Accept job interruption as expected; document in UI that deployments cancel jobs

**Priority:** Medium - affects batch operations but has documented workaround.

---

## Security Considerations

### Environment Configuration Scattered Across Sources

**Risk:** Multiple sources of truth for API credentials (env vars, GCP Secrets Manager, Supabase Auth, session tokens).

**Files:**
- `dashboard/.env.local` (local development only)
- `dashboard/src/app/api/health/route.ts` (credential parsing from env)
- `src/feedops/api/main.py` (Google Ads auth via env vars)
- GCP Secrets Manager (production credentials, auto-bound to Cloud Run)

**Current Mitigation:**
- No secrets committed to git (.env files in .gitignore)
- GCP Secrets Manager ensures production isolation
- Local dev requires manual .env setup

**Recommendation:**
- Document all required secrets in `SECRETS.md` (what keys, where they come from)
- Add pre-commit hook to catch .env commits
- Implement secret rotation schedule for GCP secrets

---

### Service Account Key Parsing Without Validation

**Risk:** Service account JSON parsing assumes correct structure without schema validation.

**Files:** `dashboard/src/app/api/health/route.ts` (lines 131-139)

**Impact:** Malformed or incomplete service account JSON would cause runtime error instead of validation error.

**Fix Approach:**
```typescript
const credentials = z.object({
  client_email: z.string(),
  private_key: z.string(),
  project_id: z.string()
}).parse(JSON.parse(serviceAccountJson))
```

---

### Admin/User Role Not Enforced

**Risk:** Approval and publishing endpoints have no role checks; any authenticated user can approve content or publish batches.

**Files:**
- `dashboard/src/app/api/publish/batch/route.ts`
- `dashboard/src/app/api/review/images/approve/route.ts`

**Current Mitigation:** Vercel deployment limits dashboard access; not suitable for multi-user production.

**Fix Approach:**
- Add role-based access control (RBAC) checks
- Create users table with roles (admin, reviewer, publisher)
- Enforce role checks in middleware or route handlers

**Priority:** High if multi-user production deployment planned.

---

## Performance Bottlenecks

### Large File Queries on variant_index Without Pagination

**Issue:** Queries fetch all variants for a master_sku without limit, potential memory/performance issue with large product catalogs.

**Files:** `src/feedops/api/performance_baseline.py` (lines 97-99)

**Problem:**
```python
variant_result = supabase.table("variant_index").select("gmc_offer_id")\
    .eq("master_sku", master_sku).execute()
```

No pagination; for product families with 1000+ variants, this loads entire result set into memory.

**Impact:** Slow baseline capture for high-variant products; potential OOM errors.

**Fix Approach:**
- Add pagination with `.limit(100).offset(i)` loop
- Or use streaming/generator pattern for large result sets
- Profile query performance with real SKUs

---

### Sequential Google Ads API Calls in Batch Operations

**Issue:** Performance baseline captures performance data sequentially for each master_sku instead of batching.

**Files:** `src/feedops/api/performance_baseline.py` (lines 94-143)

**Problem:**
```python
for master_sku in request.master_skus:  # Sequential loop
    # ... fetch variants ...
    # ... query Google Ads ...
```

For 100 SKUs × 2 API calls = 200 sequential calls, bottlenecked by API latency.

**Impact:** Baseline capture for 50+ SKUs takes 10-15 minutes instead of 2-3 minutes.

**Fix Approach:**
- Use `asyncio.gather()` to parallelize Google Ads queries
- Implement batch query optimization (GAQL `IN` operator for multiple offer IDs)
- Respect Google Ads rate limits (implement backoff)

---

### Synchronous Lifestyle Image Generation

**Issue:** Image generation (`/generate-images` endpoint) blocks on Gemini Imagen API without timeout or parallel processing.

**Files:** `src/feedops/pipeline/lifestyle_images.py`

**Impact:** Single image generation takes ~3 minutes; generating 10 images = 30 minutes single-threaded.

**Fix Approach:**
- Implement parallel image generation (asyncio.gather with concurrency limits)
- Add request timeout and retry logic
- Consider image batch endpoint if API supports

---

## Fragile Areas

### Finish Sentence Injection for Multi-Platform Publishing

**Issue:** Finish sentences (e.g., "2X magnification") injected differently per platform (Google vs Bing descriptions) with minimal test coverage.

**Files:**
- `src/feedops/pipeline/finish_injection.py` (896 lines)
- `src/feedops/api/hybrid_generation.py` (variant_finish_sentences integration)
- No dedicated test file for finish sentence logic

**Why Fragile:**
- Template string manipulation (find/replace) is error-prone
- Multi-platform expectations differ (Google accepts structured fields, Bing doesn't)
- Test coverage gaps for finish permutation edge cases

**Safe Modification:**
1. Add comprehensive test suite for finish injection scenarios (2X, 3X, 4X variants)
2. Use templating library (Jinja2) instead of string replace
3. Add validation that finish sentences match variant specs

---

### Google Sheets Publishing Without Schema Validation

**Issue:** Grid expansion, column mapping, and data writes to Google Sheets assume correct state without pre-check.

**Files:** `dashboard/src/lib/publishing/google-sheets.ts` (328-422 lines)

**Known Issues Fixed:**
- Grid expansion failure when adding new columns (fixed 2026-02-08)
- Offer ID case mismatch (uppercase vs lowercase - fixed 2026-02-08)
- Column mapping defaulting to hardcoded positions (fixed 2026-02-06)

**Current Risk:**
- If sheet structure changes externally, publishing fails silently
- No validation that all required columns exist before write
- No rollback if partial write fails

**Safe Modification:**
1. Add sheet structure validation before publishing
2. Check column headers exist and are at expected positions
3. Implement atomic transaction or partial rollback
4. Add dry-run mode to preview changes

---

### Supabase JSONB Parsing Without Type Safety

**Issue:** JSONB fields (quality_breakdown, item_issues) parsed with type casting `::jsonb` without schema validation.

**Files:**
- `src/feedops/db/schema.py` (JSONB handling)
- Various query files using `(column#>>'{}')::jsonb` pattern

**Impact:** Malformed JSON in database causes silent failures or runtime errors.

**Fix Approach:**
- Create Pydantic models for JSONB shape validation
- Add database constraints or triggers to validate JSON structure
- Use `json_schema_validation()` in PostgreSQL if available

---

## Scaling Limits

### Cloud Run Container Timeout on Large Batches

**Current Limit:** Cloud Run default timeout ~60-120 seconds depending on SKU complexity.

**Impact:** Batches >50 SKUs timeout; jobs fail with no error.

**Evidence:** Hybrid generation with 51 SKUs times out on Vercel (15 min max), partially succeeds on Cloud Run with threading.

**Scaling Path:**
1. Increase Cloud Run timeout configuration (max 3600 seconds)
2. Implement checkpointing to resume interrupted jobs
3. Split large batches into smaller parallel jobs
4. Move to external task queue (Pub/Sub) for unbounded jobs

---

### Database Connection Pool Saturation

**Issue:** `supabase_client.py` creates new connection per request without connection pooling.

**Files:** `src/feedops/db/supabase_client.py` (get_client pattern)

**Impact:** High-concurrency scenarios (10+ parallel Cloud Run instances) exhaust connection limits.

**Fix Approach:**
- Implement connection pooling (pgBouncer or Supabase connection pooling)
- Use connection pool across request handlers
- Monitor active connection count

---

### Google Ads API Rate Limiting Not Respected

**Issue:** Query throttling uses simple retry loops without proper rate limit detection.

**Files:** `src/feedops/integrations/google_ads_performance.py`

**Impact:** Batch operations trigger rate limiting, causing exponential backoff and cascading failures.

**Fix Approach:**
- Parse Google Ads rate limit headers (429 responses)
- Implement token bucket algorithm for request throttling
- Document API quotas and batch size limits

---

## Dependencies at Risk

### FastAPI BackgroundTasks Cloud Run Incompatibility

**Status:** Partially mitigated with threading (2026-02-08), but still has known limits.

**Risk:** Background jobs fail during container deployments; no recovery mechanism.

**Migration Path:**
1. Short-term: Accept job interruption risk, document in UI
2. Long-term: Migrate to Google Cloud Tasks or Pub/Sub for reliable async jobs

**Files:** `src/feedops/api/main.py` (run_async_in_thread pattern)

---

### bingads Package Version Pinned to 13.0.x

**Issue:** bingads 14.0 released but package conflict with project dependencies.

**Files:** `pyproject.toml` (bingads==13.0.x)

**Impact:** Security patches and features in 14.0 unavailable; maintenance burden increases over time.

**Fix Approach:**
- Test compatibility with bingads 14.0
- Update if compatible, or document version constraint reason

---

### Google Sheets Python Client Permissions Fragility

**Issue:** Google Sheets API auth uses service account with hardcoded scopes; any permission change breaks publishing.

**Files:** `src/feedops/integrations/google_sheets.py` (scopes hardcoded)

**Impact:** If Google Workspace admin removes service account access, publishing fails with auth error.

**Fix Approach:**
- Monitor service account permissions regularly
- Document required IAM roles and scopes
- Add health check for Google Sheets connectivity

---

## Test Coverage Gaps

### No Integration Tests for Multi-SKU Performance Matching

**What's not tested:** End-to-end baseline capture for multi-SKU products (DMF-2/2X family).

**Files:** `tests/` (no performance_baseline integration tests)

**Risk:** Query logic changes could silently reintroduce 0.3% match rate bug.

**Priority:** High - critical to system stability.

---

### Finish Sentence Injection Edge Cases Untested

**What's not tested:**
- Variants with multiple finish names in same sentence
- Finish names containing special characters
- Empty finish list scenarios
- Mismatched variant/finish combinations

**Files:** `src/feedops/pipeline/finish_injection.py` (896 lines, minimal test coverage)

**Risk:** Production publishing breaks with unexpected SKU/finish combinations.

**Priority:** High - impacts all variant publishing.

---

### Google Sheets Publishing Atomic Transaction Coverage Missing

**What's not tested:**
- Partial failure scenarios (grid expanded, but header write fails)
- Rollback behavior when data write fails mid-batch
- Concurrent publish batch operations to same sheet

**Files:** `dashboard/src/lib/publishing/google-sheets.ts`

**Risk:** Sheet corruption if write fails mid-operation; no rollback mechanism.

**Priority:** High - data integrity risk.

---

### Cloud Run Background Job Resumption Not Tested

**What's not tested:**
- Job resumption after container restart
- Status persistence during deployment
- Partial completion rollback scenarios

**Files:** `src/feedops/api/main.py` (background job implementation)

**Risk:** Stuck jobs with stale status; no visibility into failure.

**Priority:** Medium - partial mitigation exists with threading.

---

### Performance Baseline Query Validation Missing

**What's not tested:**
- Empty result set handling (SKU not in Google Ads)
- Multi-SKU product matching (product_id-based)
- Case sensitivity of offer IDs
- Campaign type filtering correctness

**Files:** `tests/api/test_performance_baseline.py` (if exists, likely minimal)

**Risk:** Silent failures; 0.3% match rate recurrence if query changes.

**Priority:** High - critical to feature stability.

---

## Missing Critical Features

### Job Queue Persistence for Batch Operations

**Problem:** Batch generation jobs stored in memory; lost on container restart.

**Impact:** Cannot resume interrupted batches; must restart from scratch.

**Blocking:** Low - workaround is user re-submit.

---

### Search Query Deduplication Not Implemented

**Problem:** Multiple uploads of same search query create duplicates in `search_queries` table.

**Files:** `src/feedops/api/search_insights.py` (sync endpoint)

**Impact:** Query analytics inflated; duplicate data in reports.

**Fix Approach:** Add unique constraint or dedup logic before insert.

---

### Variant Lifestyle Image Deduplication

**Problem:** Same image URL can exist in both `product_lifestyle_images` and `variant_lifestyle_images` tables.

**Files:** `dashboard/src/components/sku-review/page.tsx` (dedup by URL)

**Current Mitigation:** Dashboard deduplicates by image_url (prefer variant records).

**Fix Approach:** Add database unique constraint or cleanup job to remove exact duplicates.

---

---

*Concerns audit: 2026-02-11*
