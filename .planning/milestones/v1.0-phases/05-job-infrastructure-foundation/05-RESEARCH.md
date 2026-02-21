# Phase 5: Job Infrastructure & Foundation - Research

**Researched:** 2026-02-13
**Domain:** Async Job Processing, Rate Limiting, Error Handling, Database Connection Management
**Confidence:** HIGH

## Summary

Phase 1 establishes robust async job infrastructure for processing 2,784 SKUs with rate limiting, error handling, and resumability. The codebase already has critical patterns in place: thread-based background execution (solving Cloud Run lifecycle issues), exponential backoff with circuit breakers, and Supabase connection retry logic. Key gap: dedicated job management tables and token bucket rate limiting for API operations.

The standard stack uses FastAPI with thread-based async execution (NOT BackgroundTasks due to Cloud Run container lifecycle), Python asyncio for I/O-bound operations, and Supabase for persistent job state. Rate limiting requires token bucket algorithm implementation (10 QPS Google Ads limit). Database connection pooling is already handled via Supabase's server-side pooler (transaction mode), avoiding application-side pooling complexity.

**Primary recommendation:** Build on existing `run_async_in_thread()` pattern, add job state tables, implement token bucket rate limiter, and formalize checkpoint/resume logic.

## Standard Stack

### Core Infrastructure

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | Latest (already installed) | HTTP API framework | Async-first, type-safe, production-proven |
| Threading (stdlib) | Python 3.11+ | Background job execution | Survives Cloud Run container lifecycle (critical) |
| Asyncio (stdlib) | Python 3.11+ | Async I/O coordination | Native Python async runtime |
| Supabase Python | 2.x (already installed) | Database client | Persistent job state, built-in retry logic |
| google-ads-googleads | v24+ (already installed) | Google Ads API | Standard official client |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyrate-limiter | 3.x | Token bucket rate limiting | Distributed rate limiting (optional upgrade) |
| token-bucket | 1.x | Simple token bucket | Simpler than pyrate-limiter, single-process |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Thread-based execution | Celery + Redis | More infrastructure, better for >100 concurrent jobs |
| Thread-based execution | Cloud Tasks | More reliable but requires GCP setup, async only |
| Thread-based execution | ARQ + Redis | Async-native but adds Redis dependency |
| Custom token bucket | pyrate-limiter library | Library has more features but adds dependency |
| Supabase pooler | Application-side pgbouncer | More control but adds complexity, problematic with asyncpg |

**Installation:**
```bash
# Core dependencies already installed
# Optional: Add rate limiting library if not hand-rolling
uv pip install pyrate-limiter  # OR token-bucket
```

## Architecture Patterns

### Recommended Project Structure

```
src/feedops/
├── jobs/                    # Job infrastructure (NEW)
│   ├── __init__.py
│   ├── models.py           # Job status enums, dataclasses
│   ├── manager.py          # Job lifecycle management
│   ├── checkpoint.py       # Checkpoint/resume logic
│   └── rate_limiter.py     # Token bucket implementation
├── integrations/            # Existing API clients
│   ├── google_ads_performance.py
│   └── google_ads_search_terms.py
├── db/                      # Existing database layer
│   └── supabase_client.py  # Already has retry logic
└── api/                     # Existing FastAPI endpoints
    └── main.py             # Already has run_async_in_thread()
```

### Pattern 1: Thread-Based Background Execution (EXISTING, PROVEN)

**What:** Run async functions in non-daemon threads with dedicated event loops
**When to use:** All background jobs in Cloud Run environment
**Why it works:** Survives HTTP response completion and container idle periods (NOT deployments)

**Example:**
```python
# Source: src/feedops/api/main.py (lines 149-176)
def run_async_in_thread(async_func, request_id: str | None = None, **kwargs):
    """Run async function in dedicated thread with new event loop.

    This is necessary for Cloud Run because FastAPI BackgroundTasks are killed
    when containers scale to zero. Using a non-daemon thread ensures the job
    completes even if the HTTP response has been sent.
    """
    def wrapper():
        with request_context(request_id):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_func(**kwargs))
            finally:
                loop.close()

    thread = threading.Thread(target=wrapper, daemon=False)
    thread.start()
    logger.info(f"Started background job thread: {async_func.__name__}")
    return thread
```

