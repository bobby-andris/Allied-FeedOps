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

Route handlers live in feedops.api.routes (DECOMP-09, Plan 03-02).
This module contains only: lifespan, app creation, middleware, and router mounts.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from feedops.api.env_contract import (
    RuntimeEnvContractError,
    validate_runtime_env_contract,
)
from feedops.observability import request_context
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

# Include all main route handlers (extracted in DECOMP-09 Plan 03-02)
from feedops.api.routes import router as main_router
app.include_router(main_router)


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
# Backward-compatibility re-exports (DECOMP-09 dual-namespace pattern)
#
# Tests import `feedops.api.main as api_main` and access route handler
# functions directly (e.g. api_main.regenerate_content). After extracting
# handlers to routes.py, we re-export them here so monkeypatching still works.
# The route handlers registered on the FastAPI app will use whatever is bound
# in the routes module at call time — monkeypatches on api_main attributes
# affect code paths that reference the name via this module.
# =============================================================================
from feedops.api.routes import (  # noqa: E402,F401
    # Route handlers
    root,
    health_check,
    optimize_single_sku,
    process_regenerate_job,
    regenerate_content,
    get_regenerate_status,
    generate_lifestyle_images,
    batch_optimize,
    get_batch_status,
    hybrid_generate,
    api_start_backfill,
    api_validation_report,
    api_get_backfill_status,
    api_resume_backfill,
    api_list_backfill_jobs,
)

# Re-export imported helpers that tests access via api_main.*
from feedops.api.schemas import (  # noqa: E402,F401
    OptimizeRequest,
    RegenerateRequest,
    BatchOptimizeRequest,
    HealthResponse,
    OptimizeResponse,
    RegenerateResponse,
    RegenerateJobResponse,
    RegenerateJobStatusResponse,
    BatchJobResponse,
    BatchStatusResponse,
    GenerateImagesRequest,
    GenerateImagesResponse,
    HybridGenerateRequest,
    HybridJobResponse,
    ScoreIntentRequest,
    ScoreIntentItem,
    ScoreIntentResponse,
    _normalize_regeneration_job_status,
    _normalize_generation_options,
    _content_field_key,
    _extract_content_from_schema_response,
)
from feedops.api.prompt_loader import (  # noqa: E402,F401
    get_system_prompt,
    get_system_prompt_hash,
    get_platform_system_prompt,
    get_category_guidance,
    format_gold_standard_examples,
    get_finish_list,
    get_platform_system_prompt_hash,
)
from feedops.api.supabase_loader import (  # noqa: E402,F401
    get_product_catalog_count,
    load_parent_sku_from_supabase,
)
from feedops.api.generation_telemetry import (  # noqa: E402,F401
    estimate_openai_cost_usd_from_usage as _estimate_openai_cost_usd_from_usage,
    extract_platform_telemetry as _extract_platform_telemetry,
    extract_scoped_telemetry as _extract_scoped_telemetry,
    provider_label as _provider_label,
    safe_int as _safe_int,
)
from feedops.db.supabase_client import get_client, is_supabase_available  # noqa: E402,F401
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown  # noqa: E402,F401
from feedops.api.prompt_builder import build_core_prompt, apply_feedback_layer  # noqa: E402,F401
from feedops.providers import get_provider  # noqa: E402,F401
from feedops.providers.base import close_provider  # noqa: E402,F401
from feedops.api.multi_sku_detection import detect_multi_sku_families  # noqa: E402,F401
from feedops.api.telemetry import (  # noqa: E402,F401
    run_async_in_thread,
    _emit_generation_summary,
    _telemetry_scope_for_content,
    _generate_with_metrics,
    _should_persist_finish_sentences,
)
from feedops.api.persistence import (  # noqa: E402,F401
    _lookup_generated_content_id,
    _load_generated_content_row,
    _assembled_prompt_hash,
    _enforce_write_time_finish_placeholder_contract,
    _persist_regeneration_result,
    _persist_generated_content_and_history,
    _persist_finish_prompt_lineage,
    _upsert_batch_job_sku_status,
)
from feedops.api.job_management import (  # noqa: E402,F401
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
from feedops.api.hybrid_generation import adapt_variant_content  # noqa: E402,F401
from feedops.api.job_runner import JobRunner  # noqa: E402,F401
from feedops.api.sku_alias import (  # noqa: E402,F401
    resolve_canonical_master_sku,
    resolve_canonical_master_skus,
)
from feedops.api.runtime_controls import (  # noqa: E402,F401
    diagnostic_mode_enabled,
    ensure_generation_enabled,
    finish_sentence_regeneration_enabled,
)
from feedops.pipeline.feature_flags import capture_flag_snapshot  # noqa: E402,F401
from feedops.pipeline.generator import GenerationBudgetExceededError, generate_per_platform  # noqa: E402,F401
from feedops.observability import get_request_id, log_event  # noqa: E402,F401
from feedops.api.generation import (  # noqa: E402,F401
    _build_generation_user_prompt,
    _execute_regeneration_request,
)
from feedops.api.finish_processing import (  # noqa: E402,F401
    _build_finish_sentences_user_prompt,
    _validate_finish_sentences_payload,
    _enforce_finish_sentence_parity,
)
from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics  # noqa: E402,F401
