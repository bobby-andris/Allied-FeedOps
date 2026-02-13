# Phase 2: Data Collection Pipeline - Research

**Researched:** 2026-02-13
**Domain:** Data Collection Implementation (Google Ads API, Keyword Planner API, Merchant Center API)
**Confidence:** HIGH

## Summary

This phase implements the data collection infrastructure validated during Phase 0 (Discovery) and Phase 1 (Job Infrastructure). The core technical stack is already in place: google-ads Python client library (v24+), Supabase for storage, and a mature job management system with checkpointing/rate limiting. Key finding: All data collection patterns were validated in Phase 0 with real API testing, and Phase 1 built the job infrastructure that Phase 2 will use.

The primary challenge is NOT technical (all APIs and patterns are proven) but operational: coordinating 4 concurrent data collection streams with proper idempotency, error handling, and rate limiting to backfill 2,784 SKUs worth of data.

**Primary recommendation:** Build 4 worker functions that plug into the Phase 1 job infrastructure (BatchProcessor + TokenBucket rate limiting + checkpoint/resume). Each worker implements the collection logic validated in Phase 0, using idempotent upserts (ON CONFLICT) for all database writes.

## User Constraints

No user constraints from CONTEXT.md (file does not exist for this phase).

## Standard Stack

### Core Infrastructure (ALREADY IMPLEMENTED)

| Component | Version/Location | Purpose | Status |
|-----------|-----------------|---------|--------|
| google-ads Python client | v24+ | Google Ads API interactions | Production-ready in codebase |
| Supabase Python client | supabase-py | Database operations | Production-ready in codebase |
| BatchProcessor | `src/feedops/jobs/processor.py` | Generic batch processing with checkpointing | Tested in Phase 1 |
| TokenBucket | `src/feedops/jobs/rate_limiter.py` | Thread-safe rate limiting | Tested in Phase 1 |
| JobManager | `src/feedops/jobs/manager.py` | Job lifecycle management | Tested in Phase 1 |
| SearchTermsClient | `src/feedops/integrations/google_ads_search_terms.py` | Search terms collection | Production-ready |
| KeywordPlannerClient | `src/feedops/integrations/google_ads_search_terms.py` | Keyword Planner enrichment | Production-ready |
| PerformanceClient | `src/feedops/integrations/google_ads_performance.py` | Performance metrics collection | Production-ready |

### Database Tables (ALREADY EXIST)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| backfill_jobs | Job tracking | id, job_type, status, total_items, checkpoint_data |
| backfill_job_errors | Error logs | job_id, item_id, error_type, error_message |
| search_queries | Search terms data | query_text, gmc_offer_id, master_sku, period_start/end |
| keyword_metrics | Keyword Planner cache | keyword, avg_monthly_searches, competition, updated_at |
| performance_baselines | Pre-publish metrics | master_sku, platform, avg_impressions, avg_ctr |
| variant_index | SKU → offer ID mapping | master_sku, gmc_offer_id, finish, finish_code |

### API Credentials (ALREADY CONFIGURED)

All required secrets exist as GCP Cloud Run secrets (confirmed 2026-02-08):
- `feedops-google-ads-developer-token`
- `feedops-google-ads-client-id`
- `feedops-google-ads-client-secret`
- `feedops-google-ads-refresh-token`
- `feedops-google-ads-login-customer-id`
- `feedops-supabase-url`
- `feedops-supabase-key`

## Architecture Patterns

### Pattern 1: Job Infrastructure Integration

**What:** Each data collection endpoint creates a backfill job and spawns a BatchProcessor to execute it.

**When to use:** All 4 data collection endpoints (search terms, performance metrics, keyword planner, custom labels).

**Validated in:** Phase 1 (05-01 through 05-04)

**Example:**
```python
# Endpoint creates job
job_id = create_job(
    job_type="search_terms",
    skus=master_skus,
    config={"batch_size": 10, "days_lookback": 180}
)

# Spawn processor in background thread (survives HTTP response)
run_async_in_thread(_process_search_terms_job, job_id=job_id)

# Return job_id to client immediately
return {"job_id": job_id, "status": "running"}
```

