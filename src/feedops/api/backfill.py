"""Backfill API endpoints for data collection job management.

This module exposes the backfill job infrastructure as HTTP endpoints,
enabling dashboard and external callers to create, monitor, and resume
data backfill jobs for search terms, performance metrics, and keyword planner data.

Endpoints:
- POST /backfill/start - Create and start a backfill job
- GET /backfill/status/{job_id} - Get backfill job progress
- POST /backfill/resume/{job_id} - Resume failed/partial job
- GET /backfill/jobs - List backfill jobs
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class StartBackfillRequest(BaseModel):
    """Request to start a backfill job."""

    job_type: Literal[
        "search_terms",
        "performance_metrics",
        "keyword_planner",
        "custom_labels",
        "full_backfill",
    ] = Field(..., description="Type of backfill job to run")
    skus: list[str] = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="SKU IDs to process",
    )
    config: dict = Field(
        default_factory=dict,
        description="Job config: batch_size, days_lookback, etc.",
    )


class ResumeBackfillRequest(BaseModel):
    """Empty body - job_id comes from URL path."""

    pass


class BackfillJobResponse(BaseModel):
    """Response for single backfill job status."""

    job_id: str
    job_type: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    eta_seconds: int | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    checkpoint_data: dict | None
    progress_pct: float  # Computed: completed_items / total_items * 100


class BackfillJobListResponse(BaseModel):
    """Response for list of backfill jobs."""

    jobs: list[BackfillJobResponse]
    active_count: int
    max_concurrent: int  # Always 3


# =============================================================================
# Helper Functions
# =============================================================================


def compute_date_range(days_lookback: int = 180) -> tuple[str, str]:
    """Compute explicit date range for GAQL queries (DATA-07).

    Google Ads API requires explicit date ranges in YYYY-MM-DD format,
    not LAST_N_DAYS syntax (validated in Phase 0.3).

    Args:
        days_lookback: Number of days to look back from today

    Returns:
        Tuple of (start_date, end_date) in YYYY-MM-DD format
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days_lookback)
    return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")


def normalize_offer_id(offer_id: str) -> str:
    """Ensure offer ID uses lowercase 'us' for API queries (DATA-08).

    Database stores offer IDs as shopify_us_* but GMC uses shopify_US_*.
    For API queries, we need lowercase format.

    Args:
        offer_id: Offer ID in any case format

    Returns:
        Offer ID with lowercase 'us': shopify_us_{product_id}_{variant_id}
    """
    return offer_id.replace("shopify_US_", "shopify_us_")


async def _noop_process(batch: list[str]) -> list[dict]:
    """Placeholder process function for Phase 1.

    This allows testing the full job infrastructure without requiring
    actual Google Ads API calls. Phase 2 will replace this with real
    data collection functions for each job type.

    Args:
        batch: List of SKU IDs to process

    Returns:
        List of result dicts with item_id and status
    """
    logger.info(f"Processing batch of {len(batch)} items (noop)")
    await asyncio.sleep(0.1)  # Simulate work
    return [{"item_id": item, "status": "ok"} for item in batch]


def _job_to_response(job) -> BackfillJobResponse:
    """Convert BackfillJob model to API response format.

    Args:
        job: BackfillJob Pydantic model from manager

    Returns:
        BackfillJobResponse with computed progress_pct
    """
    progress_pct = 0.0
    if job.total_items > 0:
        progress_pct = (job.completed_items / job.total_items) * 100

    return BackfillJobResponse(
        job_id=str(job.id),
        job_type=job.job_type,
        status=job.status,
        total_items=job.total_items,
        completed_items=job.completed_items,
        failed_items=job.failed_items,
        eta_seconds=job.eta_seconds,
        created_at=job.created_at.isoformat() if job.created_at else "",
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        checkpoint_data=job.checkpoint_data,
        progress_pct=round(progress_pct, 1),
    )


async def _start_background_processing(job_id: str, skus: list[str], config: dict):
    """Background processing function for backfill jobs.

    This will be called via run_async_in_thread from main.py to ensure
    the job survives HTTP response completion.

    Phase 1: Uses _noop_process placeholder
    Phase 2: Will route to real collection functions based on job_type

    Args:
        job_id: Job UUID
        skus: List of SKU IDs to process
        config: Job configuration dict
    """
    from feedops.jobs.manager import get_job, update_job_status
    from feedops.jobs.processor import BatchProcessor
    from feedops.jobs.rate_limiter import google_ads_limiter

    try:
        # Get job details
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found, cannot start processing")
            return

        # Update status to running
        update_job_status(job_id, "running")

        # Extract config
        batch_size = config.get("batch_size", 10)
        checkpoint_interval = config.get("checkpoint_interval", 100)

        # Create processor with appropriate rate limiter
        # For Phase 1, all jobs use google_ads_limiter
        # Phase 2 will select limiter based on job_type
        processor = BatchProcessor(
            job_id=job_id,
            items=skus,
            batch_size=batch_size,
            checkpoint_interval=checkpoint_interval,
            rate_limiter=google_ads_limiter,
        )

        # Run processing (with noop function for Phase 1)
        await processor.run(process_fn=_noop_process)

        logger.info(f"Background processing completed for job {job_id}")

    except Exception as e:
        logger.error(f"Background processing failed for job {job_id}: {e}")
        # Processor will have marked job as failed via manager functions