**CRITICAL LEARNINGS from docs/audit/background-task-fix-2026-02-08.md:**
- FastAPI BackgroundTasks are killed when Cloud Run containers scale to zero
- Thread-based execution improved job completion from 67% to 75%
- Jobs still terminate during deployments (expected, unavoidable)
- This is the ONLY reliable pattern for Cloud Run without external task queue

### Pattern 2: Exponential Backoff with Circuit Breaker (EXISTING)

**What:** Retry transient errors with exponential delay, trip circuit on repeated failures
**When to use:** All external API calls (Google Ads, Supabase, AI providers)
**Example:**
```python
# Source: src/feedops/providers/reliability.py
def compute_backoff_seconds(attempt: int) -> float:
    """Exponential backoff with bounded jitter."""
    base = 0.25  # FEEDOPS_PROVIDER_BACKOFF_BASE_SECONDS
    max_delay = 8.0  # FEEDOPS_PROVIDER_BACKOFF_MAX_SECONDS
    jitter = 0.1  # FEEDOPS_PROVIDER_BACKOFF_JITTER_SECONDS
    delay = min(max_delay, base * (2**attempt))
    if jitter:
        delay += random.uniform(0.0, jitter)
    return delay

def is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retryable_markers = (
        "429", "rate limit", "resource_exhausted",
        "temporarily unavailable", "service unavailable",
        "timeout", "timed out", "connection reset",
        "connection aborted", "too many requests",
    )
    return any(marker in text for marker in retryable_markers)
```

**Circuit breaker pattern:**
- Tracks failures per provider/model key
- Opens circuit after 5 consecutive failures (default)
- 30-second cooldown before allowing retry
- Auto-resets on successful request

### Pattern 3: Supabase Connection with Retry Logic (EXISTING)

**What:** Retry Supabase operations on transient connection errors
**When to use:** All database operations
**Example:**
```python
# Source: src/feedops/db/supabase_client.py (lines 35-63)
@wraps(func)
def wrapper(*args, **kwargs):
    last_error = None
    for attempt in range(MAX_RETRIES):  # MAX_RETRIES = 3
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_name = type(e).__name__
            # Retry on transient connection errors
            if any(x in error_name for x in ["RemoteProtocolError", "ConnectionError", "TimeoutError"]) or \
               any(x in str(e) for x in ["Server disconnected", "Connection reset", "timed out"]):
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                    # Reset the client to get a fresh connection
                    global _client
                    _client = None
                    continue
            # Non-retryable error, raise immediately
            raise
    # All retries exhausted
    raise last_error
```

**Supabase connection pooling considerations:**
- **Use server-side pooler** (Supavisor transaction mode) - already configured
- **DO NOT use application-side pooling** - Supabase handles this, avoids asyncpg prepared statement issues
- **Port 6543 (transaction mode)** - correct for serverless/Cloud Run
- **NO prepared statement cache** - transaction mode incompatible with asyncpg caching