**Worker function pattern:**
```python
async def _process_search_terms_job(job_id: str):
    """Background worker for search terms collection."""
    job = get_job(job_id)

    # Initialize processor with rate limiting
    processor = BatchProcessor(
        job_id=job_id,
        items=job.skus,
        batch_size=10,
        checkpoint_interval=100,
        rate_limiter=google_ads_limiter  # 10 QPS
    )

    # Process batches
    await processor.run(process_fn=_collect_search_terms_batch)
```

### Pattern 2: Campaign-Join for Search Terms

**What:** Use 2-step query to associate search terms with products (validated in Phase 0.1).

**Why:** Google Ads API cannot filter search_term_view by product_item_id directly.

**Validated in:** Phase 0.1 (Phase 0 discovery)

**Implementation:** Already implemented in `SearchTermsClient.fetch_search_terms()` (lines 520-621):

```python
# Step 1: Fetch products by campaign
campaign_products = self._fetch_campaign_products(days)
# Returns: {campaign_id: [offer_id1, offer_id2, ...]}

# Step 2: Fetch search terms by campaign
query = """
    SELECT search_term_view.search_term, campaign.id, metrics.*
    FROM search_term_view
    WHERE segments.date DURING LAST_N_DAYS
"""

# Step 3: Join via campaign_id
for row in results:
    campaign_id = row['campaign']['id']
    item_ids = campaign_products.get(campaign_id, [])
    # Lookup master_sku + finish via variant_index
```

**CRITICAL:** This pattern is PRODUCTION-READY and TESTED. Do NOT re-implement it.

### Pattern 3: Idempotent Upserts with ON CONFLICT

**What:** All database writes use upserts with unique constraints to handle checkpoint/resume.

**Why:** Prevents duplicate data when resuming from checkpoints (JOB-06 requirement from Phase 1).

**Validated in:** Phase 1 (05-04: idempotent contract test)

**Example:**
```python
# CORRECT: Idempotent upsert
self.supabase.table("search_queries").upsert(
    rows,
    on_conflict="query_text,gmc_offer_id,period_start,period_end",
    ignore_duplicates=False  # Update existing rows
).execute()

# WRONG: Direct insert (creates duplicates on resume)
self.supabase.table("search_queries").insert(rows).execute()
```

**Database unique constraints (already exist):**
- `search_queries`: `(query_text, gmc_offer_id, period_start, period_end)`
- `keyword_metrics`: `keyword` (primary key)
- `performance_baselines`: `(master_sku, platform)` (primary key)

### Pattern 4: Rate Limiting with TokenBucket

**What:** Use TokenBucket rate limiters for all API calls.

**When to use:** Mandatory for all Google Ads API calls.

**Validated in:** Phase 0.3 (batch size 10 testing), Phase 1 (05-02: rate limiter tests)

**Rate limits:**
- Standard Google Ads API: 10 QPS (TokenBucket: rate=10.0, capacity=20)
- Keyword Planner API: 2 QPS (TokenBucket: rate=2.0, capacity=5)

**Example:**
```python
# Pre-configured instances exist in rate_limiter.py
from feedops.jobs.rate_limiter import google_ads_limiter, keyword_planner_limiter

# Processor automatically handles rate limiting
processor = BatchProcessor(
    job_id=job_id,
    items=skus,
    rate_limiter=google_ads_limiter  # Processor calls await rate_limiter.acquire()
)
```

### Pattern 5: Background Task Survival

**What:** Use `run_async_in_thread()` helper to survive HTTP response (validated in Cloud Run).

**Why:** FastAPI BackgroundTasks are killed when containers scale to zero.

**Validated in:** 2026-02-08 background task fix (audit doc)

**Implementation:** Already exists in `src/feedops/api/main.py`:

