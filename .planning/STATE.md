# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation
**Current focus:** v1.0 milestone complete — Production observability and automation operational

## Current Position

Phase: 8 of 8 (Monitoring & Automation)
Plan: 5 of 5
Status: Complete
Last activity: 2026-02-13 — Completed Phase 8 Plan 5 (monitoring endpoint gap closure)

Progress: [██████████] 100% (v1.0 milestone complete - 16/16 plans)

## Performance Metrics

**Phase 0 Velocity (Discovery Milestone):**
- Total plans completed: 11
- Average duration: 3.3 minutes
- Total execution time: 0.63 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 0.1 API Capability Validation | 2 | 9 min | 4.5 min |
| 0.2 Comprehensive Data Discovery | 4 | 11 min | 2.75 min |
| 0.3 Sample Testing & Analysis | 3 | 14 min | 4.7 min |
| 0.4 Documentation & Decision | 2 | 8 min | 4.0 min |

**v1.0 Velocity:**
- Total plans completed: 16
- Average duration: 3.1 minutes
- Total execution time: 49.5 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 5 Job Infrastructure & Foundation | 4 | 13.3 min | 3.3 min |
| 6 Data Collection Pipeline | 3 | 11.4 min | 3.8 min |
| 7 Data Quality & Validation | 4 | 10.4 min | 2.6 min |
| 8 Monitoring & Automation | 5 | 14.5 min | 2.9 min |

*Updated after each plan completion*
| Phase 08 P04 | 5 | 2 tasks | 1 file |
| Phase 08 P05 | 2 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

**Phase 8 (Monitoring & Automation):**

1. **SQL Aggregation for Stale Detection** (Plan 08-02)
   - Use SQL aggregation with MAX() over timestamps rather than per-SKU loops
   - Single query per data source with Python-side grouping
   - Impact: Efficient at scale - O(n) complexity for full catalog stale detection

2. **Fire-and-Forget Notification Pattern** (Plan 08-02)
   - All notification calls wrapped in try/except, never raise exceptions
   - Graceful degradation when env vars not configured (logs warning, returns False)
   - Impact: Notification failures never affect job processing reliability

3. **Incremental Mode Auto-Detection** (Plan 08-02)
   - Allow empty SKU list when config.mode='incremental', auto-detect stale SKUs
   - Alternative: Always require SKU list or separate endpoint
   - Impact: Enables Cloud Scheduler to POST minimal payload for daily sync automation

4. **OIDC Authentication for Cloud Scheduler** (Plan 08-04)
   - Use existing profit-pilot-runtime service account with OIDC tokens for Cloud Scheduler HTTP jobs
   - Alternative: Create separate scheduler service account or use API keys
   - Impact: Secure Cloud Run invocation without managing API keys, leverages existing IAM setup

5. **Slack-Only Notifications** (Plan 08-04)
   - Configure Slack webhook directly on Cloud Run env var, skip email notifications (optional)
   - Alternative: Use Cloud Monitoring alert policies or configure both Slack and email
   - Impact: Simpler setup, notification logic already in Python app from Plan 08-02

6. **Daily 2am PT Schedule** (Plan 08-04)
   - Cloud Scheduler runs incremental refresh at 2:00 AM Pacific Time daily
   - Alternative: Run at different time or multiple times per day
   - Impact: Minimizes impact on business hours, allows overnight processing of previous day's data

7. **Direct Table Queries Over RPC** (Plan 08-05)
   - Replace all execute_sql RPC calls with direct supabase.table() queries
   - RPC returns JSONB (single JSON value), not list-of-dicts like table queries
   - Impact: Reliable data structure handling, no RPC wrapping surprises

8. **Python-Side Aggregation for Coverage** (Plan 08-05)
   - Use len(set(...)) instead of SQL COUNT(DISTINCT ...) for coverage calculations
   - Simpler code, no RPC complexity, minimal performance difference for ~2,800 SKU catalog
   - Impact: Clearer code, easier to debug

**Phase 7 (Data Quality & Validation):**

1. **Type Coercion Enabled in Pydantic Models** (Plan 07-01)
   - ConfigDict(strict=False) allows API responses with numeric types to be coerced
   - Prevents validation failures on valid data with minor type mismatches (100 vs 100.0)
   - Impact: More robust validation accepts both int and float for numeric fields

2. **Validation Errors as Item-Level Status** (Plan 07-01)
   - Invalid records produce 'validation_error' status (not batch-level exceptions)
   - Allows batch processing to continue when one item fails validation
   - Impact: Resilient batch processing - one bad record doesn't block entire batch

