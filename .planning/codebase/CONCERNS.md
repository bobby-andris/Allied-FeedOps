# Codebase Concerns

**Analysis Date:** 2026-02-20

## Tech Debt

### TypeScript Type Duplication (HIGH IMPACT)
**Files:**
- `dashboard/src/components/review/SkuReviewClient.tsx`
- `dashboard/src/app/(dashboard)/review/page.tsx`
- `dashboard/src/lib/supabase/types.ts`
- `dashboard/src/lib/supabase/queries.ts`

**Issue:** Multiple interface definitions duplicated across files:
- `ContentRecord` interface defined in page.tsx AND SkuReviewClient.tsx (must stay in sync manually)
- `PerformanceBaseline` / `PerformanceSnapshot` types duplicated across files with incomplete nullable field definitions
- Inconsistencies when one copy is updated without updating others

**Impact:** Hard to maintain. Type changes require finding and updating 3+ locations. Missing fields cause runtime errors.

**Fix approach:**
- Consolidate all shared types to `dashboard/src/lib/supabase/types.ts`
- Re-export from components that need them
- Add TypeScript strict mode validation

---

### SkuReviewClient Component Variants (MEDIUM COMPLEXITY)
**Files:**
- `dashboard/src/components/review/SkuReviewClient.tsx` (628 lines)
- `dashboard/src/components/review/SkuReviewClient.magazine.tsx` (696 lines)
- `dashboard/src/components/review/SkuReviewClient.original.tsx` (746 lines)

**Issue:** Three parallel implementations of same component. Each variant:
- Uses different subsets of imports (must `grep` before cleanup)
- Requires prop changes in all 3 locations
- Has slightly different rendering logic that could diverge
- Makes it hard to know which version is authoritative

**Impact:** Changes are 3x slower to implement. Bug fixes must be replicated. Code maintenance risk.

**Fix approach:**
- Extract common logic to shared module
- Use feature flags/props to control rendering differences
- Single source of truth for component

---

### TypeScript Prompt Reference Legacy Code (MEDIUM)
**Files:**
- `dashboard/src/lib/regeneration/prompts.ts`
- `dashboard/src/lib/regeneration/core.ts`

**Issue:** Contains legacy prompt logic that's NOT runtime source-of-truth. Python pipeline in `src/feedops/pipeline/prompts.py` is the actual authority. TypeScript code exists for reference only but is easily confused with active code.

**Impact:** New developers may update TypeScript prompts thinking they affect content generation. They don't—only Python changes matter.

**Fix approach:**
- Add prominent comments: "REFERENCE ONLY - DO NOT EDIT"
- Move to separate `legacy/` or `reference/` directory
- Document Python as source-of-truth in CLAUDE.md (already done, but needs enforcement)

---

## Known Bugs

### Batch Publishing Status Never Updates (CRITICAL)
**Files:**
- `dashboard/src/app/api/publish/batch/route.ts` (1217 lines)

**Issue:** Final `UPDATE publish_batches SET status = 'published'` fails silently. Batch remains stuck in "executing" status indefinitely even after all content is published to Google Sheets and Shopify.

**Symptoms:**
- Batch shows green checkmarks (all SKUs published)
- Status stays "executing" instead of "published"
- No error logs appear
- Happens after long-running Google Sheets + Shopify operations

**Root cause:** Status update happens at the very end, after timeout-prone external API calls. Likely exceeds serverless function timeout (15 min for Vercel).

**Files affected:**
- `dashboard/src/app/api/publish/batch/route.ts` - Line ~1100 region where status update happens
- `dashboard/src/lib/batches/reconciliation.ts` - Status enum logic

**Workaround:** Manually update via Supabase:
```sql
UPDATE publish_batches SET status = 'published' WHERE batch_id = 'batch-id'
```

**Fix approach:**
- Move status update BEFORE long-running operations, or
- Use background task to finalize status after retry delay, or
- Implement database trigger to auto-finalize when all SKU assignments succeed

---

### Multi-SKU Product Query Logic Vulnerability (HIGH)
**Files:**
- `src/feedops/integrations/google_ads_performance.py`
- `src/feedops/api/performance_baseline.py`

**Issue:** Query logic is too specific for master_sku when Google Ads returns data at product_id level. This was the root cause of "0.3% match rate" bug in 2026-02-08.