```python
def run_async_in_thread(coro_fn, **kwargs):
    """Run async function in non-daemon thread with dedicated event loop.

    Survives HTTP response and container lifecycle (until completion or deployment).
    """
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(coro_fn(**kwargs))
        finally:
            loop.close()

    thread = threading.Thread(target=run, daemon=False)
    thread.start()
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Batch processing | Custom loops with manual checkpointing | BatchProcessor (Phase 1) | Handles checkpointing, rate limiting, progress tracking, error handling automatically |
| Rate limiting | time.sleep() between calls | TokenBucket (Phase 1) | Thread-safe, burst-aware, validated with Google Ads API |
| Job tracking | Custom status fields | JobManager functions (Phase 1) | Atomic operations, ETA calculation, error aggregation |
| Search term collection | Custom campaign-join logic | SearchTermsClient.fetch_search_terms() | Production-ready, variant-aware, tested |
| Keyword enrichment | Direct Keyword Planner calls | KeywordPlannerClient.get_historical_metrics() | 30-day caching, batch optimization |
| Performance queries | Custom GAQL queries | PerformanceClient.fetch_batch_product_performance() | Handles IN clause batching, aggregation |
| Background tasks | FastAPI BackgroundTasks | run_async_in_thread() helper | Survives container scale-to-zero |

**Key insight:** Phase 1 built a complete job infrastructure specifically for this phase. Using it is NOT optional - it's the correct architecture. Custom implementations will lack checkpointing, rate limiting, error tracking, and resumability.

## Common Pitfalls

### Pitfall 1: Forgetting Idempotent Upserts

**What goes wrong:** Worker functions use `.insert()` instead of `.upsert()` with `on_conflict`. When job resumes from checkpoint, creates duplicate rows.

**Why it happens:** Direct inserts are simpler/faster to write.

**How to avoid:**
- ALWAYS use `.upsert()` with `on_conflict` parameter matching the table's unique constraint
- Set `ignore_duplicates=False` to update existing rows instead of ignoring
- Phase 1 contract test (05-04) validates this pattern - reference it

**Warning signs:**
- Database unique constraint violations in logs
- Duplicate rows after job resume
- Test with: create job, process 1 batch, kill job, resume - should NOT create duplicates

### Pitfall 2: Rate Limiting Only First API Call in Batch

**What goes wrong:** Acquiring rate limit token BEFORE processing batch, then making MULTIPLE API calls within batch without additional rate limiting.

**Why it happens:** Misunderstanding of batch vs. API call granularity.

**How to avoid:**
- If batch processing makes N API calls, acquire N tokens OR make 1 combined API call
- Example: `fetch_batch_product_performance(batch)` makes 1 API call for entire batch - acquire 1 token
- Example: If processing each SKU individually, acquire token PER SKU

**Pattern:**
```python
# CORRECT: 1 API call for entire batch
await rate_limiter.acquire(1)
results = client.fetch_batch_product_performance(batch)  # Single IN clause query

# WRONG: N API calls without rate limiting
await rate_limiter.acquire(1)
for sku in batch:
    results.append(client.fetch_performance(sku))  # N unrated calls!

# CORRECT: Rate limit per item
for sku in batch:
    await rate_limiter.acquire(1)
    results.append(client.fetch_performance(sku))
```

### Pitfall 3: Using FastAPI BackgroundTasks for Long Jobs

**What goes wrong:** Job dies when Cloud Run container scales to zero or during deployments. No error, just silent termination.

**Why it happens:** BackgroundTasks are tied to container lifecycle.

**How to avoid:**
- ALWAYS use `run_async_in_thread()` helper (exists in `main.py`)
- Never use `background_tasks.add_task()` for data collection jobs
- This pattern is validated and documented (2026-02-08 audit)

**Warning signs:**
- Jobs stuck in "running" status forever
- No errors in logs, just stops mid-execution
- Deployments during job execution

### Pitfall 4: Lowercase vs Uppercase Offer ID Format

**What goes wrong:** Database has lowercase `shopify_us_`, but GMC/Google Sheets require uppercase `shopify_US_`. Publishing breaks.

**Why it happens:** Different systems have different conventions.

**How to avoid:**
- Database queries: Use lowercase `shopify_us_` (this is the stored format)
- When writing to Google Sheets: Transform to uppercase `shopify_US_`
- SearchTermsClient already handles this (lines 894-906)

**Pattern:**
```python
# Database query: lowercase
variant = supabase.table("variant_index").eq("gmc_offer_id", "shopify_us_123_456")

# Google Sheets write: uppercase
sheet_offer_id = variant['gmc_offer_id'].replace('shopify_us_', 'shopify_US_')
```

### Pitfall 5: Not Handling Multi-SKU Products

**What goes wrong:** Performance queries return aggregated data for product_id, but multiple master_skus share same product_id (e.g., DMF-2/2X, DMF-2/3X, DMF-2/4X). Metrics attributed to wrong SKU.

**Why it happens:** Google Ads aggregates at product_id level, not master_sku level.

**How to avoid:**
- Query by offer_id (variant-level) NOT product_id
- Use `variant_index` table to map offer_id → master_sku
- Aggregate variant metrics to master_sku level in application code
- Phase 0 discovery (02-03) documented this pattern

**Pattern:**
```python
# WRONG: Query by product_id (aggregates multiple SKUs)
query = f"WHERE segments.product_id = '{product_id}'"

