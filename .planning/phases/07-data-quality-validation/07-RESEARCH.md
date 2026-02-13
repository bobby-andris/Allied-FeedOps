# Phase 3: Data Quality & Validation - Research

**Researched:** 2026-02-13
**Domain:** Data Quality Assurance, Statistical Validation, Freshness Monitoring
**Confidence:** HIGH

## Summary

Data quality validation sits at the intersection of data engineering (ensuring completeness and freshness) and statistical analysis (detecting anomalies and contamination). The phase builds on Phase 5's job infrastructure and Phase 6's collection workers to add validation layers that prevent data quality issues from propagating downstream to content generation.

The research confirms that Pydantic v2 (already in use) provides optimal validation architecture via field validators and constraints, Python's statistical libraries offer mature outlier detection (Z-score, IQR, isolation forests), and timestamp-based freshness monitoring is the industry standard approach for TTL validation. Key finding: validation should occur at collection time (not query time) to fail fast and maintain data integrity.

**Primary recommendation:** Implement validation as a three-layer strategy: (1) Schema validation at write time via Pydantic models, (2) Range/logic checks in worker functions before database writes, (3) Post-collection validation jobs that flag stale data and statistical outliers for dashboard visibility.

## User Constraints

No CONTEXT.md exists for this phase - no user decisions have been made yet via /gsd:discuss-phase.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | 2.x (already in use) | Schema validation, type coercion, constraints | Already powering job models (`BackfillJob`, `JobError`), proven performance, declarative validation |
| Supabase Client | Current (postgrest-py) | Database constraints, CHECK clauses, triggers | Already integrated, ACID guarantees, constraint violations = instant failures |
| NumPy | Latest | Statistical computations (mean, std, percentiles) | De facto standard for numerical operations, required by outlier detection libs |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SciPy | Latest | Statistical tests (Z-score, IQR) | Outlier detection on metric distributions (CTR, impression share) |
| Pandas | Latest (optional) | Batch statistical analysis | Optional for dashboard analytics; NOT required for validation logic |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic field validators | Manual validation functions | Pydantic provides declarative, optimized, type-safe validation - manual validation is error-prone and verbose |
| Database CHECK constraints | Application-layer validation only | DB constraints provide ACID guarantees and prevent bad data at the source - app validation can be bypassed |
| Z-score/IQR for outliers | ML-based isolation forests | IQR/Z-score are interpretable, deterministic, and sufficient for bounded metrics (CTR 0-1, impression share 0-100); isolation forests add complexity without clear benefit for structured metrics |

**Installation:**
```bash
# Core dependencies (already installed)
pip install pydantic supabase

# Supporting (for statistical validation)
pip install scipy numpy
```

## Architecture Patterns

### Pattern 1: Pydantic Field Validators with Constraints

**What:** Use Pydantic's `Field()` constraints for declarative validation rules that execute at model instantiation time.

**When to use:** Validating bounded metrics (CTR, impression share), required fields, type coercion.

**Example:**
```python
from pydantic import BaseModel, Field, field_validator

class PerformanceMetrics(BaseModel):
    """Validated performance metrics schema."""

    impressions: int = Field(ge=0, description="Must be non-negative")
    clicks: int = Field(ge=0, description="Must be non-negative")
    ctr: float = Field(ge=0.0, le=1.0, description="CTR must be 0-1")

    @field_validator('clicks')
    @classmethod
    def clicks_lte_impressions(cls, v, info):
        """Validate clicks <= impressions logical constraint."""
        if 'impressions' in info.data and v > info.data['impressions']:
            raise ValueError(f'Clicks ({v}) cannot exceed impressions ({info.data["impressions"]})')
        return v
```

