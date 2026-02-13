# Technology Stack

**Project:** Allied FeedOps - Large-Scale Batch Orchestration & Monitoring
**Researched:** 2026-02-13
**Previous Research:** 2026-02-11 (Google Ads API Integration)

## Recommended Stack Additions

### Core Orchestration & Job Management

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **asyncio** (stdlib) | 3.11+ | Async batch processing, concurrent API calls | Built-in, zero dependencies, TaskGroup in 3.11+ provides structured concurrency for clean error handling |
| **asyncio.Semaphore** (stdlib) | 3.11+ | Concurrency limiting (10 concurrent SKUs) | Simple, effective rate limiting without external dependencies |
| **tenacity** | 9.1.4 (latest: 2026-02-07) | Retry logic with exponential backoff | Google Ads API best practice: handles RESOURCE_TEMPORARILY_EXHAUSTED with configurable backoff + jitter |
| **aiolimiter** | 1.2.1 | Token bucket rate limiting | Precise QPS control for Google Ads API (per-CID and per-developer-token metering) |

**Rationale**: Avoid heavyweight orchestration (Airflow, Prefect, Dagster) which add deployment complexity and don't fit Cloud Run's request-response + background task model. Your existing `run_async_in_thread()` pattern (main.py:149-150) handles background jobs; just need better async primitives for batch control.

**Integration**: Extend existing FastAPI endpoints with async batch controllers:
```python
# Existing pattern in main.py
async def process_batch(batch_id: str, sku_list: list[str]):
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent
    limiter = AsyncLimiter(5, 1)  # 5 req/sec per CID

    async def process_one(sku: str):
        async with semaphore, limiter:
            # Existing SKU optimization logic
            pass

    await asyncio.gather(*[process_one(sku) for sku in sku_list])
```

### Data Validation & Quality

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Pydantic** | 2.0+ (already installed) | Schema validation, type safety | Already in pyproject.toml; v2 is 4-50x faster than v1, perfect for validating 2,784 SKU records |
| **PostgreSQL check constraints** | Native | Database-level validation | Leverage existing Supabase schema (SCHEMA.md); cheaper than app-layer validation |
| **Custom validation functions** | Python | Business rule validation (e.g., finish coverage, keyword freshness) | Domain-specific rules don't fit generic frameworks |

**Rationale**: Great Expectations is overkill (designed for data warehouse profiling/reporting). You need lightweight validation for API responses and database writes. Pydantic v2 (already installed) handles schema validation; custom Python for domain logic (e.g., "all 28 finishes have search data").

**Integration**: Create validation models in `src/feedops/validation/`:
```python
from pydantic import BaseModel, Field, field_validator

class SearchTermRecord(BaseModel):
    master_sku: str
    gmc_offer_id: str
    query: str
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)

    @field_validator('master_sku')
    def validate_sku_format(cls, v):
        # Existing SKU format logic from sku-utils.ts
        return v

class BatchValidationResult(BaseModel):
    total_skus: int
    valid_skus: int
    missing_data: list[str]
    stale_data: list[str]  # > 7 days old
```

### Error Handling & Retry Logic

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **tenacity** | 9.1.4 | Declarative retry logic | Industry standard; supports all Google Ads API retry patterns (exponential backoff, jitter, conditional retry) |
| **Custom error types** | Python | Domain-specific errors | Distinguish retryable (API rate limit) vs non-retryable (missing SKU) errors |

**Rationale**: Tenacity is mature (Apache 2.0), supports async, and handles Google Ads API error codes cleanly. Alternative (retrying) is deprecated.

**Integration**: Wrap Google Ads API calls with retry decorators:
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

class RetryableAPIError(Exception):
    """Rate limits, timeouts, server errors"""
    pass