**Details:**
- Multiple master SKUs share same product_id (e.g., DMF-2/2X, DMF-2/3X, DMF-2/4X all share product_id 4539975336068)
- Google Ads aggregates at product_id level
- Query requests variants for DMF-2/2X only, but Google returns DMF-2/5X variant (higher impressions)
- Code rejects match because variant_id doesn't match

**Impact:** Missing 95%+ of performance data for multi-SKU products.

**Vulnerable SKU families:**
- DMF-2 family (2X, 3X, 4X, 5X)
- Others potentially undiscovered

**Fix approach:**
- Extract product_id from offer_id
- Accept ANY variant with matching product_id (not just master_sku-specific variants)
- See: `docs/architecture/multi-sku-pattern.md` for detailed solution

---

### Background Task Failures on Deployments (HIGH)
**Files:**
- `src/feedops/api/main.py` (lines 175-201: `run_async_in_thread`)
- `src/feedops/api/backfill.py`

**Issue:** Background jobs using `run_async_in_thread()` die silently when Cloud Run deploys new container revision. Old container's background thread is killed by SIGTERM, new container doesn't resume the job.

**Documented failure:**
- Job `3da77cd6`: Backfill stuck at 100/2784 SKUs after deployment
- Latest: Job `3da77cd6` killed entirely on 2026-02-20

**Impact:**
- Long-running backfill jobs never complete
- No error indication to user (job status stays "running")
- Manual database cleanup required to reset

**Current status:** KNOWN LIMITATION documented in CLAUDE.md. Not a code bug, but architectural limitation of Cloud Run + FastAPI pattern.

**Fix approach (future):**
- Implement external task queue (Cloud Tasks, Pub/Sub, or Celery)
- Add checkpoint recovery on startup (in-progress)
- Use durable execution pattern with database-backed state

---

### Google Sheets Grid Expansion Race Condition (MEDIUM)
**Files:**
- `dashboard/src/lib/publishing/google-sheets.ts` (817 lines)

**Issue:** When adding new columns (structured_title, lifestyle_image_link), code checks grid size but doesn't lock against concurrent requests. If two publish operations hit simultaneously:
1. Operation A checks grid: needs expansion
2. Operation B checks grid: needs expansion (both see same state)
3. Both try to appendDimension → potential sheet corruption

**Impact:** Rare but possible data corruption if batches publish in parallel.

**Fix approach:**
- Add advisory lock before appendDimension
- Or: Use transactional batchUpdate for all sheet modifications

---

## Security Considerations

### Google Service Account Key in Environment (ACCEPTED RISK)
**Files:**
- `dashboard/src/lib/publishing/google-sheets.ts` (lines 37-78)
- `dashboard/src/app/api/publish/batch/route.ts` (uses credentials)

**Issue:** Google service account credentials stored in base64-encoded GOOGLE_SERVICE_ACCOUNT_KEY environment variable. If leaked, attacker gains full access to Google Sheets and Drive.

**Mitigation in place:**
- Credentials live in GCP Secret Manager (not checked into git)
- Accessed only at runtime by Vercel
- .env files in .gitignore
- CRITICAL: Never echo/log the actual credentials

**Risk level:** LOW if secrets remain in GCP, HIGH if ever exposed.

**Recommendations:**
- Rotate service account keys quarterly
- Monitor GCP audit logs for unauthorized access
- Consider Workload Identity Federation for Vercel (advanced option)

---

### Shopify Access Token in Environment (ACCEPTED RISK)
**Files:**
- `dashboard/src/lib/publishing/shopify.ts`
- `dashboard/src/lib/publishing/shopify-images.ts`

**Issue:** Shopify store access token in SHOPIFY_ACCESS_TOKEN env var enables full store modifications.

**Mitigation:**
- Stored in Vercel secrets
- Access token has minimal required scopes
- Rotated after any incident

---

### No Rate Limiting on API Routes (LOW RISK)
**Files:**
- `dashboard/src/app/api/regenerate/route.ts`
- `dashboard/src/app/api/sku-selection/generate-hybrid/route.ts`
- `dashboard/src/app/api/publish/batch/route.ts`

**Issue:** No per-user or per-IP rate limiting. A malicious user with dashboard access could:
- Spam regeneration requests (costs OpenAI credits)
- Trigger hundreds of batch publishes (spams Google Sheets/Shopify)

**Impact:** Cost abuse possible, but requires dashboard authentication first.