3. **Light Validation for Supplementary Data** (Plan 07-01)
   - Keyword Planner and Custom Labels use non-blocking validation (warnings only)
   - Core metrics (performance, search terms) strictly enforce constraints
   - Impact: Critical data quality enforced, supplementary data logs warnings

4. **Multi-SKU Metadata in JSONB Column** (Plan 07-02)
   - Flexible metadata storage without schema changes for future validation flags
   - Alternative: Separate table or boolean columns
   - Impact: JSONB metadata column supports arbitrary validation metadata

5. **Batch Eligibility Check Before Data Fetch** (Plan 07-02)
   - Contamination check before API calls prevents wasted quota on ineligible SKUs
   - Alternative: Check during upsert or separate pre-validation step
   - Impact: More efficient - filters before expensive API operations

6. **30-Day Contamination Threshold** (Plan 07-02)
   - SKUs published within 30 days are ineligible for baseline capture
   - Alternative: 14 days or 60 days
   - Impact: Ensures sufficient separation between baseline and post-publish periods (configurable)

7. **Scipy as Optional Dependency** (Plan 07-03)
   - Outlier detection requires scipy for Z-score calculation, but system degrades gracefully without it
   - Alternative: Make scipy required or implement custom Z-score calculation
   - Impact: Outlier detection unavailable without scipy, but core validation functions work

8. **Direct DB Queries for Freshness** (Plan 07-03)
   - Use Supabase queries directly rather than RPC functions for flexibility
   - Alternative: Create RPC functions for counting or use materialized views
   - Impact: More flexible, no schema migrations needed, slightly less efficient but acceptable

**Phase 6 (Data Collection Pipeline):**

1. **GMC Data Caching Strategy** (Plan 06-01)
   - Module-level cache with 5-minute TTL avoids redundant API calls across consecutive batches
   - GMC API returns all products at once (expensive call)
   - Impact: Significant API cost reduction for large backfill jobs

2. **Search Terms Filtering Approach** (Plan 06-01)
   - Worker filters results after fetch (client is batch-native with campaign-join pattern)
   - Client handles campaign-join, worker handles batch filtering
   - Impact: Clean separation of concerns, preserves existing client API

3. **Full Backfill as Composite Worker** (Plan 06-02)
   - Single processor runs all 4 collection types sequentially (not 4 separate jobs)
   - Composite worker calls individual workers in dependency order
   - Impact: Simpler implementation, clearer checkpoint/resume semantics

**Phase 5 (Job Infrastructure):**

1. **JSONB for SKU Lists and Checkpoint Data** (Plan 05-01)
   - Store SKU arrays and checkpoint state as JSONB (not separate table or TEXT arrays)
   - Enables flexible checkpoint state without schema changes
   - Impact: Simplified schema, supports arbitrary checkpoint complexity

2. **RPC Function for Atomic Failure Increment** (Plan 05-01)
   - increment_backfill_failures() prevents race conditions during concurrent error logging
   - Guarantees accurate failed_items count under concurrent writes
   - Impact: Reliable failure tracking in multi-threaded job processing

3. **ETA Calculation in Python Manager** (Plan 05-01)
   - Rate-based ETA calculated in manager.py (not SQL triggers)
   - Centralized logic easier to test and modify
   - Impact: Requires passing started_at_epoch from caller

4. **Thread-Safe Rate Limiting with threading.Lock** (Plan 05-02)
   - TokenBucket uses threading.Lock (not asyncio.Lock) for process-wide thread safety
   - Multiple async tasks in same process can safely share token buckets
   - Impact: Prevents race conditions in multi-task concurrent job execution

2. **Dynamic Imports for Parallel Execution** (Plan 05-02)
   - BatchProcessor imports job manager functions inside run() method (not module-level)
   - Avoids circular import errors during Wave 1 parallel plan execution
   - Impact: 05-01 and 05-02 can execute simultaneously without dependency issues

3. **95% Success Threshold for Job Completion** (Plan 05-02)
   - Jobs marked 'complete' if ≥95% of items succeed (some failures acceptable)
   - Aligned with VALID-08 requirement
   - Impact: Resilient to transient failures without blocking overall progress

4. **Placeholder _noop_process for Phase 1** (Plan 05-03) - REPLACED in 06-02
   - Backfill endpoints used placeholder process function for Phase 1 testing
   - Replaced with job-type routing in Plan 06-02
   - Impact: Endpoints now route to real collection workers

5. **Job Validation in Resume Endpoint** (Plan 05-03)
   - Resume endpoint validates job status (only 'failed' or 'partial' can resume)
   - Prevents accidental duplicate processing of completed jobs
   - Impact: Clear contract for callers, safety against state errors