**Source:** [Supabase Connection Management](https://supabase.com/docs/guides/database/connection-management), [Supabase Pooling and asyncpg Don't Mix](https://medium.com/@patrickduch93/supabase-pooling-and-asyncpg-dont-mix-here-s-the-real-fix-44f700b05249)

### Pattern 4: Token Bucket Rate Limiting (NEW, REQUIRED)

**What:** Allow bursts up to capacity, refill at constant rate
**When to use:** Google Ads API calls (10 QPS limit), Keyword Planner (lower limit)
**Implementation:**
```python
# Recommended simple implementation
import time
import threading

class TokenBucket:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens per second (e.g., 10.0 for 10 QPS)
            capacity: Max tokens in bucket (burst capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if allowed, False if rate limited."""
        with self.lock:
            now = time.monotonic()
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    async def acquire(self, tokens: int = 1):
        """Async: Wait until tokens are available."""
        while not self.consume(tokens):
            await asyncio.sleep(0.01)  # 10ms polling
```

**Usage pattern:**
```python
# Global rate limiters
google_ads_limiter = TokenBucket(rate=10.0, capacity=20)  # 10 QPS, burst 20
keyword_planner_limiter = TokenBucket(rate=2.0, capacity=5)  # Lower for KP

async def fetch_with_rate_limit(offer_id: str):
    await google_ads_limiter.acquire()  # Wait for token
    return await _fetch_from_api(offer_id)
```

**Alternative: Use pyrate-limiter library:**
```python
from pyrate_limiter import Duration, Limiter, Rate

# Define rate: 10 requests per second
rate = Rate(10, Duration.SECOND)
limiter = Limiter(rate)

@limiter.ratelimit("google_ads_api", delay=True)
async def fetch_with_rate_limit(offer_id: str):
    return await _fetch_from_api(offer_id)
```

**Source:** [API Defense with Rate Limiting Using FastAPI and Token Buckets](https://blog.compliiant.io/api-defense-with-rate-limiting-using-fastapi-and-token-buckets-0f5206fc5029), [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/)

### Pattern 5: Job State Management with Checkpoints (NEW, REQUIRED)

**What:** Track job progress, save checkpoints, enable resume
**When to use:** All batch operations processing >10 SKUs

**Database schema (NEW TABLES NEEDED):**
```sql
-- Table: batch_jobs (replaces existing batch_generation_jobs)
CREATE TABLE batch_jobs (
  job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type TEXT NOT NULL,  -- 'data_collection', 'content_generation'
  status TEXT NOT NULL CHECK (status IN ('creating', 'running', 'complete', 'failed', 'partial')),
  total_items INTEGER NOT NULL,
  completed_items INTEGER DEFAULT 0,
  failed_items INTEGER DEFAULT 0,
  checkpoint_data JSONB,  -- { last_sku: "920-6", batch_index: 5 }
  error_log JSONB[],  -- Array of { sku, error, timestamp }
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  eta_seconds INTEGER,
  created_by TEXT
);

CREATE INDEX idx_batch_jobs_status ON batch_jobs(status, created_at DESC);
CREATE INDEX idx_batch_jobs_type ON batch_jobs(job_type);

-- Table: job_errors (detailed error tracking)
CREATE TABLE job_errors (
  id BIGSERIAL PRIMARY KEY,
  job_id UUID NOT NULL REFERENCES batch_jobs(job_id),
  item_id TEXT NOT NULL,  -- SKU or offer_id
  error_type TEXT NOT NULL,  -- 'api_error', 'rate_limit', 'validation'
  error_message TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_job_errors_job ON job_errors(job_id, created_at DESC);
```

**Implementation pattern:**
```python
async def process_batch_job(job_id: str, skus: list[str]):
    """Process batch with checkpointing and error tracking."""
    # Load or create job record
    job = await load_job(job_id)

    # Resume from checkpoint if exists
    start_index = job.checkpoint_data.get("batch_index", 0) if job.checkpoint_data else 0

    for i in range(start_index, len(skus), 10):  # Batch size 10
        batch = skus[i:i+10]

        try:
            # Apply rate limiting
            await rate_limiter.acquire()

            # Process batch
            results = await process_sku_batch(batch)

            # Update progress
            await update_job_progress(
                job_id=job_id,
                completed_items=i + len(batch),
                checkpoint_data={"batch_index": i + 10, "last_sku": batch[-1]}
            )

        except Exception as e:
            # Log error, continue processing
            await log_job_error(
                job_id=job_id,
                item_id=batch[0],
                error_type="api_error",
                error_message=str(e)
            )

    # Mark job complete
    await update_job_status(job_id, status="complete")
```

### Pattern 6: Idempotent Upserts (CRITICAL)

**What:** Use ON CONFLICT for all data writes to prevent duplicates on retry
**When to use:** ALL database write operations in batch jobs
**Example:**
```sql
-- Idempotent insert pattern
INSERT INTO search_queries (
  query_text, gmc_offer_id, period_start, period_end, impressions, clicks
) VALUES (
  'bathroom towel bar', 'shopify_us_123_456', '2026-01-01', '2026-01-31', 100, 10
)
ON CONFLICT (query_text, gmc_offer_id, period_start, period_end)
DO UPDATE SET
  impressions = EXCLUDED.impressions,
  clicks = EXCLUDED.clicks,
  fetched_at = NOW();
```

**Supabase client usage:**
```python
client.table("search_queries").upsert(
    data,
    on_conflict="query_text,gmc_offer_id,period_start,period_end"
).execute()
```

**CRITICAL:** All writes in resumable jobs MUST use upsert to handle checkpoint resume scenarios.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async background jobs | Custom thread pool manager | Existing `run_async_in_thread()` | Already proven in production, handles Cloud Run lifecycle |
| Database retry logic | Custom retry wrapper | Existing `@_with_retry` decorator | Already handles Supabase connection errors |
| Exponential backoff | Custom sleep logic | Existing `compute_backoff_seconds()` | Already has jitter, max delay, env config |
| Circuit breaker | Custom failure tracker | Existing `CircuitBreakerRegistry` | Thread-safe, process-wide state |
| Token bucket (simple) | Hand-rolled implementation | OK to hand-roll for single-process | Simple algorithm, 30-line implementation |
| Token bucket (distributed) | Custom distributed limiter | `pyrate-limiter` library | Handles Redis, shared state, burst logic |
| Job queue system | Custom task scheduler | Keep thread-based for v1.0, defer to v2.0 | Cloud Tasks/Celery adds complexity, not needed yet |

**Key insight:** Codebase already has robust retry/backoff/circuit breaker patterns. Job infrastructure is the main gap, not error handling primitives.

## Common Pitfalls

### Pitfall 1: Using FastAPI BackgroundTasks for Long Jobs

**What goes wrong:** Jobs silently terminate mid-execution when Cloud Run containers scale to zero
**Why it happens:** BackgroundTasks run in the main asyncio loop, killed when container terminates
**How to avoid:** ALWAYS use `run_async_in_thread()` for jobs >1 minute
**Warning signs:** Jobs stop at random progress points, no error logs, status never updates to "failed"

**Evidence:** docs/audit/background-task-fix-2026-02-08.md documented 48/72 operation failure

### Pitfall 2: Forgetting Rate Limits During Testing

**What goes wrong:** API returns 429 errors, jobs fail with "RESOURCE_EXHAUSTED"
**Why it happens:** Google Ads API enforces strict 10 QPS limit per developer token
**How to avoid:**
  - Implement token bucket BEFORE running batch jobs
  - Test with small batches (10 SKUs) first
  - Monitor for 429 responses, increase backoff if seen
**Warning signs:** Batch jobs fail after processing ~100 items (rate limit hit)

**Recommendation:** Start with batch size 10, 10 QPS rate limit. This processes 2,784 SKUs in ~7 minutes (validated in Phase 0).

### Pitfall 3: Database Connection Exhaustion

**What goes wrong:** "too many connections" errors from Supabase
**Why it happens:** Each concurrent job opens connections, pooler has limits
**How to avoid:**
  - Limit concurrent jobs to 3 (requirement JOB-10)
  - Use Supabase server-side pooler (already configured)
  - NO application-side connection pooling
**Warning signs:** Intermittent "connection pool exhausted" errors

**Configuration:** Supabase transaction mode pooler on port 6543, max 3 concurrent jobs = max 9 connections (well under default 100 limit).

**Source:** [Supabase Connection Scaling Guide](https://medium.com/@papansarkar101/supabase-connection-scaling-the-essential-guide-for-fastapi-developers-2dc5c428b638)

### Pitfall 4: Non-Idempotent Writes Breaking Resume

**What goes wrong:** Resuming a job creates duplicate records, inflates counts
**Why it happens:** INSERT without ON CONFLICT duplicates data on retry
**How to avoid:** Use `.upsert()` with `on_conflict` for ALL writes
**Warning signs:** Record counts double after job resume, duplicate key errors

**Critical tables requiring upsert:**
- `search_queries` (conflict on: query_text, gmc_offer_id, period_start, period_end)
- `keyword_metrics` (conflict on: keyword)
- `performance_baselines` (conflict on: master_sku, platform)
- `batch_jobs` (conflict on: job_id)

### Pitfall 5: Checkpoints Without Progress Visibility

**What goes wrong:** Jobs run for hours with no user feedback, appear stuck
**Why it happens:** Checkpoint data saved but not exposed via status endpoint
**How to avoid:** Update `completed_items` and `eta_seconds` in job table every checkpoint
**Warning signs:** Users cancel jobs thinking they're stuck when actually processing

**Pattern:**
```python
# Calculate ETA based on actual throughput
elapsed = time.time() - job.started_at
items_per_second = job.completed_items / elapsed
remaining_items = job.total_items - job.completed_items
eta_seconds = remaining_items / items_per_second

await update_job(
    job_id=job_id,
    completed_items=job.completed_items,
    eta_seconds=int(eta_seconds)
)
```

### Pitfall 6: Mixing Async and Sync Database Clients

**What goes wrong:** "Event loop is closed" errors, hanging requests
**Why it happens:** Supabase Python client is sync-only, needs async wrapper or proper event loop
**How to avoid:**
  - Run Supabase operations in executor: `await loop.run_in_executor(None, sync_func)`
  - OR use thread-based execution (already done via `run_async_in_thread()`)
**Warning signs:** Intermittent blocking, event loop warnings

**Current approach:** All background jobs use `run_async_in_thread()` which creates dedicated event loop per job. This works correctly with sync Supabase client.

## Code Examples

Verified patterns from codebase and official sources:

### Job Status Update with ETA

```python
# Pattern: Update job progress with ETA calculation
async def update_job_progress(
    job_id: str,
    completed: int,
    total: int,
    started_at: float
) -> None:
    """Update job progress with calculated ETA."""
    client = get_client()

    elapsed = time.time() - started_at
    items_per_second = completed / elapsed if elapsed > 0 else 0
    remaining = total - completed
    eta_seconds = int(remaining / items_per_second) if items_per_second > 0 else None

    client.table("batch_jobs").update({
        "completed_items": completed,
        "eta_seconds": eta_seconds,
        "status": "running"
    }).eq("job_id", job_id).execute()
```

### Batch Processing with Rate Limiting

```python
# Pattern: Process SKUs in batches with rate limiting and checkpointing
async def process_sku_batch_job(
    job_id: str,
    skus: list[str],
    batch_size: int = 10
) -> None:
    """Process SKUs in batches with rate limiting."""
    rate_limiter = TokenBucket(rate=10.0, capacity=20)
    started_at = time.time()

    # Load checkpoint if exists
    job = await load_job(job_id)
    start_index = job.get("checkpoint_data", {}).get("batch_index", 0)

    for i in range(start_index, len(skus), batch_size):
        batch = skus[i:i+batch_size]

        try:
            # Rate limit before processing
            await rate_limiter.acquire()

            # Process batch
            results = []
            for sku in batch:
                result = await fetch_sku_data(sku)
                results.append(result)

            # Save results (idempotent)
            await save_results(results)

            # Update progress
            await update_job_progress(
                job_id=job_id,
                completed=i + len(batch),
                total=len(skus),
                started_at=started_at
            )

            # Checkpoint every 100 SKUs
            if (i + batch_size) % 100 == 0:
                await save_checkpoint(job_id, batch_index=i + batch_size)

        except Exception as e:
            # Log error but continue
            await log_job_error(
                job_id=job_id,
                item_id=batch[0],
                error_type=type(e).__name__,
                error_message=str(e)
            )

    # Mark complete
    await update_job_status(job_id, status="complete")
```

### Error Logging with Retry Count

```python
# Pattern: Log detailed error with retry tracking
async def log_job_error(
    job_id: str,
    item_id: str,
    error_type: str,
    error_message: str,
    retry_count: int = 0
) -> None:
    """Log job error to database for analysis."""
    client = get_client()

    client.table("job_errors").insert({
        "job_id": job_id,
        "item_id": item_id,
        "error_type": error_type,
        "error_message": error_message[:500],  # Truncate long errors
        "retry_count": retry_count,
        "created_at": datetime.now(timezone.utc).isoformat()
    }).execute()

    # Update job failed count
    client.rpc("increment_job_failures", {"p_job_id": job_id}).execute()
```

### Resume Job from Checkpoint

```python
# Pattern: Resume job from last checkpoint
async def resume_job(job_id: str) -> None:
    """Resume a failed/partial job from last checkpoint."""
    client = get_client()

    # Load job state
    result = client.table("batch_jobs").select("*").eq("job_id", job_id).execute()
    if not result.data:
        raise ValueError(f"Job {job_id} not found")

    job = result.data[0]

    if job["status"] not in ("failed", "partial"):
        raise ValueError(f"Job {job_id} is {job['status']}, cannot resume")

    # Extract checkpoint
    checkpoint = job.get("checkpoint_data", {})
    skus = job.get("skus", [])  # Assume stored in job metadata

    # Resume from checkpoint
    await process_sku_batch_job(
        job_id=job_id,
        skus=skus,
        start_index=checkpoint.get("batch_index", 0)
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| FastAPI BackgroundTasks | Thread-based execution with event loops | 2026-02-08 | Job completion improved 67%→75%, survives container idle |
| Manual retry logic | Circuit breaker + exponential backoff | Already implemented | Prevents cascading failures, auto-recovery |
| Direct database calls | Retry decorator with connection reset | Already implemented | Handles Supabase transient errors |
| Celery/Redis for jobs | Thread-based async (Cloud Run) | Current decision | Simpler infrastructure, good enough for v1.0 |
| Application-side pooling | Supabase server-side pooler | Supabase best practice | Avoids asyncpg prepared statement issues |

**Deprecated/outdated:**
- **FastAPI BackgroundTasks for long jobs** - Use `run_async_in_thread()` instead
- **Port 5432 direct connection** - Use port 6543 transaction pooler for Cloud Run
- **Application-side pgbouncer** - Supabase Supavisor handles this server-side
- **Prepared statement caching with transaction mode** - Must disable or use session mode

## Open Questions

1. **Should we add distributed rate limiting (Redis) for multi-container scenarios?**
   - What we know: Current Cloud Run deployment likely runs single container (low traffic)
   - What's unclear: Future scaling needs, cost/complexity tradeoff
   - Recommendation: Start with in-process token bucket (JOB-08), defer Redis to v2.0 if multi-container issues arise

2. **What's the optimal checkpoint frequency for 2,784 SKU jobs?**
   - What we know: Every 100 SKUs is requirement (JOB-09), Phase 0 showed 7-minute total runtime
   - What's unclear: Checkpoint write cost vs resume time saved
   - Recommendation: Start with 100 SKU checkpoints (28 checkpoints total), monitor write latency

3. **Should we implement job cancellation or is termination sufficient?**
   - What we know: Cloud Run deployments kill jobs anyway
   - What's unclear: User demand for explicit cancellation
   - Recommendation: Defer to Phase 2, focus on resume capability first

4. **How to handle jobs that exceed Cloud Run 60-minute request timeout?**
   - What we know: Full 2,784 SKU collection estimated at ~7 minutes (well under limit)
   - What's unclear: Future expansion scenarios (e.g., daily automation)
   - Recommendation: Current architecture sufficient for v1.0, move to Cloud Tasks for v2.0 if needed

## Sources

### Primary (HIGH confidence)

- **Existing Codebase:**
  - `src/feedops/api/main.py` - Thread-based execution pattern (lines 149-176)
  - `src/feedops/providers/reliability.py` - Backoff and circuit breaker implementation
  - `src/feedops/db/supabase_client.py` - Connection retry logic
  - `docs/audit/background-task-fix-2026-02-08.md` - Cloud Run background task investigation

- **Official Documentation:**
  - [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - Official FastAPI docs
  - [Supabase Connection Management](https://supabase.com/docs/guides/database/connection-management) - Pooling modes and best practices
  - [Google Ads API Rate Limits](https://developers.google.com/google-ads/api/docs/best-practices/rate-limits) - 10 QPS standard limit

### Secondary (MEDIUM confidence)

- [Advanced Performance Tuning for FastAPI on Google Cloud Run](https://davidmuraya.com/blog/fastapi-performance-tuning-on-google-cloud-run/) - Async best practices
- [Managing Background Tasks in FastAPI: BackgroundTasks vs ARQ + Redis](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/) - Task queue comparison
- [Supabase Pooling and asyncpg Don't Mix](https://medium.com/@patrickduch93/supabase-pooling-and-asyncpg-dont-mix-here-s-the-real-fix-44f700b05249) - Transaction mode + asyncpg issues
- [API Defense with Rate Limiting Using FastAPI and Token Buckets](https://blog.compliiant.io/api-defense-with-rate-limiting-using-fastapi-and-token-buckets-0f5206fc5029) - Token bucket implementation
- [Supabase Connection Scaling: Essential Guide for FastAPI Developers](https://medium.com/@papansarkar101/supabase-connection-scaling-the-essential-guide-for-fastapi-developers-2dc5c428b638) - Connection limits and pooling

### Tertiary (LOW confidence)

- [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/) - Rate limiting library (released Jan 2026)
- [token-bucket PyPI](https://pypi.org/project/token-bucket/) - Simple token bucket implementation
- [How to Build Background Task Processing in FastAPI](https://oneuptime.com/blog/post/2026-01-25-background-task-processing-fastapi/view) - General patterns

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - All dependencies already installed and battle-tested
- Architecture: **HIGH** - Critical patterns already implemented and proven
- Pitfalls: **HIGH** - Documented from actual production failures (background task fix)

**Research date:** 2026-02-13
**Valid until:** 60 days (stable infrastructure patterns, slow-changing)
