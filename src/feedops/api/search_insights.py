"""Search Insights API endpoints for Cloud Run.

Provides endpoints for syncing and querying search term data from Google Ads,
with Keyword Planner enrichment for search volume context.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.integrations.google_ads_search_terms import (
    SearchTermsClient,
    KeywordPlannerClient,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search-insights", tags=["Search Insights"])


# =============================================================================
# Request/Response Models
# =============================================================================


class SyncSearchTermsRequest(BaseModel):
    """Request to sync search terms from Google Ads."""

    days: int = Field(
        default=30, ge=7, le=90, description="Days of data to fetch"
    )
    limit: int = Field(
        default=1000, ge=100, le=5000, description="Max search terms to fetch"
    )
    enrich_with_keyword_planner: bool = Field(
        default=True, description="Enrich with Keyword Planner search volume data"
    )


class EnrichKeywordsRequest(BaseModel):
    """Request to enrich keywords with Keyword Planner data."""

    keywords: list[str] = Field(
        ..., min_length=1, max_length=500, description="Keywords to enrich"
    )
    use_cache: bool = Field(
        default=True, description="Use cached metrics if available"
    )


class SyncJobResponse(BaseModel):
    """Response from sync endpoint."""

    success: bool
    job_id: str
    status: str
    days_requested: int
    enrich_requested: bool


class SyncStatusResponse(BaseModel):
    """Response from sync status endpoint."""

    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    queries_fetched: int
    queries_enriched: int
    error_message: str | None


class KeywordMetricsResponse(BaseModel):
    """Response from keyword metrics endpoint."""

    keywords: dict  # keyword -> metrics
    cached_count: int
    fetched_count: int


class SearchTermsResponse(BaseModel):
    """Response from search terms query endpoint."""

    success: bool
    count: int
    data: list[dict]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/sync", response_model=SyncJobResponse)
async def sync_search_terms(request: SyncSearchTermsRequest):
    """Sync search terms from Google Ads.

    Creates a sync job and processes in the background.
    Use GET /search-insights/sync/{job_id} to check status.
    """
    try:
        supabase = get_client()

        # Create sync job record
        job_result = supabase.table("search_query_sync_jobs").insert({
            "status": "pending",
            "job_type": "full_sync" if request.enrich_with_keyword_planner else "search_terms",
            "days_lookback": request.days,
            "limit_results": request.limit,
            "enrich_with_keyword_planner": request.enrich_with_keyword_planner,
            "queries_fetched": 0,
            "queries_enriched": 0,
        }).execute()

        job_id = job_result.data[0]["id"]

        # Queue background processing (using thread to survive container lifecycle)
        from feedops.api.main import run_async_in_thread
        run_async_in_thread(
            process_sync_job,
            job_id=job_id,
            days=request.days,
            limit=request.limit,
            enrich=request.enrich_with_keyword_planner,
        )

        return SyncJobResponse(
            success=True,
            job_id=str(job_id),
            status="pending",
            days_requested=request.days,
            enrich_requested=request.enrich_with_keyword_planner,
        )

    except Exception as e:
        logger.error(f"Sync job creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/{job_id}", response_model=SyncStatusResponse)
async def get_sync_status(job_id: str):
    """Get status of a search terms sync job."""
    try:
        supabase = get_client()

        result = supabase.table("search_query_sync_jobs").select("*").eq(
            "id", job_id
        ).single().execute()

        if not result.data:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        job = result.data
        return SyncStatusResponse(
            job_id=job_id,
            status=job["status"],
            queries_fetched=job.get("queries_fetched", 0),
            queries_enriched=job.get("queries_enriched", 0),
            error_message=job.get("error_message"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enrich", response_model=KeywordMetricsResponse)
async def enrich_keywords(request: EnrichKeywordsRequest):
    """Enrich keywords with Keyword Planner metrics.

    Fetches search volume, competition, and CPC data for the provided keywords.
    Results are cached in the keyword_metrics table.
    """
    try:
        kp_client = KeywordPlannerClient()

        metrics = kp_client.get_historical_metrics(
            keywords=request.keywords,
            use_cache=request.use_cache,
        )

        # Count cached vs fetched
        cached_count = 0
        fetched_count = 0

        if request.use_cache:
            # Check which were in cache
            supabase = get_client()
            cached = supabase.table("keyword_metrics").select("keyword").in_(
                "keyword", request.keywords
            ).execute()
            cached_keywords = {r["keyword"] for r in (cached.data or [])}
            cached_count = len(cached_keywords & set(metrics.keys()))
            fetched_count = len(metrics) - cached_count
        else:
            fetched_count = len(metrics)

        return KeywordMetricsResponse(
            keywords=metrics,
            cached_count=cached_count,
            fetched_count=fetched_count,
        )

    except Exception as e:
        logger.error(f"Keyword enrichment failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/terms", response_model=SearchTermsResponse)
async def get_search_terms(
    master_sku: str | None = None,
    finish_code: str | None = None,
    min_impressions: int = 0,
    limit: int = 100,
):
    """Query stored search terms from database.

    Args:
        master_sku: Filter by master SKU
        finish_code: Filter by finish code (variant)
        min_impressions: Minimum impressions threshold
        limit: Max results to return
    """
    try:
        supabase = get_client()

        query = supabase.table("search_queries").select("*").order(
            "impressions", desc=True
        ).limit(limit)

        if master_sku:
            canonical_master_sku = resolve_canonical_master_sku(
                supabase,
                master_sku,
                tables=("search_queries", "variant_index", "product_catalog"),
            )
            query = query.eq("master_sku", canonical_master_sku)

        if finish_code:
            query = query.eq("finish_code", finish_code)

        if min_impressions > 0:
            query = query.gte("impressions", min_impressions)

        result = query.execute()

        return SearchTermsResponse(
            success=True,
            count=len(result.data or []),
            data=result.data or [],
        )

    except Exception as e:
        logger.error(f"Failed to query search terms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregated", response_model=SearchTermsResponse)
async def get_aggregated_terms(
    master_sku: str | None = None,
    limit: int = 100,
):
    """Query aggregated search terms (across all variants of a master SKU).

    Args:
        master_sku: Filter by master SKU
        limit: Max results to return
    """
    try:
        supabase = get_client()

        query = supabase.table("search_queries_by_master_sku").select("*").order(
            "total_impressions", desc=True
        ).limit(limit)

        if master_sku:
            canonical_master_sku = resolve_canonical_master_sku(
                supabase,
                master_sku,
                tables=(
                    "search_queries_by_master_sku",
                    "search_queries",
                    "variant_index",
                    "product_catalog",
                ),
            )
            query = query.eq("master_sku", canonical_master_sku)

        result = query.execute()

        return SearchTermsResponse(
            success=True,
            count=len(result.data or []),
            data=result.data or [],
        )

    except Exception as e:
        logger.error(f"Failed to query aggregated terms: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/keywords/ideas")
async def get_keyword_ideas(
    seed_keywords: str,
    seed_url: str | None = None,
    limit: int = 50,
):
    """Generate keyword ideas from Keyword Planner.

    Args:
        seed_keywords: Comma-separated seed keywords
        seed_url: Optional URL to extract keywords from
        limit: Max ideas to return
    """
    try:
        keywords = [k.strip() for k in seed_keywords.split(",") if k.strip()]

        if not keywords and not seed_url:
            raise HTTPException(
                status_code=400,
                detail="Must provide seed_keywords or seed_url"
            )

        kp_client = KeywordPlannerClient()

        ideas = kp_client.generate_keyword_ideas(
            seed_keywords=keywords if keywords else None,
            seed_url=seed_url,
            limit=limit,
        )

        return {
            "success": True,
            "count": len(ideas),
            "seed_keywords": keywords,
            "seed_url": seed_url,
            "ideas": ideas,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Keyword ideas failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Background Tasks
# =============================================================================


async def process_sync_job(
    job_id: str,
    days: int,
    limit: int,
    enrich: bool,
):
    """Background task to sync search terms from Google Ads.

    1. Fetches search terms with variant mapping
    2. Saves to search_queries table
    3. Aggregates by master SKU
    4. Optionally enriches with Keyword Planner data
    """
    from datetime import datetime, timezone

    supabase = get_client()

    try:
        # Update job status
        supabase.table("search_query_sync_jobs").update({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        # Initialize client
        client = SearchTermsClient()

        # Calculate period
        period_end = date.today()
        period_start = period_end - timedelta(days=days)

        # Fetch search terms
        logger.info(f"Fetching search terms for last {days} days...")
        search_terms = client.fetch_search_terms(days=days, limit=limit)

        queries_fetched = len(search_terms)
        logger.info(f"Fetched {queries_fetched} search terms")

        # Update progress
        supabase.table("search_query_sync_jobs").update({
            "queries_fetched": queries_fetched,
        }).eq("id", job_id).execute()

        # Save to database
        saved_count = client.save_search_terms_to_db(
            search_terms=search_terms,
            period_start=period_start,
            period_end=period_end,
            sync_job_id=job_id,
        )
        logger.info(f"Saved {saved_count} search terms to database")

        # Aggregate by master SKU
        aggregated_count = client.aggregate_by_master_sku(
            period_start=period_start,
            period_end=period_end,
        )
        logger.info(f"Created {aggregated_count} aggregated records")

        # Enrich with Keyword Planner if requested
        queries_enriched = 0
        if enrich:
            logger.info("Enriching with Keyword Planner metrics...")
            queries_enriched = client.enrich_with_keyword_metrics(
                period_start=period_start,
                period_end=period_end,
            )
            logger.info(f"Enriched {queries_enriched} queries")

        # Mark job complete
        supabase.table("search_query_sync_jobs").update({
            "status": "completed",
            "queries_fetched": queries_fetched,
            "queries_enriched": queries_enriched,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()

        logger.info(f"Sync job {job_id} completed successfully")

    except Exception as e:
        logger.error(f"Sync job {job_id} failed: {e}")

        supabase.table("search_query_sync_jobs").update({
            "status": "failed",
            "error_message": str(e)[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", job_id).execute()