**Fix approach:**
- Add Redis rate limiter (Upstash compatible with Vercel)
- Implement per-user request quotas
- Log abnormal request patterns

---

## Performance Bottlenecks

### Large File Uploads Without Chunking (MEDIUM)
**Files:**
- `src/feedops/pipeline/lifestyle_images.py` (1990 lines)

**Issue:** Lifestyle image generation and uploads happen synchronously in single requests. Generating images for 100 SKUs:
- Takes ~3 minutes per SKU
- Ties up Cloud Run container for 5+ hours
- No progress reporting to user
- Single failure kills entire batch

**Impact:** Cannot scale beyond ~20 SKUs per request. Backfill jobs timeout.

**Current workaround:** Background tasks with checkpointing (but limited by deployment interruptions).

**Fix approach:**
- Implement chunked image generation (10 SKUs per background job)
- Add progress webhooks to dashboard
- Use Cloud Tasks for reliable distributed processing

---

### Google Ads Query Chunking with ThreadPoolExecutor (ACCEPTABLE)
**Files:**
- `src/feedops/integrations/google_ads_performance.py` (lines 370-440)

**Issue:** Chunks offer IDs into groups of 25 and runs parallel queries with ThreadPoolExecutor(5 workers). Rate limiting depends on Google Ads API quotas.

**Impact:** Works for backfills up to ~2,500 SKUs. May exceed API quotas for larger operations.

**Fix approach:** Monitor error rates in production. If quota exceeded, reduce worker count or add exponential backoff.

---

### Dashboard Build Time Not Optimized (LOW)
**Files:**
- All of `dashboard/src`

**Issue:** `npm run build` takes ~45-60 seconds locally. Large bundle from 54K+ lines of TypeScript.

**Impact:** Slow local development iteration. Vercel deploys take longer.

**Fix approach:**
- Profile bundle (npx bundle-analyzer)
- Code-split large components (SkuReviewClient variants, review dashboards)
- Lazy-load non-critical routes

---

## Fragile Areas

### Variant Expansion Logic (CRITICAL DEPENDENCY)
**Files:**
- `dashboard/src/lib/publishing/expand-variants.ts`

**Issue:** Core business logic that expands master SKU variants into platform-specific finishes. The function `expandVariantsForPublish()` is:
- 400+ lines of intricate logic
- No comprehensive test coverage
- Depends on exact variant naming patterns (e.g., `{FINISH_NAME}` placeholder)
- Used by both Google Sheets and Shopify publishing

**Risk:** Single bug here breaks publishing for ALL products. Example: Off-by-one error in finish expansion = wrong finish names on 100+ products in GMC.

**Safe modification:**
- Add integration tests for each product family BEFORE changing
- Use snapshot testing to detect variant count changes
- Document finish placeholder contract clearly

**Test coverage gaps:**
- Multi-SKU families not tested
- Variant count validation missing
- Edge cases (very large finish lists) untested

---

### Publishing Event Snapshot Logic (MEDIUM)
**Files:**
- `dashboard/src/lib/publishing/final-payload.ts`
- `dashboard/src/app/api/publish/batch/route.ts`

**Issue:** Builds final payload snapshots for `publish_events` table to enable rollback. Logic involves:
- Hashing prompt + content combinations
- Tracking lineage through generation pipeline
- Deduplicating identical variants

**Fragility:**
- Hash algorithm changes break historical comparisons
- Missing fields in snapshot = can't rollback properly
- Multi-platform content interleaving complex

**Safe modification:**
- Never change hash algorithm (creates version mismatch)
- Add all newly tracked fields to schema FIRST, then use them
- Write unit tests before modifying snapshot builder

---

### Google Sheets Column Mapping (MEDIUM)
**Files:**
- `dashboard/src/lib/publishing/google-sheets.ts` (lines 155-250)

**Issue:** `buildColumnMap()` dynamically detects column positions from sheet headers. If sheet layout changes unexpectedly:
- Wrong columns get updated
- Data corruption possible
- No validation that expected columns exist

**Recent bug (fixed 2026-02-06):** Code used hardcoded DEFAULT_COLUMN_MAP without verifying sheet headers, wrote to wrong columns.

**Safe modification:**
- Always verify actual sheet headers before any write
- Validate that `structured_title`, `lifestyle_image_link` exist at expected positions
- Add pre-flight check that fails loudly if columns missing

---