# CORRECT: Query by offer_id (variant-specific)
query = f"WHERE segments.product_item_id = '{offer_id}'"

# Then aggregate to master_sku
for variant in variants:
    metrics = fetch_performance(variant.gmc_offer_id)
    aggregate_to_master_sku(variant.master_sku, metrics)
```

## Code Examples

Verified patterns from production codebase:

### Search Terms Collection

Already implemented in `SearchTermsClient`:

```python
# Source: src/feedops/integrations/google_ads_search_terms.py (lines 520-621)
client = SearchTermsClient(customer_id="6253381786")

# Fetch search terms with variant tracking
search_terms = client.fetch_search_terms(
    days=180,  # DATA-02: 180 days lookback
    limit=10000
)

# Save to database with idempotent upsert
period_start = date.today() - timedelta(days=180)
period_end = date.today()
count = client.save_search_terms_to_db(
    search_terms,
    period_start=period_start,
    period_end=period_end,
    sync_job_id=job_id
)

# Aggregate by master_sku
count = client.aggregate_by_master_sku(period_start, period_end)
```

### Keyword Planner Enrichment

Already implemented in `KeywordPlannerClient`:

```python
# Source: src/feedops/integrations/google_ads_search_terms.py (lines 86-263)
kp_client = KeywordPlannerClient(customer_id="6253381786")

# Get metrics with 30-day caching
keywords = ["bathroom towel bar", "chrome towel rack"]
metrics = kp_client.get_historical_metrics(
    keywords,
    use_cache=True,
    cache_max_age_days=30  # DATA-03: 30-day TTL
)

# Returns: {keyword: {avg_monthly_searches, competition, competition_index, ...}}
```

### Performance Metrics Collection

Already implemented in `PerformanceClient`:

```python
# Source: src/feedops/integrations/google_ads_performance.py (lines 288-426)
from feedops.integrations.google_ads_performance import fetch_batch_product_performance

# Batch query (efficient)
offer_ids = [variant.gmc_offer_id for variant in variants]
results = fetch_batch_product_performance(
    offer_ids,
    start_date="2025-08-01",  # DATA-02: 180 days
    end_date="2026-02-13",
    customer_id="6253381786"
)

# Returns: {offer_id: {impressions, clicks, ctr, conversions, ...}}
```

### Batch Processing with Checkpointing

Pattern from Phase 1:

```python
# Source: src/feedops/jobs/processor.py (lines 82-254)
async def _collect_search_terms_batch(batch: list[str]) -> list[dict]:
    """Process function for BatchProcessor.

    MUST use idempotent upserts (ON CONFLICT) for all writes.
    """
    client = SearchTermsClient()

    # Collect data
    results = []
    for master_sku in batch:
        terms = client.fetch_search_terms(days=180)
        results.extend(terms)

    # Save with idempotent upsert
    period_start = date.today() - timedelta(days=180)
    period_end = date.today()
    client.save_search_terms_to_db(results, period_start, period_end)

    return results

# Spawn processor
processor = BatchProcessor(
    job_id=job_id,
    items=skus,
    batch_size=10,
    checkpoint_interval=100,
    rate_limiter=google_ads_limiter
)
await processor.run(process_fn=_collect_search_terms_batch)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual batch loops | BatchProcessor with checkpointing | Phase 1 (2026-02-13) | Automatic resume, progress tracking, ETA |
| time.sleep() rate limiting | TokenBucket with burst | Phase 1 (2026-02-13) | Thread-safe, burst-aware, validated |
| FastAPI BackgroundTasks | run_async_in_thread() | 2026-02-08 | Survives container restarts |
| Custom checkpoint JSON files | JSONB checkpoint_data in DB | Phase 1 (2026-02-13) | Atomic updates, queryable |
| Search term view direct query | Campaign-join pattern | Phase 0.1 (2026-02-12) | Only working pattern for product-level search terms |
| Keyword Planner every query | 30-day cached metrics | Production (existing) | 30x fewer API calls |

**Deprecated/outdated:**
- Direct search_term_view filtering by product_item_id (API limitation discovered Phase 0.1)
- LAST_N_DAYS date syntax (API rejects, use BETWEEN 'YYYY-MM-DD' from Phase 0.3)
- Manual status updates (use JobManager atomic operations)

