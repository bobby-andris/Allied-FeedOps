# Phase 08: Monitoring & Automation - Research

**Researched:** 2026-02-13
**Domain:** Production observability, alerting, scheduling, incremental data sync
**Confidence:** HIGH

## Summary

Phase 8 adds production-grade monitoring and automation on top of the completed job infrastructure (Phases 5-7). The system currently has job tracking, batch processing, and data collection in place, but lacks real-time visibility, automated recovery, and ongoing sync mechanisms.

This phase addresses three critical gaps: **observability** (knowing what's happening), **alerting** (being notified when things break), and **automation** (running jobs without manual intervention). The recommended approach leverages GCP's native tooling (Cloud Scheduler, Cloud Monitoring, Cloud Logging) rather than external services, minimizing operational complexity and cost.

**Primary recommendation:** Build dashboard UI with real-time job monitoring, wire Cloud Monitoring alert policies with Slack/email channels, and configure Cloud Scheduler to trigger incremental refresh jobs daily. Use existing Prometheus metrics infrastructure and structured logging to enable observability without adding new dependencies.

## Standard Stack

### Core (Already Installed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **FastAPI** | 0.115.5 | HTTP endpoints for monitoring APIs | Already in stack; existing `/backfill/status` endpoints |
| **Prometheus client** | 0.21.1 | Metrics export | Already in STACK.md; existing metrics_registry in use |
| **Python logging** | stdlib | Structured logging | Already configured with JSON output for Cloud Logging |
| **Next.js** | 15.x | Dashboard UI | Already in stack; existing monitoring page at `/monitoring` |
| **Supabase client** | Latest | Database queries for job status | Already in use across all phases |

### Supporting (New for Phase 8)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Tremor** | 3.21.0+ | Pre-built dashboard components | KPI cards, progress bars, data tables for backfill dashboard |
| **GCP Cloud Scheduler** | Native | Cron job scheduling | Daily incremental refresh triggers |
| **GCP Cloud Monitoring** | Native | Alert policy configuration | Job failure alerts, error rate thresholds |
| **Slack incoming webhooks** | Native | Slack notifications | Job completion/failure messages |
| **Resend** or **SendGrid** | Cloud API | Email notifications | Alternative to GCP's email delivery |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| GCP Cloud Scheduler | Cron in Cloud Run | Cloud Run containers scale to zero; cron won't run |
| GCP Cloud Monitoring | Datadog / New Relic | Adds $50-200/mo cost; overkill for 1 service |
| Tremor dashboard components | Hand-rolled React components | Weeks of dev time; Tremor provides 30+ components |
| Slack webhooks | PagerDuty / Opsgenie | Adds on-call rotation features not needed yet |
| Prometheus + Grafana Cloud | Cloud Monitoring dashboards | Grafana requires separate hosting/maintenance |

**Installation:**
```bash
# Dashboard (Tremor for monitoring UI)
cd dashboard
npm install @tremor/react@latest

# No Python dependencies (all observability features already in stack)
```

## Architecture Patterns

### Recommended Project Structure
```
src/feedops/
├── api/
│   ├── main.py                    # Existing: /backfill/* endpoints
│   └── monitoring.py              # NEW: /monitoring/* endpoints (health, metrics summary)
├── jobs/
│   ├── manager.py                 # Existing: Job CRUD operations
│   ├── processor.py               # Existing: Batch processing
│   ├── scheduler.py               # NEW: Incremental refresh trigger logic
│   └── health.py                  # NEW: System health checks
├── observability/
│   ├── __init__.py               # Existing: request_context, log_event
│   ├── metrics.py                # Existing: MetricsRegistry
│   └── alerts.py                 # NEW: Alert helpers (format messages, call webhooks)
└── quality/
    └── review_dashboard.py        # Existing: Quality reports

dashboard/src/
├── app/(dashboard)/
│   ├── monitoring/
│   │   └── page.tsx              # Existing: Performance/search delta monitoring
│   └── backfill/                 # NEW: Backfill job dashboard
│       ├── page.tsx              # Job list, active jobs, coverage metrics
│       └── [jobId]/
│           └── page.tsx          # Job detail page with progress
├── app/api/
│   ├── monitoring/               # Existing: performance-delta, search-delta APIs
│   └── backfill/                 # NEW: Proxy to Python /backfill/* endpoints
│       ├── jobs/route.ts         # List jobs
│       ├── [jobId]/route.ts      # Job status
│       └── start/route.ts        # Start new job
└── components/
    └── backfill/                 # NEW: Backfill-specific UI components
        ├── JobStatusCard.tsx     # Tremor card with progress
        ├── CoverageHeatmap.tsx   # Data freshness visualization
        └── ApiHealthMetrics.tsx  # Latency p95, error rates
```

### Pattern 1: Real-Time Job Status Updates (Polling)

**What:** Dashboard polls `/backfill/status/{job_id}` every 5 seconds to show live progress

**When to use:** Active jobs (status = "running"); stop polling when job reaches terminal state

**Example:**
```tsx
// dashboard/src/app/(dashboard)/backfill/[jobId]/page.tsx
import { useQuery } from '@tanstack/react-query';
import { Card, ProgressBar, Metric, Text } from '@tremor/react';

export default function BackfillJobPage({ params }: { params: { jobId: string } }) {
  const { data: job } = useQuery({
    queryKey: ['backfill-job', params.jobId],
    queryFn: async () => {
      const res = await fetch(`/api/backfill/${params.jobId}`);
      return res.json();
    },
    refetchInterval: (query) => {
      // Stop polling when job completes
      const status = query.state.data?.status;
      return status === 'running' ? 5000 : false;
    },
  });

  if (!job) return <div>Loading...</div>;

  const progress = (job.completed_items / job.total_items) * 100;

  return (
    <div className="space-y-6">
      <Card>
        <Text>Progress</Text>
        <Metric>{job.completed_items} / {job.total_items} SKUs</Metric>
        <ProgressBar value={progress} className="mt-2" />
        {job.eta_seconds && (
          <Text className="mt-1 text-sm text-gray-500">
            ETA: {Math.floor(job.eta_seconds / 60)} minutes
          </Text>
        )}
      </Card>

      <Card>
        <Text>Status</Text>
        <Metric>{job.status}</Metric>
        {job.failed_items > 0 && (
          <Text className="text-red-600">
            {job.failed_items} items failed
          </Text>
        )}
      </Card>
    </div>
  );
}
```

**Source:** Existing pattern in `dashboard/src/app/(dashboard)/monitoring/page.tsx` (lines 118-122)

### Pattern 2: GCP Cloud Scheduler for Incremental Refresh

**What:** Daily cron job triggers `/backfill/start` with 1-day lookback instead of 180-day backfill

**When to use:** After initial 180-day backfill completes; ongoing daily sync

**Example:**
```bash
# Create Cloud Scheduler job (one-time setup)
gcloud scheduler jobs create http daily-incremental-refresh \
  --location=us-east1 \
  --schedule="0 2 * * *" \
  --uri="https://feedops-pipeline-623866089882.us-east1.run.app/backfill/start" \
  --http-method=POST \
  --headers="Content-Type=application/json" \
  --message-body='{
    "job_type": "full_backfill",
    "skus": [],
    "config": {
      "days_lookback": 1,
      "batch_size": 50,
      "mode": "incremental"
    }
  }' \
  --oidc-service-account-email="profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com" \
  --oidc-token-audience="https://feedops-pipeline-623866089882.us-east1.run.app"
```

**Python API handler (detect incremental mode):**
```python
# src/feedops/api/backfill.py (modify start_backfill)
from feedops.jobs.scheduler import get_all_active_skus

async def start_backfill(request: StartBackfillRequest):
    # If skus list is empty + config.mode == "incremental", fetch stale SKUs
    skus = request.skus
    if not skus and request.config.get("mode") == "incremental":
        skus = await get_stale_skus(days_threshold=request.config.get("days_lookback", 1))
        logger.info(f"Incremental refresh: identified {len(skus)} stale SKUs")

    # ... existing job creation logic
```

**Source:** [Execute jobs on a schedule | Cloud Run](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule), [Quickstart: Schedule and run a cron job](https://docs.cloud.google.com/scheduler/docs/schedule-run-cron-job)

### Pattern 3: Cloud Monitoring Alert Policy with Slack Webhook

**What:** Alert policy detects job failures (error logs matching "backfill.*failed") and posts to Slack

**When to use:** Production monitoring; notify team when automated jobs fail

**Example:**
```bash
# 1. Create notification channel (Slack webhook)
gcloud alpha monitoring channels create \
  --display-name="FeedOps Alerts Slack" \
  --type=slack \
  --channel-labels=url=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# 2. Create alert policy (job failure detection)
gcloud alpha monitoring policies create \
  --notification-channels=projects/bobbys-project-346400/notificationChannels/CHANNEL_ID \
  --display-name="Backfill Job Failure Alert" \
  --condition-display-name="Job failed" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='
    resource.type="cloud_run_revision"
    AND resource.labels.service_name="feedops-pipeline"
    AND jsonPayload.event=~"backfill.*failed"'
```

**Structured logging (ensures alert triggers):**
```python
# src/feedops/api/backfill.py
from feedops.observability import log_event

async def _start_background_processing(...):
    try:
        # ... job processing
        if job.status == "failed":
            log_event(
                logger,
                logging.ERROR,
                "backfill.job.failed",
                job_id=job_id,
                total_items=len(skus),
                failed_items=job.failed_items,
                success_rate=(job.completed_items / len(skus)) * 100,
            )
    except Exception as e:
        log_event(logger, logging.ERROR, "backfill.job.exception", job_id=job_id, error=str(e))
```

**Source:** [Create and manage notification channels](https://cloud.google.com/monitoring/support/notification-options), [Use Slack and webhooks for notifications](https://cloud.google.com/blog/products/devops-sre/use-slack-and-webhooks-for-notifications/)

### Pattern 4: Data Freshness Heatmap

**What:** Visual grid showing which SKUs have fresh data (green) vs stale data (yellow/red)

**When to use:** Dashboard overview; identify data gaps at a glance

**Example:**
```tsx
// dashboard/src/components/backfill/CoverageHeatmap.tsx
import { Card, Text } from '@tremor/react';

interface FreshnessData {
  master_sku: string;
  search_terms_age_days: number;
  performance_age_days: number;
  keywords_age_days: number;
}

function getFreshnessColor(ageDays: number): string {
  if (ageDays <= 7) return 'bg-green-500';
  if (ageDays <= 30) return 'bg-yellow-500';
  if (ageDays <= 60) return 'bg-orange-500';
  return 'bg-red-500';
}

export function CoverageHeatmap({ data }: { data: FreshnessData[] }) {
  return (
    <Card>
      <Text className="text-lg font-semibold mb-4">Data Freshness by SKU</Text>
      <div className="grid grid-cols-20 gap-1">
        {data.map((item) => {
          const avgAge = (
            item.search_terms_age_days +
            item.performance_age_days +
            item.keywords_age_days
          ) / 3;

          return (
            <div
              key={item.master_sku}
              className={`w-4 h-4 rounded ${getFreshnessColor(avgAge)}`}
              title={`${item.master_sku}: ${Math.round(avgAge)} days old`}
            />
          );
        })}
      </div>
      <div className="flex gap-4 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-green-500 rounded" />
          <Text>≤7 days</Text>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-yellow-500 rounded" />
          <Text>8-30 days</Text>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 bg-red-500 rounded" />
          <Text>&gt;60 days</Text>
        </div>
      </div>
    </Card>
  );
}
```

**API endpoint (calculate freshness):**
```python
# src/feedops/api/monitoring.py (NEW file)
from fastapi import APIRouter
from feedops.db.supabase_client import get_client
from datetime import datetime, timezone

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])

@router.get("/freshness")
async def get_data_freshness():
    """Calculate data age for all SKUs across all collection types."""
    supabase = get_client()
    now = datetime.now(timezone.utc)

    # Query each data table for latest collection timestamp
    results = []

    # Get all SKUs from variant_index
    skus_query = supabase.table("variant_index").select("master_sku").execute()
    master_skus = list(set(row["master_sku"] for row in skus_query.data))

    for sku in master_skus:
        # Search terms age
        st_query = (
            supabase.table("search_queries")
            .select("collected_at")
            .eq("master_sku", sku)
            .order("collected_at", desc=True)
            .limit(1)
            .execute()
        )
        search_age = calculate_age_days(st_query.data[0]["collected_at"] if st_query.data else None, now)

        # Performance age
        perf_query = (
            supabase.table("performance_baselines")
            .select("captured_at")
            .eq("master_sku", sku)
            .order("captured_at", desc=True)
            .limit(1)
            .execute()
        )
        perf_age = calculate_age_days(perf_query.data[0]["captured_at"] if perf_query.data else None, now)

        # Keyword planner age (from search_queries.keyword_metrics_collected_at)
        kw_query = (
            supabase.table("search_queries")
            .select("keyword_metrics_collected_at")
            .eq("master_sku", sku)
            .not_.is_("keyword_metrics_collected_at", "null")
            .order("keyword_metrics_collected_at", desc=True)
            .limit(1)
            .execute()
        )
        kw_age = calculate_age_days(kw_query.data[0]["keyword_metrics_collected_at"] if kw_query.data else None, now)

        results.append({
            "master_sku": sku,
            "search_terms_age_days": search_age,
            "performance_age_days": perf_age,
            "keywords_age_days": kw_age,
        })

    return {"freshness": results}

def calculate_age_days(timestamp_str: str | None, now: datetime) -> int:
    if not timestamp_str:
        return 999  # No data
    ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    return (now - ts).days
```

**Source:** Existing freshness validation in `src/feedops/quality/review_dashboard.py`

### Pattern 5: Prometheus Metrics Endpoint

**What:** Expose `/metrics` endpoint for Prometheus scraping (job progress, API latency, error counts)

**When to use:** Existing metrics_registry already tracks these; just need HTTP endpoint

**Example:**
```python
# src/feedops/api/main.py (add to existing FastAPI app)
from prometheus_client import make_asgi_app, REGISTRY

# Mount Prometheus metrics app at /metrics
metrics_app = make_asgi_app(registry=REGISTRY)
app.mount("/metrics", metrics_app)

# Metrics are already tracked via metrics_registry.increment() and .observe()
# Examples from main.py:
# - Line 143-148: http_request_error_total counter
# - Line 150-156: http_request_latency_seconds histogram
# - Line 398-404: provider_error_total counter
# - Line 407-414: generation_latency_seconds histogram
```

**Prometheus scrape config (for external Prometheus instance):**
```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'feedops-pipeline'
    metrics_path: '/metrics'
    scheme: 'https'
    static_configs:
      - targets: ['feedops-pipeline-623866089882.us-east1.run.app']
    scrape_interval: 15s
```

**Source:** [prometheus-fastapi-instrumentator](https://pypi.org/project/prometheus-fastapi-instrumentator/), [Building a Powerful Observability Stack for FastAPI with Prometheus, Grafana & Loki](https://dimasyotama.medium.com/building-a-powerful-observability-stack-for-fastapi-with-prometheus-grafana-loki-426822422fd6)

### Anti-Patterns to Avoid

- **WebSockets for progress updates:** SSE or polling is simpler; WebSockets add connection management complexity
- **Storing logs in database:** Use Cloud Logging; database logs cause bloat and slow queries
- **Running cron in Cloud Run containers:** Containers scale to zero; use Cloud Scheduler instead
- **Creating custom KPI components:** Use Tremor's pre-built components; saves weeks of dev time
- **Polling every 1 second:** Wastes Cloud Run CPU; poll every 5-10 seconds for active jobs

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron scheduling | Custom scheduler in Cloud Run | GCP Cloud Scheduler | Cloud Run scales to zero; cron won't run reliably |
| Alert notifications | Custom webhook handler | Cloud Monitoring notification channels | Handles retries, rate limiting, delivery tracking |
| Dashboard progress bars | Custom React components | Tremor KPI cards, ProgressBar | 30+ pre-built components, Tailwind-integrated |
| Metrics aggregation | Custom metrics storage | Prometheus metrics_registry (already in place) | Thread-safe, standard format, Grafana-compatible |
| Email delivery | Direct SMTP | Resend or SendGrid API | Handles deliverability, bounce tracking, reputation |
| Data freshness checks | Manual queries per SKU | Quality report module (already exists) | Centralized logic in `src/feedops/quality/review_dashboard.py` |

**Key insight:** GCP provides managed services for all operational concerns (scheduling, alerting, logging, metrics). Adding external services (Airflow, Datadog, PagerDuty) increases complexity and cost without meaningful benefit at this scale (1 service, 2,784 SKUs).

## Common Pitfalls

### Pitfall 1: Polling Without Backoff

**What goes wrong:** Dashboard polls `/backfill/status/{job_id}` every second, hammering Cloud Run even when job is idle

**Why it happens:** Default `refetchInterval: 1000` in react-query; no conditional polling

**How to avoid:** Use conditional refetch that stops when job reaches terminal state

**Warning signs:** Cloud Run CPU spikes during idle periods; excessive /backfill/status requests in logs

**Solution:**
```tsx
const { data: job } = useQuery({
  queryKey: ['job', jobId],
  queryFn: () => fetch(`/api/backfill/${jobId}`).then(r => r.json()),
  refetchInterval: (query) => {
    const status = query.state.data?.status;
    // Stop polling when job completes/fails
    if (status === 'complete' || status === 'failed') return false;
    // Active jobs: poll every 5 seconds
    return status === 'running' ? 5000 : 10000;
  },
});
```

### Pitfall 2: Missing OIDC Authentication for Cloud Scheduler

**What goes wrong:** Cloud Scheduler job fails with 403 Forbidden when calling authenticated Cloud Run endpoint

**Why it happens:** Cloud Run requires OIDC token for authentication; Cloud Scheduler defaults to no auth

**How to avoid:** Always specify `--oidc-service-account-email` and `--oidc-token-audience` when creating scheduler jobs

**Warning signs:** Scheduler job history shows "Failed (403)" status; Cloud Run logs show "Missing authentication"

**Solution:**
```bash
# CORRECT (includes OIDC auth)
gcloud scheduler jobs create http my-job \
  --oidc-service-account-email="profit-pilot-runtime@bobbys-project-346400.iam.gserviceaccount.com" \
  --oidc-token-audience="https://feedops-pipeline-623866089882.us-east1.run.app" \
  --uri="https://feedops-pipeline-623866089882.us-east1.run.app/backfill/start"

# WRONG (no auth - will fail)
gcloud scheduler jobs create http my-job \
  --uri="https://feedops-pipeline-623866089882.us-east1.run.app/backfill/start"
```

### Pitfall 3: Incremental Refresh Fetches All SKUs

**What goes wrong:** Daily incremental job queries all 2,784 SKUs instead of only stale SKUs (>7 days old)

**Why it happens:** Default behavior in backfill API is "fetch all SKUs if list is empty"

**How to avoid:** Add `mode: "incremental"` config flag that triggers stale SKU detection before job creation

**Warning signs:** Daily refresh takes same time as full backfill; API quota consumption stays high after initial backfill

**Solution:**
```python
# src/feedops/jobs/scheduler.py (NEW file)
from feedops.db.supabase_client import get_client
from datetime import datetime, timedelta, timezone

async def get_stale_skus(days_threshold: int = 7) -> list[str]:
    """Identify SKUs with data older than threshold."""
    supabase = get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    cutoff_str = cutoff.isoformat()

    # Get all master SKUs
    all_skus_query = supabase.table("variant_index").select("master_sku").execute()
    all_skus = list(set(row["master_sku"] for row in all_skus_query.data))

    stale_skus = []
    for sku in all_skus:
        # Check search_queries for this SKU
        recent_query = (
            supabase.table("search_queries")
            .select("collected_at")
            .eq("master_sku", sku)
            .gte("collected_at", cutoff_str)
            .limit(1)
            .execute()
        )

        if not recent_query.data:
            # No recent data - stale
            stale_skus.append(sku)

    return stale_skus
```

### Pitfall 4: Slack Webhook Rate Limiting

**What goes wrong:** Batch job completes 100 SKUs, sends 100 Slack messages, hits rate limit (1 msg/sec)

**Why it happens:** Notification sent per SKU instead of per job

**How to avoid:** Send notifications at job level (started, completed, failed), not per-item level

**Warning signs:** Slack webhook returns 429 Too Many Requests; some notifications don't arrive

**Solution:**
```python
# WRONG (per-SKU notification)
for sku in skus:
    process_sku(sku)
    send_slack_notification(f"Completed {sku}")  # 2,784 messages!

# CORRECT (per-job notification)
job_started_notification(job_id, total_skus)
for sku in skus:
    process_sku(sku)
job_completed_notification(job_id, completed_count, failed_count)
```

### Pitfall 5: Dashboard Shows Stale Job Status

**What goes wrong:** Job completes but dashboard still shows "running" for 5 minutes

**Why it happens:** Client-side cache (react-query) doesn't invalidate on job completion

**How to avoid:** Use `onSuccess` callback to invalidate queries when terminal state detected

**Warning signs:** Manual refresh shows correct status; auto-refresh shows stale data

**Solution:**
```tsx
const { data: job } = useQuery({
  queryKey: ['job', jobId],
  queryFn: () => fetch(`/api/backfill/${jobId}`).then(r => r.json()),
  refetchInterval: 5000,
  select: (data) => {
    // Detect terminal state
    if (data.status === 'complete' || data.status === 'failed') {
      // Invalidate related queries (job list, coverage stats)
      queryClient.invalidateQueries({ queryKey: ['backfill-jobs'] });
      queryClient.invalidateQueries({ queryKey: ['coverage'] });
    }
    return data;
  },
});
```

## Code Examples

Verified patterns from existing codebase:

### Job Status Polling (Existing Pattern)

```tsx
// Source: dashboard/src/app/(dashboard)/monitoring/page.tsx (lines 59-93)
const fetchPerformanceDeltas = async () => {
  setLoadingPerformance(true)
  try {
    const params = new URLSearchParams()
    if (skuFilter) params.set('master_sku', skuFilter)

    const res = await fetch(`/api/monitoring/performance-delta?${params}`)
    if (!res.ok) throw new Error('Failed to fetch performance deltas')

    const data = await res.json()
    setPerformanceDeltas(data.deltas || [])
  } catch (err) {
    console.error('Failed to fetch performance deltas:', err)
  } finally {
    setLoadingPerformance(false)
  }
}

// Poll on mount and when filter changes
useEffect(() => {
  fetchPerformanceDeltas()
}, [skuFilter])
```

### Structured Logging (Existing Pattern)

```python
# Source: src/feedops/observability/__init__.py (lines 45-58)
def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    **fields: Any,
) -> None:
    """Emit one structured JSON log line with request ID context."""
    payload: dict[str, Any] = {
        "ts": time.time(),
        "event": event,
        "request_id": get_request_id(),
    }
    payload.update(fields)
    logger.log(level, json.dumps(payload, default=str, sort_keys=True))

# Usage example from main.py (lines 819-823)
log_event(
    logger,
    logging.INFO,
    "generation.optimize.start",
    endpoint="optimize_single_sku",
    master_sku=canonical_master_sku,
    requested_master_sku=request.master_sku,
    request_id=get_request_id(),
)
```

### Prometheus Metrics (Existing Pattern)

```python
# Source: src/feedops/api/main.py (lines 143-156)
try:
    response = await call_next(request)
except Exception:
    metrics_registry.increment(
        "http_request_error_total",
        method=request.method,
        path=request.url.path,
    )
    raise
finally:
    metrics_registry.observe(
        "http_request_latency_seconds",
        time.perf_counter() - started,
        method=request.method,
        path=request.url.path,
    )
```

### Quality Report Integration (Existing)

```python
# Source: src/feedops/jobs/quality_report.py (already exists)
# Use existing quality report module for completeness/freshness checks
from feedops.quality.review_dashboard import (
    calculate_completeness_report,
    calculate_freshness_report,
    detect_outliers,
)

# Example: Get validation report for job
report = {
    "completeness": calculate_completeness_report(job_id),
    "freshness": calculate_freshness_report(),
    "outliers": detect_outliers(),
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual batch execution | Cloud Scheduler automation | GCP feature (2016+) | Zero-touch daily sync |
| Text logs | Structured JSON logs | Python logging stdlib (always) | Cloud Logging auto-parsing |
| Custom metrics storage | Prometheus format | Prometheus client (2012+) | Standard scraping, Grafana dashboards |
| Hand-rolled dashboard components | Tremor pre-built components | Tremor 3.0 (2023) | 80% faster dashboard dev |
| WebSockets for progress | Server-Sent Events (SSE) | HTML5 standard (2015) | Simpler, auto-reconnect |
| Email via SMTP | Transactional email APIs (Resend, SendGrid) | 2010s shift | Better deliverability, tracking |

**Deprecated/outdated:**
- **Loguru for async logging:** Lacks ContextVars support; structlog is better for async request tracking (2024+ best practice)
- **Chart.js for React:** Imperative API; Recharts/Tremor are declarative (React-native since 2016)
- **Airflow for API-triggered jobs:** DAG-centric design; better for scheduled pipelines than request-response workflows

## Open Questions

1. **Should email alerts use Resend or SendGrid?**
   - What we know: Both have generous free tiers (Resend: 100/day, SendGrid: 100/day); both support transactional email
   - What's unclear: Which has better deliverability for automated alerts?
   - Recommendation: Start with Resend (simpler API, better DX); migrate to SendGrid if deliverability issues arise

2. **Should we add Grafana Cloud for Prometheus visualization?**
   - What we know: Grafana provides richer dashboards than Cloud Monitoring; costs $8-29/mo for 1 service
   - What's unclear: Is Tremor dashboard sufficient for observability needs?
   - Recommendation: Start with Tremor; add Grafana only if custom metric queries become critical

3. **Should incremental refresh run daily or hourly?**
   - What we know: Search terms change slowly (7-day threshold); performance data updates daily
   - What's unclear: Optimal refresh cadence for balancing freshness vs API quota
   - Recommendation: Start with daily refresh (2am PT); monitor stale SKU counts and adjust if needed

## Sources

### Primary (HIGH confidence)

**GCP Cloud Scheduler & Cloud Run:**
- [Execute jobs on a schedule | Cloud Run](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Quickstart: Schedule and run a cron job](https://docs.cloud.google.com/scheduler/docs/schedule-run-cron-job)
- [Running services on a schedule](https://docs.cloud.google.com/run/docs/triggering/using-scheduler)
- [Triggering Cloud Run Jobs with Cloud Scheduler | Google Codelabs](https://codelabs.developers.google.com/cloud-run-jobs-and-cloud-scheduler)

**GCP Cloud Monitoring & Alerting:**
- [Create and manage notification channels](https://cloud.google.com/monitoring/support/notification-options)
- [Configure and manage notifications | Error Reporting](https://docs.cloud.google.com/error-reporting/docs/notifications)
- [Use Slack and webhooks for notifications | Google Cloud Blog](https://cloud.google.com/blog/products/devops-sre/use-slack-and-webhooks-for-notifications/)
- [Configure Slack notifications | Cloud Build](https://cloud.google.com/build/docs/configuring-notifications/configure-slack)

**Prometheus Metrics with FastAPI:**
- [prometheus-fastapi-instrumentator · PyPI](https://pypi.org/project/prometheus-fastapi-instrumentator/)
- [Prometheus on a FastAPI application | Medium](https://medium.com/@hitorunajp/prometheus-on-a-fastapi-application-aa25e5223a9e)
- [Building a Powerful Observability Stack for FastAPI with Prometheus, Grafana & Loki](https://dimasyotama.medium.com/building-a-powerful-observability-stack-for-fastapi-with-prometheus-grafana-loki-426822422fd6)
- [FastAPI + Gunicorn | client_python](http://prometheus.github.io/client_python/exporting/http/fastapi-gunicorn/)

**Dashboard Visualization (Tremor):**
- [Tremor React UI Components](https://www.tremor.so/)
- [Using Next.js and Tremor for charts](https://www.erichowey.dev/writing/using-nextjs-tremor-for-charts-graphs-data-visualization/)
- [Building a Real-Time Dashboard with Next.js and Chart.js](https://cloudactivelabs.com/en/blog/building-a-real-time-dashboard-with-nextjs-and-chartjs)

**Codebase (Existing Patterns):**
- `dashboard/src/app/(dashboard)/monitoring/page.tsx` — Existing monitoring UI with polling pattern
- `src/feedops/api/main.py` — Request ID middleware, Prometheus metrics, background task pattern
- `src/feedops/observability/__init__.py` — Structured logging with request context
- `src/feedops/api/backfill.py` — Job lifecycle endpoints, status queries
- `src/feedops/quality/review_dashboard.py` — Existing quality report module

### Secondary (MEDIUM confidence)

**Incremental Refresh Patterns:**
- [Backfilling Data Pipelines (Medium)](https://medium.com/@andymadson/backfilling-data-pipelines-concepts-examples-and-best-practices-19f7a6b20c82) — Chunk-based processing, idempotent operations
- [Incremental Patterns for Near Real-Time Data (dbt)](https://docs.getdbt.com/best-practices/how-we-handle-real-time-data/2-incremental-patterns) — Microbatch approach, lookback parameters
- `.planning/research/FEATURES.md` (lines 88-111) — Project-specific incremental refresh strategy

**Notification Integrations:**
- [GitHub - doitintl/gSlack](https://github.com/doitintl/gSlack) — GCP to Slack notification forwarder
- [GCP - Send Error Logs to Slack Channel by Cloud Monitoring](https://didikmulyadi.medium.com/being-more-aware-of-application-errors-by-connecting-cloud-monitoring-to-slack-channel-d976e6c29761)
- [Configuring Slack Notifications For Google Cloud Build Using Cloud Run](https://blog.thecloudside.com/configuring-slack-notifications-for-google-cloud-build-using-cloud-run-2e89323293ab)

### Tertiary (LOW confidence)

None — all monitoring/automation recommendations based on official GCP documentation and established patterns.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — All libraries already in project or official GCP services
- Architecture: **HIGH** — Patterns match existing codebase conventions (polling, structured logging, Prometheus)
- Pitfalls: **HIGH** — Based on common GCP Cloud Scheduler/Monitoring issues documented in official guides
- Open questions: **MEDIUM** — Email provider and Grafana decisions depend on production usage patterns

**Research date:** 2026-02-13
**Valid until:** 60 days (GCP services are stable; Tremor updates monthly but breaking changes rare)