### Batch Status State Machine (MEDIUM)
**Files:**
- `dashboard/src/app/api/publish/batch/route.ts`
- `dashboard/src/lib/batches/reconciliation.ts`
- `dashboard/src/lib/supabase/types.ts`

**Issue:** Batch status flow is implicit:
```
draft → pending → executing → [published | partial | failed]
```

But code has multiple places checking status:
- `normalizeBatchStatus()` in route.ts
- Reconciliation logic in reconciliation.ts
- UI checks in BatchesClient.tsx

**Risk:** Inconsistent status handling if flow changes. Example: If new status added, must update 5+ locations or batches get stuck.

**Safe modification:**
- Extract status enum and valid transitions to single location
- Add exhaustive switch statements (TypeScript strict mode)
- Document state transition rules explicitly

---

## Scaling Limits

### Content Generation Throughput (KNOWN LIMITATION)
**Constraint:** Cloud Run instance can handle ~1 content generation request at a time.

**Numbers:**
- Single SKU: ~3 minutes (OpenAI + Gemini)
- Batch of 10: ~30 minutes
- Batch of 100: ~300+ minutes (5+ hours)
- Multiple concurrent requests queue up, not parallel

**Scaling approach:**
- Current: Batch jobs in background threads (limited by container lifecycle)
- Future: Distributed queue (Cloud Tasks) with multiple worker containers
- Cost: OpenAI + Gemini API usage scales linearly with SKU count

---

### Database Connection Pool (MONITORED)
**File:**
- `src/feedops/db/supabase_client.py` (lines 32-68)

**Issue:** Supabase client uses single connection with 3-retry pattern. Under high concurrent load (100+ simultaneous backfill operations), connection pool can saturate.

**Current status:** Functional for current scale (< 50 concurrent users). Not tested at 100+ concurrent operations.

**Monitoring:** Watch Cloud Run logs for "Connection reset" or "Too many connections" errors.

**Fix approach:** Implement connection pooling if bottleneck appears.

---

### Google Sheets API Quota (THEORETICAL RISK)
**Numbers:** Google Sheets API allows 60,000 requests/minute per project.

**Current usage:** ~10-20 requests per publish batch. Publishing 100 batches/day = ~2,000 requests. Well below quota.

**Scaling limit:** Could hit quota if publishing 1,000+ batches daily. Unlikely at current scale.

**Monitoring:** Implement quota monitoring (GCP Cloud Monitoring).

---

## Test Coverage Gaps

### Publishing Route Integration Tests Missing (HIGH)
**Files:**
- `dashboard/src/app/api/publish/batch/route.ts` - 1217 lines, NO TESTS
- `dashboard/src/app/api/publish/sku/route.ts` - 912 lines, NO TESTS

**What's NOT tested:**
- Full publish flow (content → Google Sheets → Shopify)
- Error handling (what happens if Shopify upload fails mid-batch?)
- Idempotency (publishing same batch twice)
- Variant expansion correctness
- Status transitions

**Risk:** Publishing bugs only caught in production.

**Priority:** Add integration tests before adding new publishing features.

---

### Performance Impact Calculation Tests Missing (MEDIUM)
**Files:**
- `src/feedops/monitoring/performance_impact.py`
- Tests: `tests/test_performance_impact.py` (exists but incomplete)

**What's NOT tested:**
- Edge cases (0 baseline impressions, negative deltas)
- Multi-month attribution windows
- Concurrent performance updates
- Database upsert race conditions

---

### Google Sheets Concurrent Write Tests Missing (MEDIUM)
**Files:**
- `dashboard/src/lib/publishing/google-sheets.ts` - NO CONCURRENT WRITE TESTS

**What's NOT tested:**
- Two batch operations updating different columns simultaneously
- Column expansion while writes in progress
- Sheet lock timeout handling

---

## Dependencies at Risk

### OpenAI API Provider (MEDIUM RISK)
**File:**
- `src/feedops/providers/openai_provider.py`

**Risk:** Dependency on OpenAI for content generation. If API becomes unavailable or pricing changes significantly, entire regeneration pipeline blocked.

**Mitigation:**
- Alternative: Could fall back to Gemini (already used for images)
- Cost monitoring in place
- Rate limiting to prevent runaway costs

**Monitoring:** Watch for API errors in logs. Alert on >5% error rate.

---

