"""Job lifecycle management functions for backfill jobs.

This module provides CRUD operations for backfill jobs, following the same
patterns as the existing Supabase client (get_client(), @_with_retry decorator).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from feedops.jobs.models import BackfillJob, JobError


def create_job(
    job_type: str,
    skus: list[str],
    config: dict[str, Any] | None = None,
    created_by: str | None = None,
) -> str:
    """Create a new backfill job record.

    Args:
        job_type: Type of job (search_terms, performance_metrics, etc.)
        skus: List of SKU strings to process
        config: Optional job configuration (batch_size, days_lookback, etc.)
        created_by: Optional identifier of the job creator

    Returns:
        The UUID of the created job as a string

    Example:
        job_id = create_job('search_terms', ['WP-2/16-GAL', '920D-6'], 
                           config={'batch_size': 10, 'days_lookback': 180})
    """
    from feedops.db.supabase_client import get_client

    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    data = {
        "job_type": job_type,
        "status": "creating",
        "total_items": len(skus),
        "completed_items": 0,
        "failed_items": 0,
        "skus": skus,
        "config": config or {},
        "created_at": now,
        "created_by": created_by,
    }

    result = client.table("backfill_jobs").insert(data).execute()

    if not result.data:
        raise RuntimeError("Failed to create backfill job")

    return str(result.data[0]["id"])


def get_job(job_id: str) -> BackfillJob | None:
    """Retrieve a backfill job by ID.

    Args:
        job_id: UUID string of the job

    Returns:
        BackfillJob model or None if not found
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    result = client.table("backfill_jobs").select("*").eq("id", job_id).execute()

    if not result.data:
        return None

    return BackfillJob(**result.data[0])


def get_active_jobs() -> list[BackfillJob]:
    """Retrieve all active jobs (creating or running status).

    Returns:
        List of BackfillJob models, ordered by created_at ascending
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    result = (
        client.table("backfill_jobs")
        .select("*")
        .in_("status", ["creating", "running"])
        .order("created_at", desc=False)
        .execute()
    )

    return [BackfillJob(**row) for row in result.data]


def get_active_job_count() -> int:
    """Count active jobs (creating or running status).

    Returns:
        Number of active jobs
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    result = (
        client.table("backfill_jobs")
        .select("id", count="exact")
        .in_("status", ["creating", "running"])
        .execute()
    )

    return result.count or 0


def update_job_status(
    job_id: str, status: str, completed_at: datetime | None = None
) -> None:
    """Update the status of a backfill job.

    Args:
        job_id: UUID string of the job
        status: New status ('creating', 'running', 'complete', 'failed', 'partial')
        completed_at: Optional completion timestamp (used for terminal states)

    Side effects:
        - If status is 'running' and started_at is NULL, sets started_at to NOW
        - If status is terminal ('complete', 'failed', 'partial'), sets completed_at
    """
    from feedops.db.supabase_client import get_client

    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    updates: dict[str, Any] = {"status": status}

    # Set started_at when job transitions to running (if not already set)
    if status == "running":
        # Check if started_at is already set
        job = get_job(job_id)
        if job and job.started_at is None:
            updates["started_at"] = now

    # Set completed_at for terminal states
    if status in ("complete", "failed", "partial"):
        updates["completed_at"] = completed_at.isoformat() if completed_at else now

    client.table("backfill_jobs").update(updates).eq("id", job_id).execute()


def update_job_progress(
    job_id: str, completed_items: int, total_items: int, started_at_epoch: float
) -> None:
    """Update job progress and calculate ETA.

    Args:
        job_id: UUID string of the job
        completed_items: Number of items completed so far
        total_items: Total number of items to process
        started_at_epoch: Unix timestamp when the job started (from time.time())

    Calculation:
        - elapsed = current_time - started_at_epoch
        - rate = completed_items / elapsed (items per second)
        - remaining = total_items - completed_items
        - eta = remaining / rate (seconds)

    Edge cases:
        - If elapsed <= 0 or rate <= 0, sets eta_seconds to NULL
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    # Calculate ETA
    elapsed = time.time() - started_at_epoch
    eta_seconds = None

    if elapsed > 0 and completed_items > 0:
        rate = completed_items / elapsed
        if rate > 0:
            remaining = total_items - completed_items
            eta_seconds = int(remaining / rate)

    updates = {
        "completed_items": completed_items,
        "eta_seconds": eta_seconds,
    }

    client.table("backfill_jobs").update(updates).eq("id", job_id).execute()


def save_checkpoint(job_id: str, checkpoint_data: dict[str, Any]) -> None:
    """Save checkpoint data for job resumption.

    Args:
        job_id: UUID string of the job
        checkpoint_data: Dictionary containing checkpoint state
                        (e.g., {"batch_index": 50, "last_sku": "920D-6"})

    This allows long-running jobs to resume from the last checkpoint
    after a Cloud Run container restart.
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    updates = {"checkpoint_data": checkpoint_data}

    client.table("backfill_jobs").update(updates).eq("id", job_id).execute()


def log_job_error(
    job_id: str,
    item_id: str,
    error_type: str,
    error_message: str,
    retry_count: int = 0,
) -> None:
    """Log an error for a specific item in a backfill job.

    Args:
        job_id: UUID string of the job
        item_id: Identifier of the failed item (usually a SKU)
        error_type: Category of error (e.g., 'api_error', 'validation_error')
        error_message: Detailed error message (truncated to 500 chars)
        retry_count: Number of retry attempts for this item

    Side effects:
        - Inserts error record into backfill_job_errors table
        - Atomically increments failed_items counter via RPC function
    """
    from feedops.db.supabase_client import get_client

    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    # Truncate error message to 500 characters
    truncated_message = error_message[:500] if error_message else None

    # Insert error record
    error_data = {
        "job_id": job_id,
        "item_id": item_id,
        "error_type": error_type,
        "error_message": truncated_message,
        "retry_count": retry_count,
        "created_at": now,
    }

    client.table("backfill_job_errors").insert(error_data).execute()

    # Atomically increment failed_items counter
    client.rpc("increment_backfill_failures", {"p_job_id": job_id}).execute()


def get_job_errors(job_id: str, limit: int = 100) -> list[JobError]:
    """Retrieve error logs for a backfill job.

    Args:
        job_id: UUID string of the job
        limit: Maximum number of errors to return (default 100)

    Returns:
        List of JobError models, ordered by created_at descending (most recent first)
    """
    from feedops.db.supabase_client import get_client

    client = get_client()

    result = (
        client.table("backfill_job_errors")
        .select("*")
        .eq("job_id", job_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return [JobError(**row) for row in result.data]