# =============================================================================
# Endpoint Handlers
# =============================================================================


async def start_backfill(request: StartBackfillRequest) -> BackfillJobResponse:
    """Create and start a new data backfill job.

    Enforces maximum 3 concurrent jobs (JOB-10) to prevent database
    connection exhaustion. Creates job record, starts background processing
    via run_async_in_thread (not BackgroundTasks), and returns initial state.

    Args:
        request: Job configuration with type, SKUs, and config

    Returns:
        Initial job state

    Raises:
        HTTPException: 429 if max concurrent jobs reached
    """
    from feedops.jobs.manager import create_job, get_active_job_count

    # Check concurrent job limit (JOB-10)
    active_count = get_active_job_count()
    if active_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent jobs (3) reached. Wait for active jobs to complete.",
        )

    logger.info(
        f"Starting backfill job: type={request.job_type}, skus={len(request.skus)}"
    )

    # Create job in database
    job_id = create_job(
        job_type=request.job_type,
        item_ids=request.skus,
        config=request.config,
    )

    # Start background processing via run_async_in_thread (imported from main.py)
    # This ensures the job survives HTTP response completion on Cloud Run
    from feedops.api.main import run_async_in_thread

    run_async_in_thread(
        _start_background_processing,
        request_id=None,  # TODO: Pass request_id from context
        job_id=str(job_id),
        skus=request.skus,
        config=request.config,
    )

    # Get job to return initial state
    from feedops.jobs.manager import get_job

    job = get_job(str(job_id))
    if not job:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve created job {job_id}"
        )

    return _job_to_response(job)


async def get_backfill_status(job_id: str) -> BackfillJobResponse:
    """Get backfill job status and progress.

    Args:
        job_id: Job UUID

    Returns:
        Current job state with progress percentage

    Raises:
        HTTPException: 404 if job not found
    """
    from feedops.jobs.manager import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return _job_to_response(job)


async def resume_backfill(job_id: str) -> BackfillJobResponse:
    """Resume a failed or partial backfill job from its last checkpoint.

    Validates job status (must be 'failed' or 'partial'), enforces
    concurrent job limit, and starts background processing from checkpoint.

    Args:
        job_id: Job UUID to resume

    Returns:
        Updated job state

    Raises:
        HTTPException: 404 if not found, 400 if wrong status, 429 if too many active
    """
    from feedops.jobs.manager import get_job, get_active_job_count

    # Get job and validate status
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    if job.status not in ["failed", "partial"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume job with status '{job.status}'. Only 'failed' or 'partial' jobs can be resumed.",
        )

    # Check concurrent job limit (JOB-10)
    active_count = get_active_job_count()
    if active_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent jobs (3) reached. Wait for active jobs to complete.",
        )

    logger.info(f"Resuming backfill job: {job_id} from checkpoint")

    # Extract SKUs and config from job
    skus = job.item_ids if hasattr(job, "item_ids") else []
    config = job.config or {}

    # Start background processing from checkpoint
    from feedops.api.main import run_async_in_thread

    run_async_in_thread(
        _start_background_processing,
        request_id=None,  # TODO: Pass request_id from context
        job_id=job_id,
        skus=skus,
        config=config,
    )

    # Get updated job state
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve job {job_id} after resume"
        )

    return _job_to_response(job)


async def list_backfill_jobs(
    status: str | None = None, limit: int = 20
) -> BackfillJobListResponse:
    """List backfill jobs, optionally filtered by status.

    Args:
        status: Optional status filter ('creating', 'running', 'complete', 'failed', 'partial')
        limit: Maximum number of jobs to return (default 20)

    Returns:
        List of jobs with active count and max concurrent limit
    """
    from feedops.db.supabase_client import get_client
    from feedops.jobs.manager import get_active_job_count
    from feedops.jobs.models import BackfillJob

    supabase = get_client()

    # Build query
    query = supabase.table("backfill_jobs").select("*").order("created_at", desc=True)

    if status:
        query = query.eq("status", status)

    query = query.limit(limit)

    # Execute query
    result = query.execute()

    # Convert to BackfillJob models
    jobs = []
    for row in result.data:
        try:
            job = BackfillJob.model_validate(row)
            jobs.append(_job_to_response(job))
        except Exception as e:
            logger.warning(f"Failed to parse job {row.get('id')}: {e}")

    # Get active count
    active_count = get_active_job_count()

    return BackfillJobListResponse(
        jobs=jobs,
        active_count=active_count,
        max_concurrent=3,
    )
