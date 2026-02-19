"""Monitoring API endpoints for production observability.

Provides data layer for dashboard UI monitoring, coverage tracking, and API health visibility.

Endpoints:
- GET /monitoring/freshness - Per-SKU data age for search_terms, performance, keywords
- GET /monitoring/coverage - SKU coverage counts per collection type
- GET /monitoring/api-health - API latency p95, error counts, rate limit hits
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from feedops.db.supabase_client import get_client
from feedops.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# =============================================================================
# Response Models
# =============================================================================


class SKUFreshnessData(BaseModel):
    """Per-SKU data freshness metrics."""

    master_sku: str
    search_terms_age_days: int
    performance_age_days: int
    keywords_age_days: int


class FreshnessResponse(BaseModel):
    """Freshness endpoint response."""

    freshness: list[SKUFreshnessData]


class CoverageResponse(BaseModel):
    """Coverage endpoint response."""

    total_skus: int                    # distinct master_skus in variant_index
    total_offer_ids: int               # distinct gmc_offer_ids in variant_index
    search_terms_coverage: int         # master SKUs with any search term data (backwards compat alias)
    search_terms_sku_coverage: int     # master SKUs with any search term data (explicit name)
    search_terms_offer_coverage: int   # distinct gmc_offer_ids in search_queries
    performance_coverage: int          # master SKUs with performance_baselines
    keywords_coverage: int             # master SKUs with keyword metrics in search_queries


class ApiHealthResponse(BaseModel):
    """API health endpoint response."""

    error_count: int
    provider_errors: int
    latency_p95_ms: float
    rate_limit_hits: int
    sample_size: int


# =============================================================================
# Helper Functions
# =============================================================================


def _paginate_all(supabase, table: str, columns: str, page_size: int = 1000) -> list[dict]:
    """Fetch all rows from a table using range pagination to bypass the 1000-row PostgREST limit.

    Args:
        supabase: Supabase client
        table: Table name
        columns: Columns to select (comma-separated string)
        page_size: Rows per page (default 5000)

    Returns:
        All rows as a list of dicts
    """
    all_rows = []
    offset = 0
    while True:
        result = (
            supabase.table(table)
            .select(columns)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_rows


# =============================================================================
# Monitoring Endpoints
# =============================================================================


@router.get("/freshness", response_model=FreshnessResponse)
async def get_data_freshness():
    """Get per-SKU data age for search_terms, performance, and keywords.

    Returns age in days for each data collection type per SKU.
    Age defaults to 999 if no data has been collected.

    Uses paginated Supabase table queries to bypass the 1000-row PostgREST limit.
    """
    try:
        supabase = get_client()
        now = datetime.now(timezone.utc)

        # 1. Get all distinct master_skus (variant_index has ~72k rows — must paginate)
        vi_rows = _paginate_all(supabase, "variant_index", "master_sku")
        all_skus = sorted(set(row["master_sku"] for row in vi_rows if row.get("master_sku")))

        # 2. Get search_queries freshness (most recent fetched_at per SKU)
        # search_queries can have many rows — paginate to ensure we get all
        sq_rows = _paginate_all(supabase, "search_queries", "master_sku,fetched_at")
        search_freshness = {}
        for row in sq_rows:
            sku = row.get("master_sku")
            fetched = row.get("fetched_at")
            if sku and fetched:
                ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
                if sku not in search_freshness or ts > search_freshness[sku]:
                    search_freshness[sku] = ts

        # 3. Get performance_baselines freshness (most recent created_at per SKU)
        # performance_baselines has at most ~2784 rows — single paginated fetch is fine
        pb_rows = _paginate_all(supabase, "performance_baselines", "master_sku,created_at")
        perf_freshness = {}
        for row in pb_rows:
            sku = row.get("master_sku")
            created = row.get("created_at")
            if sku and created:
                ts = datetime.fromisoformat(created.replace("Z", "+00:00"))
                if sku not in perf_freshness or ts > perf_freshness[sku]:
                    perf_freshness[sku] = ts

        # 4. Get keyword metrics freshness (most recent keyword_metrics_updated_at per SKU)
        # Only rows where keyword_metrics_updated_at is not null
        kw_rows = (
            supabase.table("search_queries")
            .select("master_sku,keyword_metrics_updated_at")
            .not_.is_("keyword_metrics_updated_at", "null")
            .range(0, 9999)
            .execute()
        ).data or []
        kw_freshness = {}
        for row in kw_rows:
            sku = row.get("master_sku")
            updated = row.get("keyword_metrics_updated_at")
            if sku and updated:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if sku not in kw_freshness or ts > kw_freshness[sku]:
                    kw_freshness[sku] = ts

        # 5. Compute ages in days
        freshness_data = []
        for sku in all_skus:
            # Calculate days since last update, default to 999 if no data
            if sku in search_freshness:
                search_age = min(int((now - search_freshness[sku]).total_seconds() / 86400), 999)
            else:
                search_age = 999

            if sku in perf_freshness:
                perf_age = min(int((now - perf_freshness[sku]).total_seconds() / 86400), 999)
            else:
                perf_age = 999

            if sku in kw_freshness:
                kw_age = min(int((now - kw_freshness[sku]).total_seconds() / 86400), 999)
            else:
                kw_age = 999

            freshness_data.append(
                SKUFreshnessData(
                    master_sku=sku,
                    search_terms_age_days=search_age,
                    performance_age_days=perf_age,
                    keywords_age_days=kw_age,
                )
            )

        logger.info(f"Freshness check returned data for {len(freshness_data)} SKUs")
        return FreshnessResponse(freshness=freshness_data)

    except Exception as e:
        logger.exception(f"Freshness endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch freshness data: {str(e)}")


@router.get("/coverage", response_model=CoverageResponse)
async def get_data_coverage():
    """Get SKU coverage counts per collection type.

    Returns:
    - total_skus: Total distinct master_skus in variant_index
    - total_offer_ids: Total distinct gmc_offer_ids in variant_index
    - search_terms_coverage: Master SKUs with at least one search query (backwards compat)
    - search_terms_sku_coverage: Master SKUs with at least one search query
    - search_terms_offer_coverage: Distinct gmc_offer_ids in search_queries
    - performance_coverage: Master SKUs with at least one performance baseline
    - keywords_coverage: Master SKUs with keyword metrics collected

    Uses paginated Supabase table queries to bypass the 1000-row PostgREST limit.
    variant_index has ~72k rows; must paginate to get accurate counts.
    """
    try:
        supabase = get_client()

        # 1. Total distinct master_skus and gmc_offer_ids in variant_index
        # variant_index has ~72k rows — paginate to get all
        vi_rows = _paginate_all(supabase, "variant_index", "master_sku,gmc_offer_id")
        all_vi_skus = set()
        all_vi_offer_ids = set()
        for row in vi_rows:
            if row.get("master_sku"):
                all_vi_skus.add(row["master_sku"])
            if row.get("gmc_offer_id"):
                all_vi_offer_ids.add(row["gmc_offer_id"])
        total_skus = len(all_vi_skus)
        total_offer_ids = len(all_vi_offer_ids)

        # 2. Search terms SKU coverage — distinct master_skus with any search term data
        # Also collect distinct gmc_offer_ids for offer-level coverage
        sq_rows = _paginate_all(supabase, "search_queries", "master_sku,gmc_offer_id")
        sq_skus = set()
        sq_offer_ids = set()
        for row in sq_rows:
            if row.get("master_sku"):
                sq_skus.add(row["master_sku"])
            if row.get("gmc_offer_id"):
                sq_offer_ids.add(row["gmc_offer_id"])
        search_sku_coverage = len(sq_skus)
        search_offer_coverage = len(sq_offer_ids)

        # 3. Performance coverage — distinct master_skus with at least one performance baseline
        # performance_baselines has at most ~2784 rows — range(0, 2999) is sufficient
        pb_result = (
            supabase.table("performance_baselines")
            .select("master_sku")
            .range(0, 2999)
            .execute()
        )
        perf_coverage = len(set(
            row["master_sku"] for row in (pb_result.data or []) if row.get("master_sku")
        ))

        # 4. Keywords coverage — distinct master_skus with keyword metrics collected
        kw_result = (
            supabase.table("search_queries")
            .select("master_sku")
            .not_.is_("keyword_metrics_updated_at", "null")
            .range(0, 9999)
            .execute()
        )
        kw_coverage = len(set(
            row["master_sku"] for row in (kw_result.data or []) if row.get("master_sku")
        ))

        logger.info(
            f"Coverage: {search_sku_coverage}/{total_skus} SKUs with search terms, "
            f"{search_offer_coverage}/{total_offer_ids} offer IDs with search terms, "
            f"{perf_coverage}/{total_skus} performance, {kw_coverage}/{total_skus} keywords"
        )

        return CoverageResponse(
            total_skus=total_skus,
            total_offer_ids=total_offer_ids,
            search_terms_coverage=search_sku_coverage,       # backwards compat alias
            search_terms_sku_coverage=search_sku_coverage,
            search_terms_offer_coverage=search_offer_coverage,
            performance_coverage=perf_coverage,
            keywords_coverage=kw_coverage,
        )

    except Exception as e:
        logger.exception(f"Coverage endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch coverage data: {str(e)}")


@router.get("/api-health", response_model=ApiHealthResponse)
async def get_api_health():
    """Get API health metrics from metrics_registry.

    Returns:
    - error_count: Total HTTP request errors
    - provider_errors: Total provider (LLM/API) errors
    - latency_p95_ms: 95th percentile request latency
    - rate_limit_hits: Count of rate limit errors
    - sample_size: Number of latency observations

    Reads from in-memory metrics (not database).
    """
    try:
        snapshot = metrics_registry.snapshot()

        counters = snapshot.get("counters", {})
        timings = snapshot.get("timings", {})

        # Extract error counts
        error_count = 0
        provider_errors = 0
        rate_limit_hits = 0

        for (metric_name, tags), count in counters.items():
            if metric_name == "http_request_error_total":
                error_count += count
            elif metric_name == "provider_error_total":
                provider_errors += count
            elif "rate_limit" in metric_name.lower():
                rate_limit_hits += count

        # Calculate p95 latency from http_request_latency_seconds
        all_latencies = []
        for (metric_name, tags), latency_list in timings.items():
            if metric_name == "http_request_latency_seconds":
                all_latencies.extend(latency_list)

        latency_p95_ms = 0.0
        sample_size = len(all_latencies)

        if all_latencies:
            sorted_latencies = sorted(all_latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            if p95_index < len(sorted_latencies):
                latency_p95_ms = sorted_latencies[p95_index] * 1000  # Convert to ms

        logger.info(
            f"API health: {error_count} errors, {provider_errors} provider errors, "
            f"p95={latency_p95_ms:.2f}ms, {rate_limit_hits} rate limits (n={sample_size})"
        )

        return ApiHealthResponse(
            error_count=error_count,
            provider_errors=provider_errors,
            latency_p95_ms=latency_p95_ms,
            rate_limit_hits=rate_limit_hits,
            sample_size=sample_size,
        )

    except Exception as e:
        logger.exception(f"API health endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch API health: {str(e)}")
