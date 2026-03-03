"""FastAPI entry point for Cloud Run deployment.

This module exposes the FeedOps Python pipeline as HTTP endpoints,
enabling the Next.js dashboard to call Python-based content generation.

Endpoints:
- GET / - API info
- GET /health - Health check with Supabase status
- POST /optimize-sku - Single SKU optimization
- POST /regenerate - Content regeneration with feedback
- POST /batch-optimize - Batch job creation
- GET /batch-status/{job_id} - Batch job progress
- POST /hybrid-generate - Hybrid multi-SKU batch generation
- POST /performance/capture-baseline - Capture performance baselines for SKUs
- GET /performance/baseline/{master_sku} - Get baseline status for SKU
- POST /performance/collect-daily - Collect durable daily performance snapshots
- POST /performance/compute-impact - Compute persisted diff-in-diff impact scores
- GET /performance/impact-scores - Read persisted impact scorecards
- POST /performance/capture-snapshot - Backward-compatible collector alias
- POST /search-insights/sync - Sync search terms from Google Ads
- GET /search-insights/sync/{job_id} - Get search term sync status
- POST /backfill/start - Create and start a backfill job
- GET /backfill/status/{job_id} - Get backfill job progress
- POST /backfill/resume/{job_id} - Resume failed/partial job
- GET /backfill/jobs - List backfill jobs
- POST /score-intent - Score search queries for feed alignment
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import logging
import threading
import time
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from feedops.api.schemas import (
    OptimizeRequest, RegenerateRequest, BatchOptimizeRequest,
    HealthResponse, OptimizeResponse, RegenerateResponse,
    RegenerateJobResponse, RegenerateJobStatusResponse,
    BatchJobResponse, BatchStatusResponse,
    GenerateImagesRequest, GenerateImagesResponse,
    HybridGenerateRequest, HybridJobResponse,
    ScoreIntentRequest, ScoreIntentItem, ScoreIntentResponse,
    _normalize_regeneration_job_status,
    _normalize_generation_options,
    _content_field_key,
    _extract_content_from_schema_response,
)

from feedops.api.supabase_loader import (
    get_product_catalog_count,
    load_parent_sku_from_supabase,
)
from feedops.api.prompt_loader import (
    get_system_prompt,
    get_system_prompt_hash,
    get_platform_system_prompt,
    get_category_guidance,
    format_gold_standard_examples,
    get_finish_list,
    get_platform_system_prompt_hash,
)
from feedops.api.generation_telemetry import (
    estimate_openai_cost_usd_from_usage as _estimate_openai_cost_usd_from_usage,
    extract_platform_telemetry as _extract_platform_telemetry,
    extract_scoped_telemetry as _extract_scoped_telemetry,
    provider_label as _provider_label,
    safe_int as _safe_int,
)
from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.api.prompt_builder import build_core_prompt, apply_feedback_layer
from feedops.pipeline.finish_sentence_validation import (
    normalize_and_validate_finish_sentences,
)
from feedops.pipeline.finish_sentence_placeholder import (
    build_fallback_finish_sentences,
    count_finish_sentence_placeholders,
    normalize_base_description_with_finish_placeholder,
    strip_hardcoded_finish_names,
    strip_generic_finish_count_claims,
)
from feedops.providers import get_provider
from feedops.providers.base import close_provider
from feedops.api.multi_sku_detection import detect_multi_sku_families
from feedops.generation.persistence import (
    get_finish_task_result,
    persist_finish_sentences,
)
from feedops.api.telemetry import (
    run_async_in_thread,
    _emit_generation_summary,
    _telemetry_scope_for_content,
    _generate_with_metrics,
    _should_persist_finish_sentences,
)
from feedops.api.persistence import (
    _lookup_generated_content_id,
    _load_generated_content_row,
    _assembled_prompt_hash,
    _enforce_write_time_finish_placeholder_contract,
    _persist_regeneration_result,
    _persist_generated_content_and_history,
    _persist_finish_prompt_lineage,
    _upsert_batch_job_sku_status,
)
from feedops.api.job_management import (
    _create_regeneration_job,
    _format_job_error,
    _require_request_id,
    _resolve_execution_request_id,
    _regeneration_idempotency_key,
    _hybrid_generation_idempotency_key,
    _find_active_regeneration_job,
    _find_active_hybrid_job,
    _normalize_regeneration_job_row,
)
from feedops.api.hybrid_generation import adapt_variant_content  # noqa: F401 - re-exported for test patching compatibility
from feedops.api.job_runner import JobRunner
from feedops.api.sku_alias import (
    resolve_canonical_master_sku,
    resolve_canonical_master_skus,
)
from feedops.api.runtime_controls import (
    diagnostic_mode_enabled,
    ensure_generation_enabled,
    finish_sentence_regeneration_enabled,
)
from feedops.api.env_contract import (
    RuntimeEnvContractError,
    validate_runtime_env_contract,
)
from feedops.pipeline.feature_flags import capture_flag_snapshot
from feedops.pipeline.generator import GenerationBudgetExceededError, generate_per_platform
from feedops.observability import get_request_id, log_event, request_context
from feedops.observability.metrics import metrics_registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# API version
API_VERSION = "1.0.0"

@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    """Fail fast on missing runtime env contract requirements."""
    try:
        validate_runtime_env_contract()
    except RuntimeEnvContractError as exc:
        logger.error(str(exc))
        raise RuntimeError(str(exc)) from exc

    # Recover stale jobs left behind by container restarts
    try:
        from feedops.db.supabase_client import get_client
        from datetime import datetime, timezone, timedelta
        sb = get_client()
        stale_cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        stale = sb.table("batch_generation_jobs") \
            .select("id") \
            .eq("status", "processing") \
            .lt("created_at", stale_cutoff) \
            .execute()
        for row in (stale.data or []):
            sb.table("batch_generation_jobs").update({
                "status": "failed",
                "error_message": "Recovered: container restart during processing",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", row["id"]).execute()
            logger.warning("Recovered stale job %s", row["id"])
    except Exception as recovery_err:
        logger.error("Startup recovery sweep failed: %s", recovery_err)

    yield


app = FastAPI(
    title="FeedOps Pipeline API",
    description="Content generation pipeline for Allied Brass products",
    version=API_VERSION,
    lifespan=_app_lifespan,
)

# CORS middleware — allow dashboard to call Cloud Run endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://allied-feed-ops.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Prometheus /metrics endpoint (MON-10)
from prometheus_client import make_asgi_app, REGISTRY
metrics_app = make_asgi_app(registry=REGISTRY)
app.mount("/metrics", metrics_app)

# Include search insights router
from feedops.api.search_insights import router as search_insights_router
app.include_router(search_insights_router)

# Include monitoring router
from feedops.api.monitoring import router as monitoring_router
app.include_router(monitoring_router)

# Include GMC sync router
from feedops.api.gmc_sync import router as gmc_sync_router
app.include_router(gmc_sync_router)

# Include performance baseline router
from feedops.api.performance_baseline import router as performance_baseline_router
app.include_router(performance_baseline_router)

# Include intent scoring router
from feedops.api.intent_scoring import router as intent_scoring_router
app.include_router(intent_scoring_router)

# Import backfill endpoints
from feedops.api.backfill import (
    StartBackfillRequest,
    BackfillJobResponse,
    BackfillJobListResponse,
    ValidationReportResponse,
    start_backfill,
    get_backfill_status,
    resume_backfill,
    list_backfill_jobs,
    get_validation_report,
)


@app.middleware("http")
async def attach_request_context(request: Request, call_next):
    """Attach request ID context for structured logs/metrics."""
    request_id = (
        request.headers.get("x-request-id")
        or request.headers.get("x-correlation-id")
        or uuid.uuid4().hex
    )

    with request_context(request_id):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics_registry.increment(
                "http_request_error_total",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            metrics_registry.observe(
                "http_request_latency_seconds",
                time.perf_counter() - started,
                method=request.method,
                path=request.url.path,
            )

    response.headers["X-Request-ID"] = request_id
    return response


# =============================================================================
# Background Job Helper — imported from telemetry.py
# =============================================================================
# run_async_in_thread imported at top of file via:
#   from feedops.api.telemetry import run_async_in_thread, ...

# =============================================================================
# Request/Response Models — imported from schemas.py
# =============================================================================
# All 17 Pydantic models and 4 helper functions live in feedops.api.schemas.
# They are imported at the top of this file via:
#   from feedops.api.schemas import ...


# _generate_with_metrics imported from feedops.api.telemetry


from feedops.api.generation import (
    _build_generation_user_prompt,
    _execute_regeneration_request,
)

from feedops.api.finish_processing import (
    _build_finish_sentences_user_prompt,
    _validate_finish_sentences_payload,
    _enforce_finish_sentence_parity,
)

# =============================================================================
# Persistence helpers — imported from feedops.api.persistence (Plan 01-02)
# =============================================================================
# _lookup_generated_content_id, _load_generated_content_row,
# _assembled_prompt_hash, _enforce_write_time_finish_placeholder_contract,
# _persist_regeneration_result, _persist_generated_content_and_history,
# _persist_finish_prompt_lineage, _upsert_batch_job_sku_status
# are all imported at the top of this file via:
#   from feedops.api.persistence import ...


from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics

# =============================================================================
# Job management helpers — imported from feedops.api.job_management (Plan 01-02)
# =============================================================================
# _create_regeneration_job, _format_job_error, _require_request_id,
# _resolve_execution_request_id, _regeneration_idempotency_key,
# _hybrid_generation_idempotency_key, _find_active_regeneration_job,
# _find_active_hybrid_job, _normalize_regeneration_job_row
# are all imported at the top of this file via:
#   from feedops.api.job_management import ...

# _emit_generation_summary, _telemetry_scope_for_content,
# _generate_with_metrics, _should_persist_finish_sentences
# are all imported from feedops.api.telemetry


# =============================================================================
# Finish processing helpers — imported from feedops.api.finish_processing (Plan 02-01)
# =============================================================================
# _build_finish_sentences_user_prompt, _validate_finish_sentences_payload,
# _enforce_finish_sentence_parity
# are all imported above via:
#   from feedops.api.finish_processing import ...

# =============================================================================
# Health & Status Endpoints
# =============================================================================


@app.get("/", tags=["Status"])
async def root():
    """Root endpoint with API info."""
    return {
        "service": "FeedOps Pipeline API",
        "version": API_VERSION,
        "documentation": "/docs",
        "endpoints": {
            "health": "GET /health",
            "optimize": "POST /optimize-sku",
            "regenerate": "POST /regenerate",
            "regenerate_status": "GET /regenerate/status/{job_id}",
            "batch_optimize": "POST /batch-optimize",
            "batch_status": "GET /batch-status/{job_id}",
            "generate_images": "POST /generate-images",
            "hybrid_generate": "POST /hybrid-generate",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["Status"])
async def health_check():
    """Health check endpoint for Cloud Run.

    Returns service status, Supabase connectivity, and product catalog count.
    """
    supabase_ok = False
    catalog_count = 0

    if is_supabase_available():
        try:
            catalog_count = get_product_catalog_count()
            supabase_ok = True
        except Exception as e:
            logger.warning(f"Supabase health check failed: {e}")

    status = "healthy" if supabase_ok else "degraded"

    return HealthResponse(
        status=status,
        service="feedops-pipeline",
        version=API_VERSION,
        product_catalog_count=catalog_count,
        supabase_connected=supabase_ok,
    )


# =============================================================================
# Single SKU Optimization
# =============================================================================


@app.post("/optimize-sku", response_model=OptimizeResponse, tags=["Generation"])
async def optimize_single_sku(request: OptimizeRequest):
    """Optimize a single SKU - generates titles, descriptions for all platforms.

    This endpoint:
    1. Load product data from Supabase
    2. Build evidence table
    3. Generate content via LLM for each platform
    4. Save results to generated_content table (if not dry_run)
    """
    try:
        ensure_generation_enabled(operation="optimize_single_sku")
        supabase = get_client()
        canonical_master_sku = resolve_canonical_master_sku(
            supabase, request.master_sku
        )
        logger.info(
            "Optimizing SKU: requested=%s canonical=%s",
            request.master_sku,
            canonical_master_sku,
        )
        log_event(
            logger,
            logging.INFO,
            "generation.optimize.start",
            endpoint="optimize_single_sku",
            master_sku=canonical_master_sku,
            requested_master_sku=request.master_sku,
            request_id=get_request_id(),
        )

        # Load from Supabase
        parent_sku = load_parent_sku_from_supabase(canonical_master_sku)
        if not parent_sku:
            raise HTTPException(
                status_code=404, detail=f"SKU not found: {request.master_sku}"
            )

        # Build evidence table
        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        # Get LLM provider
        provider = get_provider()

        results = []
        platforms = ["google", "bing", "shopify"]
        content_types = ["title", "description"]

        try:
            generated = await generate_per_platform(
                parent_sku=parent_sku,
                provider=provider,
                prompt_version="v2",
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
        request_id = _resolve_execution_request_id()

        for platform in platforms:
            for content_type in content_types:
                field_key = _content_field_key(platform, content_type)
                content = str(generated.get(field_key, "")).strip()
                results.append(f"{platform}/{content_type}: {content[:100]}...")
                if request.dry_run:
                    continue
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
                    master_sku=canonical_master_sku,
                    platform=platform,
                    content_type=content_type,
                    content=content,
                    generation_model=_provider_label(provider),
                    prompt_hash=str(
                        prompt_hashes.get(
                            platform, get_platform_system_prompt_hash(platform)
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
                    request_id=request_id,
                )
                _emit_generation_summary(
                    endpoint="optimize_single_sku",
                    request_id=request_id,
                    master_sku=canonical_master_sku,
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

        if not request.dry_run:
            _persist_finish_prompt_lineage(
                supabase=supabase,
                master_sku=canonical_master_sku,
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
                request_id=request_id,
            )

        finish_sentences = generated.get("finish_sentences", {})
        if not request.dry_run:
            for platform in ("google", "bing"):
                if platform in platforms and _should_persist_finish_sentences(
                    platform=platform,
                    content_type="description",
                    finish_sentences=finish_sentences,
                ):
                    persist_finish_sentences(
                        supabase=supabase,
                        master_sku=canonical_master_sku,
                        platform=platform,
                        finish_sentences=finish_sentences,
                    )

        return OptimizeResponse(
            success=True,
            master_sku=canonical_master_sku,
            message=f"Generated content for {len(platforms)} platforms",
            report="\n".join(results),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Optimization failed for {request.master_sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Content Regeneration (with feedback)
# =============================================================================


async def process_regenerate_job(job_id: str, request_payload: dict):
    """Background worker for async regenerate jobs."""
    from datetime import datetime, timezone

    supabase = get_client()

    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        (
            supabase.table("generation_jobs")
            .update({"status": "running", "started_at": now_iso, "attempt_count": 1})
            .eq("id", job_id)
            .execute()
        )
        ensure_generation_enabled(operation="process_regenerate_job")
        request = RegenerateRequest(**request_payload)
        request.async_mode = False
        request_id = _require_request_id(get_request_id())
        result = await _execute_regeneration_request(request=request, request_id=request_id)
        (
            supabase.table("generation_jobs")
            .update(
                {
                    "status": "completed",
                    "result": result.model_dump(),
                    "error": None,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", job_id)
            .execute()
        )
        _emit_generation_summary(
            endpoint="process_regenerate_job",
            request_id=request_id,
            job_id=job_id,
            master_sku=str(request_payload.get("master_sku", "")),
            platform=str(request_payload.get("platform", "")),
            content_type=str(request_payload.get("content_type", "")),
            mode="async_job",
            result_state="completed",
        )
    except GenerationBudgetExceededError as exc:
        formatted = _format_job_error(exc)
        logger.warning("Async regenerate job %s budget-stopped: %s", job_id, formatted)
        request_id = get_request_id()
        try:
            (
                supabase.table("generation_jobs")
                .update(
                    {
                        "status": "failed",
                        "error": formatted,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("id", job_id)
                .execute()
            )
        except Exception as persist_exc:
            logger.error(
                "Failed to persist budget-stop state for async regenerate job %s: %s",
                job_id,
                persist_exc,
            )
        _emit_generation_summary(
            endpoint="process_regenerate_job",
            request_id=request_id,
            job_id=job_id,
            master_sku=str(request_payload.get("master_sku", "")),
            platform=str(request_payload.get("platform", "")),
            content_type=str(request_payload.get("content_type", "")),
            mode="async_job",
            result_state="failed",
            budget_stop_triggered=True,
        )
    except Exception as exc:
        formatted = _format_job_error(exc)
        logger.error("Async regenerate job %s failed: %s", job_id, formatted)
        request_id = get_request_id()
        try:
            (
                supabase.table("generation_jobs")
                .update(
                    {
                        "status": "failed",
                        "error": formatted,
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("id", job_id)
                .execute()
            )
        except Exception as persist_exc:
            logger.error(
                "Failed to persist failure state for async regenerate job %s: %s",
                job_id,
                persist_exc,
            )
        _emit_generation_summary(
            endpoint="process_regenerate_job",
            request_id=request_id,
            job_id=job_id,
            master_sku=str(request_payload.get("master_sku", "")),
            platform=str(request_payload.get("platform", "")),
            content_type=str(request_payload.get("content_type", "")),
            mode="async_job",
            result_state="failed",
        )


@app.post(
    "/regenerate",
    response_model=RegenerateResponse | RegenerateJobResponse,
    tags=["Generation"],
)
async def regenerate_content(request: RegenerateRequest):
    """Regenerate content either synchronously (default) or as queued async job."""
    request_id = (get_request_id() or "").strip()
    if not request_id or request_id == "-":
        request_id = uuid.uuid4().hex
    try:
        ensure_generation_enabled(operation="regenerate_content")
        request_id = _require_request_id(request_id)

        if request.async_mode:
            supabase = get_client()
            canonical_master_sku = resolve_canonical_master_sku(
                supabase, request.master_sku
            )
            idempotency_key = _regeneration_idempotency_key(
                request=request,
                canonical_master_sku=canonical_master_sku,
            )
            active_job = _find_active_regeneration_job(
                supabase=supabase,
                canonical_master_sku=canonical_master_sku,
                idempotency_key=idempotency_key,
            )
            if active_job and active_job.get("id"):
                normalized_status = _normalize_regeneration_job_status(
                    active_job.get("status")
                )
                return RegenerateJobResponse(
                    success=True,
                    job_id=str(active_job["id"]),
                    status=normalized_status,
                    request_id=request_id,
                    master_sku=canonical_master_sku,
                    content_type=request.content_type,
                    platform=request.platform,
                    deduplicated=True,
                )
            job_id = _create_regeneration_job(
                supabase=supabase,
                request=request,
                canonical_master_sku=canonical_master_sku,
                request_id=request_id,
                idempotency_key=idempotency_key,
            )
            request_payload = request.model_dump()
            request_payload["master_sku"] = canonical_master_sku
            request_payload["async_mode"] = False
            run_async_in_thread(
                process_regenerate_job,
                request_id=request_id,
                job_id=job_id,
                request_payload=request_payload,
            )
            return RegenerateJobResponse(
                success=True,
                job_id=job_id,
                status="pending",
                request_id=request_id,
                master_sku=canonical_master_sku,
                content_type=request.content_type,
                platform=request.platform,
                deduplicated=False,
            )

        return await _execute_regeneration_request(request=request, request_id=request_id)

    except GenerationBudgetExceededError as exc:
        _emit_generation_summary(
            endpoint="regenerate",
            request_id=request_id,
            master_sku=request.master_sku,
            platform=request.platform,
            content_type=request.content_type,
            mode="with_feedback" if request.feedback else "simple",
            result_state="failed",
            budget_stop_triggered=True,
        )
        raise HTTPException(
            status_code=429,
            detail={
                "code": "generation_budget_cap_exceeded",
                "message": str(exc),
                "platform": request.platform,
                "content_type": request.content_type,
            },
        ) from exc
    except HTTPException:
        _emit_generation_summary(
            endpoint="regenerate",
            request_id=request_id,
            master_sku=request.master_sku,
            platform=request.platform,
            content_type=request.content_type,
            mode="with_feedback" if request.feedback else "simple",
            result_state="failed",
            budget_stop_triggered=False,
        )
        raise
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        _emit_generation_summary(
            endpoint="regenerate",
            request_id=request_id,
            master_sku=request.master_sku,
            platform=request.platform,
            content_type=request.content_type,
            mode="with_feedback" if request.feedback else "simple",
            result_state="failed",
            budget_stop_triggered=False,
        )
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/regenerate/status/{job_id}",
    response_model=RegenerateJobStatusResponse,
    tags=["Generation"],
)
async def get_regenerate_status(job_id: str):
    """Get async regenerate job status and completed payload."""
    try:
        supabase = get_client()
        job = (
            supabase.table("generation_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("job_type", "regenerate")
            .maybe_single()
            .execute()
        )
        row = getattr(job, "data", None)
        if not isinstance(row, dict):
            raise HTTPException(status_code=404, detail=f"Regenerate job not found: {job_id}")
        return _normalize_regeneration_job_row(row)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to get regenerate job status for %s: %s", job_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# =============================================================================
# Lifestyle Image Generation
# =============================================================================


@app.post(
    "/generate-images",
    response_model=GenerateImagesResponse,
    tags=["Generation"],
)
async def generate_lifestyle_images(request: GenerateImagesRequest):
    """Generate lifestyle images for a SKU with smart finish selection.

    Uses Google Ads performance data to select the most popular finish,
    then generates lifestyle images using Gemini Imagen API.
    Images are uploaded to Supabase Storage and records inserted into
    product_lifestyle_images and variant_lifestyle_images tables.

    This endpoint runs synchronously (~2-4 minutes).
    """
    try:
        logger.info(
            f"Generating lifestyle images for {request.master_sku} "
            f"(variations={request.num_variations}, dry_run={request.dry_run})"
        )

        from feedops.pipeline.lifestyle_images import (
            generate_lifestyle_images_for_sku,
        )

        result = generate_lifestyle_images_for_sku(
            master_sku=request.master_sku,
            num_variations=request.num_variations,
            dry_run=request.dry_run,
            force_finish_code=request.selected_finish_code,
        )

        return GenerateImagesResponse(
            success=result["images_generated"] > 0,
            master_sku=result["master_sku"],
            selected_finish=result["selected_finish"],
            selected_finish_code=result["selected_finish_code"],
            images_generated=result["images_generated"],
            message=result["message"],
        )

    except ValueError as e:
        logger.warning(f"Image generation validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Image generation failed for {request.master_sku}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Optimization
# =============================================================================


@app.post("/batch-optimize", response_model=BatchJobResponse, tags=["Generation"])
async def batch_optimize(request: BatchOptimizeRequest):
    """Queue batch optimization job for multiple SKUs.

    Creates a job record in Supabase and processes SKUs in the background.
    Use GET /batch-status/{job_id} to check progress.
    """
    try:
        ensure_generation_enabled(operation="batch_optimize")
        supabase = get_client()
        canonical_skus = list(
            dict.fromkeys(resolve_canonical_master_skus(supabase, request.skus))
        )
        options = _normalize_generation_options(request.options)

        if not options["titles"] and not options["descriptions"]:
            raise HTTPException(
                status_code=400,
                detail="At least one content type must be selected (titles or descriptions)",
            )
        if not options["platforms"]:
            raise HTTPException(
                status_code=400, detail="At least one platform must be selected"
            )

        # Create job in Supabase (using existing table from migration 006)
        job_result = (
            supabase.table("batch_generation_jobs")
            .insert(
                {
                    "status": "queued",
                    "total_skus": len(canonical_skus),
                    "completed_skus": 0,
                    "failed_skus": 0,
                    "options": {
                        "num_candidates": request.num_candidates,
                        "dry_run": request.dry_run,
                        "titles": options["titles"],
                        "descriptions": options["descriptions"],
                        "platforms": options["platforms"],
                    },
                }
            )
            .execute()
        )

        job_id = job_result.data[0]["id"]

        # Create individual SKU records
        sku_records = [
            {"job_id": job_id, "master_sku": sku, "status": "pending"}
            for sku in canonical_skus
        ]
        supabase.table("batch_generation_job_skus").insert(sku_records).execute()

        # Queue background processing (using thread to survive container lifecycle)
        run_async_in_thread(
            JobRunner(mode="batch").run,
            request_id=get_request_id(),
            job_id=job_id,
            skus=canonical_skus,
            num_candidates=request.num_candidates,
            dry_run=request.dry_run,
            options=options,
        )

        return BatchJobResponse(
            success=True,
            job_id=str(job_id),
            status="queued",
            total_skus=len(canonical_skus),
        )

    except Exception as e:
        logger.error(f"Batch job creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/batch-status/{job_id}", response_model=BatchStatusResponse, tags=["Generation"]
)
async def get_batch_status(job_id: str):
    """Get status of a batch optimization job."""
    try:
        supabase = get_client()

        job = (
            supabase.table("batch_generation_jobs")
            .select("*")
            .eq("id", job_id)
            .single()
            .execute()
        )

        if not job.data:
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        # Get SKU-level details
        skus = (
            supabase.table("batch_generation_job_skus")
            .select("*")
            .eq("job_id", job_id)
            .execute()
        )

        return BatchStatusResponse(
            job_id=job_id,
            status=job.data["status"],
            total_skus=job.data["total_skus"],
            completed_skus=job.data.get("completed_skus", 0),
            failed_skus=job.data.get("failed_skus", 0),
            expanded_total_skus=int(
                (job.data.get("options") or {}).get("expanded_total_skus", 0)
            ),
            expanded_completed_skus=int(
                (job.data.get("options") or {}).get("expanded_completed_skus", 0)
            ),
            expanded_failed_skus=int(
                (job.data.get("options") or {}).get("expanded_failed_skus", 0)
            ),
            skus=skus.data or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Hybrid Multi-SKU Generation
# =============================================================================


@app.post("/hybrid-generate", response_model=HybridJobResponse, tags=["Generation"])
async def hybrid_generate(request: HybridGenerateRequest):
    """Generate content for multi-SKU families using hybrid approach.

    Detects multi-SKU product families (multiple master_skus sharing same product_id)
    and uses hybrid generation:
    - Base SKU: Full content generation
    - Variant SKUs: Adaptation from base content (60% cost savings)

    Creates a job record and processes in background without timeout limits.
    """
    try:
        ensure_generation_enabled(operation="hybrid_generate")
        supabase = get_client()
        canonical_skus = list(
            dict.fromkeys(resolve_canonical_master_skus(supabase, request.skus))
        )

        # Validate options
        options = _normalize_generation_options(request.options)
        if not options.get("titles") and not options.get("descriptions"):
            raise HTTPException(
                status_code=400,
                detail="At least one content type must be selected (titles or descriptions)",
            )

        platforms = options.get("platforms", ["google", "bing", "shopify"])
        if not platforms:
            raise HTTPException(
                status_code=400, detail="At least one platform must be selected"
            )

        hybrid_idempotency_key = _hybrid_generation_idempotency_key(
            canonical_skus=canonical_skus,
            options=options,
        )
        options = dict(options)
        options["idempotency_key"] = hybrid_idempotency_key
        active_job = _find_active_hybrid_job(
            supabase=supabase,
            idempotency_key=hybrid_idempotency_key,
        )
        if active_job and active_job.get("id"):
            active_options = active_job.get("options") if isinstance(active_job.get("options"), dict) else {}
            return HybridJobResponse(
                success=True,
                job_id=str(active_job["id"]),
                status=str(active_job.get("status") or "queued"),
                total_skus=int(active_job.get("total_skus") or len(canonical_skus)),
                multi_sku_families=int(active_options.get("multi_sku_families") or 0),
                single_skus=int(active_options.get("single_skus") or 0),
                strategy={
                    "base_skus": int(active_options.get("base_skus") or 0),
                    "variant_skus": int(active_options.get("variant_skus") or 0),
                },
                deduplicated=True,
            )

        logger.info(
            "Hybrid generation requested for %s SKUs: requested=%s canonical=%s",
            len(request.skus),
            request.skus,
            canonical_skus,
        )

        # Detect multi-SKU families
        families = detect_multi_sku_families(supabase, canonical_skus)

        # Get single SKUs (not in any family)
        family_skus = set()
        for family in families:
            family_skus.update(family.master_skus)
        single_skus = [sku for sku in canonical_skus if sku not in family_skus]

        requested_scope = set(canonical_skus)
        processing_scope = set(single_skus)
        for family in families:
            processing_scope.add(family.base_sku)
            processing_scope.update(family.variant_skus)
        expanded_total_skus = len(processing_scope - requested_scope)
        total_variants = sum(len(f.variant_skus) for f in families)
        base_skus_count = len(families) + len(single_skus)

        logger.info(
            f"Detected {len(families)} multi-SKU families and {len(single_skus)} single SKUs"
        )

        # Create job record
        job_result = (
            supabase.table("batch_generation_jobs")
            .insert(
                {
                    "status": "queued",
                    "total_skus": len(canonical_skus),
                    "completed_skus": 0,
                    "failed_skus": 0,
                    "options": {
                        "titles": options.get("titles", True),
                        "descriptions": options.get("descriptions", True),
                        "platforms": platforms,
                        "hybrid": True,
                        "idempotency_key": hybrid_idempotency_key,
                        "expanded_total_skus": expanded_total_skus,
                        "expanded_completed_skus": 0,
                        "expanded_failed_skus": 0,
                        "multi_sku_families": len(families),
                        "single_skus": len(single_skus),
                        "base_skus": base_skus_count,
                        "variant_skus": total_variants,
                    },
                }
            )
            .execute()
        )

        job_id = job_result.data[0]["id"]

        # Ensure per-SKU detail rows exist for the entire processing scope.
        sku_records = [
            {"job_id": job_id, "master_sku": sku, "status": "pending"}
            for sku in sorted(processing_scope)
        ]
        if sku_records:
            supabase.table("batch_generation_job_skus").insert(sku_records).execute()

        # Queue background processing (using thread to survive container lifecycle)
        run_async_in_thread(
            JobRunner(mode="hybrid").run,
            request_id=get_request_id(),
            job_id=job_id,
            families=families,
            single_skus=single_skus,
            requested_skus=canonical_skus,
            options=options,
        )

        return HybridJobResponse(
            success=True,
            job_id=str(job_id),
            status="queued",
            total_skus=len(canonical_skus),
            multi_sku_families=len(families),
            single_skus=len(single_skus),
            strategy={
                "base_skus": base_skus_count,
                "variant_skus": total_variants,
            },
            deduplicated=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hybrid generation request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Background job processing delegated to JobRunner (Plan 03-01)
# =============================================================================
# process_batch_job and process_hybrid_batch_job have been moved to
# feedops.api.job_runner.JobRunner. Route handlers above use:
#   run_async_in_thread(JobRunner(mode="batch").run, ...)
#   run_async_in_thread(JobRunner(mode="hybrid").run, ...)


# =============================================================================
# Backfill Job Endpoints (v1.0 Data Collection Infrastructure)
# =============================================================================


@app.post("/backfill/start", response_model=BackfillJobResponse)
async def api_start_backfill(request: StartBackfillRequest):
    """Create and start a new data backfill job.

    Processes SKUs in batches with rate limiting, checkpointing, and error tracking.
    Maximum 3 concurrent jobs allowed.
    """
    return await start_backfill(request)


@app.get("/backfill/validation-report", response_model=ValidationReportResponse)
async def api_validation_report(job_id: str | None = None):
    """Get data quality validation report.

    Returns completeness (if job_id provided), freshness, and outlier metrics.
    Dashboard uses this to display data quality indicators.
    """
    return await get_validation_report(job_id=job_id)


@app.get("/backfill/status/{job_id}", response_model=BackfillJobResponse)
async def api_get_backfill_status(job_id: str):
    """Get backfill job status and progress."""
    return await get_backfill_status(job_id)


@app.post("/backfill/resume/{job_id}", response_model=BackfillJobResponse)
async def api_resume_backfill(job_id: str):
    """Resume a failed or partial backfill job from its last checkpoint."""
    return await resume_backfill(job_id)


@app.get("/backfill/jobs", response_model=BackfillJobListResponse)
async def api_list_backfill_jobs(status: str | None = None, limit: int = 20):
    """List backfill jobs, optionally filtered by status."""
    return await list_backfill_jobs(status=status, limit=limit)


# =============================================================================
# Intent Scoring (Feed Alignment)
# =============================================================================
# Extracted to feedops.api.intent_scoring (Plan 02-01).
# Route registered via app.include_router(intent_scoring_router) above.
# _get_intent_scorer, _extract_query_intent_generation_diagnostics, api_score_intent
# are all in feedops.api.intent_scoring.