6. **Fix Processor Async/Sync Mismatch** (Plan 05-04)
   - Processor was calling sync manager functions with await
   - Fixed to call manager functions directly (not async)
   - Impact: Processor now works correctly with manager layer

7. **Idempotent Upsert Contract Test** (Plan 05-04)
   - Test validates and documents JOB-06 requirement for Phase 2
   - Proves upsert pattern prevents duplicates during checkpoint/resume
   - Impact: Executable documentation for Phase 2 collection worker implementors

**Phase 0 (Discovery):**

Key decisions from Phase 0 (discovery) affecting v1.0 implementation:

1. **Campaign-Join Pattern Required for Search Terms** (Phase 0.1)
   - API cannot filter search_term_view by product_item_id directly
   - Must use 2-step query: shopping_performance_view → search_term_view → join in memory
   - Impact: DATA-01 requirement implementation

2. **Batch Size 10 Optimal for API Performance** (Phase 0.3)
   - Testing showed 127ms p95 per SKU with batch size 10
   - Full 2,784 SKU catalog completes in 7.1 minutes
   - Impact: DATA-06 requirement (process SKUs in batches of 10)

3. **Explicit Date Ranges Required** (Phase 0.3)
   - API rejects LAST_N_DAYS syntax
   - Must use BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD' format
   - Impact: DATA-07 requirement (explicit date ranges)

4. **Lowercase Offer IDs for API Queries** (Phase 0.1)
   - API expects shopify_us_ format (lowercase 'us')
   - Database format already correct
   - Impact: DATA-08 requirement (handle lowercase offer IDs)

5. **Keyword Planner Coverage Gap Identified** (Phase 0.4)
   - 43% of potential search volume (168K monthly) not currently captured
   - Recommendation: Run Keyword Planner for ALL SKUs, not just cold-start
   - Impact: DATA-03 requirement (Keyword Planner for all 2,784 SKUs)

6. **Multi-SKU Family Pattern Documented** (Phase 0.3)
   - Google Ads aggregates metrics by product_id (not master_sku)
   - Example: DMF-2/2X, DMF-2/3X, DMF-2/4X all share same product_id
   - Impact: VALID-03 requirement (detect multi-SKU families)

7. **Competitive Metrics Have 33% Coverage** (Phase 0.4)
   - Impression/click share only available for products with sufficient volume
   - This is acceptable - high-value SKUs are what matter
   - Impact: DATA-09 requirement (collect where available)
- [Phase 07]: Scipy as Optional Dependency - Outlier detection requires scipy, but system degrades gracefully without it
- [Phase 07]: Direct DB Queries for Freshness - Use Supabase queries directly rather than RPC functions for flexibility
- [Phase 08-01]: RPC execute_sql for freshness queries - Enables single-query freshness check for all SKUs via SQL aggregation instead of N queries
- [Phase 08-01]: Separate coverage and freshness endpoints - Dashboard can fetch coverage frequently without transferring large freshness arrays
- [Phase 08-01]: P95 calculation in Python (not database) - Faster response, no additional database load for health checks
- [Phase 08-03]: Install Tremor with --legacy-peer-deps - React 19 compatibility workaround, no runtime issues
- [Phase 08-03]: Separate polling for jobs vs. monitoring data - jobs refresh every 5s, monitoring data fetches once on mount
- [Phase 08-03]: Limit freshness heatmap to 500 SKUs - performance optimization for browser rendering

### Pending Todos

**Post-Deployment Verification (Phase 08 Plan 05):**
- Verify coverage endpoint returns valid JSON with total_skus, search_terms_coverage, performance_coverage, keywords_coverage
- Verify freshness endpoint returns valid JSON with per-SKU data age arrays
- Verify api-health endpoint returns valid JSON (precautionary check)
- Commands in 08-05-SUMMARY.md Next Phase Readiness section

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Add backfill monitoring to sidebar, check performance snapshots data, set up Cloud Scheduler for daily snapshot capture | 2026-02-18 | 758d344f | [1-add-backfill-monitoring-to-sidebar-check](.planning/quick/1-add-backfill-monitoring-to-sidebar-check/) |

### Blockers/Concerns

None. Phase 0 issued GO recommendation with 4.65/5 confidence.

**Validation needed during Phase 1:**
- Confirm rate limiting works at scale (100+ SKU test)
- Verify connection pooling prevents exhaustion with 3 concurrent jobs
- Test checkpoint recovery with actual Cloud Run container restart

## Session Continuity

Last session: 2026-02-18 — Completed quick task 1: sidebar + performance snapshots + Cloud Scheduler
Stopped at: Quick task 1 complete
Resume file: None

---
*Next step:* Phase 8 complete. Ready for Phase 9 (Full-Catalog Backfill Execution) or v1.0 milestone completion