## Open Questions

### Q1: Should custom_label_0 sync be real-time or batch?

**What we know:**
- Google Merchant Center API can fetch product attributes including custom_label_0
- Supabase has no dedicated table for custom labels (would need to add column to variant_index)
- Current system uses Google Sheets as intermediate (custom_label_0 populated during publishing)

**What's unclear:**
- Frequency of custom_label_0 changes (is daily sync sufficient?)
- Whether to store in Supabase or just query-on-demand from GMC

**Recommendation:**
- Start with batch collection (daily sync) stored in variant_index table
- Endpoint: GET all products, extract custom_label_0, upsert to variant_index
- Can optimize to real-time if business need arises

### Q2: Should Keyword Planner run for ALL 2,784 SKUs or just cold-start?

**What we know:**
- Phase 0.4 found 43% coverage gap (168K monthly searches missed)
- Keyword Planner has lower rate limit (2 QPS vs 10 QPS)
- Search terms data already covers active queries

**What's unclear:**
- Cost/benefit of running Keyword Planner for SKUs with zero search term data
- Whether keyword ideas discover genuinely new opportunities

**Recommendation:**
- Run for ALL SKUs (DATA-03 requirement says "all 2,784 SKUs")
- Use 2 QPS rate limiter (keyword_planner_limiter already exists)
- 2,784 SKUs * 0.5s = ~23 minutes (acceptable for backfill job)
- Phase 0.4 validated the value (43% coverage gap)

### Q3: What's the optimal checkpoint interval for 2,784 SKU backfill?

**What we know:**
- Phase 1 default is 100 items (JOB-09 requirement)
- Checkpoint saves ~100ms (database write)
- 2,784 SKUs at batch size 10 = 278 batches

**What's unclear:**
- Whether 100-item checkpoint is too frequent for this workload
- Tradeoff between resume granularity and checkpoint overhead

**Recommendation:**
- Start with 100 (Phase 1 default)
- Monitor checkpoint timing in first backfill run
- If checkpoint writes become bottleneck, increase to 250
- 100 is safe default (278 batches / 10 per batch / 10 checkpoints = ~28 checkpoints)

## Sources

### Primary (HIGH confidence)

- **Codebase:**
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/google_ads_search_terms.py` - SearchTermsClient and KeywordPlannerClient implementations
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/integrations/google_ads_performance.py` - PerformanceClient implementation
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/jobs/processor.py` - BatchProcessor with checkpointing
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/jobs/rate_limiter.py` - TokenBucket rate limiters
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/src/feedops/jobs/manager.py` - Job lifecycle management
  - `/Users/bobby/Documents/GitHub/Allied-FeedOps/docs/database/SCHEMA.md` - Complete database schema

- **Phase 0 Discovery Research:**
  - `.planning/phases/02-comprehensive-data-discovery/02-RESEARCH.md` - Complete Google Ads API inventory, validated patterns

- **Phase 1 Job Infrastructure:**
  - Phase 1 plan summaries (05-01 through 05-04) - Job models, manager, rate limiter, processor, tests

- **Google Merchant Center API:**
  - [Custom Labels Documentation](https://support.google.com/merchants/answer/6324473?hl=en) - custom_label_0-4 fields
  - [Merchant API Products Guide](https://developers.google.com/merchant/api/guides/products/add-manage) - Product retrieval patterns
  - [Merchant API Reference](https://developers.google.com/merchant/api/reference/rest) - API v1 reference (v1beta deprecated Feb 2026)

### Secondary (MEDIUM confidence)

- CLAUDE.md anti-patterns and stack conventions
- Prior phase decisions (Phase 0: campaign-join, batch size 10, explicit date ranges)
- 2026-02-08 background task fix audit document

### Tertiary (LOW confidence)

None - all findings verified with codebase or official documentation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All components exist and tested in codebase
- Architecture: HIGH - Patterns validated in Phase 0 and implemented in Phase 1
- Pitfalls: HIGH - Based on Phase 0 discoveries and Phase 1 testing
- Open questions: MEDIUM - Business decisions more than technical unknowns

**Research date:** 2026-02-13
**Valid until:** 2026-03-13 (30 days for stable infrastructure, Google Ads API versions change quarterly)