@retry(
    retry=retry_if_exception_type(RetryableAPIError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
async def fetch_search_terms(master_sku: str):
    try:
        # Existing Google Ads API call
        pass
    except Exception as e:
        if "RESOURCE_TEMPORARILY_EXHAUSTED" in str(e):
            raise RetryableAPIError(e) from e
        raise  # Non-retryable
```

### Monitoring & Observability

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **structlog** | 24.5.0+ | Structured logging with context propagation | Better than loguru for async: ContextVars support, integrates with Cloud Run structured logging, observable with GCP Logging |
| **Prometheus client** (python) | 0.21.1 | Custom metrics (batch progress, API latency) | Supabase already exposes Prometheus endpoint; you can push custom metrics to same stack |
| **Supabase Metrics API** | Native | Database health monitoring | Already available (200+ Postgres metrics); scrape into Grafana or Datadog |
| **Google Cloud Logging** | Native | Log aggregation, alerting | Cloud Run auto-integration; structlog outputs JSON that GCP parses automatically |

**Rationale**: Structlog is the modern choice for async Python logging in 2026. It has steeper learning curve than loguru but critical advantages: async context propagation (request_id follows across async calls), integration with Cloud Logging structured JSON, and production-grade observability. Your existing `request_context()` middleware (main.py:112-141) already uses contextvars—structlog builds on this pattern.

**Integration**: Replace basic logging with structlog:
```python
# In main.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()  # Cloud Run parses this
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

# Usage in batch jobs
logger.info("batch_started", batch_id=batch_id, sku_count=len(skus))
logger.info("sku_processed", master_sku=sku, duration_ms=elapsed)
logger.error("sku_failed", master_sku=sku, error=str(e))
```

**Prometheus Integration**: Add custom metrics for batch progress:
```python
from prometheus_client import Counter, Histogram, Gauge

batch_jobs_total = Counter('batch_jobs_total', 'Total batch jobs started')
batch_skus_processed = Counter('batch_skus_processed', 'SKUs processed', ['status'])
batch_duration = Histogram('batch_duration_seconds', 'Batch job duration')
active_batch_jobs = Gauge('active_batch_jobs', 'Currently running batches')

# Expose /metrics endpoint
from prometheus_client import make_asgi_app
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
```

### Dashboard Visualization

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Recharts** | 3.7.0 (already installed) | Base charts (progress bars, line charts) | Already in package.json; mature (9.5M weekly downloads), good for custom charts |
| **Tremor** | 3.21.0+ | Pre-built dashboard components (KPI cards, tables) | Built on Recharts + Radix; provides 30+ dashboard components with Tailwind integration—eliminates custom component building |
| **Zustand** | 5.0.11 (already installed) | Client state (real-time batch progress) | Already installed; lightweight, perfect for polling batch status without Redux overhead |
| **Server-Sent Events (SSE)** | Native | Real-time progress updates | Lightweight alternative to WebSockets; Cloud Run supports long-lived connections |

**Rationale**: Recharts (already installed) handles custom charts. Add Tremor for high-level dashboard components (KPI cards showing "2,105 / 2,784 SKUs processed", progress rings, data tables). Tremor is opinionated but saves weeks of component development. For real-time updates, SSE is simpler than WebSockets and works with Cloud Run's HTTP/2.

**Integration**: Add Tremor to dashboard:
```bash
cd dashboard
npm install @tremor/react
```

```tsx
// New dashboard page: /dashboard/src/app/(dashboard)/backfill/page.tsx
import { Card, ProgressBar, Metric, Text, BarChart } from '@tremor/react';

export default function BackfillDashboard() {
  const { data: progress } = useQuery({
    queryKey: ['batch-progress'],
    queryFn: () => fetch('/api/batch-status/current').then(r => r.json()),
    refetchInterval: 5000  // Poll every 5s
  });

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <Card>
        <Text>SKUs Processed</Text>
        <Metric>{progress.completed} / {progress.total}</Metric>
        <ProgressBar value={(progress.completed / progress.total) * 100} />
      </Card>

      <Card>
        <Text>API Calls Today</Text>
        <Metric>{progress.api_calls}</Metric>
        <Text className="text-sm">Quota: {progress.quota_remaining} remaining</Text>
      </Card>

      <Card>
        <Text>Error Rate</Text>
        <Metric>{progress.error_rate}%</Metric>
      </Card>
    </div>
  );
}
```

**SSE for Real-Time Updates** (optional, better than polling):
```python
# In main.py
from fastapi.responses import StreamingResponse

@app.get("/batch-status/{job_id}/stream")
async def stream_batch_progress(job_id: str):
    async def event_stream():
        while True:
            status = await get_batch_status(job_id)
            yield f"data: {json.dumps(status)}\n\n"
            if status['state'] in ['completed', 'failed']:
                break
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

### Database Connection Pooling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Supabase pooler** | Native | Connection pooling (transaction mode) | Built-in, no code changes; prevents exhausting Postgres connections during 2,784 SKU batch |
| **asyncpg** (optional) | Latest | Direct async Postgres access | If Supabase client is bottleneck; bypasses REST API for bulk inserts |

**Rationale**: Supabase provides connection pooling out-of-the-box. For 2,784 SKU batch writes, transaction mode pooler handles concurrency. Only add asyncpg if Supabase REST API becomes a bottleneck (unlikely for batch sizes of 10).

**Integration**: Use existing Supabase client with pooled connection string (if needed):
```python
# Already in place via SUPABASE_URL
# If adding asyncpg for bulk operations:
import asyncpg

async def bulk_insert_search_terms(records: list[dict]):
    pool = await asyncpg.create_pool(
        os.getenv('DATABASE_URL'),  # Direct Postgres URL
        min_size=5,
        max_size=20
    )
    async with pool.acquire() as conn:
        await conn.executemany(
            'INSERT INTO search_queries (...) VALUES ($1, $2, ...)',
            [(r['sku'], r['query'], ...) for r in records]
        )
```

## Existing Stack (From 2026-02-11 Research)

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| google-ads | 29.0.0 | Official Google Ads API client library | Google's official Python client with full API coverage, active maintenance, and best-in-class authentication handling. Supports GAQL queries, streaming for large datasets, and all Google Ads API v18+ features. |
| Python | >=3.11 | Runtime environment | Project already on 3.11+. Library requires >=3.9 but 3.11+ provides better performance and type hints. Cloud Run supports 3.11+ natively. |
| GAQL | v18+ | Google Ads Query Language | Standard query language for Google Ads API. SQL-like syntax optimized for advertising data. Required for search_stream and search operations. |
| google-auth | >=2.48.0 | Authentication | Official OAuth2/service account library. Already in project dependencies. Handles refresh tokens and credential lifecycle. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | >=2.0 | Data processing for large result sets | Processing 50K+ row query results before Supabase insert. Already in project. Essential for batch operations and data transformation. |
| supabase | >=2.0 | Data storage | Storing search terms, performance data, keyword metrics. Already integrated with project. |
| google-api-python-client | >=2.0 | Merchant API integration | Required for custom_label_0 sync via Merchant API. Already in project for GMC integration. |
| httpx | >=0.25 | HTTP client for API calls | Async-capable client for concurrent API operations. Already in project dependencies. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Orchestration | asyncio + Semaphore | Airflow / Prefect / Dagster | Too heavyweight for Cloud Run; designed for scheduled DAGs, not API-triggered batches; adds deployment complexity (need separate Airflow server) |
| Orchestration | asyncio + Semaphore | Cloud Tasks | Good option but adds GCP service dependency; asyncio is simpler for tightly coupled batch work; consider if jobs need to survive deployments (current limitation of Cloud Run background tasks) |
| Rate Limiting | aiolimiter | Token bucket from scratch | Don't reinvent; aiolimiter is battle-tested, async-native |
| Retry Logic | tenacity | retrying library | retrying is deprecated, not maintained since 2016 |
| Validation | Pydantic v2 | Great Expectations | GE is for data warehouse profiling/reporting; overkill for API validation |
| Validation | Pydantic v2 | Pandera | Designed for DataFrame validation; you're working with dict/JSON from APIs |
| Logging | structlog | loguru | Loguru is simpler but lacks async context propagation (ContextVars); structlog integrates better with Cloud Run structured logging |
| Logging | structlog | python-json-logger | Minimal features; structlog provides richer processor pipeline |
| Dashboards | Recharts + Tremor | Chart.js | Chart.js is imperative (not React-friendly); Recharts is declarative |
| Dashboards | Recharts + Tremor | D3.js | Too low-level; D3 requires custom SVG manipulation; Recharts/Tremor are higher-level |
| Dashboards | Recharts + Tremor | Plotly | Heavy library (larger bundle); Recharts is lighter, faster |
| Real-time | SSE | WebSockets (Socket.IO) | SSE is simpler for one-way updates (server → client); WebSockets are overkill for batch progress |
| Queue | asyncio tasks | RQ / Celery / Dramatiq | Require Redis/RabbitMQ; added infrastructure; Cloud Run background tasks are sufficient for 6-minute jobs |

## Installation

### Python Pipeline

```bash
cd /Users/bobby/Documents/GitHub/Allied-FeedOps

# New dependencies for v1.0 (add to pyproject.toml)
uv pip install tenacity==9.1.4
uv pip install aiolimiter==1.2.1
uv pip install structlog>=24.5.0
uv pip install prometheus-client==0.21.1

# Update pyproject.toml
# [project]
# dependencies = [
#   ...existing...
#   "tenacity>=9.1.4",
#   "aiolimiter>=1.2.1",
#   "structlog>=24.5.0",
#   "prometheus-client>=0.21.1",
# ]
```

### Dashboard

```bash
cd dashboard

# Dashboard visualization (new for v1.0)
npm install @tremor/react@latest

# Already installed (no action needed):
# - recharts@3.7.0
# - zustand@5.0.11
# - @tanstack/react-query@5.90.20
```

## Integration Points with Existing Stack

### 1. FastAPI Endpoints (main.py)
- **Current**: Single SKU optimization, basic batch creation
- **Add**: Batch orchestration with asyncio.gather, progress tracking, SSE streaming
- **Compatibility**: Extends existing `run_async_in_thread()` pattern; no breaking changes

### 2. Google Ads API Integration
- **Current**: Basic API calls in `src/feedops/integrations/google_ads_*.py`
- **Add**: Tenacity retry decorators, aiolimiter rate limiting
- **Compatibility**: Wrap existing functions; backward compatible

### 3. Database (Supabase)
- **Current**: Supabase client via REST API
- **Add**: Pydantic validation models for batch writes, optional asyncpg for bulk inserts
- **Compatibility**: Supabase pooler handles connection limits; no schema changes

### 4. Logging (main.py:76-80)
- **Current**: Basic logging with stdlib logging
- **Migration**: Replace with structlog; keeps same log levels
- **Breaking**: Log format changes from text to JSON (better for Cloud Logging)

### 5. Dashboard (Next.js)
- **Current**: Recharts for charts, custom components
- **Add**: Tremor for pre-built dashboard components, SSE for real-time updates
- **Compatibility**: Tremor builds on Recharts; coexist peacefully

### 6. Observability (main.py:112-141)
- **Current**: Request ID middleware, basic metrics
- **Extend**: Prometheus metrics, structlog context propagation
- **Compatibility**: Enhances existing middleware; no conflicts

## Anti-Patterns to Avoid

### 1. Don't Add a Full Orchestration Framework
**Anti-Pattern**: Install Airflow/Prefect for batch jobs
**Why Bad**: Requires separate deployment, DAG-centric design doesn't fit API-triggered batches, overkill for 2,784 SKUs
**Instead**: Use asyncio.gather with Semaphore for concurrency control

### 2. Don't Use Synchronous Batch Processing
**Anti-Pattern**: Process 2,784 SKUs sequentially in a loop
**Why Bad**: 2,784 SKUs × 6 min/SKU = 278 hours (11+ days)
**Instead**: Async batch processing with 10 concurrent SKUs = 28 hours (achievable)

### 3. Don't Ignore Rate Limits Until They Hit
**Anti-Pattern**: Blast Google Ads API, catch RESOURCE_TEMPORARILY_EXHAUSTED, sleep 60s
**Why Bad**: Wastes quota, unpredictable latency, triggers account review
**Instead**: Proactive rate limiting with aiolimiter (5 req/sec per CID)

### 4. Don't Validate Everything in the Database
**Anti-Pattern**: Add 50+ check constraints for complex business rules
**Why Bad**: Poor error messages, hard to debug, coupling logic to schema
**Instead**: Database for simple constraints (NOT NULL, CHECK > 0), Pydantic for complex validation

### 5. Don't Build Custom Dashboard Components
**Anti-Pattern**: Hand-code KPI cards, progress bars, data tables from scratch
**Why Bad**: Weeks of dev time, inconsistent styling, maintenance burden
**Instead**: Use Tremor's pre-built components (30+ components, Tailwind-integrated)

### 6. Don't Poll Every Second for Progress
**Anti-Pattern**: `setInterval(() => fetch('/batch-status'), 1000)`
**Why Bad**: Hammers API, wastes Cloud Run CPU, delays scale-to-zero
**Instead**: Use SSE for server-push updates or poll every 5-10 seconds

### 7. Don't Mix Pydantic v1 and v2
**Anti-Pattern**: Keep some models on v1 (`from pydantic.v1 import BaseModel`)
**Why Bad**: Confusing, dual validation logic, performance penalty
**Instead**: Migrate fully to v2 (already in pyproject.toml; ensure all code uses v2)

### 8. Don't Use WebSockets for One-Way Data
**Anti-Pattern**: Implement Socket.IO for batch progress updates
**Why Bad**: Overkill for server→client streaming, harder to debug, needs connection management
**Instead**: Use SSE (simpler, built-in browser support, auto-reconnect)

### 9. Don't Store Logs in Database
**Anti-Pattern**: `INSERT INTO batch_logs (level, message, timestamp) VALUES (...)`
**Why Bad**: Database bloat, slow queries, hard to search/aggregate
**Instead**: Use Cloud Logging (auto-ingestion from Cloud Run), query with Log Explorer

### 10. Don't Retry Non-Retryable Errors
**Anti-Pattern**: Retry all exceptions 5 times
**Why Bad**: Wastes time on permanent failures (missing SKU, auth errors)
**Instead**: Classify errors (retryable vs permanent), use `retry_if_exception_type(RetryableAPIError)`

## Configuration Example

### Environment Variables (.env.vercel)
```bash
# Existing variables (no changes)
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
GOOGLE_ADS_DEVELOPER_TOKEN=...

# New: Rate limiting config
GOOGLE_ADS_QPS_LIMIT=5  # Queries per second per CID
BATCH_CONCURRENCY=10     # Max concurrent SKUs

# New: Batch job config
BATCH_SIZE=10            # SKUs per batch
BACKFILL_DAYS=180        # Historical data window
```

### Feature Flags (optional)
```python
# In runtime_controls.py (already exists)
ENABLE_BATCH_BACKFILL = os.getenv('ENABLE_BATCH_BACKFILL', 'true').lower() == 'true'
ENABLE_PROMETHEUS_METRICS = os.getenv('ENABLE_PROMETHEUS_METRICS', 'true').lower() == 'true'
```

## Migration Path

### Phase 1: Validation & Error Handling (Week 1)
1. Add tenacity, aiolimiter to pyproject.toml
2. Create Pydantic validation models in `src/feedops/validation/`
3. Wrap Google Ads API calls with retry decorators
4. Test with single SKU

### Phase 2: Async Batch Processing (Week 2)
1. Refactor batch job to use asyncio.gather + Semaphore
2. Add rate limiting with aiolimiter
3. Test with 50 SKU batch

### Phase 3: Observability (Week 2)
1. Replace logging with structlog
2. Add Prometheus metrics endpoint
3. Set up GCP Logging alerts for errors

### Phase 4: Dashboard (Week 3)
1. Install Tremor
2. Build backfill dashboard page with progress KPIs
3. Add SSE for real-time updates (optional)

### Phase 5: Full Backfill (Week 4)
1. Run 180-day backfill for 2,784 SKUs
2. Monitor metrics, adjust concurrency/rate limits
3. Validate data completeness

## Sources

**Batch Orchestration**:
- [Top 17 Data Orchestration Tools for 2026](https://lakefs.io/blog/data-orchestration-tools/)
- [Python Workflow Framework: 4 Orchestration Tools to Know](https://www.advsyscon.com/blog/workload-orchestration-tools-python/)
- [Cloud Run Jobs & Scheduler](https://medium.com/@markwkiehl/google-cloud-run-jobs-scheduler-22a4e9252cf0)
- [Cloud Tasks Python App Engine: Queues Routing 2026](https://johal.in/cloud-tasks-python-app-engine-queues-routing-2026/)

**Error Handling & Retry**:
- [Retry Failed Python Requests in 2026](https://decodo.com/blog/python-requests-retry)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)
- [API Error Handling & Retry Strategies: Python Guide 2026](https://easyparser.com/blog/api-error-handling-retry-strategies-python-guide)
- [Google Ads API Rate Limits Best Practices](https://developers.google.com/google-ads/api/docs/productionize/rate-limits)

**Data Validation**:
- [The data validation landscape in 2025](https://aeturrell.com/blog/posts/the-data-validation-landscape-in-2025/)
- [Exploring Data Quality Frameworks](https://www.perarduaconsulting.com/post/exploring-data-quality-frameworks-great-expectations-pandas-profiling-and-pydantic-in-python)
- [Pydantic v2 Migration Guide](https://docs.pydantic.dev/latest/migration/)

**Async & Rate Limiting**:
- [AsyncIO Rate Limiter Documentation](https://asynciolimiter.readthedocs.io/)
- [Limiting concurrency in Python asyncio](https://death.andgravity.com/limit-concurrency)
- [Python asyncio: Complete Guide 2026](https://devtoolbox.dedyn.io/blog/python-asyncio-complete-guide)

**Observability**:
- [Structured Logging in Python using Loguru](https://www.soumendrak.com/series/practical-observability-with-python/structured-logging/)
- [Structlog ContextVars: Python Async Logging 2026](https://johal.in/structlog-contextvars-python-async-logging-2026/)
- [From Chaos to Clarity: Structured Logging on GCP](https://www.waltlabs.io/blog/structured-logging-in-python-on-gcp)
- [Supabase Metrics API](https://supabase.com/docs/guides/telemetry/metrics)

**Dashboard Visualization**:
- [Using Next.js and Tremor for charts](https://www.erichowey.dev/writing/using-nextjs-tremor-for-charts-graphs-data-visualization/)
- [Tremor React UI Components](https://www.tremor.so/)
- [Building a Real-Time Dashboard with Next.js and Chart.js](https://cloudactivelabs.com/en/blog/building-a-real-time-dashboard-with-nextjs-and-chartjs)
- [React Chart Libraries Comparison](https://www.kylegill.com/essays/react-chart-libraries)
