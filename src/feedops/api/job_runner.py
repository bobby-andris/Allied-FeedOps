"""Unified background job processor for batch and hybrid generation jobs.

Replaces process_batch_job() and process_hybrid_batch_job() from main.py with a
single JobRunner class that dispatches on mode. Extracted as Plan 03-01 of the
Phase 3 (JobRunner and Route Extraction) decomposition.

JOBS-01: Unified class replacing both process_batch_job and process_hybrid_batch_job
JOBS-02: Single run() entry point with mode flag dispatch
JOBS-03: Shared retry logic, error handling, and status updates
JOBS-04: Variant adaptation only in hybrid mode
JOBS-05: Graceful cancellation via threading.Event checked at SKU boundary
JOBS-06: Identical persistence call sequence to old functions
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone

from feedops.api.generation_telemetry import (
    extract_scoped_telemetry as _extract_scoped_telemetry,
    provider_label as _provider_label,
)
from feedops.api.hybrid_generation import adapt_variant_content
from feedops.api.multi_sku_detection import extract_spec_difference
from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
from feedops.api.job_management import _resolve_execution_request_id
from feedops.api.persistence import (
    _persist_finish_prompt_lineage,
    _persist_generated_content_and_history,
    _upsert_batch_job_sku_status,
)
from feedops.api.prompt_loader import get_platform_system_prompt_hash
from feedops.api.runtime_controls import ensure_generation_enabled
from feedops.api.schemas import _content_field_key, _normalize_generation_options
from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.api.telemetry import (
    _emit_generation_summary,
    _should_persist_finish_sentences,
    _telemetry_scope_for_content,
)
from feedops.db.supabase_client import get_client
from feedops.generation.persistence import persist_finish_sentences
from feedops.pipeline.generator import generate_per_platform
from feedops.providers import get_provider
from feedops.providers.base import close_provider

logger = logging.getLogger(__name__)


# =============================================================================
# Cancellation registry (JOBS-05)
# =============================================================================

_active_runners: dict[str, "JobRunner"] = {}


def register_runner(job_id: str, runner: "JobRunner") -> None:
    """Register a runner for a job ID (enables per-job cancellation)."""
    _active_runners[job_id] = runner


def unregister_runner(job_id: str) -> None:
    """Unregister a runner after the job completes."""
    _active_runners.pop(job_id, None)


def cancel_runner(job_id: str) -> bool:
    """Cancel a registered runner by job ID. Returns True if found and cancelled."""
    runner = _active_runners.get(job_id)
    if runner:
        runner.cancel_event.set()
        return True
    return False


# =============================================================================
# JobRunner class
# =============================================================================


class JobRunner:
    """Unified background job processor for batch and hybrid generation jobs.

    Usage:
        runner = JobRunner(mode="batch")
        await runner.run(job_id=job_id, skus=skus, num_candidates=1, dry_run=False, options=options)

        runner = JobRunner(mode="hybrid")
        await runner.run(job_id=job_id, families=families, single_skus=single_skus, options=options)

    Cancellation:
        event = threading.Event()
        runner = JobRunner(mode="batch", cancel_event=event)
        # From another thread:
        event.set()  # Stops processing at next SKU boundary
    """

    def __init__(self, mode: str, cancel_event: threading.Event | None = None):
        """
        Args:
            mode: "batch" or "hybrid"
            cancel_event: Optional threading.Event for graceful cancellation.
                          Checked before each SKU. If set, job terminates cleanly.
        """
        assert mode in ("batch", "hybrid"), f"Unknown mode: {mode}"
        self.mode = mode
        self.cancel_event = cancel_event or threading.Event()

    async def run(self, *, job_id: str, **kwargs) -> None:
        """Entry point called by run_async_in_thread().

        Registers the runner for the job ID, dispatches to the appropriate
        mode handler, and unregisters on completion.
        """
        register_runner(job_id, self)
        try:
            if self.mode == "batch":
                await self._run_batch(job_id=job_id, **kwargs)
            else:
                await self._run_hybrid(job_id=job_id, **kwargs)
        finally:
            unregister_runner(job_id)

    def _is_cancelled(self) -> bool:
        """Return True if the cancel event has been set."""
        return self.cancel_event.is_set()

    # =========================================================================
    # Batch mode (JOBS-01, JOBS-02, JOBS-06 parity with process_batch_job)
    # =========================================================================

    async def _run_batch(
        self,
        *,
        job_id: str,
        skus: list[str],
        num_candidates: int,
        dry_run: bool,
        options: dict | None = None,
    ) -> None:
        """Batch mode: simple counter tracking, direct SKU list.

        Identical logic to old process_batch_job(). Only additions:
        - Cancellation check at top of SKU loop (JOBS-05)
        - Conversion from top-level function to instance method (self)
        """
        ensure_generation_enabled(operation="process_batch_job")
        supabase = get_client()

        # Update job status to processing
        supabase.table("batch_generation_jobs").update(
            {"status": "processing", "started_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", job_id).execute()

        completed = 0
        failed = 0
        normalized_options = _normalize_generation_options(options)
        platforms = normalized_options["platforms"]
        request_id = _resolve_execution_request_id()
        lineage_request_id = request_id
        content_types = []
        if normalized_options["titles"]:
            content_types.append("title")
        if normalized_options["descriptions"]:
            content_types.append("description")

        for sku in skus:
            # JOBS-05: Cancellation check at SKU boundary
            if self._is_cancelled():
                logger.info("Job %s: cancellation requested before %s, stopping.", job_id, sku)
                supabase.table("batch_generation_jobs").update({
                    "status": "failed",
                    "error_message": "Job cancelled",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", job_id).execute()
                return

            canonical_sku = sku
            try:
                canonical_sku = resolve_canonical_master_sku(supabase, sku)
                # Update SKU status
                _upsert_batch_job_sku_status(
                    supabase=supabase,
                    job_id=job_id,
                    master_sku=canonical_sku,
                    status="processing",
                    started_at=datetime.now(timezone.utc).isoformat(),
                )

                # Load and generate for this SKU
                parent_sku = load_parent_sku_from_supabase(canonical_sku)
                if not parent_sku:
                    raise ValueError(f"SKU not found: {canonical_sku}")

                provider = get_provider()
                try:
                    generated = await asyncio.wait_for(
                        generate_per_platform(
                            parent_sku=parent_sku,
                            provider=provider,
                            prompt_version="v2",
                            selected_platforms=tuple(
                                list(platforms)
                                + (
                                    ["finish"]
                                    if "description" in content_types
                                    and any(platform in {"google", "bing"} for platform in platforms)
                                    else []
                                )
                            ),
                            selected_content_types=tuple(content_types),
                            request_id=lineage_request_id,
                        ),
                        timeout=300.0,
                    )
                finally:
                    await close_provider(provider)
                prompt_hashes = generated.get("prompt_hashes", {})
                system_prompts = generated.get("system_prompts", {})
                user_prompts = generated.get("user_prompts", {})
                usage_by_platform = generated.get("usage_by_platform", {})
                latencies = generated.get("latency_by_platform", {})
                parse_by_platform = generated.get("parse_by_platform", {})
                retry_by_platform = generated.get("retry_by_platform", {})

                if not dry_run:
                    primary_content_type = content_types[0] if content_types else None
                    for platform in platforms:
                        for content_type in content_types:
                            platform_telemetry = _extract_scoped_telemetry(
                                platforms=_telemetry_scope_for_content(
                                    platform=platform,
                                    content_type=content_type,
                                    generated=generated,
                                ),
                                usage_by_platform=usage_by_platform,
                                latency_by_platform=latencies,
                                retry_by_platform=retry_by_platform,
                            )
                            field_key = _content_field_key(platform, content_type)
                            content = str(generated.get(field_key, "")).strip()
                            include_platform_telemetry = content_type == primary_content_type
                            _persist_generated_content_and_history(
                                supabase=supabase,
                                master_sku=canonical_sku,
                                platform=platform,
                                content_type=content_type,
                                content=content,
                                generation_model=_provider_label(provider),
                                prompt_hash=str(
                                    prompt_hashes.get(
                                        platform,
                                        get_platform_system_prompt_hash(platform),
                                    )
                                ),
                                system_prompt=str(system_prompts.get(platform, "")),
                                user_prompt=str(user_prompts.get(platform, "")),
                                mode="full_generation_v2",
                                tokens_used=platform_telemetry["tokens_used"]
                                if include_platform_telemetry
                                else 0,
                                cost_usd=platform_telemetry["cost_usd"]
                                if include_platform_telemetry
                                else 0.0,
                                latency_ms=platform_telemetry["latency_ms"]
                                if include_platform_telemetry
                                else 0,
                                provider_attempt_count=platform_telemetry["provider_attempt_count"]
                                if include_platform_telemetry
                                else 0,
                                parse_retry_count=platform_telemetry["parse_retry_count"]
                                if include_platform_telemetry
                                else 0,
                                generation_diagnostics={
                                    "selected_platforms": list(platforms),
                                    "usage_by_platform": usage_by_platform
                                    if isinstance(usage_by_platform, dict)
                                    else {},
                                    "latency_by_platform": latencies
                                    if isinstance(latencies, dict)
                                    else {},
                                    "parse_by_platform": parse_by_platform
                                    if isinstance(parse_by_platform, dict)
                                    else {},
                                    "retry_by_platform": retry_by_platform
                                    if isinstance(retry_by_platform, dict)
                                    else {},
                                    **_extract_query_intent_generation_diagnostics(generated),
                                },
                                request_id=lineage_request_id,
                            )
                            _emit_generation_summary(
                                endpoint="process_batch_job",
                                request_id=request_id,
                                job_id=job_id,
                                master_sku=canonical_sku,
                                platform=platform,
                                content_type=content_type,
                                mode="full_generation_v2",
                                result_state="completed",
                                tokens_used=platform_telemetry["tokens_used"]
                                if include_platform_telemetry
                                else 0,
                                cost_usd=platform_telemetry["cost_usd"]
                                if include_platform_telemetry
                                else 0.0,
                                latency_ms=platform_telemetry["latency_ms"]
                                if include_platform_telemetry
                                else 0,
                                provider_attempt_count=platform_telemetry["provider_attempt_count"]
                                if include_platform_telemetry
                                else 0,
                                parse_retry_count=platform_telemetry["parse_retry_count"]
                                if include_platform_telemetry
                                else 0,
                            )

                    _persist_finish_prompt_lineage(
                        supabase=supabase,
                        master_sku=canonical_sku,
                        generated=generated,
                        mode="full_generation_v2",
                        generation_model=_provider_label(provider),
                        generation_diagnostics={
                            "selected_platforms": list(platforms),
                            "usage_by_platform": usage_by_platform
                            if isinstance(usage_by_platform, dict)
                            else {},
                            "latency_by_platform": latencies
                            if isinstance(latencies, dict)
                            else {},
                            "parse_by_platform": parse_by_platform
                            if isinstance(parse_by_platform, dict)
                            else {},
                            "retry_by_platform": retry_by_platform
                            if isinstance(retry_by_platform, dict)
                            else {},
                        },
                        request_id=lineage_request_id,
                    )

                    finish_sentences = generated.get("finish_sentences", {})
                    if "description" in content_types:
                        for platform in ("google", "bing"):
                            if platform in platforms and _should_persist_finish_sentences(
                                platform=platform,
                                content_type="description",
                                finish_sentences=finish_sentences,
                            ):
                                persist_finish_sentences(
                                    supabase=supabase,
                                    master_sku=canonical_sku,
                                    platform=platform,
                                    finish_sentences=finish_sentences,
                                )

                completed += 1

                # Update SKU as completed
                _upsert_batch_job_sku_status(
                    supabase=supabase,
                    job_id=job_id,
                    master_sku=canonical_sku,
                    status="completed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                )

            except Exception as e:
                failed += 1
                logger.error(f"Batch SKU {sku} failed: {e}")

                # Update SKU as failed
                _upsert_batch_job_sku_status(
                    supabase=supabase,
                    job_id=job_id,
                    master_sku=canonical_sku,
                    status="failed",
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    error_message=str(e),
                )
                _emit_generation_summary(
                    endpoint="process_batch_job",
                    request_id=request_id,
                    job_id=job_id,
                    master_sku=canonical_sku,
                    platform=None,
                    content_type=None,
                    mode="full_generation_v2",
                    result_state="failed",
                )

            # Update job progress
            supabase.table("batch_generation_jobs").update(
                {"completed_skus": completed, "failed_skus": failed}
            ).eq("id", job_id).execute()

        # Mark job complete (batch_generation_jobs only supports queued/processing/completed/failed)
        final_status = "completed" if failed == 0 else "failed"
        final_payload = {
            "status": final_status,
            "completed_skus": completed,
            "failed_skus": failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        if failed > 0 and completed > 0:
            final_payload["error_message"] = (
                f"Completed {completed} of {len(skus)} SKUs; {failed} failed"
            )
        supabase.table("batch_generation_jobs").update(final_payload).eq("id", job_id).execute()

        logger.info(f"Batch job {job_id} finished: {completed} completed, {failed} failed")
        _emit_generation_summary(
            endpoint="process_batch_job",
            request_id=request_id,
            job_id=job_id,
            master_sku="*batch*",
            platform=None,
            content_type=None,
            mode="full_generation_v2",
            result_state=final_status,
        )

    # =========================================================================
    # Hybrid mode (JOBS-01, JOBS-02, JOBS-04, JOBS-06 parity with process_hybrid_batch_job)
    # =========================================================================

    async def _run_hybrid(
        self,
        *,
        job_id: str,
        families: list,
        single_skus: list[str],
        options: dict,
        requested_skus: list[str] | None = None,
    ) -> None:
        """Hybrid mode: requested/expanded scope tracking, variant adaptation after base.

        Identical logic to old process_hybrid_batch_job(). Only additions:
        - Cancellation check at top of each SKU loop (JOBS-05)
        - Conversion from top-level function to instance method (self)
        - generate_full_content_v2 inner closure extracted to _generate_full_sku() method
        """
        ensure_generation_enabled(operation="process_hybrid_batch_job")
        supabase = get_client()

        # Update job status to processing
        supabase.table("batch_generation_jobs").update(
            {"status": "processing", "started_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", job_id).execute()

        requested_scope = set(requested_skus or [])
        if not requested_scope:
            requested_scope.update(single_skus)
            for family in families:
                requested_scope.update(family.master_skus)

        processing_scope = set(single_skus)
        for family in families:
            processing_scope.add(family.base_sku)
            processing_scope.update(family.variant_skus)

        requested_total = len(requested_scope)
        expanded_total = len(processing_scope - requested_scope)

        requested_completed = 0
        requested_failed = 0
        expanded_completed = 0
        expanded_failed = 0

        platforms = options.get("platforms", ["google", "bing", "shopify"])
        request_id = _resolve_execution_request_id()
        lineage_request_id = request_id
        content_types = []
        if options.get("titles"):
            content_types.append("title")
        if options.get("descriptions"):
            content_types.append("description")

        provider = get_provider()

        def _build_job_options() -> dict:
            return {
                "titles": options.get("titles", True),
                "descriptions": options.get("descriptions", True),
                "platforms": platforms,
                "hybrid": True,
                "idempotency_key": options.get("idempotency_key"),
                "expanded_total_skus": expanded_total,
                "expanded_completed_skus": expanded_completed,
                "expanded_failed_skus": expanded_failed,
                "multi_sku_families": len(families),
                "single_skus": len(single_skus),
                "base_skus": len(families) + len(single_skus),
                "variant_skus": sum(len(f.variant_skus) for f in families),
            }

        def _update_job_progress(
            *,
            status: str | None = None,
            completed_at: str | None = None,
            error_message: str | None = None,
            enforce_invariant: bool = True,
        ) -> None:
            processed_requested = requested_completed + requested_failed
            if enforce_invariant and processed_requested > requested_total:
                overflow_message = (
                    f"Hybrid progress overflow: requested {processed_requested} exceeds total {requested_total}"
                )
                supabase.table("batch_generation_jobs").update(
                    {
                        "status": "failed",
                        "completed_skus": requested_completed,
                        "failed_skus": requested_failed,
                        "options": _build_job_options(),
                        "error_message": overflow_message[:500],
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).eq("id", job_id).execute()
                raise ValueError(overflow_message)

            payload: dict[str, object] = {
                "completed_skus": requested_completed,
                "failed_skus": requested_failed,
                "options": _build_job_options(),
            }
            if status:
                payload["status"] = status
            if completed_at:
                payload["completed_at"] = completed_at
            if error_message:
                payload["error_message"] = error_message[:500]

            supabase.table("batch_generation_jobs").update(payload).eq("id", job_id).execute()

        def _record_sku_result(sku: str, *, success: bool) -> None:
            nonlocal requested_completed, requested_failed, expanded_completed, expanded_failed
            if sku in requested_scope:
                if success:
                    requested_completed += 1
                else:
                    requested_failed += 1
            else:
                if success:
                    expanded_completed += 1
                else:
                    expanded_failed += 1

        try:
            # Process single SKUs (full generation)
            logger.info(f"Processing {len(single_skus)} single SKUs")
            for sku in single_skus:
                # JOBS-05: Cancellation check at SKU boundary
                if self._is_cancelled():
                    logger.info("Job %s: cancellation requested before %s, stopping.", job_id, sku)
                    supabase.table("batch_generation_jobs").update({
                        "status": "failed",
                        "error_message": "Job cancelled",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", job_id).execute()
                    return

                sku_failed = False
                sku_error: str | None = None
                _upsert_batch_job_sku_status(
                    supabase=supabase,
                    job_id=job_id,
                    master_sku=sku,
                    status="processing",
                    started_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    await asyncio.wait_for(
                        self._generate_full_sku(
                            supabase=supabase,
                            provider=provider,
                            sku=sku,
                            platforms=platforms,
                            content_types=content_types,
                            lineage_request_id=lineage_request_id,
                            job_id=job_id,
                            request_id=request_id,
                            options=options,
                        ),
                        timeout=300.0,
                    )
                    logger.info("✓ Generated %s via per-platform v2 package", sku)
                except asyncio.TimeoutError:
                    sku_failed = True
                    sku_error = "SKU generation timed out after 300s"
                    logger.error("✗ Timed out %s after 300s", sku)
                except Exception as e:
                    sku_failed = True
                    sku_error = str(e)
                    logger.error("✗ Failed %s via per-platform v2 package: %s", sku, e)
                    _emit_generation_summary(
                        endpoint="process_hybrid_batch_job",
                        request_id=request_id,
                        job_id=job_id,
                        master_sku=sku,
                        platform=None,
                        content_type=None,
                        mode="full_generation_v2",
                        result_state="failed",
                    )

                try:
                    _record_sku_result(sku, success=not sku_failed)
                    _upsert_batch_job_sku_status(
                        supabase=supabase,
                        job_id=job_id,
                        master_sku=sku,
                        status="failed" if sku_failed else "completed",
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        error_message=sku_error if sku_failed else None,
                    )
                    _update_job_progress()
                except Exception as progress_err:
                    logger.error("Progress update failed for %s: %s", sku, progress_err)

            # Process multi-SKU families (hybrid approach)
            logger.info(f"Processing {len(families)} multi-SKU families")
            for family in families:
                # JOBS-05: Cancellation check at family/base_sku boundary
                if self._is_cancelled():
                    logger.info("Job %s: cancellation requested before family %s, stopping.", job_id, family.master_skus)
                    supabase.table("batch_generation_jobs").update({
                        "status": "failed",
                        "error_message": "Job cancelled",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("id", job_id).execute()
                    return

                logger.info(f"Processing family: {family.master_skus}")

                # Step 1: Generate base SKU (full generation)
                base_sku = family.base_sku
                base_generated: dict[str, object] | None = None

                base_sku_failed = False
                base_sku_error: str | None = None
                _upsert_batch_job_sku_status(
                    supabase=supabase,
                    job_id=job_id,
                    master_sku=base_sku,
                    status="processing",
                    started_at=datetime.now(timezone.utc).isoformat(),
                )
                try:
                    base_generated = await asyncio.wait_for(
                        self._generate_full_sku(
                            supabase=supabase,
                            provider=provider,
                            sku=base_sku,
                            platforms=platforms,
                            content_types=content_types,
                            lineage_request_id=lineage_request_id,
                            job_id=job_id,
                            request_id=request_id,
                            options=options,
                        ),
                        timeout=300.0,
                    )
                    logger.info("✓ Generated BASE %s via per-platform v2 package", base_sku)
                except asyncio.TimeoutError:
                    base_sku_failed = True
                    base_sku_error = "Base SKU generation timed out after 300s"
                    logger.error("✗ Timed out BASE %s after 300s", base_sku)
                except Exception as e:
                    base_sku_failed = True
                    base_sku_error = str(e)
                    logger.error(
                        "✗ Failed BASE %s via per-platform v2 package: %s",
                        base_sku,
                        e,
                    )
                    _emit_generation_summary(
                        endpoint="process_hybrid_batch_job",
                        request_id=request_id,
                        job_id=job_id,
                        master_sku=base_sku,
                        platform=None,
                        content_type=None,
                        mode="full_generation_v2",
                        result_state="failed",
                    )

                try:
                    _record_sku_result(base_sku, success=not base_sku_failed)
                    _upsert_batch_job_sku_status(
                        supabase=supabase,
                        job_id=job_id,
                        master_sku=base_sku,
                        status="failed" if base_sku_failed else "completed",
                        completed_at=datetime.now(timezone.utc).isoformat(),
                        error_message=base_sku_error if base_sku_failed else None,
                    )
                    _update_job_progress()
                except Exception as progress_err:
                    logger.error("Progress update failed for %s: %s", base_sku, progress_err)

                if base_sku_failed or base_generated is None:
                    for variant_sku in family.variant_skus:
                        variant_error = (
                            f"Skipped variant adaptation because base SKU {base_sku} failed: "
                            f"{base_sku_error or 'unknown base generation error'}"
                        )
                        _record_sku_result(variant_sku, success=False)
                        _upsert_batch_job_sku_status(
                            supabase=supabase,
                            job_id=job_id,
                            master_sku=variant_sku,
                            status="failed",
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            error_message=variant_error,
                        )
                        _emit_generation_summary(
                            endpoint="process_hybrid_batch_job",
                            request_id=request_id,
                            job_id=job_id,
                            master_sku=variant_sku,
                            platform=None,
                            content_type=None,
                            mode="variant_adaptation_v2",
                            result_state="failed",
                        )
                        _update_job_progress()
                    continue

                # Step 2: Variant SKUs (JOBS-04: adapt_variant_content only in hybrid mode)
                for variant_sku in family.variant_skus:
                    # JOBS-05: Cancellation check at variant boundary
                    if self._is_cancelled():
                        logger.info("Job %s: cancellation requested before variant %s, stopping.", job_id, variant_sku)
                        supabase.table("batch_generation_jobs").update({
                            "status": "failed",
                            "error_message": "Job cancelled",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", job_id).execute()
                        return

                    variant_sku_failed = False
                    variant_sku_error: str | None = None
                    _upsert_batch_job_sku_status(
                        supabase=supabase,
                        job_id=job_id,
                        master_sku=variant_sku,
                        status="processing",
                        started_at=datetime.now(timezone.utc).isoformat(),
                    )
                    try:
                        for platform in platforms:
                            for content_type in content_types:
                                base_spec, variant_spec = extract_spec_difference(
                                    base_sku, variant_sku
                                )
                                base_field_key = _content_field_key(platform, content_type)
                                base_content = str(base_generated.get(base_field_key, "")).strip()
                                adaptation_result = await asyncio.wait_for(
                                    adapt_variant_content(
                                        supabase=supabase,
                                        base_sku=base_sku,
                                        variant_sku=variant_sku,
                                        platform=platform,
                                        content_type=content_type,
                                        base_spec=base_spec,
                                        variant_spec=variant_spec,
                                        base_content=base_content,
                                        base_finish_sentences=base_generated.get("finish_sentences"),
                                        request_id=lineage_request_id,
                                        provider=provider,
                                    ),
                                    timeout=120.0,
                                )
                                if not adaptation_result.get("success"):
                                    raise ValueError(
                                        adaptation_result.get(
                                            "error",
                                            f"Variant adaptation failed for {variant_sku}",
                                        )
                                    )
                        logger.info("✓ Adapted VARIANT %s from BASE %s", variant_sku, base_sku)
                    except Exception as e:
                        variant_sku_failed = True
                        variant_sku_error = str(e)
                        logger.error(
                            "✗ Failed VARIANT %s via adaptation from BASE %s: %s",
                            variant_sku,
                            base_sku,
                            e,
                        )
                        _emit_generation_summary(
                            endpoint="process_hybrid_batch_job",
                            request_id=request_id,
                            job_id=job_id,
                            master_sku=variant_sku,
                            platform=None,
                            content_type=None,
                            mode="variant_adaptation_v2",
                            result_state="failed",
                        )

                    try:
                        _record_sku_result(variant_sku, success=not variant_sku_failed)
                        _upsert_batch_job_sku_status(
                            supabase=supabase,
                            job_id=job_id,
                            master_sku=variant_sku,
                            status="failed" if variant_sku_failed else "completed",
                            completed_at=datetime.now(timezone.utc).isoformat(),
                            error_message=variant_sku_error if variant_sku_failed else None,
                        )
                        _update_job_progress()
                    except Exception as progress_err:
                        logger.error("Progress update failed for %s: %s", variant_sku, progress_err)

            # Mark job complete (batch_generation_jobs only supports queued/processing/completed/failed)
            total_failures = requested_failed + expanded_failed
            final_status = "completed" if total_failures == 0 else "failed"
            final_error: str | None = None
            if total_failures > 0:
                final_error = (
                    f"Requested: {requested_completed}/{requested_total} completed, "
                    f"{requested_failed} failed; Expanded: {expanded_completed}/{expanded_total} completed, "
                    f"{expanded_failed} failed"
                )
            _update_job_progress(
                status=final_status,
                completed_at=datetime.now(timezone.utc).isoformat(),
                error_message=final_error,
            )

            logger.info(
                "✓ Hybrid generation job %s finished: requested %s/%s completed (%s failed), "
                "expanded %s/%s completed (%s failed)",
                job_id,
                requested_completed,
                requested_total,
                requested_failed,
                expanded_completed,
                expanded_total,
                expanded_failed,
            )
            _emit_generation_summary(
                endpoint="process_hybrid_batch_job",
                request_id=request_id,
                job_id=job_id,
                master_sku="*batch*",
                platform=None,
                content_type=None,
                mode="full_generation_v2",
                result_state=final_status,
            )

        except Exception as e:
            logger.error(f"Hybrid generation processing error: {e}")
            _update_job_progress(
                status="failed",
                completed_at=datetime.now(timezone.utc).isoformat(),
                error_message=str(e),
                enforce_invariant=False,
            )
            _emit_generation_summary(
                endpoint="process_hybrid_batch_job",
                request_id=request_id,
                job_id=job_id,
                master_sku="*batch*",
                platform=None,
                content_type=None,
                mode="full_generation_v2",
                result_state="failed",
            )
        finally:
            await close_provider(provider)

    # =========================================================================
    # Shared full generation (extracted from generate_full_content_v2 closure)
    # =========================================================================

    async def _generate_full_sku(
        self,
        *,
        supabase,
        provider,
        sku: str,
        platforms: list[str],
        content_types: list[str],
        lineage_request_id: str,
        job_id: str,
        request_id: str,
        options: dict | None = None,
    ) -> dict[str, object]:
        """Generate and persist per-platform content package for one SKU.

        Extracted from the generate_full_content_v2 inner closure in
        process_hybrid_batch_job. Used by _run_hybrid for both single SKUs
        and family base SKUs.

        All formerly-captured closure variables are passed as explicit parameters
        (Pitfall 2 from research: inner closure vars must become explicit params).
        """
        canonical_sku = resolve_canonical_master_sku(supabase, sku)
        parent_sku = load_parent_sku_from_supabase(canonical_sku)
        if not parent_sku:
            raise ValueError(f"SKU not found: {canonical_sku}")

        selected_platforms = tuple(
            list(platforms)
            + (
                ["finish"]
                if "description" in content_types
                and any(platform in {"google", "bing"} for platform in platforms)
                else []
            )
        )
        generated = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
            selected_platforms=selected_platforms,
            selected_content_types=tuple(content_types),
            request_id=lineage_request_id,
        )
        prompt_hashes = generated.get("prompt_hashes", {})
        system_prompts = generated.get("system_prompts", {})
        user_prompts = generated.get("user_prompts", {})
        usage_by_platform = generated.get("usage_by_platform", {})
        latencies = generated.get("latency_by_platform", {})
        parse_by_platform = generated.get("parse_by_platform", {})
        retry_by_platform = generated.get("retry_by_platform", {})

        for platform in platforms:
            for content_type in content_types:
                field_key = _content_field_key(platform, content_type)
                content = str(generated.get(field_key, "")).strip()
                telemetry = _extract_scoped_telemetry(
                    platforms=_telemetry_scope_for_content(
                        platform=platform,
                        content_type=content_type,
                        generated=generated,
                    ),
                    usage_by_platform=usage_by_platform,
                    latency_by_platform=latencies,
                    retry_by_platform=retry_by_platform,
                )
                _persist_generated_content_and_history(
                    supabase=supabase,
                    master_sku=canonical_sku,
                    platform=platform,
                    content_type=content_type,
                    content=content,
                    generation_model=_provider_label(provider),
                    prompt_hash=str(
                        prompt_hashes.get(
                            platform,
                            get_platform_system_prompt_hash(platform),
                        )
                    ),
                    system_prompt=str(system_prompts.get(platform, "")),
                    user_prompt=str(user_prompts.get(platform, "")),
                    mode="full_generation_v2",
                    tokens_used=telemetry["tokens_used"],
                    cost_usd=telemetry["cost_usd"],
                    latency_ms=telemetry["latency_ms"],
                    provider_attempt_count=telemetry["provider_attempt_count"],
                    parse_retry_count=telemetry["parse_retry_count"],
                    generation_diagnostics={
                        "selected_platforms": list(selected_platforms),
                        "usage_by_platform": usage_by_platform
                        if isinstance(usage_by_platform, dict)
                        else {},
                        "latency_by_platform": latencies
                        if isinstance(latencies, dict)
                        else {},
                        "parse_by_platform": parse_by_platform
                        if isinstance(parse_by_platform, dict)
                        else {},
                        "retry_by_platform": retry_by_platform
                        if isinstance(retry_by_platform, dict)
                        else {},
                        **_extract_query_intent_generation_diagnostics(generated),
                    },
                    request_id=lineage_request_id,
                    idempotency_key=options.get("idempotency_key") if options else None,
                )
                _emit_generation_summary(
                    endpoint="process_hybrid_batch_job",
                    request_id=request_id,
                    job_id=job_id,
                    master_sku=canonical_sku,
                    platform=platform,
                    content_type=content_type,
                    mode="full_generation_v2",
                    result_state="completed",
                    tokens_used=telemetry["tokens_used"],
                    cost_usd=telemetry["cost_usd"],
                    latency_ms=telemetry["latency_ms"],
                    provider_attempt_count=telemetry["provider_attempt_count"],
                    parse_retry_count=telemetry["parse_retry_count"],
                )
        _persist_finish_prompt_lineage(
            supabase=supabase,
            master_sku=canonical_sku,
            generated=generated,
            mode="full_generation_v2",
            generation_model=_provider_label(provider),
            generation_diagnostics={
                "selected_platforms": list(selected_platforms),
                "usage_by_platform": usage_by_platform
                if isinstance(usage_by_platform, dict)
                else {},
                "latency_by_platform": latencies
                if isinstance(latencies, dict)
                else {},
                "parse_by_platform": parse_by_platform
                if isinstance(parse_by_platform, dict)
                else {},
                "retry_by_platform": retry_by_platform
                if isinstance(retry_by_platform, dict)
                else {},
            },
            request_id=lineage_request_id,
            idempotency_key=options.get("idempotency_key") if options else None,
        )
        finish_sentences = generated.get("finish_sentences", {})
        if "description" in content_types:
            for platform in ("google", "bing"):
                if platform in platforms and _should_persist_finish_sentences(
                    platform=platform,
                    content_type="description",
                    finish_sentences=finish_sentences,
                ):
                    persist_finish_sentences(
                        supabase=supabase,
                        master_sku=canonical_sku,
                        platform=platform,
                        finish_sentences=finish_sentences,
                    )
        return generated
