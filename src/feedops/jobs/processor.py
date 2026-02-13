"""Generic batch processor with checkpointing, rate limiting, and error handling.

This module provides a reusable batch processing infrastructure that Phase 2 data
collection endpoints will use. The BatchProcessor handles:

- Batching: Process items in configurable batch sizes (default 10 per DATA-06)
- Checkpointing: Save progress every N items (default 100 per JOB-09) for resumability
- Rate limiting: Optional integration with TokenBucket rate limiters
- Error handling: Exponential backoff on transient errors, logging of permanent errors
- Progress tracking: Real-time progress updates to database
- Status management: Proper lifecycle from 'running' to 'complete'/'partial'

The processor is designed to work with the job management infrastructure created in
05-01 (parallel execution in Wave 1). It imports job management functions dynamically
inside the run() method to avoid circular import issues.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable

from feedops.jobs.rate_limiter import TokenBucket
from feedops.providers.reliability import (
    compute_backoff_seconds,
    is_retryable_provider_error,
)

logger = logging.getLogger(__name__)


class BatchProcessor:
    """Generic batch processor with checkpointing, rate limiting, and error handling.

    This is a base infrastructure class that data collection pipelines in Phase 2 will use.
    The processor handles all the cross-cutting concerns (batching, checkpointing, errors,
    progress) while the specific data processing logic is provided via the process_fn callback.

    Usage:
        processor = BatchProcessor(
            job_id="abc-123",
            items=["SKU-1", "SKU-2", ...],
            batch_size=10,
            checkpoint_interval=100,
            rate_limiter=google_ads_limiter,
        )
        await processor.run(process_fn=my_async_function)

    The process_fn receives a batch of item IDs and returns a list of result dicts.
    It MUST use idempotent upserts (ON CONFLICT) for all database writes to ensure
    checkpoint/resume doesn't create duplicates (JOB-06).
    """

    def __init__(
        self,
        job_id: str,
        items: list[str],
        batch_size: int = 10,
        checkpoint_interval: int = 100,
        rate_limiter: TokenBucket | None = None,
        max_retries: int = 3,
    ):
        """
        Args:
            job_id: The backfill_jobs UUID for tracking this job
            items: List of item IDs to process (SKUs, offer IDs, etc.)
            batch_size: Items per batch (default 10 per DATA-06)
            checkpoint_interval: Save checkpoint every N items (default 100 per JOB-09)
            rate_limiter: Optional TokenBucket rate limiter for API calls
            max_retries: Maximum retries per batch on transient errors (default 3)
        """
        self.job_id = job_id
        self.items = items
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval
        self.rate_limiter = rate_limiter
        self.max_retries = max_retries

    async def run(
        self, process_fn: Callable[[list[str]], Awaitable[list[dict]]]
    ) -> None:
        """Execute the batch processing job.

        Args:
            process_fn: Async function that receives a batch of item IDs and returns
                       a list of result dicts. MUST use idempotent upserts (ON CONFLICT)
                       for all database writes.

        This method:
        1. Loads job from DB to check for checkpoint data
        2. Resumes from checkpoint if it exists, else starts from beginning
        3. Sets job status to 'running'
        4. Processes items in batches with rate limiting and error handling
        5. Saves checkpoints every checkpoint_interval items
        6. Updates progress after each batch
        7. Determines final status based on success/failure counts
        8. Updates job with final status and completion timestamp
        """
        # Import job management functions inside method to avoid circular imports
        # (05-01 and 05-02 execute in parallel during Wave 1)
        from feedops.jobs.manager import (
            get_job,
            update_job_status,
            update_job_progress,
            save_checkpoint,
            log_job_error,
        )

        # Load job to check for checkpoint
        job = get_job(self.job_id)
        if not job:
            raise ValueError(f"Job {self.job_id} not found")

        # Resume from checkpoint if exists
        checkpoint_data = job.checkpoint_data or {}
        start_index = checkpoint_data.get("batch_index", 0)
        logger.info(
            f"Job {self.job_id}: Starting from index {start_index} "
            f"(checkpoint found: {bool(checkpoint_data)})"
        )

        # Set job to running status
        update_job_status(self.job_id, "running")

        # Track metrics
        start_time = time.time()
        total_items = len(self.items)
        completed_items = start_index
        failed_items = 0

        # Process items in batches
        batch_index = start_index
        while batch_index < total_items:
            batch_end = min(batch_index + self.batch_size, total_items)
            batch = self.items[batch_index:batch_end]
            batch_num = (batch_index // self.batch_size) + 1

            logger.info(
                f"Job {self.job_id}: Processing batch {batch_num} "
                f"(items {batch_index}-{batch_end-1})"
            )

            # Rate limiting
            if self.rate_limiter:
                await self.rate_limiter.acquire()

            # Process batch with retry logic
            success = False
            for attempt in range(self.max_retries + 1):
                try:
                    # Call the processing function
                    results = await process_fn(batch)
                    success = True
                    logger.info(
                        f"Job {self.job_id}: Batch {batch_num} completed - "
                        f"processed {len(results)} items"
                    )
                    break

                except Exception as exc:
                    is_last_attempt = attempt == self.max_retries

                    # Check if error is retryable
                    if is_retryable_provider_error(exc) and not is_last_attempt:
                        backoff = compute_backoff_seconds(attempt)
                        logger.warning(
                            f"Job {self.job_id}: Batch {batch_num} failed (attempt {attempt + 1}), "
                            f"retrying in {backoff:.2f}s: {exc}"
                        )
                        await asyncio.sleep(backoff)
                        continue

                    # Permanent error or max retries exceeded
                    logger.error(
                        f"Job {self.job_id}: Batch {batch_num} failed permanently: {exc}"
                    )
                    # Log error for first item in batch as representative
                    item_id = batch[0] if batch else "unknown"
                    error_context = f"batch_index={batch_index}, batch_size={len(batch)}, attempt={attempt + 1}"
                    log_job_error(
                        self.job_id,
                        item_id=item_id,
                        error_type="batch_error",
                        error_message=f"{str(exc)} [{error_context}]",
                        retry_count=attempt,
                    )
                    failed_items += len(batch)
                    break

            # Update completed count
            if success:
                completed_items += len(batch)

            # Update progress
            progress_pct = int((completed_items / total_items) * 100)
            update_job_progress(
                self.job_id,
                completed_items=completed_items,
                total_items=total_items,
                started_at_epoch=start_time,
            )

            logger.info(
                f"Job {self.job_id}: Progress {completed_items}/{total_items} ({progress_pct}%)"
            )

            # Save checkpoint every checkpoint_interval items
            if completed_items % self.checkpoint_interval == 0 or batch_end >= total_items:
                save_checkpoint(
                    self.job_id,
                    {
                        "batch_index": batch_end,
                        "last_item": batch[-1] if batch else None,
                    },
                )
                logger.info(f"Job {self.job_id}: Checkpoint saved at index {batch_end}")

            # Move to next batch
            batch_index = batch_end

        # Determine final status
        success_rate = completed_items / total_items if total_items > 0 else 0.0
        if failed_items == 0:
            final_status = "complete"
        elif success_rate >= 0.95:
            # Some failures acceptable (VALID-08 requirement)
            final_status = "complete"
            logger.info(
                f"Job {self.job_id}: Completed with {failed_items} failures "
                f"(success rate: {success_rate:.1%})"
            )
        else:
            final_status = "partial"
            logger.warning(
                f"Job {self.job_id}: Partial completion - success rate: {success_rate:.1%} "
                f"({completed_items}/{total_items} items)"
            )

        # Update job with final status
        duration = time.time() - start_time
        from datetime import datetime, timezone
        update_job_status(
            self.job_id,
            final_status,
            completed_at=datetime.now(timezone.utc),
        )

        # Post-completion validation: correct status if processor's success calculation
        # doesn't match the 95% threshold from VALIDATION_THRESHOLDS (VALID-07)
        try:
            from feedops.jobs.quality_report import correct_job_status
            correction = correct_job_status(self.job_id)
            if correction["corrected"]:
                final_status = correction["new_status"]
                logger.warning(
                    f"Job {self.job_id}: Status corrected from "
                    f"'{correction['old_status']}' to '{correction['new_status']}' "
                    f"by post-completion validation"
                )
        except Exception as e:
            # Don't let validation failure break the processor
            logger.error(f"Job {self.job_id}: Post-completion validation failed: {e}")

        logger.info(
            f"Job {self.job_id}: Finished with status '{final_status}' - "
            f"duration {duration:.1f}s, completed {completed_items}/{total_items} items, "
            f"failed {failed_items} items"
        )
