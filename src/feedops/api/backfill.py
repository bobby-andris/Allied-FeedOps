"""Backfill API endpoints for data collection job management.

This module exposes the backfill job infrastructure as HTTP endpoints,
enabling dashboard and external callers to create, monitor, and resume
data backfill jobs for search terms, performance metrics, and keyword planner data.

Endpoints:
- POST /backfill/start - Create and start a backfill job
- GET /backfill/status/{job_id} - Get backfill job progress
- POST /backfill/resume/{job_id} - Resume failed/partial job
- GET /backfill/jobs - List backfill jobs

Job Type Routing:
The system routes each job_type to the appropriate worker and rate limiter:

- search_terms: collect_search_terms_batch with google_ads_limiter (10 QPS)
  - Uses campaign-join pattern for search term collection
  - Saves to search_queries table with idempotent upserts

- performance_metrics: collect_performance_batch with google_ads_limiter (10 QPS)
  - Aggregates variant-level metrics to master_sku level
  - Saves to performance_baselines with 180-day window

- keyword_planner: collect_keyword_planner_batch with keyword_planner_limiter (2 QPS)
  - Enriches keywords with search volume and competition data
  - Uses 30-day cache to minimize API calls

- custom_labels: collect_custom_labels_batch with no rate limiter
  - Syncs GMC custom labels to variant_index.custom_labels JSONB
  - Caches GMC data for 5 minutes (reused across batches)

- full_backfill: collect_full_backfill_batch with google_ads_limiter (10 QPS)
  - Composite worker that runs all 4 collection types sequentially
  - Execution order: search_terms → performance_metrics → keyword_planner → custom_labels
  - Single job, single processor, sequential sub-worker execution
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from feedops.api.telemetry import run_async_in_thread
from feedops.observability import get_request_id, log_event

logger = logging.getLogger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class StartBackfillRequest(BaseModel):
    """Request to start a backfill job.

    Config Options:
    - batch_size (default 10): Number of items processed per batch
    - checkpoint_interval (default 100): Save checkpoint every N items
    - days_lookback (default 180): Date range for data collection (search terms, performance)
    - mode (optional): Set to "incremental" to auto-detect stale SKUs when skus list is empty
    """

    job_type: Literal[
        "search_terms",
        "performance_metrics",
        "keyword_planner",
        "custom_labels",
        "full_backfill",
    ] = Field(..., description="Type of backfill job to run")
    skus: list[str] = Field(
        ...,
        min_length=0,
        max_length=3000,
        description="SKU IDs to process (can be empty if mode=incremental in config)",
    )
    config: dict = Field(
        default_factory=dict,
        description="Job config: batch_size (10), checkpoint_interval (100), days_lookback (180), mode (incremental)",
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


class ValidationReportResponse(BaseModel):
    """Response for data quality validation report."""

    completeness: dict | None = None
    freshness: dict
    outliers: dict
    generated_at: str


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


def _get_worker_config(job_type: str) -> tuple:
    """Get the worker function and rate limiter for a job type.

    Maps job_type to the appropriate collection worker and rate limiter
    based on API-specific rate limits:
    - search_terms: 10 QPS (Google Ads API)
    - performance_metrics: 10 QPS (Google Ads API)
    - keyword_planner: 2 QPS (Keyword Planner API)
    - custom_labels: No rate limit (GMC API has different limits)
    - full_backfill: Runs all 4 sequentially, uses most restrictive limiter (10 QPS)

    Args:
        job_type: One of search_terms, performance_metrics, keyword_planner, custom_labels, full_backfill

    Returns:
        Tuple of (process_fn, rate_limiter)

    Raises:
        ValueError: If job_type is unknown
    """
    from feedops.jobs.workers import (
        collect_search_terms_batch,
        collect_performance_batch,
        collect_keyword_planner_batch,
        collect_custom_labels_batch,
    )
    from feedops.jobs.rate_limiter import google_ads_limiter, keyword_planner_limiter

    async def collect_full_backfill_batch(batch: list[str]) -> list[dict]:
        """Composite worker: runs all 4 collection types sequentially for the same batch.

        Executes workers in dependency order:
        1. search_terms (feeds keyword_planner)
        2. performance_metrics
        3. keyword_planner (uses search_terms as seeds)
        4. custom_labels

        Args:
            batch: List of master SKU IDs to process

        Returns:
            List of result dicts with item_id, status, and sub_results
        """
        results = {}
        for sku in batch:
            results[sku] = {"item_id": sku, "status": "ok", "sub_results": {}}

        # Run in dependency order
        for sub_type, worker_fn in [
            ("search_terms", collect_search_terms_batch),
            ("performance_metrics", collect_performance_batch),
            ("keyword_planner", collect_keyword_planner_batch),
            ("custom_labels", collect_custom_labels_batch),
        ]:
            try:
                sub_results = await worker_fn(batch)
                for r in sub_results:
                    results[r["item_id"]]["sub_results"][sub_type] = r["status"]
            except Exception as e:
                logger.error(f"full_backfill sub-worker {sub_type} failed: {e}")
                for sku in batch:
                    results[sku]["sub_results"][sub_type] = "error"

        return list(results.values())

    config_map = {
        "search_terms": (collect_search_terms_batch, google_ads_limiter),
        "performance_metrics": (collect_performance_batch, google_ads_limiter),
        "keyword_planner": (collect_keyword_planner_batch, keyword_planner_limiter),
        "custom_labels": (collect_custom_labels_batch, None),
        "full_backfill": (collect_full_backfill_batch, google_ads_limiter),
    }

    if job_type not in config_map:
        raise ValueError(f"Unknown job type: {job_type}")

    return config_map[job_type]


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


async def _start_background_processing(job_id: str, skus: list[str], config: dict, job_type: str):
    """Background processing function for backfill jobs.

    This will be called via run_async_in_thread from main.py to ensure
    the job survives HTTP response completion.

    Routes to the correct worker function based on job_type:
    - search_terms: collect_search_terms_batch with google_ads_limiter (10 QPS)
    - performance_metrics: collect_performance_batch with google_ads_limiter (10 QPS)
    - keyword_planner: collect_keyword_planner_batch with keyword_planner_limiter (2 QPS)
    - custom_labels: collect_custom_labels_batch with no rate limiter
    - full_backfill: collect_full_backfill_batch (composite worker, runs all 4 sequentially)

    Sends notifications at job start/complete/fail via notify_job_event().

    Args:
        job_id: Job UUID
        skus: List of SKU IDs to process
        config: Job configuration dict
        job_type: Type of backfill job (determines worker selection)
    """
    from feedops.jobs.manager import get_job, update_job_status
    from feedops.jobs.processor import BatchProcessor
    from feedops.observability.alerts import notify_job_event

    try:
        # Get job details
        job = get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found, cannot start processing")
            return

        # Update status to running
        update_job_status(job_id, "running")

        # Log job start event with structured context
        log_event(
            logger,
            logging.INFO,
            "backfill.job.started",
            job_id=job_id,
            job_type=job_type,
            total_items=len(skus),
            batch_size=config.get("batch_size", 10),
        )

        # Send start notification (fire-and-forget)
        try:
            notify_job_event(
                event_type="started",
                job_id=job_id,
                job_type=job_type,
                details={"total_items": len(skus)},
            )
        except Exception as notify_error:
            logger.warning(f"Failed to send start notification: {notify_error}")

        # Extract config
        batch_size = config.get("batch_size", 10)
        checkpoint_interval = config.get("checkpoint_interval", 100)

        # Get worker function and rate limiter for this job type
        process_fn, rate_limiter = _get_worker_config(job_type)

        # If force_backfill is set in config, wrap the performance worker to bypass
        # the contamination check (designed for historical backfills, not live captures)
        if config.get("force_backfill") and job_type in ("performance_metrics", "full_backfill"):
            _base_fn = process_fn
            async def process_fn(batch: list[str]) -> list[dict]:
                return await _base_fn(batch, force_backfill=True)

        # Create processor with job-type-specific worker and rate limiter
        processor = BatchProcessor(
            job_id=job_id,
            items=skus,
            batch_size=batch_size,
            checkpoint_interval=checkpoint_interval,
            rate_limiter=rate_limiter,
        )

        # Run processing with real worker function
        await processor.run(process_fn=process_fn)

        # Log job completion event
        final_job = get_job(job_id)
        if final_job:
            log_event(
                logger,
                logging.INFO,
                "backfill.job.completed",
                job_id=job_id,
                job_type=job_type,
                status=final_job.status,
                completed_items=final_job.completed_items,
                failed_items=final_job.failed_items,
            )

            # Send completion notification (fire-and-forget)
            try:
                notify_job_event(
                    event_type="completed",
                    job_id=job_id,
                    job_type=job_type,
                    details={
                        "total": final_job.total_items,
                        "completed": final_job.completed_items,
                        "failed": final_job.failed_items,
                    },
                )
            except Exception as notify_error:
                logger.warning(f"Failed to send completion notification: {notify_error}")

        logger.info(f"Background processing completed for job {job_id}")

    except Exception as e:
        # Log job failure event
        log_event(
            logger,
            logging.ERROR,
            "backfill.job.failed",
            job_id=job_id,
            job_type=job_type,
            error=str(e),
            error_type=type(e).__name__,
        )
        logger.error(f"Background processing failed for job {job_id}: {e}")

        # Send failure notification (fire-and-forget)
        try:
            job = get_job(job_id)
            notify_job_event(
                event_type="failed",
                job_id=job_id,
                job_type=job_type,
                details={
                    "error": str(e),
                    "total": job.total_items if job else len(skus),
                    "completed": job.completed_items if job else 0,
                    "failed": job.failed_items if job else 0,
                },
            )
        except Exception as notify_error:
            logger.warning(f"Failed to send failure notification: {notify_error}")

        # Processor will have marked job as failed via manager functions


# =============================================================================
# Endpoint Handlers
# =============================================================================


async def start_backfill(request: StartBackfillRequest) -> BackfillJobResponse:
    """Create and start a new data backfill job.

    Enforces maximum 3 concurrent jobs (JOB-10) to prevent database
    connection exhaustion. Creates job record, starts background processing
    via run_async_in_thread (not BackgroundTasks), and returns initial state.

    Supports incremental mode: if config.mode == "incremental" and skus list is empty,
    automatically detects stale SKUs using get_stale_skus().

    Args:
        request: Job configuration with type, SKUs, and config

    Returns:
        Initial job state

    Raises:
        HTTPException: 429 if max concurrent jobs reached
        HTTPException: 400 if skus empty and mode is not incremental
    """
    from feedops.jobs.manager import create_job, get_active_job_count

    # Check concurrent job limit (JOB-10)
    active_count = get_active_job_count()
    if active_count >= 3:
        raise HTTPException(
            status_code=429,
            detail="Maximum concurrent jobs (3) reached. Wait for active jobs to complete.",
        )

    # Handle incremental mode: auto-detect stale SKUs if list is empty
    skus = request.skus
    mode = request.config.get("mode")

    if not skus:
        if mode == "incremental":
            logger.info("Incremental mode detected with empty SKU list - auto-detecting stale SKUs")
            from feedops.jobs.scheduler import get_stale_skus

            days_threshold = request.config.get("days_lookback", 7)
            skus = get_stale_skus(days_threshold=days_threshold)

            if not skus:
                logger.info("No stale SKUs found - nothing to process")
                # Still create a job for tracking purposes but it will complete immediately
                skus = []
        else:
            raise HTTPException(
                status_code=400,
                detail="SKU list cannot be empty unless config.mode is set to 'incremental'",
            )

    # Log job creation event with structured context
    log_event(
        logger,
        logging.INFO,
        "backfill.job.created",
        job_type=request.job_type,
        total_skus=len(skus),
        mode=mode,
        batch_size=request.config.get("batch_size", 10),
        checkpoint_interval=request.config.get("checkpoint_interval", 100),
        request_id=get_request_id(),
    )

    logger.info(
        f"Starting backfill job: type={request.job_type}, skus={len(skus)}, mode={mode}"
    )

    # Create job in database (use resolved skus, not request.skus)
    job_id = create_job(
        job_type=request.job_type,
        skus=skus,
        config=request.config,
    )

    # Start background processing via run_async_in_thread from telemetry
    # This ensures the job survives HTTP response completion on Cloud Run
    run_async_in_thread(
        _start_background_processing,
        request_id=None,  # TODO: Pass request_id from context
        job_id=str(job_id),
        skus=skus,  # Use resolved skus, not request.skus
        config=request.config,
        job_type=request.job_type,
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

    # Extract SKUs, config, and job_type from job
    skus = job.skus or []
    config = job.config or {}
    job_type = job.job_type

    # Start background processing from checkpoint
    run_async_in_thread(
        _start_background_processing,
        request_id=None,  # TODO: Pass request_id from context
        job_id=job_id,
        skus=skus,
        config=config,
        job_type=job_type,
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


async def get_validation_report(job_id: str | None = None) -> ValidationReportResponse:
    """Get data quality validation report.

    Returns completeness (if job_id provided), freshness, and outlier metrics.
    Dashboard uses this to display data quality indicators.

    Args:
        job_id: Optional job ID for completeness check

    Returns:
        ValidationReportResponse with quality metrics
    """
    from feedops.jobs.quality_report import generate_full_quality_report
    from datetime import datetime, timezone

    report = generate_full_quality_report(job_id=job_id)

    return ValidationReportResponse(
        completeness=report.get("completeness"),
        freshness=report["freshness"],
        outliers=report["outliers"],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