### Google Ads API Stability (LOW RISK)
**File:**
- `src/feedops/integrations/google_ads_performance.py`

**Risk:** Google Ads Python client (bingads v13.0) pins to older version. Updates rare, but breakage possible on Google API changes.

**Mitigation:**
- Test Google Ads queries regularly (backfill jobs do this)
- Monitor query response formats for changes

---

### Shopify API Webhooks (MEDIUM RISK)
**File:**
- Not implemented. Lifestyle images pushed directly to Shopify.

**Issue:** No webhook validation. If Shopify image upload endpoint changes, CDN migration silently fails.

**Mitigation:** Monitor Shopify GraphQL errors in Cloud Run logs.

---

## Missing Critical Features

### No Automatic Job Recovery on Deployment (HIGH IMPACT)
**Issue:** Background jobs die silently on Cloud Run deployments. No auto-resume.

**Affects:**
- Backfill jobs (stuck at 100/2784)
- Batch image generation (incomplete uploads)
- Search term syncing (partial syncs)

**Workaround:** Manual restart via dashboard or curl.

**Fix approach:**
- Add job checkpoint recovery on startup
- Implement persistent queue (Cloud Tasks)

---

### No Rate Limiting on Public Endpoints (LOW IMPACT)
**Issue:** No per-user or per-IP rate limiting on API routes.

**Risk:** Cost abuse if dashboard compromised.

**Fix approach:** Add Upstash Redis rate limiter.

---

### No Async Job Progress Reporting (MEDIUM IMPACT)
**Issue:** Users can't see real-time progress of long-running jobs. Only poll for final status.

**Affects:** Batch generation, image generation, backfill operations.

**Fix approach:**
- Implement Server-Sent Events (SSE) for progress updates
- Or: WebSocket connection for real-time status

---

### No Scheduled Maintenance Jobs (MEDIUM)
**Issue:** No automatic cleanup of:
- Stale job records (backfill_jobs from weeks ago)
- Orphaned search_query_snapshots
- Old publish_events (audit log grows unbounded)

**Impact:** Database bloat over time. Manual cleanup currently required.

**Fix approach:** Add Cloud Scheduler jobs for daily cleanup tasks.

---

## Database Schema Issues

### Inconsistent Column Naming Across Tables (LOW)
**Issue:** Some tables use `created_at`, some use `created` (see variant_lifestyle_images vs product_lifestyle_images).

**Impact:** Query confusion, potential typos. Not critical since migrations are already deployed, but indicates schema evolution without convention enforcement.

**Recommendation:** Document column naming convention in SCHEMA.md. Future migrations should follow pattern.

---

### JSONB Parsing Complexity (ACCEPTED TRADEOFF)
**Files:**
- `src/feedops/db/supabase_client.py`
- Multiple query files

**Issue:** JSONB columns require manual parsing with `(column#>>'{}')::jsonb` before operations. Error-prone.

**Mitigation:** Schema documentation (SCHEMA.md) covers patterns. Well-tested in existing queries.

**Acceptable:** This is cost of flexible JSONB storage. Alternative would be normalized tables (more rigid).

---

## Logging & Observability Gaps

### Missing Request-Level Tracing (MEDIUM)
**Files:**
- `src/feedops/api/main.py` (has request_id context but not fully utilized)

**Issue:** Not all logs tagged with request_id. Hard to trace single request through multi-component system.

**Fix approach:**
- Ensure request_id attached to EVERY log in request path
- Propagate to background jobs
- Export to Datadog or similar

---

### Missing Cloud Run Metrics for Job Duration (MEDIUM)
**Issue:** No automated alerts for jobs exceeding expected duration.

**Example:** Backfill job stuck for 4+ hours with no alert.

**Fix approach:**
- Add Prometheus metrics for job start/end times
- Cloud Monitoring alert if job_duration > 2x expected

---

### Silent Failures in Background Tasks (HIGH)
**Files:**
- `src/feedops/api/main.py` (lines 175-201)
- `src/feedops/api/backfill.py`

**Issue:** When background thread dies, no alert or error logging. Job status stuck in "running" forever.

**Example:** Job `3da77cd6` (backfill) stuck at 100/2784 for 4+ hours with no indication of failure.

**Fix approach:**
- Add timeout monitoring for background jobs
- Alert if job shows no progress for > 30 minutes
- Implement automatic job failure after timeout

---

*Concerns audit: 2026-02-20*