**Source:** [Pydantic Validators Documentation](https://docs.pydantic.dev/latest/concepts/validators/)

### Pattern 2: Database-Level Validation with CHECK Constraints

**What:** Enforce data integrity at the database layer using PostgreSQL CHECK constraints.

**When to use:** Critical invariants that must NEVER be violated (bounded ranges, enum values, non-null requirements).

**Example:**
```sql
-- Already exists in backfill_jobs (Phase 5 pattern)
ALTER TABLE performance_baselines
ADD CONSTRAINT ctr_range CHECK (avg_ctr >= 0 AND avg_ctr <= 1);

ALTER TABLE performance_baselines
ADD CONSTRAINT clicks_lte_impressions
CHECK (avg_clicks <= avg_impressions);

-- Freshness constraint (enforced at application layer)
CREATE INDEX idx_performance_baselines_stale
ON performance_baselines (master_sku, platform, created_at)
WHERE created_at < NOW() - INTERVAL '60 days';
```

**Pattern from existing codebase:** `supabase/migrations/026_backfill_jobs.sql` already uses CHECK constraints for `status IN (...)` and `job_type IN (...)`.

### Pattern 3: Timestamp-Based Freshness Monitoring

**What:** Store collection timestamps (`created_at`, `updated_at`, `fetched_at`) on all data tables and query for stale records exceeding TTL thresholds.

**When to use:** Detecting stale baselines (>60 days), stale search terms (>7 days), stale keyword metrics (>30 days).

**Example:**
```python
from datetime import datetime, timedelta, timezone

async def check_baseline_freshness(master_sku: str, platform: str) -> dict:
    """Check if performance baseline is stale (>60 days)."""
    from feedops.db.supabase_client import get_client

    client = get_client()
    threshold = datetime.now(timezone.utc) - timedelta(days=60)

    result = client.table('performance_baselines') \
        .select('master_sku, platform, created_at') \
        .eq('master_sku', master_sku) \
        .eq('platform', platform) \
        .execute()

    if not result.data:
        return {'status': 'missing', 'age_days': None}

    created_at = datetime.fromisoformat(result.data[0]['created_at'])
    age_days = (datetime.now(timezone.utc) - created_at).days
    is_stale = created_at < threshold

    return {
        'status': 'stale' if is_stale else 'fresh',
        'age_days': age_days,
        'threshold_days': 60
    }
```

**Sources:**
- [Data Freshness Best Practices - Elementary Data](https://www.elementary-data.com/post/data-freshness-best-practices-and-key-metrics-to-measure-success)
- [Data Freshness Metrics - Anomalo](https://www.anomalo.com/blog/defining-data-freshness-measuring-and-monitoring-data-timeliness/)

### Pattern 4: Statistical Outlier Detection (Z-Score Method)

**What:** Detect statistical anomalies in collected metrics using Z-score (standard deviations from mean).

**When to use:** Flagging suspicious metric values (e.g., CTR > 10% when category average is 1.2%, impression share = 100% when typical is 15-25%).

**Example:**
```python
import numpy as np
from scipy import stats

def detect_outliers_zscore(values: list[float], threshold: float = 3.0) -> list[int]:
    """Detect outliers using Z-score method.

    Args:
        values: List of metric values
        threshold: Z-score threshold (default 3.0 = 99.7% confidence interval)

    Returns:
        Indices of outlier values
    """
    if len(values) < 3:
        return []  # Need minimum 3 data points for meaningful statistics

    arr = np.array(values)
    z_scores = np.abs(stats.zscore(arr, nan_policy='omit'))
    outlier_indices = np.where(z_scores > threshold)[0].tolist()

    return outlier_indices

# Example usage for CTR validation
def validate_ctr_distribution(ctrs: list[float]) -> dict:
    """Validate CTR distribution for a category/SKU set."""
    outlier_indices = detect_outliers_zscore(ctrs, threshold=3.0)

    return {
        'total_skus': len(ctrs),
        'outlier_count': len(outlier_indices),
        'outlier_pct': len(outlier_indices) / len(ctrs) * 100,
        'outlier_indices': outlier_indices,
        'mean_ctr': np.mean(ctrs),
        'std_ctr': np.std(ctrs)
    }
```

**Sources:**
- [Outlier Detection in Python - Built In](https://builtin.com/data-science/outlier-detection-python)
- [Outlier Detection Methods with IQR & Z-Score - Medium](https://vatsal12-p.medium.com/outlier-detection-methods-in-python-w-iqr-standard-deviation-bf8653f544bb)

### Pattern 5: Multi-SKU Family Detection

**What:** Identify SKUs sharing the same `product_id` via `variant_index` lookups to flag aggregated data.

**When to use:** Detecting when Google Ads aggregates performance at product level instead of master_sku level (documented multi-SKU pattern).

**Example:**
```python
async def detect_multi_sku_families() -> list[dict]:
    """Find product_ids with multiple master_skus (aggregated data sources)."""
    from feedops.db.supabase_client import get_client

    client = get_client()

    # Query variant_index for product_ids with multiple master_skus
    result = client.rpc('find_multi_sku_products').execute()

    # Alternative: SQL query
    # SELECT shopify_product_id, ARRAY_AGG(DISTINCT master_sku) as skus, COUNT(DISTINCT master_sku) as sku_count
    # FROM variant_index
    # WHERE shopify_product_id IS NOT NULL
    # GROUP BY shopify_product_id
    # HAVING COUNT(DISTINCT master_sku) > 1

    return result.data

async def flag_aggregated_data(master_sku: str) -> bool:
    """Check if master_sku is part of a multi-SKU family (aggregated data)."""
    from feedops.db.supabase_client import get_client

    client = get_client()

    # Get product_id for this master_sku
    sku_result = client.table('variant_index') \
        .select('shopify_product_id') \
        .eq('master_sku', master_sku) \
        .limit(1) \
        .execute()

    if not sku_result.data:
        return False

    product_id = sku_result.data[0]['shopify_product_id']

    # Count distinct master_skus for this product_id
    count_result = client.table('variant_index') \
        .select('master_sku', count='exact') \
        .eq('shopify_product_id', product_id) \
        .execute()

    # Multi-SKU family if count > 1
    return count_result.count > 1
```

**Pattern from existing codebase:** Multi-SKU pattern documented in `docs/architecture/multi-sku-pattern.md` and `docs/audit/variant-id-mismatch-root-cause-2026-02-08.md`.

### Pattern 6: Completeness Validation (Coverage Check)

**What:** Validate that job processing achieved expected SKU coverage (actual count vs target 2,784 SKUs).

**When to use:** Post-job validation to detect missing SKUs or partial failures.

**Example:**
```python
async def validate_job_completeness(job_id: str) -> dict:
    """Validate backfill job achieved expected coverage.

    Success criteria:
    - success_count >= 95% of total_items (Phase 5 decision)
    - All 2,784 SKUs accounted for (processed or failed)
    """
    from feedops.jobs import get_job

    job = await get_job(job_id)
    if not job:
        return {'valid': False, 'reason': 'Job not found'}

    total = job.total_items
    completed = job.completed_items
    failed = job.failed_items

    # Calculate coverage metrics
    processed = completed + failed
    coverage_pct = (processed / total) * 100
    success_rate = (completed / total) * 100

    # Validation rules
    is_complete = processed == total  # All SKUs accounted for
    is_successful = success_rate >= 95.0  # 95% success threshold (Phase 5)

    return {
        'valid': is_complete and is_successful,
        'total_items': total,
        'completed_items': completed,
        'failed_items': failed,
        'coverage_pct': coverage_pct,
        'success_rate': success_rate,
        'is_complete': is_complete,
        'is_successful': is_successful
    }
```

**Pattern from Phase 5:** 95% success threshold defined in Phase 5 decision log.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Type validation | Custom type checkers, manual isinstance() chains | Pydantic BaseModel with Field constraints | Handles coercion, nested models, JSON serialization, error messages automatically |
| Statistical outlier detection | Manual percentile calculations, custom threshold logic | SciPy `stats.zscore()` or `stats.iqr()` | Battle-tested implementations, handles edge cases (NaN, insufficient data), optimized for NumPy arrays |
| Date range validation | String parsing with datetime.strptime() | Pydantic datetime fields with `ge=` constraints | Automatic timezone handling, ISO 8601 parsing, validation errors with context |
| Database constraint validation | Try/except wrappers around inserts | PostgreSQL CHECK constraints | Enforced at DB level (ACID), prevents bad data even from direct SQL, returns structured error codes |

**Key insight:** Data validation is a solved problem with mature tooling. Custom validation logic is almost always buggier, slower, and harder to maintain than declarative constraints (Pydantic) + database guarantees (CHECK constraints) + established statistical methods (SciPy).

## Common Pitfalls

### Pitfall 1: Validating at Query Time Instead of Write Time

**What goes wrong:** Data quality issues aren't detected until SKUs are queried for content generation, causing cascading failures and poor user experience (missing data, partial results).

**Why it happens:** Validation is easier to add as a query filter (`WHERE created_at > NOW() - INTERVAL '60 days'`) than as a collection-time check.

**How to avoid:**
1. Add validation to worker functions BEFORE database writes (`collect_performance_batch` should validate CTR range before upserting)
2. Use database CHECK constraints to enforce invariants at write time
3. Run post-collection validation jobs to flag issues for dashboard visibility

**Warning signs:**
- Dashboard queries returning NULL/missing data frequently
- Content generation failing with "insufficient data" errors
- No alerts when stale data is written to the database

### Pitfall 2: Treating Multi-SKU Families as Bad Data

**What goes wrong:** Flagging multi-SKU families (DMF-2/2X, DMF-2/3X sharing product_id) as data quality issues and attempting to "fix" them, when this is actually correct behavior.

**Why it happens:** Misunderstanding Google Ads aggregation behavior - campaigns aggregate at product_id level, not master_sku level, so multiple master_skus naturally share performance data.

**How to avoid:**
1. Detect multi-SKU families via `shopify_product_id` matching
2. FLAG (not REJECT) these SKUs in the database with a `is_multi_sku_family` boolean or JSONB metadata field
3. Adjust content generation prompts to account for aggregated data (e.g., "performance data represents all finishes of this product family")
4. Display badges in dashboard ("⚠️ Aggregated Data - Shared with DMF-2/3X, DMF-2/4X") for transparency

**Warning signs:**
- Validation jobs rejecting 10-15% of SKUs for "duplicate performance data"
- User confusion about why SKUs are marked invalid when data looks correct
- Attempts to de-duplicate performance data that should be shared

**Reference:** See `docs/architecture/multi-sku-pattern.md` for detailed explanation.

### Pitfall 3: Hard-Coding Threshold Values

**What goes wrong:** Validation thresholds (60-day freshness, 95% success rate, 3.0 Z-score) hard-coded in validation logic, making it impossible to tune without code changes.

**Why it happens:** Thresholds seem obvious during implementation ("obviously baselines should refresh every 60 days"), but production reveals need for adjustments.

**How to avoid:**
1. Store thresholds in database config table or environment variables
2. Use constants at module level with clear comments explaining rationale
3. Make thresholds configurable via API/dashboard (advanced: allow per-category thresholds)

**Example:**
```python
# BAD: Hard-coded threshold
if (datetime.now() - created_at).days > 60:
    return 'stale'

# GOOD: Configurable constant
BASELINE_FRESHNESS_DAYS = 60  # VALID-02 requirement

if (datetime.now() - created_at).days > BASELINE_FRESHNESS_DAYS:
    return 'stale'

# BETTER: Database-driven config
config = get_validation_config()
threshold_days = config.get('baseline_freshness_days', 60)
```

**Warning signs:**
- Pull requests that only change magic numbers in validation logic
- Support requests to "temporarily disable validation" for specific SKUs
- Different thresholds in different files (database migration vs Python code)

### Pitfall 4: Ignoring Publish Event Contamination

**What goes wrong:** Capturing performance baselines for SKUs that were recently published (last 30 days), mixing pre-optimization and post-optimization data in the "baseline" snapshot.

**Why it happens:** Not checking `publish_events` table before baseline capture; assuming all SKUs are at steady-state.

**How to avoid:**
1. ALWAYS query `publish_events` for the SKU before capturing baseline
2. If publish event exists in last 30 days, SKIP baseline capture and log warning
3. Add database constraint or trigger to prevent baseline inserts when recent publish exists

**Example:**
```python
async def validate_baseline_capture_eligibility(master_sku: str, platform: str) -> tuple[bool, str]:
    """Check if SKU is eligible for baseline capture (no recent publish)."""
    from feedops.db.supabase_client import get_client

    client = get_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    result = client.table('publish_events') \
        .select('published_at') \
        .eq('master_sku', master_sku) \
        .eq('platform', platform) \
        .gte('published_at', cutoff.isoformat()) \
        .limit(1) \
        .execute()

    if result.data:
        published_at = result.data[0]['published_at']
        days_since_publish = (datetime.now(timezone.utc) - datetime.fromisoformat(published_at)).days
        return False, f'Published {days_since_publish} days ago (< 30 day threshold)'

    return True, 'No recent publish events'
```

**Warning signs:**
- Baseline metrics showing dramatic changes week-over-week (not seasonality)
- Post-publish delta analysis showing negative improvements (worse than baseline)
- SKUs showing "improvement" immediately after baseline capture

## Code Examples

### Example 1: Complete Performance Metrics Validation

```python
"""Complete validation example for performance metrics collection."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
from scipy import stats
import numpy as np

class ValidatedPerformanceMetrics(BaseModel):
    """Performance metrics with comprehensive validation."""

    master_sku: str = Field(..., min_length=1, max_length=50)
    platform: str = Field(..., pattern=r'^(google|bing)$')

    # Metrics with range validation
    impressions: int = Field(ge=0, description="Non-negative integer")
    clicks: int = Field(ge=0, description="Non-negative integer")
    avg_ctr: float = Field(ge=0.0, le=1.0, description="CTR in range 0-1")
    conversions: float = Field(ge=0.0, description="Non-negative conversions")

    # Date range validation
    baseline_start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    baseline_end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')

    # Timestamp validation
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('clicks')
    @classmethod
    def clicks_lte_impressions(cls, v, info):
        """Validate clicks <= impressions (VALID-06)."""
        if 'impressions' in info.data and v > info.data['impressions']:
            raise ValueError(
                f'Clicks ({v}) cannot exceed impressions ({info.data["impressions"]})'
            )
        return v

    @field_validator('baseline_end_date')
    @classmethod
    def end_date_after_start(cls, v, info):
        """Validate end_date > start_date (VALID-09)."""
        if 'baseline_start_date' in info.data:
            if v <= info.data['baseline_start_date']:
                raise ValueError(
                    f'End date ({v}) must be after start date ({info.data["baseline_start_date"]})'
                )
        return v

def validate_metrics_statistical(metrics: list[ValidatedPerformanceMetrics]) -> dict:
    """Detect statistical outliers in batch of metrics (VALID-10)."""
    if len(metrics) < 3:
        return {'outliers': [], 'analysis': 'Insufficient data for statistical analysis'}

    # Extract CTRs for outlier detection
    ctrs = [m.avg_ctr for m in metrics if m.avg_ctr is not None]

    if len(ctrs) < 3:
        return {'outliers': [], 'analysis': 'Insufficient CTR data'}

    # Z-score outlier detection
    z_scores = np.abs(stats.zscore(ctrs))
    outlier_indices = np.where(z_scores > 3.0)[0].tolist()

    outlier_skus = [metrics[i].master_sku for i in outlier_indices]

    return {
        'total': len(metrics),
        'outliers': outlier_skus,
        'outlier_count': len(outlier_skus),
        'mean_ctr': float(np.mean(ctrs)),
        'std_ctr': float(np.std(ctrs)),
        'analysis': f'{len(outlier_skus)} outliers detected (Z-score > 3.0)'
    }
```

### Example 2: Freshness Validation Query

```python
"""Data freshness validation with TTL checks."""

from datetime import datetime, timedelta, timezone
from typing import Literal

async def check_data_freshness(
    master_sku: str,
    data_type: Literal['baseline', 'search_terms', 'keywords']
) -> dict:
    """Check if data is fresh according to TTL thresholds (VALID-02).

    TTL Thresholds:
    - baselines: 60 days
    - search_terms: 7 days
    - keywords: 30 days (Keyword Planner cache TTL from Phase 6)
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    # Map data type to table and TTL
    config = {
        'baseline': {'table': 'performance_baselines', 'ttl_days': 60, 'timestamp_col': 'created_at'},
        'search_terms': {'table': 'search_queries', 'ttl_days': 7, 'timestamp_col': 'fetched_at'},
        'keywords': {'table': 'keyword_metrics', 'ttl_days': 30, 'timestamp_col': 'updated_at'}
    }

    cfg = config[data_type]
    threshold = datetime.now(timezone.utc) - timedelta(days=cfg['ttl_days'])

    # Query for most recent record
    result = client.table(cfg['table']) \
        .select(f'master_sku, {cfg["timestamp_col"]}') \
        .eq('master_sku', master_sku) \
        .order(cfg['timestamp_col'], desc=True) \
        .limit(1) \
        .execute()

    if not result.data:
        return {
            'status': 'missing',
            'master_sku': master_sku,
            'data_type': data_type,
            'age_days': None,
            'ttl_days': cfg['ttl_days']
        }

    timestamp = datetime.fromisoformat(result.data[0][cfg['timestamp_col']])
    age_days = (datetime.now(timezone.utc) - timestamp).days
    is_fresh = timestamp >= threshold

    return {
        'status': 'fresh' if is_fresh else 'stale',
        'master_sku': master_sku,
        'data_type': data_type,
        'age_days': age_days,
        'ttl_days': cfg['ttl_days'],
        'last_updated': timestamp.isoformat()
    }

async def get_stale_data_report() -> dict:
    """Generate report of all stale data across the system (VALID-02)."""
    from feedops.db.supabase_client import get_client

    client = get_client()
    now = datetime.now(timezone.utc)

    # Check baselines (>60 days)
    baseline_threshold = now - timedelta(days=60)
    stale_baselines = client.table('performance_baselines') \
        .select('master_sku, platform, created_at') \
        .lt('created_at', baseline_threshold.isoformat()) \
        .execute()

    # Check search terms (>7 days)
    search_threshold = now - timedelta(days=7)
    stale_search = client.table('search_queries') \
        .select('master_sku', count='exact') \
        .lt('fetched_at', search_threshold.isoformat()) \
        .execute()

    # Check keyword metrics (>30 days)
    keyword_threshold = now - timedelta(days=30)
    stale_keywords = client.table('keyword_metrics') \
        .select('keyword', count='exact') \
        .lt('updated_at', keyword_threshold.isoformat()) \
        .execute()

    return {
        'generated_at': now.isoformat(),
        'stale_baselines': {
            'count': len(stale_baselines.data),
            'threshold_days': 60,
            'samples': stale_baselines.data[:5]  # First 5 examples
        },
        'stale_search_terms': {
            'count': stale_search.count,
            'threshold_days': 7
        },
        'stale_keywords': {
            'count': stale_keywords.count,
            'threshold_days': 30
        }
    }
```

### Example 3: Job Success Validation

```python
"""Job completion and success rate validation."""

from feedops.jobs.models import BackfillJob, JobStatus

def validate_job_success_rate(job: BackfillJob) -> dict:
    """Validate job meets 95% success threshold (VALID-07).

    Success criteria from Phase 5:
    - Status should be 'complete' if success_count >= 95%
    - Status should be 'partial' if 0% < success_count < 95%
    - Status should be 'failed' if success_count = 0%
    """
    total = job.total_items
    completed = job.completed_items
    failed = job.failed_items

    if total == 0:
        return {'valid': False, 'reason': 'Total items is zero'}

    success_rate = (completed / total) * 100
    expected_status = None

    if success_rate >= 95.0:
        expected_status = JobStatus.COMPLETE
    elif success_rate > 0:
        expected_status = JobStatus.PARTIAL
    else:
        expected_status = JobStatus.FAILED

    status_matches = job.status == expected_status

    return {
        'valid': status_matches,
        'job_id': str(job.id),
        'total_items': total,
        'completed_items': completed,
        'failed_items': failed,
        'success_rate': success_rate,
        'actual_status': job.status.value,
        'expected_status': expected_status.value,
        'threshold': 95.0
    }

async def validate_all_skus_processed(job: BackfillJob) -> dict:
    """Validate all 2,784 SKUs were processed (VALID-01)."""
    EXPECTED_TOTAL = 2784

    total = job.total_items
    processed = job.completed_items + job.failed_items

    # Check if job was created with correct total
    if total != EXPECTED_TOTAL:
        return {
            'valid': False,
            'reason': f'Job created with {total} SKUs, expected {EXPECTED_TOTAL}'
        }

    # Check if all SKUs were accounted for
    if processed != total:
        missing = total - processed
        return {
            'valid': False,
            'reason': f'{missing} SKUs unprocessed (completed: {job.completed_items}, failed: {job.failed_items})'
        }

    return {
        'valid': True,
        'total_skus': total,
        'completed': job.completed_items,
        'failed': job.failed_items,
        'coverage_pct': 100.0
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Application-only validation | Database CHECK constraints + Pydantic models | 2020s (PostgreSQL 9.x+) | Prevents bad data at source, ACID guarantees |
| Manual outlier thresholds | Statistical methods (Z-score, IQR) with SciPy | 2010s (SciPy maturity) | Reproducible, interpretable, handles edge cases |
| String-based timestamp comparisons | Timezone-aware datetime with Pydantic | Pydantic v2 (2023) | Automatic timezone normalization, prevents DST bugs |
| Query-time validation filters | Collection-time validation + flags | Modern data engineering (2020s) | Fail fast, better error visibility |

**Deprecated/outdated:**
- **Pandas for validation logic:** Pandas is excellent for analysis but overkill for validation (high memory, slow instantiation). Use Pydantic + NumPy instead. Pandas remains useful for dashboard analytics.
- **Custom date parsing:** Python's `datetime.fromisoformat()` and Pydantic's datetime fields handle 99% of cases. Don't write custom parsers.
- **Isolation forests for bounded metrics:** ML-based outlier detection (isolation forests, autoencoders) adds complexity for metrics with known bounds (CTR 0-1, impression share 0-100). Use Z-score/IQR instead.

## Open Questions

1. **Question: Should multi-SKU family detection trigger automatic flagging in `variant_index` or be computed at query time?**
   - What we know: Multi-SKU pattern exists (DMF-2/2X, DMF-2/3X), affects 10-15% of SKUs, needs visibility in dashboard
   - What's unclear: Trade-off between database normalization (computed column/trigger) vs application-layer detection
   - Recommendation: Start with application-layer detection (Phase 3), add database column in Phase 4 if performance becomes issue

2. **Question: What constitutes a "statistical outlier" that should block publishing vs just flag for review?**
   - What we know: Z-score > 3.0 is standard threshold (99.7% confidence), CTR/impression share have known bounds
   - What's unclear: Whether outliers indicate data quality issues or genuine performance anomalies (viral product, promotional campaign)
   - Recommendation: Flag outliers with warnings but DO NOT block publishing automatically. Require manual review for outliers exceeding 3.0 Z-score.

3. **Question: Should freshness validation prevent new content generation or just display warnings?**
   - What we know: Stale data leads to suboptimal content (missing recent search trends, outdated baselines)
   - What's unclear: Balance between data quality enforcement vs user flexibility (user may want to generate content anyway)
   - Recommendation: Display prominent warnings in dashboard but allow generation to proceed. Add "refresh data" button next to warnings.

## Sources

### Primary (HIGH confidence)

- [Pydantic Validators Documentation](https://docs.pydantic.dev/latest/concepts/validators/) - Field validators and constraints
- [Pydantic Complete Guide 2026 - DevToolbox](https://devtoolbox.dedyn.io/blog/pydantic-complete-guide) - Best practices for validation patterns
- [Data Freshness Best Practices - Elementary Data](https://www.elementary-data.com/post/data-freshness-best-practices-and-key-metrics-to-measure-success) - TTL monitoring strategies
- [Outlier Detection in Python - Built In](https://builtin.com/data-science/outlier-detection-python) - Z-score and IQR methods
- SciPy Documentation - Statistical functions (zscore, iqr)
- Existing codebase patterns:
  - `src/feedops/jobs/models.py` - Pydantic models with ConfigDict
  - `src/feedops/pipeline/validators.py` - Content validation patterns
  - `supabase/migrations/026_backfill_jobs.sql` - CHECK constraints
  - `docs/database/SCHEMA.md` - Schema validation requirements
  - `docs/architecture/multi-sku-pattern.md` - Multi-SKU family documentation

### Secondary (MEDIUM confidence)

- [Data Freshness Metrics - Anomalo](https://www.anomalo.com/blog/defining-data-freshness-measuring-and-monitoring-data-timeliness/) - SLA definitions
- [How to Use Pydantic for Data Validation - OneUpTime](https://oneuptime.com/blog/post/2026-01-28-use-pydantic-data-validation-python/view) - Practical examples
- [Outlier Detection Methods with IQR & Z-Score - Medium](https://vatsal12-p.medium.com/outlier-detection-methods-in-python-w-iqr-standard-deviation-bf8653f544bb) - Statistical method comparisons

### Tertiary (LOW confidence)

- [Why Data Freshness Matters - Tacnode](https://tacnode.io/post/data-freshness-use-cases) - Use case examples (not technical)
- [Stale Data Impact - Acceldata](https://www.acceldata.io/blog/how-to-identify-and-eliminate-stale-data-to-optimize-business-decisions) - Business context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Pydantic and SciPy are proven, existing patterns confirmed in codebase
- Architecture: HIGH - Patterns validated against Phase 5/6 implementations, database schema confirmed in SCHEMA.md
- Pitfalls: HIGH - Multi-SKU pattern documented in existing architecture docs, timestamp validation is standard practice

**Research date:** 2026-02-13
**Valid until:** 2026-03-13 (30 days - stable domain, Python data validation tooling changes slowly)

**Key limitations:**
- Did not research ML-based anomaly detection (out of scope - statistical methods sufficient for bounded metrics)
- Did not research real-time validation (out of scope - batch collection model sufficient for v1.0)
- Did not research custom Supabase functions/triggers (can add in Phase 4 if needed)
