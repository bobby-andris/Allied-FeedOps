# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Transform low-performing product feeds into high-converting assets by combining real search query data with AI content generation
**Current focus:** Phase 6 - Data Collection Pipeline (v1.0 milestone)

## Current Position

Phase: 3 of 4 (Data Quality & Validation)
Plan: 2 of 4
Status: In progress
Last activity: 2026-02-13 — Completed 07-02-PLAN.md (multi-SKU detection and contamination prevention)

Progress: [███████░░░] 65% (2.5/4 phases complete in v1.0 milestone)

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
- Total plans completed: 9
- Average duration: 3.5 minutes
- Total execution time: 30.8 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 5 Job Infrastructure & Foundation | 4 | 13.3 min | 3.3 min |
| 6 Data Collection Pipeline | 3 | 11.4 min | 3.8 min |
| 7 Data Quality & Validation | 2 | 6.2 min | 3.1 min |

*Updated after each plan completion*

## Accumulated Context

### Decisions

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

### Pending Todos

None yet. Will populate during v1.0 execution.

### Blockers/Concerns

None. Phase 0 issued GO recommendation with 4.65/5 confidence.

**Validation needed during Phase 1:**
- Confirm rate limiting works at scale (100+ SKU test)
- Verify connection pooling prevents exhaustion with 3 concurrent jobs
- Test checkpoint recovery with actual Cloud Run container restart

## Session Continuity

Last session: 2026-02-13 — Phase 7 plan execution
Stopped at: Completed 07-02-PLAN.md (multi-SKU detection and contamination prevention)
Resume file: None

---
*Next step:* Continue Phase 7 - Execute 07-03-PLAN.md (validation testing)
