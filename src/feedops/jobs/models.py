"""Pydantic models and enums for backfill job data structures."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobStatus(str, Enum):
    """Job lifecycle status values."""

    CREATING = "creating"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    PARTIAL = "partial"


class JobType(str, Enum):
    """Supported backfill job types."""

    SEARCH_TERMS = "search_terms"
    PERFORMANCE_METRICS = "performance_metrics"
    KEYWORD_PLANNER = "keyword_planner"
    CUSTOM_LABELS = "custom_labels"
    FULL_BACKFILL = "full_backfill"


class BackfillJob(BaseModel):
    """Represents a backfill job record from the database.

    This model mirrors the backfill_jobs table structure and supports
    type-safe access to job data.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_type: JobType
    status: JobStatus
    total_items: int
    completed_items: int
    failed_items: int
    skus: list[str] | None = None
    checkpoint_data: dict[str, Any] | None = None
    config: dict[str, Any]
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    eta_seconds: int | None = None
    created_by: str | None = None


class JobError(BaseModel):
    """Represents an error log entry for a backfill job.

    Captures per-item failures to support debugging and selective retry.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: UUID
    item_id: str
    error_type: str
    error_message: str | None = None
    retry_count: int
    created_at: datetime
