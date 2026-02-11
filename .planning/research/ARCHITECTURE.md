# Architecture Research: Google Ads API Backfill Systems

**Domain:** Data backfill and monitoring for Google Ads API
**Researched:** 2026-02-11
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ Dashboard  │  │  Batch     │  │  Manual    │            │
│  │  Trigger   │  │ Scheduler  │  │  Scripts   │            │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘            │
│        │                │                │                   │
├────────┴────────────────┴────────────────┴───────────────────┤
│                    Job Management Layer                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          Job Queue + Status Tracking                  │   │
│  │  (Database: job_id, status, progress, errors)        │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                       │
├──────────────────────┴───────────────────────────────────────┤
│                  Processing Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Worker 1 │  │ Worker 2 │  │ Worker 3 │  │ Worker N │    │
│  │ (Thread/ │  │ (Thread/ │  │ (Thread/ │  │ (Thread/ │    │
│  │  Process)│  │  Process)│  │  Process)│  │  Process)│    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       │             │             │             │           │
├───────┴─────────────┴─────────────┴─────────────┴───────────┤
│                  Google Ads API Layer                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  GoogleAdsService.SearchStream + Rate Limiter        │   │
│  │  - Token Bucket throttling                           │   │
│  │  - Exponential backoff + jitter                      │   │
│  │  - Partial failure handling                          │   │
│  └───────────────────┬──────────────────────────────────┘   │
│                      │                                       │
├──────────────────────┴───────────────────────────────────────┤
│                   Storage Layer                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │  Postgres  │  │   Cache    │  │   Logs     │            │
│  │ (Supabase) │  │  (Redis)   │  │ (GCP Log)  │            │
│  └────────────┘  └────────────┘  └────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Job Manager | Creates jobs, tracks status, aggregates progress | FastAPI endpoint + Supabase table (`batch_generation_jobs`, `search_query_sync_jobs`) |
| Worker Pool | Executes API calls, handles retries, stores results | Python threads with dedicated asyncio event loops (`run_async_in_thread()`) |
| Rate Limiter | Enforces API quotas, prevents throttling | Token bucket algorithm (built into google-ads client) |
| Result Store | Persists metrics, handles upserts on conflict | Supabase tables with unique constraints |
| Monitor | Tracks latency, error rates, completion status | Cloud Logging + metrics (percentiles, not just averages) |

## Recommended Project Structure

```
src/
├── feedops/
│   ├── api/
│   │   ├── main.py                      # FastAPI endpoints
│   │   ├── search_insights.py           # Search term sync router
│   │   └── performance_baseline.py      # Baseline capture router
│   ├── integrations/
│   │   ├── google_ads_search_terms.py   # SearchTermsClient
│   │   ├── google_ads_performance.py    # Performance fetching
│   │   └── keyword_planner.py           # KeywordPlannerClient
│   ├── db/
│   │   └── supabase_client.py           # Database connection
│   └── observability/
│       ├── metrics.py                   # Prometheus-style metrics
│       └── logging.py                   # Structured logging
scripts/
└── backfill-performance-baselines.py    # Standalone backfill script
```

### Structure Rationale

