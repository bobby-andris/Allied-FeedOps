"""Telemetry, metrics, and background thread helpers for FeedOps Pipeline API."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

from feedops.api.generation_telemetry import provider_label as _provider_label
from feedops.api.runtime_controls import diagnostic_mode_enabled
from feedops.generation.persistence import (
    should_persist_finish_sentences as _task_should_persist_finish_sentences,
)
from feedops.observability import log_event, request_context
from feedops.observability.metrics import metrics_registry

logger = logging.getLogger(__name__)


# =============================================================================
# Background Job Helper (Thread-based for Cloud Run compatibility)
# =============================================================================


def run_async_in_thread(async_func, request_id: str | None = None, **kwargs):
    """Run async function in dedicated thread with new event loop.

    This is necessary for Cloud Run because FastAPI BackgroundTasks are killed
    when containers scale to zero. Using a non-daemon thread ensures the job
    completes even if the HTTP response has been sent.

    Args:
        async_func: Async function to run
        **kwargs: Arguments to pass to the function

    Returns:
        threading.Thread: The started thread
    """
    def wrapper():
        with request_context(request_id):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(async_func(**kwargs))
            except Exception as exc:
                logger.error(
                    "Background job %s crashed: %s", async_func.__name__, exc,
                    exc_info=True,
                )
                try:
                    from feedops.db.supabase_client import get_client
                    from datetime import datetime, timezone
                    sb = get_client()
                    jid = kwargs.get("job_id")
                    if jid:
                        sb.table("batch_generation_jobs").update({
                            "status": "failed",
                            "error_message": f"Thread crash: {str(exc)[:450]}",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", jid).execute()
                except Exception:
                    logger.error("Failed to update job status after thread crash")
            finally:
                loop.close()

    thread = threading.Thread(target=wrapper, daemon=False)
    thread.start()
    logger.info(f"Started background job thread: {async_func.__name__}")
    return thread


# =============================================================================
# Telemetry Helpers
# =============================================================================


def _emit_generation_summary(
    *,
    endpoint: str,
    request_id: str | None,
    master_sku: str,
    platform: str | None,
    content_type: str | None,
    mode: str,
    result_state: str,
    job_id: str | None = None,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    provider_attempt_count: int | None = None,
    parse_retry_count: int | None = None,
    diagnostic_mode: bool | None = None,
    finish_subcall_executed: bool | None = None,
    budget_stop_triggered: bool | None = None,
) -> None:
    """Emit a terminal generation summary event for observability."""
    fields: dict[str, object] = {
        "endpoint": endpoint,
        "request_id": request_id,
        "job_id": job_id,
        "master_sku": master_sku,
        "platform": platform,
        "content_type": content_type,
        "mode": mode,
        "result_state": result_state,
    }
    if tokens_used is not None:
        fields["tokens_used"] = int(tokens_used)
    if cost_usd is not None:
        fields["cost_usd"] = round(float(cost_usd), 6)
    if latency_ms is not None:
        fields["latency_ms"] = int(latency_ms)
    if provider_attempt_count is not None:
        fields["provider_attempt_count"] = int(provider_attempt_count)
    if parse_retry_count is not None:
        fields["parse_retry_count"] = int(parse_retry_count)
    if diagnostic_mode is None:
        diagnostic_mode = diagnostic_mode_enabled()
    fields["diagnostic_mode"] = bool(diagnostic_mode)
    if finish_subcall_executed is not None:
        fields["finish_subcall_executed"] = bool(finish_subcall_executed)
    if budget_stop_triggered is not None:
        fields["budget_stop_triggered"] = bool(budget_stop_triggered)

    log_event(
        logger,
        logging.INFO if result_state in {"completed", "no_change"} else logging.WARNING,
        "generation.request.summary",
        **fields,
    )


def _telemetry_scope_for_content(
    *,
    platform: str,
    content_type: str,
    generated: dict,
) -> tuple[str, ...]:
    """Map one persisted content row back to the task snapshots that produced it."""
    finish_ran = bool(generated.get("finish_subcall_executed", False))
    if not finish_ran:
        finish_ran = any(
            isinstance(snapshot, dict) and "finish" in snapshot
            for snapshot in (
                generated.get("usage_by_platform"),
                generated.get("latency_by_platform"),
                generated.get("retry_by_platform"),
            )
        )
    if (
        content_type == "description"
        and platform in {"google", "bing"}
        and finish_ran
    ):
        return (platform, "finish")
    return (platform,)


async def _generate_with_metrics(
    *,
    provider,
    prompt: str,
    schema: dict,
    system_prompt: str,
    endpoint: str,
    platform: str,
    content_type: str,
):
    """Wrapper that emits generation latency/error metrics per call."""
    started = time.perf_counter()
    try:
        return await provider.generate(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
        )
    except Exception:
        metrics_registry.increment(
            "provider_error_total",
            endpoint=endpoint,
            provider=_provider_label(provider),
            platform=platform,
            content_type=content_type,
        )
        raise
    finally:
        metrics_registry.observe(
            "generation_latency_seconds",
            time.perf_counter() - started,
            endpoint=endpoint,
            provider=_provider_label(provider),
            platform=platform,
            content_type=content_type,
        )


def _should_persist_finish_sentences(
    *,
    platform: str,
    content_type: str,
    finish_sentences: object,
) -> bool:
    """Persist finish maps whenever a description flow produced concrete finish content."""
    return _task_should_persist_finish_sentences(
        platform=platform,
        content_type=content_type,
        finish_sentences=finish_sentences,
    )
