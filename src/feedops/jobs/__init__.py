"""Backfill job infrastructure for FeedOps.

This module provides the foundational job management layer for v1.0 historical
data backfill operations. It supports:

- Job creation and lifecycle tracking (creating -> running -> complete/failed/partial)
- Progress monitoring with ETA calculations
- Checkpoint/resume for long-running batch operations
- Error logging and retry tracking

Usage:
    from feedops.jobs import create_job, update_job_status, get_job

    job_id = create_job('search_terms', skus=['WP-2/16-GAL', '920D-6'])
    update_job_status(job_id, 'running')
    job = get_job(job_id)
"""

from feedops.jobs.models import JobStatus, JobType, BackfillJob, JobError
from feedops.jobs.manager import (
    create_job,
    get_job,
    get_active_jobs,
    get_active_job_count,
    update_job_status,
    update_job_progress,
    save_checkpoint,
    log_job_error,
    get_job_errors,
)
from feedops.jobs.processor import BatchProcessor
from feedops.jobs.workers import (
    collect_search_terms_batch,
    collect_performance_batch,
    collect_keyword_planner_batch,
    collect_custom_labels_batch,
)

__all__ = [
    # Models
    "JobStatus",
    "JobType",
    "BackfillJob",
    "JobError",
    # Manager functions
    "create_job",
    "get_job",
    "get_active_jobs",
    "get_active_job_count",
    "update_job_status",
    "update_job_progress",
    "save_checkpoint",
    "log_job_error",
    "get_job_errors",
    # Processor
    "BatchProcessor",
    # Workers
    "collect_search_terms_batch",
    "collect_performance_batch",
    "collect_keyword_planner_batch",
    "collect_custom_labels_batch",
]