- **api/**: HTTP entrypoints with CORS for dashboard calls
- **integrations/**: Isolated API clients with retry logic and caching
- **db/**: Single source for connection pooling and transaction management
- **observability/**: Centralized monitoring to expose latency/error patterns

## Architectural Patterns

### Pattern 1: Job-Based Backfill Architecture

**What:** Async job pattern where API creates job record, returns job_id immediately, then processes in background thread

**When to use:**
- Backfilling 2,784 SKUs (multi-minute/hour operations)
- User-facing endpoints that can't block on completion
- Operations requiring progress tracking

**Trade-offs:**
- ✅ Non-blocking: User gets immediate response
- ✅ Resumable: Job state persisted, can recover from crashes
- ✅ Observable: Progress updates, error tracking
- ❌ Complexity: Requires job table, status polling, background worker management
- ❌ Deployment risk: Workers terminate during Cloud Run container replacement (expected behavior)

**Example:**
```python
# Job creation endpoint (returns immediately)
@app.post("/search-insights/sync")
async def create_sync_job():
    job_id = str(uuid.uuid4())

    # Store job record
    supabase.table("search_query_sync_jobs").insert({
        "job_id": job_id,
        "status": "running",
        "total_skus": 2784,
        "processed_skus": 0
    }).execute()

    # Start background worker
    run_async_in_thread(sync_job_worker, job_id=job_id)

    return {"job_id": job_id}

# Background worker (async function in separate thread)
async def sync_job_worker(job_id: str):
    for sku in skus:
        try:
            data = fetch_search_terms(sku)
            save_to_db(data)
            update_progress(job_id, processed_count)
        except Exception as e:
            log_error(job_id, sku, e)

    update_status(job_id, "completed")
```

### Pattern 2: Campaign-Level Query Strategy

**What:** Fetch products by campaign first, then search terms with campaign_id, join via campaign association

**When to use:**
- Product-level filtering not directly supported in search_term_view
- Need variant-level granularity (GMC offer IDs)
- Multi-product campaigns

**Trade-offs:**
- ✅ Workaround for API limitation (search_term + product_item_id not both supported)
- ✅ Provides campaign context for debugging
- ❌ Two-query pattern (shopping_performance_view → search_term_view)
- ❌ Potential data staleness if campaign products change between queries

**Example:**
```python
# Step 1: Get products by campaign
query1 = """
SELECT
    segments.product_item_id,
    campaign.id,
    metrics.impressions
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
    AND campaign.advertising_channel_type = 'SHOPPING'
    AND metrics.impressions > 0
ORDER BY metrics.impressions DESC
LIMIT 50000
"""

# Step 2: Get search terms by campaign
query2 = """
SELECT
    search_term_view.search_term,
    campaign.id,
    metrics.impressions,
    metrics.clicks
FROM search_term_view
WHERE segments.date DURING LAST_{days}_DAYS
    AND campaign.advertising_channel_type = 'SHOPPING'
ORDER BY metrics.impressions DESC
"""

# Step 3: Join in-memory
campaign_products = {campaign_id: [offer_ids]}
for search_term in search_terms:
    offer_ids = campaign_products.get(search_term.campaign_id, [])
    # Associate search term with product variants
```

### Pattern 3: Exponential Backoff with Jitter

**What:** Retry transient errors with exponentially increasing delays plus randomization

**When to use:**
- All Google Ads API calls
- Errors: `UNAVAILABLE`, `DEADLINE_EXCEEDED`, `INTERNAL`, `TRANSIENT_ERROR`, `RATE_LIMIT_EXCEEDED`

**Trade-offs:**
- ✅ Prevents retry storms (jitter prevents synchronized retries)
- ✅ Respects API rate limits
- ✅ Built into google-ads Python client (automatic)
- ❌ Increases latency for failed requests
- ❌ Requires max retry limit to prevent infinite loops

**Example:**
```python
import random
import time

def exponential_backoff_with_jitter(
    func,
    max_retries=5,
    base_delay=5.0,
    max_delay=60.0
):
    """Retry function with exponential backoff + jitter."""
    for attempt in range(max_retries):
        try:
            return func()
        except GoogleAdsException as e:
            # Only retry transient errors
            if e.error.code().name not in [
                'UNAVAILABLE', 'DEADLINE_EXCEEDED', 'INTERNAL'
            ]:
                raise

            if attempt == max_retries - 1:
                raise

            # Calculate delay: base * 2^attempt + jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # ±10% jitter

            logger.warning(f"Retry {attempt+1}/{max_retries} after {delay+jitter:.2f}s")
            time.sleep(delay + jitter)
```

### Pattern 4: Pagination with SearchStream

**What:** Use `GoogleAdsService.search_stream()` for large result sets, client library auto-paginates

**When to use:**
- Result sets > 10,000 rows
- Performance queries with 30+ day date ranges
- Search term queries across many campaigns

**Trade-offs:**
- ✅ Handles pagination automatically (no manual token management)
- ✅ Single operation quota cost (regardless of pages)
- ✅ Server-side caching speeds up subsequent pages
- ❌ Query must be identical to leverage cache
- ❌ First page slower than subsequent pages

**Example:**
```python
from google.ads.googleads.client import GoogleAdsClient

client = GoogleAdsClient.load_from_storage()
ga_service = client.get_service("GoogleAdsService")

query = """
SELECT
    search_term_view.search_term,
    metrics.impressions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
"""

# SearchStream automatically paginates (10k rows/page)
stream = ga_service.search_stream(customer_id="1234567890", query=query)

results = []
for batch in stream:  # Each batch = 1 page
    for row in batch.results:
        results.append(row)

# Total: 1 operation quota cost regardless of page count
```

### Pattern 5: Variant-Level Caching

**What:** Cache variant_index lookups (gmc_offer_id → master_sku/finish) in-memory during batch operations

**When to use:**
- Processing thousands of search terms/performance records
- Same variants referenced repeatedly
- Batch jobs with predictable SKU sets

**Trade-offs:**
- ✅ Reduces database queries (2,784 SKUs × N records → 2,784 cache misses max)
- ✅ Speeds up processing (memory lookup vs network round-trip)
- ❌ Memory footprint (minimal: ~500KB for 2,784 variants)
- ❌ Stale data risk if variant_index changes during processing (rare)

**Example:**
```python
class SearchTermsClient:
    def __init__(self):
        self._variant_cache: dict[str, dict] = {}

    def get_variant_info(self, gmc_offer_id: str) -> dict:
        """Cache variant lookups during batch processing."""
        if gmc_offer_id in self._variant_cache:
            return self._variant_cache[gmc_offer_id]

        # Cache miss: query database
        result = supabase.table("variant_index").select(
            "master_sku, finish, finish_code"
        ).eq("gmc_offer_id", gmc_offer_id).limit(1).execute()

        info = result.data[0] if result.data else {}
        self._variant_cache[gmc_offer_id] = info
        return info
```

## Data Flow

### Backfill Request Flow

```
[User/Scheduler]
    ↓ POST /search-insights/sync
[API Endpoint] → Create job record in search_query_sync_jobs
    ↓ run_async_in_thread()
[Background Worker]
    ↓ Query variant_index for SKU list
    ↓ for each SKU chunk (batch_size=50):
[Worker] → Fetch products by campaign
    ↓ GoogleAdsService.search_stream(shopping_performance_view)
[Worker] → Fetch search terms by campaign
    ↓ GoogleAdsService.search_stream(search_term_view)
[Worker] → Join via campaign_id, lookup variant info
    ↓ Dedupe by (query_text, gmc_offer_id)
[Worker] → Upsert to search_queries table
    ↓ Update job progress
[Worker] → Aggregate by master_sku → search_queries_by_master_sku
    ↓
[Job Complete] → Update status to 'completed'
```

### Performance Baseline Capture Flow

```
[User/Scheduler]
    ↓ POST /performance/capture-baseline?master_sku=920D-6
[API Endpoint] → Check if baseline exists + age
    ↓ if missing or stale (>60 days):
[Baseline Capture] → Get all gmc_offer_ids for master_sku
    ↓ for each platform (google, bing, shopify):
[Client] → Query performance metrics
    ↓ GoogleAdsService.search_stream(shopping_performance_view)
    ↓ WHERE segments.date BETWEEN start AND end
    ↓      AND segments.product_item_id = offer_id
[Client] → Aggregate: impressions, clicks, conversions, cost, ROAS
    ↓
[Storage] → Upsert to performance_baselines
    ↓ on_conflict=(master_sku, platform)
[Response] ← Return baseline metrics
```

### Key Data Flows

1. **Job Status Updates:** Worker → Supabase → Dashboard polling (every 2-5s)
2. **Error Logging:** Worker exception → Cloud Logging → Alert policy trigger
3. **Metric Collection:** All API calls → Token bucket check → Rate limit enforcement
4. **Cache Warming:** First query → API response → In-memory cache → Subsequent queries

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-500 SKUs (current) | Single worker thread, sequential processing, ~3-5 min backfill |
| 500-5,000 SKUs | Parallel workers (5-10 threads), batch_size=50-100, ~10-20 min backfill |
| 5,000-50,000 SKUs | Distributed workers (Cloud Run Jobs, Cloud Tasks), batch_size=100-500, ~1-2 hours |
| 50,000+ SKUs | Dataflow pipeline, streaming architecture (5-10 min batches), concurrent connections (5-10) |

### Scaling Priorities

1. **First bottleneck:** API rate limits hit (~15k operations/day on Basic Access)
   - **Fix:** Request Standard Access (higher quota), implement request batching

2. **Second bottleneck:** Database upsert latency with 50k+ rows
   - **Fix:** Batch upserts (500-1000 rows/transaction), connection pooling, read replicas

3. **Third bottleneck:** Worker thread count limited by container CPU
   - **Fix:** Horizontal scaling (Cloud Run with `--min-instances=N`), async I/O instead of threads

## Anti-Patterns

### Anti-Pattern 1: Query Product and Search Term Together

**What people do:** Try to SELECT both segments.product_item_id and search_term_view fields in same query

**Why it's wrong:** Google Ads API doesn't support filtering search_term_view by product_item_id simultaneously

**Do this instead:** Two-query pattern (fetch products by campaign → search terms by campaign → join in-memory)

**Evidence:** [Google Ads API groups discussion](https://groups.google.com/g/adwords-api/c/Ll5hhZzCFXY) confirms limitation, existing code in `google_ads_search_terms.py` implements workaround

---

### Anti-Pattern 2: Polling Job Status Every Second

**What people do:** Dashboard polls job status endpoint every 1 second to show real-time progress

**Why it's wrong:**
- Wastes API quota (each poll = 1 database query)
- Increases database load (500 SKUs × 1 poll/sec = 500 queries over 500 seconds)
- No meaningful progress update sub-second

**Do this instead:** Poll every 3-5 seconds, use exponential backoff for long jobs

**Example:**
```typescript
// Bad: 1 second polling
setInterval(() => fetchJobStatus(jobId), 1000);

// Good: 5 second polling with exponential backoff
let pollInterval = 5000;
const maxInterval = 30000;

const poll = async () => {
    const status = await fetchJobStatus(jobId);
    if (status === 'running') {
        pollInterval = Math.min(pollInterval * 1.2, maxInterval);
        setTimeout(poll, pollInterval);
    }
};
```

---

### Anti-Pattern 3: Synchronous Batch Processing

**What people do:** Process all 2,784 SKUs sequentially in HTTP request handler, block until complete

**Why it's wrong:**
- Times out (Cloud Run 60 min max, Vercel 10 sec/60 sec limits)
- No progress visibility
- Wastes connection resources
- Can't cancel once started

**Do this instead:** Job-based async pattern with background workers

---

### Anti-Pattern 4: No Retry on Rate Limit

**What people do:** Catch `RATE_LIMIT_EXCEEDED` error and fail immediately

**Why it's wrong:**
- Rate limits are temporary (token bucket refills)
- Wastes already-fetched partial results
- User has to manually retry entire batch

**Do this instead:** Exponential backoff with jitter (built into google-ads client library)

---

### Anti-Pattern 5: Ignoring Partial Failures

**What people do:** Assume batch job operations are all-or-nothing transactions

**Why it's wrong:** Google Ads API batch jobs use partial failure model - successful operations persist even if others fail

**Do this instead:**
- Check `BatchJobService.ListMutateJobResults` for per-operation status
- Log failed operations separately
- Report success/failure counts to user

**Evidence:** [Batch Processing Best Practices](https://developers.google.com/google-ads/api/docs/batch-processing/best-practices) states "if a job is cancelled or individual operations fail, operations that succeeded will not be rolled back"

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google Ads API | google-ads Python client, SearchStream with retry | Token bucket rate limiting, auto-pagination |
| Supabase | supabase-py client, upsert on conflict | Connection pooling recommended (pgbouncer) |
| Cloud Logging | Python logging module → GCP Logging Handler | Structured JSON logs with request_id context |
| Cloud Run | FastAPI + uvicorn, background threads | Threads survive HTTP response but terminate on deployment |
| Vercel Dashboard | HTTP polling for job status | CORS enabled for `allied-feed-ops.vercel.app` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| API ↔ Worker | Function call + database state | run_async_in_thread() with job_id |
| Worker ↔ Google Ads API | GAQL queries via search_stream | Retry logic in client library |
| Worker ↔ Database | Supabase upsert (on_conflict) | Handles concurrent writes from multiple workers |
| Dashboard ↔ API | REST (POST to create job, GET for status) | JWT auth via Supabase auth headers |

## Query Architecture

### GAQL Query Best Practices

**1. Product-Level Filtering:**
```sql
-- Use shopping_performance_view for product metrics
SELECT
    segments.product_item_id,
    campaign.id,
    campaign.advertising_channel_type,  -- MUST SELECT when filtering by it
    metrics.impressions,
    metrics.clicks
FROM shopping_performance_view
WHERE segments.date DURING LAST_30_DAYS
    AND campaign.advertising_channel_type = 'SHOPPING'
    AND metrics.impressions > 0
ORDER BY metrics.impressions DESC
LIMIT 50000
```

**2. Search Terms by Campaign:**
```sql
SELECT
    search_term_view.search_term,
    campaign.id,
    metrics.impressions,
    metrics.clicks,
    metrics.conversions
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
    AND campaign.advertising_channel_type = 'SHOPPING'
ORDER BY metrics.impressions DESC
LIMIT 1000
```

**3. Date Range Formats:**
- Predefined: `segments.date DURING LAST_30_DAYS` (recommended for caching)
- Custom: `segments.date BETWEEN '2025-01-01' AND '2025-01-31'` (YYYY-MM-DD or YYYYMMDD)
- Historical limit: 11 years retention (data older than Nov 13, 2013 not accessible as of Nov 2024)

**4. Field Selection:**
- Only SELECT fields you need (fewer fields = faster queries)
- Campaign-level queries faster than account-level
- MUST SELECT any field used in WHERE clause (e.g., `campaign.advertising_channel_type`)

### Query Optimization Rules

1. **Use SearchStream for large result sets** (>10k rows expected)
2. **Order by meaningful metric** (impressions/clicks) to get top results first
3. **Limit result size** for exploratory queries (use pagination for full datasets)
4. **Filter by campaign when possible** (faster than account-level)
5. **Use predefined date ranges** when applicable (leverages server-side caching)

## Batch Processing Strategy

### Recommended Approach for 2,784 SKUs

**Architecture:** Job-based with sequential processing (current scale doesn't need parallelism)

**Rationale:**
- API quota: 15k operations/day (Basic Access) means ~15k SKUs/day theoretical max
- Current need: 2,784 SKUs = ~19% of daily quota
- Processing time: ~3-5 minutes for search term sync (tested in existing implementation)
- Complexity trade-off: Sequential easier to debug, sufficient for current scale

**Implementation:**
```python
# Single worker, batched API queries
async def sync_job_worker(job_id: str):
    skus = fetch_sku_list()  # 2,784 SKUs
    batch_size = 50  # Process 50 SKUs per API query

    for i in range(0, len(skus), batch_size):
        batch = skus[i:i+batch_size]

        # Single query fetches data for 50 SKUs
        campaign_products = fetch_campaign_products(days=30)
        search_terms = fetch_search_terms(days=30)

        # Join and save
        for sku in batch:
            terms = associate_search_terms(sku, campaign_products, search_terms)
            save_to_db(terms)

        update_progress(job_id, i + len(batch))
```

### When to Scale to Parallel Workers

**Trigger conditions:**
- SKU count > 5,000
- Backfill time > 30 minutes
- API quota increase to Standard Access (higher limit)

**Parallel architecture:**
```python
# Multiple workers, partitioned SKU list
async def parallel_sync(job_id: str, worker_count: int = 5):
    skus = fetch_sku_list()
    partitions = partition_list(skus, worker_count)

    tasks = [
        sync_worker(job_id, partition, worker_id)
        for worker_id, partition in enumerate(partitions)
    ]

    await asyncio.gather(*tasks)
```

## Monitoring Strategy

### Key Metrics to Track

**Latency (percentiles, not averages):**
- `google_ads_api_latency_p50`, `p90`, `p99` (ms)
- `job_completion_time` (seconds)
- `database_upsert_latency_p90` (ms)

**Throughput:**
- `skus_processed_per_minute`
- `api_requests_per_second`
- `search_terms_saved_per_minute`

**Errors:**
- `google_ads_api_error_rate` (by error code)
- `job_failure_rate`
- `retry_attempts_total`

**Resource Utilization:**
- `worker_thread_count`
- `database_connection_pool_usage`
- `memory_usage_mb`

### Alert Policies

**Critical:**
- Job failure rate > 10% (alert immediately)
- API error rate > 5% (alert within 5 minutes)
- No job completions in 2 hours (stalled workers)

**Warning:**
- p90 latency > 2x baseline (performance degradation)
- Retry attempts > 20% of requests (rate limit issues)

### Implementation

```python
from feedops.observability.metrics import metrics_registry

# In API integration code
def fetch_search_terms_with_metrics(days: int):
    started = time.perf_counter()

    try:
        result = ga_service.search_stream(query=query)
        metrics_registry.increment("google_ads_api_requests_total", status="success")
        return result
    except GoogleAdsException as e:
        metrics_registry.increment(
            "google_ads_api_errors_total",
            error_code=e.error.code().name
        )
        raise
    finally:
        latency = time.perf_counter() - started
        metrics_registry.observe("google_ads_api_latency_seconds", latency)
```

### Dashboard Queries (Cloud Logging)

```sql
-- Error rate over time
resource.type="cloud_run_revision"
severity="ERROR"
jsonPayload.component="google_ads_api"
| rate 1m

-- Slow queries (p99 latency)
resource.type="cloud_run_revision"
jsonPayload.google_ads_api_latency_seconds > 5.0
| percentile 99

-- Job completion tracking
resource.type="cloud_run_revision"
jsonPayload.event="job_completed"
| group by jsonPayload.job_id
```

## Implementation Order for Backfill System

Based on dependency analysis and risk mitigation:

### Phase 1: Validation (Low Risk, Foundation)
**Goal:** Verify query patterns work with real data

1. Test product-level filtering with `shopping_performance_view`
2. Test search term fetching by campaign
3. Verify variant_index join logic
4. Validate date range queries (30, 60, 90, 180 days)

**Deliverable:** Jupyter notebook or script demonstrating query patterns with sample data

**Risk mitigation:** Catches API limitation issues before building full system

---

### Phase 2: Core Backfill (Medium Risk, Critical Path)
**Goal:** Implement minimal backfill functionality

1. Create `search_query_sync_jobs` table
2. Implement single-SKU search term fetch function
3. Add database upsert logic with conflict resolution
4. Build sequential job processor (no parallelism yet)

**Deliverable:** `/search-insights/sync` endpoint that processes all SKUs sequentially

**Risk mitigation:** Simplest possible architecture, easy to debug

---

### Phase 3: Job Management (Low Risk, User Experience)
**Goal:** Make backfill observable and non-blocking

1. Add job status endpoint (`GET /search-insights/sync/{job_id}`)
2. Implement progress tracking (processed_skus / total_skus)
3. Add error logging to job records
4. Build dashboard polling UI

**Deliverable:** Dashboard shows real-time progress, error counts, completion status

**Risk mitigation:** User visibility into long-running operations

---

### Phase 4: Monitoring (Low Risk, Operations)
**Goal:** Detect failures and performance issues

1. Add structured logging with request_id
2. Implement metric collection (latency, error rate, throughput)
3. Create Cloud Logging queries for common issues
4. Set up alert policies for critical errors

**Deliverable:** GCP dashboard showing API health, job completion rate, error patterns

**Risk mitigation:** Proactive failure detection

---

### Phase 5: Optimization (Optional, Scale-Dependent)
**Goal:** Handle larger SKU counts if needed

1. Add parallel worker support
2. Implement caching for variant lookups
3. Tune batch sizes based on measured latency
4. Add retry budget to prevent infinite retries

**Deliverable:** Sub-5-minute backfill for 5,000+ SKUs

**Risk mitigation:** Only build if scale requires it (current 2,784 SKUs fine with sequential)

## Sources

### Official Documentation (HIGH Confidence)
- [Batch Processing Best Practices](https://developers.google.com/google-ads/api/docs/batch-processing/best-practices)
- [Batch Processing Overview](https://developers.google.com/google-ads/api/docs/batch-processing/overview)
- [Google Ads API Rate Limits](https://developers.google.com/google-ads/api/docs/best-practices/quotas)
- [Pagination with Search](https://developers.google.com/google-ads/api/docs/reporting/paging)
- [Date Ranges in GAQL](https://developers.google.com/google-ads/api/docs/query/date-ranges)
- [Error Handling Best Practices](https://developers.google.com/google-ads/api/docs/best-practices/error-types)
- [Monitoring Guidelines](https://developers.google.com/google-ads/api/docs/productionize/monitoring)

### Implementation References (HIGH Confidence)
- Existing code: `/src/feedops/integrations/google_ads_search_terms.py`
- Existing code: `/src/feedops/integrations/google_ads_performance.py`
- Existing code: `/scripts/backfill-performance-baselines.py`
- Database schema: `/docs/database/SCHEMA.md`

### Community/Blog Sources (MEDIUM Confidence)
- [Google Ads Data Retention Policy (Nov 2024)](https://support.google.com/google-ads/answer/15188209)
- [2026 API Changes Discussion](https://almcorp.com/blog/google-ads-api-conversion-data-changes-2026/)

---

*Architecture research for: Google Ads API data backfill systems*
*Researched: 2026-02-11*
*Next step: Use findings to structure backfill implementation phases in roadmap*
