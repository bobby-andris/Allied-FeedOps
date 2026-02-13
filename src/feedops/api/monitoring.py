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

from fastapi import APIRouter
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

    total_skus: int
    search_terms_coverage: int
    performance_coverage: int
    keywords_coverage: int


class ApiHealthResponse(BaseModel):
    """API health endpoint response."""

    error_count: int
    provider_errors: int
    latency_p95_ms: float
    rate_limit_hits: int
    sample_size: int


# =============================================================================
# Monitoring Endpoints
# =============================================================================


@router.get("/freshness", response_model=FreshnessResponse)
async def get_data_freshness():
    """Get per-SKU data age for search_terms, performance, and keywords.

    Returns age in days for each data collection type per SKU.
    Age defaults to 999 if no data has been collected.

    Query uses efficient SQL aggregation (not per-SKU loops).
    """
    supabase = get_client()

    # Use efficient SQL aggregation to calculate freshness for all SKUs at once
    query = """
    SELECT
        vi.master_sku,
        EXTRACT(EPOCH FROM (NOW() - MAX(sq.collected_at))) / 86400 AS search_terms_age_days,
        EXTRACT(EPOCH FROM (NOW() - MAX(pb.captured_at))) / 86400 AS performance_age_days,
        EXTRACT(EPOCH FROM (NOW() - MAX(sq.keyword_metrics_collected_at))) / 86400 AS keywords_age_days
    FROM (SELECT DISTINCT master_sku FROM variant_index) vi
    LEFT JOIN search_queries sq ON sq.master_sku = vi.master_sku
    LEFT JOIN performance_baselines pb ON pb.master_sku = vi.master_sku
    GROUP BY vi.master_sku
    ORDER BY vi.master_sku
    """

    result = supabase.rpc("execute_sql", {"query": query}).execute()

    if not result.data:
        return FreshnessResponse(freshness=[])

    freshness_data = []
    for row in result.data:
        # Convert None to 999 for missing data
        search_age = int(row.get("search_terms_age_days") or 999)
        perf_age = int(row.get("performance_age_days") or 999)
        kw_age = int(row.get("keywords_age_days") or 999)

        # Cap at 999 for consistency
        search_age = min(search_age, 999)
        perf_age = min(perf_age, 999)
        kw_age = min(kw_age, 999)

        freshness_data.append(
            SKUFreshnessData(
                master_sku=row["master_sku"],
                search_terms_age_days=search_age,
                performance_age_days=perf_age,
                keywords_age_days=kw_age,
            )
        )

    logger.info(f"Freshness check returned data for {len(freshness_data)} SKUs")
    return FreshnessResponse(freshness=freshness_data)


@router.get("/coverage", response_model=CoverageResponse)
async def get_data_coverage():
    """Get SKU coverage counts per collection type.

    Returns:
    - total_skus: Total distinct master_skus in variant_index
    - search_terms_coverage: SKUs with at least one search query
    - performance_coverage: SKUs with at least one performance baseline
    - keywords_coverage: SKUs with keyword metrics collected
    """
    supabase = get_client()

    # Total SKUs
    total_result = supabase.rpc(
        "execute_sql",
        {"query": "SELECT COUNT(DISTINCT master_sku) AS count FROM variant_index"},
    ).execute()
    total_skus = total_result.data[0]["count"] if total_result.data else 0

    # Search terms coverage
    search_result = supabase.rpc(
        "execute_sql",
        {
            "query": "SELECT COUNT(DISTINCT master_sku) AS count FROM search_queries WHERE master_sku IS NOT NULL"
        },
    ).execute()
    search_coverage = search_result.data[0]["count"] if search_result.data else 0

    # Performance coverage
    perf_result = supabase.rpc(
        "execute_sql",
        {"query": "SELECT COUNT(DISTINCT master_sku) AS count FROM performance_baselines"},
    ).execute()
    perf_coverage = perf_result.data[0]["count"] if perf_result.data else 0

    # Keywords coverage (non-null keyword_metrics_collected_at)
    kw_result = supabase.rpc(
        "execute_sql",
        {
            "query": "SELECT COUNT(DISTINCT master_sku) AS count FROM search_queries WHERE keyword_metrics_collected_at IS NOT NULL"
        },
    ).execute()
    kw_coverage = kw_result.data[0]["count"] if kw_result.data else 0

    logger.info(
        f"Coverage: {search_coverage}/{total_skus} search terms, "
        f"{perf_coverage}/{total_skus} performance, {kw_coverage}/{total_skus} keywords"
    )

    return CoverageResponse(
        total_skus=total_skus,
        search_terms_coverage=search_coverage,
        performance_coverage=perf_coverage,
        keywords_coverage=kw_coverage,
    )


@router.get("/api-health", response_model=ApiHealthResponse)
async def get_api_health():
    """Get API health metrics from metrics_registry.

    Returns:
    - error_count: Total HTTP request errors
    - provider_errors: Total provider (LLM/API) errors
    - latency_p95_ms: 95th percentile request latency
    - rate_limit_hits: Count of rate limit errors
    - sample_size: Number of latency observations
    """
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
