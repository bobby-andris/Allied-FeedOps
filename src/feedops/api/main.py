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
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

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
from feedops.api.multi_sku_detection import (
    detect_multi_sku_families,
)
from feedops.api.sku_alias import (
    resolve_canonical_master_sku,
    resolve_canonical_master_skus,
)
from feedops.api.runtime_controls import (
    ensure_generation_enabled,
    finish_sentence_regeneration_enabled,
)
from feedops.api.env_contract import (
    RuntimeEnvContractError,
    validate_runtime_env_contract,
)
from feedops.pipeline.feature_flags import capture_flag_snapshot
from feedops.pipeline.generator import generate_per_platform
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
            finally:
                loop.close()

    thread = threading.Thread(target=wrapper, daemon=False)
    thread.start()
    logger.info(f"Started background job thread: {async_func.__name__}")
    return thread


# =============================================================================
# Request/Response Models (Pydantic v2)
# =============================================================================


class OptimizeRequest(BaseModel):
    """Request to optimize a single SKU."""

    master_sku: str = Field(..., description="Master SKU to optimize (e.g., '1051')")
    num_candidates: int = Field(
        default=3, ge=1, le=10, description="Number of candidates to generate"
    )
    dry_run: bool = Field(default=True, description="If true, don't save to database")


class RegenerateRequest(BaseModel):
    """Request to regenerate specific content with feedback."""

    master_sku: str = Field(..., description="Master SKU")
    content_type: Literal["title", "description"] = Field(
        ..., description="Type of content to regenerate"
    )
    platform: Literal["google", "bing", "shopify"] = Field(
        default="google", description="Target platform"
    )
    feedback: str | None = Field(
        default=None, description="Human feedback for improvement"
    )
    finish_code: str | None = Field(
        default=None, description="Specific finish code for variant"
    )
    # Structured feedback fields (FIX-01: feedback layer)
    tone_style: Literal["formal", "conversational", "technical", "aspirational"] | None = Field(
        default=None, description="Desired tone and style for the content"
    )
    emphasis: list[Literal["finish", "dimensions", "use_case", "compatibility", "luxury"]] | None = Field(
        default=None, description="Content aspects to emphasize"
    )
    length_preference: Literal["shorter", "standard", "longer"] | None = Field(
        default=None, description="Desired length relative to current"
    )
    save_as_correction: bool = Field(
        default=False,
        description="If true, save structured feedback as a persistent correction for this SKU",
    )
    async_mode: bool = Field(
        default=False,
        description="If true, enqueue regeneration as a background job and return job_id immediately",
    )


class BatchOptimizeRequest(BaseModel):
    """Request to optimize multiple SKUs."""

    skus: list[str] = Field(
        ..., min_length=1, max_length=100, description="List of master SKUs"
    )
    num_candidates: int = Field(
        default=1, ge=1, le=5, description="Candidates per SKU"
    )
    dry_run: bool = Field(default=True, description="If true, don't save to database")
    options: dict | None = Field(
        default=None,
        description=(
            "Optional generation controls: "
            "{titles: bool, descriptions: bool, platforms: list[str]}"
        ),
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded"]
    service: str
    version: str
    product_catalog_count: int
    supabase_connected: bool


class OptimizeResponse(BaseModel):
    """Response from optimization endpoint."""

    success: bool
    master_sku: str
    message: str
    report: str | None = None
    error: str | None = None


class RegenerateResponse(BaseModel):
    """Response from regeneration endpoint."""

    success: bool
    master_sku: str
    content_type: str
    platform: str
    content: str
    finish_sentences: dict[str, str] | None = None
    used_feedback: bool
    prompt_hash: str
    model: str | None = None
    generated_content_id: str | None = None
    version: int = 0
    state: Literal["completed", "no_change"] = "completed"
    idempotent: bool = False
    request_id: str


class RegenerateJobResponse(BaseModel):
    """Response when regeneration is queued asynchronously."""

    success: bool
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    request_id: str
    master_sku: str
    content_type: str
    platform: str
    deduplicated: bool = False


class RegenerateJobStatusResponse(BaseModel):
    """Status payload for asynchronous regeneration jobs."""

    success: bool
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    request_id: str | None = None
    master_sku: str | None = None
    content_type: str | None = None
    platform: str | None = None
    result: RegenerateResponse | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


def _normalize_regeneration_job_status(raw_status: object) -> Literal["pending", "running", "completed", "failed"]:
    """Normalize DB status values into API contract enum."""
    value = str(raw_status or "").strip().lower()
    if value in {"pending", "queued"}:
        return "pending"
    if value == "running":
        return "running"
    if value == "completed":
        return "completed"
    return "failed"


class BatchJobResponse(BaseModel):
    """Response from batch optimization endpoint."""

    success: bool
    job_id: str
    status: str
    total_skus: int


class BatchStatusResponse(BaseModel):
    """Response from batch status endpoint."""

    job_id: str
    status: str
    total_skus: int
    completed_skus: int
    failed_skus: int
    expanded_total_skus: int = 0
    expanded_completed_skus: int = 0
    expanded_failed_skus: int = 0
    skus: list[dict]


class GenerateImagesRequest(BaseModel):
    """Request to generate lifestyle images for a SKU."""

    master_sku: str = Field(..., description="Master SKU to generate images for")
    num_variations: int = Field(
        default=3, ge=1, le=5, description="Number of image variations to generate"
    )
    dry_run: bool = Field(
        default=False, description="If true, generate images but don't upload/save"
    )
    selected_finish_code: str | None = Field(
        default=None,
        description="Force specific finish code (overrides auto-selection)",
    )


class GenerateImagesResponse(BaseModel):
    """Response from lifestyle image generation endpoint."""

    success: bool
    master_sku: str
    selected_finish: str
    selected_finish_code: str
    images_generated: int
    message: str


class HybridGenerateRequest(BaseModel):
    """Request for hybrid multi-SKU generation."""

    skus: list[str] = Field(
        ..., min_length=1, max_length=100, description="List of master SKUs"
    )
    options: dict = Field(
        ...,
        description="Generation options: {titles: bool, descriptions: bool, platforms: list[str]}",
    )


class HybridJobResponse(BaseModel):
    """Response from hybrid generation endpoint."""

    success: bool
    job_id: str
    status: str
    total_skus: int
    multi_sku_families: int
    single_skus: int
    strategy: dict  # {base_skus: int, variant_skus: int}
    deduplicated: bool = False


def _normalize_generation_options(options: dict | None) -> dict:
    """Normalize optional generation controls used by batch endpoints."""
    normalized = {
        "titles": True,
        "descriptions": True,
        "platforms": ["google", "bing", "shopify"],
    }
    if not isinstance(options, dict):
        return normalized

    if "titles" in options:
        normalized["titles"] = bool(options.get("titles"))
    if "descriptions" in options:
        normalized["descriptions"] = bool(options.get("descriptions"))

    raw_platforms = options.get("platforms")
    if isinstance(raw_platforms, list):
        valid = {"google", "bing", "shopify"}
        parsed_platforms = [
            platform
            for platform in raw_platforms
            if isinstance(platform, str) and platform in valid
        ]
        normalized["platforms"] = parsed_platforms

    return normalized


def _content_field_key(platform: str, content_type: str) -> str:
    """Map platform/content_type to per-platform result field key."""
    field_map = {
        ("google", "title"): "google_title",
        ("google", "description"): "google_description",
        ("bing", "title"): "bing_title",
        ("bing", "description"): "bing_description",
        ("shopify", "title"): "shopify_title",
        ("shopify", "description"): "shopify_description",
    }
    return field_map[(platform, content_type)]


def _extract_content_from_schema_response(
    response: dict,
    platform: str,
    content_type: str,
) -> str:
    """Extract platform/content content from schema response payload.

    Args:
        response: Parsed JSON dict from provider.generate().
        platform: "google", "bing", or "shopify".
        content_type: "title" or "description".

    Returns:
        The content string, stripped. Empty string if the field is absent/empty.
    """
    # Map (platform, content_type) → CANDIDATE_SCHEMA key
    _FIELD_MAP = {
        ("google", "title"): "google_title",
        ("google", "description"): "google_description",
        ("bing", "title"): "bing_title",
        ("bing", "description"): "bing_description",
        ("shopify", "title"): "shopify_title",
        ("shopify", "description"): "shopify_description",
    }
    field_key = _FIELD_MAP.get((platform, content_type))
    if not field_key:
        raise ValueError(f"Unsupported platform/content_type pair: {platform}/{content_type}")
    value = response.get(field_key, "")
    return (value or "").strip()


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
            provider=provider.name,
            platform=platform,
            content_type=content_type,
        )
        raise
    finally:
        metrics_registry.observe(
            "generation_latency_seconds",
            time.perf_counter() - started,
            endpoint=endpoint,
            provider=provider.name,
            platform=platform,
            content_type=content_type,
        )


def _build_generation_user_prompt(
    parent_sku: ParentSKU,
    evidence_markdown: str,
    platform: str,
    content_type: str,
    feedback: str | None = None,
    finish_code: str | None = None,
    evidence: list | None = None,
) -> str:
    """DEPRECATED: Use build_core_prompt() from prompt_builder.py instead.

    Thin wrapper around build_core_prompt() + apply_feedback_layer() maintained
    for backward compatibility. New call sites should call build_core_prompt()
    directly to pass the raw evidence list for keyword placement enrichment.
    """
    # Shopping intelligence/segment sections are composed inside prompt_builder.
    # This wrapper intentionally delegates all structural prompt rules there.
    core = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence or [],
        evidence_markdown=evidence_markdown,
        platform=platform,
        content_type=content_type,
        finish_code=finish_code,
    )
    return apply_feedback_layer(core, corrections=[], session_feedback=feedback)


def _build_finish_sentences_user_prompt(
    *,
    base_description: str,
    master_sku: str,
    platform: str,
) -> str:
    """Build finish-sentence prompt for Google/Bing variant descriptions."""
    finish_names = get_finish_list()
    finish_list_markdown = "\n".join(f'- "{finish}"' for finish in finish_names)
    finish_schema_template = ",\n".join(
        f'    "{finish}": "One product-specific sentence..."'
        for finish in finish_names
    )

    return f"""\
You are generating finish-specific companion lines for an existing product description.

Master SKU: {master_sku}
Platform: {platform}

Base description:
"{base_description}"

Task:
- Generate one sentence per finish in the canonical list below.
- Each sentence must reference THIS product description context (not a generic finish blurb).
- Keep claims factual and consistent with the base description.
- Do not use slash-separated keyword dumps or parenthetical keyword stuffing.

Canonical finishes:
{finish_list_markdown}

Return ONLY valid JSON:
{{
  "finish_sentences": {{
{finish_schema_template}
  }}
}}
"""


def _lookup_generated_content_id(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
) -> str | None:
    """Resolve generated_content.id for history linkage."""
    try:
        lookup = (
            supabase.table("generated_content")
            .select("id")
            .eq("master_sku", master_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .maybe_single()
            .execute()
        )
        data = getattr(lookup, "data", None)
        if isinstance(data, dict):
            content_id = data.get("id")
            if isinstance(content_id, str) and content_id:
                return content_id
    except Exception as exc:
        logger.warning(
            "Failed to resolve generated_content_id for %s/%s/%s: %s",
            master_sku,
            platform,
            content_type,
            exc,
        )
    return None


def _load_generated_content_row(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
) -> dict | None:
    """Load current generated_content row for deterministic regeneration writes."""
    lookup = (
        supabase.table("generated_content")
        .select("id,version,candidate_content")
        .eq("master_sku", master_sku)
        .eq("platform", platform)
        .eq("content_type", content_type)
        .maybe_single()
        .execute()
    )
    data = getattr(lookup, "data", None)
    return data if isinstance(data, dict) else None


def _assembled_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """Build deterministic hash of the exact prompt pair used for generation."""
    canonical = json.dumps(
        {
            "system_prompt": system_prompt or "",
            "user_prompt": user_prompt or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _enforce_write_time_finish_placeholder_contract(
    *,
    platform: str,
    content_type: str,
    content: str,
    endpoint: str,
) -> None:
    """Fail fast if Google/Bing descriptions violate finish placeholder contract."""
    if content_type != "description" or platform not in {"google", "bing"}:
        return

    placeholder_count = count_finish_sentence_placeholders(content)
    if placeholder_count == 1:
        return

    if placeholder_count == 0:
        code = "regenerate_description_missing_finish_placeholder"
        message = "Google/Bing descriptions must include exactly one {FINISH_SENTENCE} placeholder before persistence."
    else:
        code = "regenerate_description_multiple_finish_placeholders"
        message = "Google/Bing descriptions must include exactly one {FINISH_SENTENCE}; multiple placeholders are not allowed."

    raise HTTPException(
        status_code=422,
        detail={
            "code": code,
            "message": message,
            "platform": platform,
            "content_type": content_type,
            "placeholder_count": placeholder_count,
            "endpoint": endpoint,
        },
    )


def _persist_regeneration_result(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
    content: str,
    generation_model: str,
    prompt_hash: str,
    system_prompt: str,
    user_prompt: str,
    feedback_text: str | None,
    mode: str,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    generation_diagnostics: dict | None = None,
    latency_ms: int | None = None,
    provider_attempt_count: int | None = None,
    parse_retry_count: int | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Persist regeneration content/history with idempotent no-change behavior."""
    current_row = _load_generated_content_row(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    current_content = (
        str(current_row.get("candidate_content", "")).strip()
        if isinstance(current_row, dict) and current_row.get("candidate_content") is not None
        else None
    )
    normalized_content = (content or "").strip()

    if current_content is not None and current_content == normalized_content:
        current_version = int(current_row.get("version") or 1)
        return {
            "state": "no_change",
            "idempotent": True,
            "generated_content_id": current_row.get("id"),
            "version": current_version,
        }

    next_version = (
        int(current_row.get("version") or 0) + 1 if isinstance(current_row, dict) else 1
    )
    generation_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _enforce_write_time_finish_placeholder_contract(
        platform=platform,
        content_type=content_type,
        content=normalized_content,
        endpoint="_persist_regeneration_result",
    )
    write_payload = {
        "master_sku": master_sku,
        "platform": platform,
        "content_type": content_type,
        "candidate_content": normalized_content,
        "version": next_version,
        "is_current": True,
        "generation_model": generation_model,
        "generation_prompt_hash": prompt_hash,
        "generation_timestamp": generation_timestamp,
    }

    generated_content_id: str | None = None
    if isinstance(current_row, dict) and current_row.get("id"):
        (
            supabase.table("generated_content")
            .update(write_payload)
            .eq("id", current_row["id"])
            .execute()
        )
        generated_content_id = str(current_row["id"])
    else:
        (
            supabase.table("generated_content")
            .insert(write_payload)
            .execute()
        )

    if not generated_content_id:
        generated_content_id = _lookup_generated_content_id(
            supabase=supabase,
            master_sku=master_sku,
            platform=platform,
            content_type=content_type,
        )

    lineage_request_id = _require_request_id(request_id or get_request_id())
    flag_snapshot = capture_flag_snapshot()
    if isinstance(generation_diagnostics, dict) and generation_diagnostics:
        flag_snapshot = dict(flag_snapshot)
        flag_snapshot["generation_diagnostics"] = generation_diagnostics

    canonical_platform_hash = get_platform_system_prompt_hash(platform)
    assembled_prompt_hash = _assembled_prompt_hash(system_prompt, user_prompt)
    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "feedback_text": feedback_text,
        "previous_content": current_content,
        "new_content": normalized_content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:50000],
        "user_prompt": user_prompt[:50000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
        "feature_flags_active": flag_snapshot,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "provider_attempt_count": _safe_int(provider_attempt_count, 0),
        "parse_retry_count": _safe_int(parse_retry_count, 0),
        "request_id": lineage_request_id,
        "result_state": "completed",
        "result_version": next_version,
        "result_idempotent": False,
        "idempotency_key": idempotency_key,
        "canonical_platform_hash": canonical_platform_hash,
        "assembled_prompt_hash": assembled_prompt_hash,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()

    return {
        "state": "completed",
        "idempotent": False,
        "generated_content_id": generated_content_id,
        "version": next_version,
    }


def _persist_generated_content_and_history(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
    content: str,
    generation_model: str,
    prompt_hash: str,
    system_prompt: str,
    user_prompt: str,
    mode: str,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    provider_attempt_count: int | None = None,
    parse_retry_count: int | None = None,
    generation_diagnostics: dict | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
):
    """Persist generated content and linked history in one canonical path."""
    _enforce_write_time_finish_placeholder_contract(
        platform=platform,
        content_type=content_type,
        content=content,
        endpoint="_persist_generated_content_and_history",
    )
    supabase.table("generated_content").upsert(
        {
            "master_sku": master_sku,
            "platform": platform,
            "content_type": content_type,
            "candidate_content": content,
            "generation_model": generation_model,
            "generation_prompt_hash": prompt_hash,
        },
        on_conflict="master_sku,platform,content_type",
    ).execute()

    generated_content_id = _lookup_generated_content_id(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    content_row = _load_generated_content_row(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    result_version = (
        int(content_row.get("version") or 1) if isinstance(content_row, dict) else 1
    )

    lineage_request_id = _require_request_id(request_id or get_request_id())
    flag_snapshot = capture_flag_snapshot()
    if isinstance(generation_diagnostics, dict) and generation_diagnostics:
        flag_snapshot = dict(flag_snapshot)
        flag_snapshot["generation_diagnostics"] = generation_diagnostics

    canonical_platform_hash = get_platform_system_prompt_hash(platform)
    assembled_prompt_hash = _assembled_prompt_hash(system_prompt, user_prompt)
    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "new_content": content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:50000],
        "user_prompt": user_prompt[:50000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
        "feature_flags_active": flag_snapshot,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "provider_attempt_count": _safe_int(provider_attempt_count, 0),
        "parse_retry_count": _safe_int(parse_retry_count, 0),
        "request_id": lineage_request_id,
        "result_state": "completed",
        "result_version": result_version,
        "result_idempotent": False,
        "idempotency_key": idempotency_key,
        "canonical_platform_hash": canonical_platform_hash,
        "assembled_prompt_hash": assembled_prompt_hash,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()


def _create_regeneration_job(
    *,
    supabase,
    request: RegenerateRequest,
    canonical_master_sku: str,
    request_id: str,
    idempotency_key: str,
) -> str:
    """Create a generation_jobs row for async regeneration tracking."""
    job_payload = {
        "master_sku": canonical_master_sku,
        "job_type": "regenerate",
        "status": "pending",
        "priority": 0,
        "input_params": {
            "request": request.model_dump(),
            "request_id": request_id,
            "platform": request.platform,
            "content_type": request.content_type,
            "idempotency_key": idempotency_key,
        },
        "attempt_count": 0,
        "max_attempts": 1,
        "requested_by": "dashboard",
    }
    result = supabase.table("generation_jobs").insert(job_payload).execute()
    data = getattr(result, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    raise RuntimeError("Failed to create regeneration job: missing job id")


def _format_job_error(exc: Exception) -> str:
    """Create stable, actionable error text for async job records."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return json.dumps(detail, default=str)[:2000]
        return str(detail)[:2000]
    return str(exc)[:2000]


def _require_request_id(request_id: str | None) -> str:
    """Enforce non-placeholder request IDs for lineage writes."""
    rid = (request_id or "").strip()
    if not rid or rid == "-":
        raise RuntimeError("Missing request_id for regeneration lineage write")
    return rid


def _regeneration_idempotency_key(
    *,
    request: RegenerateRequest,
    canonical_master_sku: str,
) -> str:
    """Compute a stable idempotency key for async regenerate requests."""
    payload = {
        "master_sku": canonical_master_sku,
        "platform": request.platform,
        "content_type": request.content_type,
        "feedback": (request.feedback or "").strip(),
        "finish_code": (request.finish_code or "").strip(),
        "tone_style": request.tone_style,
        "emphasis": request.emphasis or [],
        "length_preference": request.length_preference,
        "save_as_correction": bool(request.save_as_correction),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hybrid_generation_idempotency_key(
    *,
    canonical_skus: list[str],
    options: dict,
) -> str:
    """Compute a stable idempotency key for hybrid generation submissions."""
    payload = {
        "skus": sorted({sku for sku in canonical_skus if isinstance(sku, str)}),
        "titles": bool(options.get("titles", True)),
        "descriptions": bool(options.get("descriptions", True)),
        "platforms": sorted(
            {platform for platform in options.get("platforms", []) if isinstance(platform, str)}
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_active_regeneration_job(
    *,
    supabase,
    canonical_master_sku: str,
    idempotency_key: str,
) -> dict | None:
    """Return matching pending/running regenerate job for dedupe window."""
    lookup = (
        supabase.table("generation_jobs")
        .select("*")
        .eq("master_sku", canonical_master_sku)
        .eq("job_type", "regenerate")
        .in_("status", ["pending", "running"])
        .execute()
    )
    rows = getattr(lookup, "data", None)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        input_params = row.get("input_params")
        if not isinstance(input_params, dict):
            continue
        if input_params.get("idempotency_key") == idempotency_key:
            return row
    return None


def _find_active_hybrid_job(
    *,
    supabase,
    idempotency_key: str,
) -> dict | None:
    """Return matching queued/processing hybrid job for dedupe window."""
    lookup = (
        supabase.table("batch_generation_jobs")
        .select("*")
        .in_("status", ["queued", "processing"])
        .execute()
    )
    rows = getattr(lookup, "data", None)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        options = row.get("options")
        if not isinstance(options, dict):
            continue
        if options.get("idempotency_key") == idempotency_key:
            return row
    return None


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

    log_event(
        logger,
        logging.INFO if result_state in {"completed", "no_change"} else logging.WARNING,
        "generation.request.summary",
        **fields,
    )


def _upsert_batch_job_sku_status(
    *,
    supabase,
    job_id: str,
    master_sku: str,
    status: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    error_message: str | None = None,
) -> None:
    """Ensure a batch SKU detail row exists and is updated deterministically."""
    payload: dict[str, object] = {
        "job_id": job_id,
        "master_sku": master_sku,
        "status": status,
    }
    if started_at:
        payload["started_at"] = started_at
    if completed_at:
        payload["completed_at"] = completed_at
    if error_message:
        payload["error_message"] = error_message[:500]
    supabase.table("batch_generation_job_skus").upsert(
        payload,
        on_conflict="job_id,master_sku",
    ).execute()


def _normalize_regeneration_job_row(job_row: dict) -> RegenerateJobStatusResponse:
    """Normalize generation_jobs row into API response contract."""
    raw_result = job_row.get("result")
    parsed_result: RegenerateResponse | None = None
    if isinstance(raw_result, dict):
        try:
            parsed_result = RegenerateResponse(**raw_result)
        except Exception:
            parsed_result = None

    request_id = None
    if parsed_result and parsed_result.request_id:
        request_id = parsed_result.request_id
    else:
        input_params = job_row.get("input_params")
        if isinstance(input_params, dict):
            rid = input_params.get("request_id")
            if isinstance(rid, str) and rid.strip():
                request_id = rid.strip()

    error_value = job_row.get("error")
    if not isinstance(error_value, str) or not error_value:
        error_value = None

    return RegenerateJobStatusResponse(
        success=True,
        job_id=str(job_row["id"]),
        status=_normalize_regeneration_job_status(job_row.get("status")),
        request_id=request_id,
        master_sku=job_row.get("master_sku"),
        content_type=(
            parsed_result.content_type
            if parsed_result
            else (
                (job_row.get("input_params") or {}).get("content_type")
                if isinstance(job_row.get("input_params"), dict)
                else None
            )
        ),
        platform=(
            parsed_result.platform
            if parsed_result
            else (
                (job_row.get("input_params") or {}).get("platform")
                if isinstance(job_row.get("input_params"), dict)
                else None
            )
        ),
        result=parsed_result,
        error=error_value,
        created_at=job_row.get("created_at"),
        started_at=job_row.get("started_at"),
        completed_at=job_row.get("completed_at"),
    )


def _validate_finish_sentences_payload(
    raw: object,
    *,
    base_description: str,
    master_sku: str,
    platform: str,
) -> dict[str, str]:
    """Normalize + validate finish sentences and log rejection reasons."""
    finish_names = get_finish_list()
    accepted, rejected = normalize_and_validate_finish_sentences(
        raw=raw,
        finish_names=finish_names,
        base_description=base_description,
    )

    if rejected:
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_rejected",
            platform=platform,
        )
        logger.warning(
            "Rejected finish sentences for %s/%s: %s",
            master_sku,
            platform,
            rejected,
        )
    if len(accepted) != len(finish_names):
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_incomplete",
            platform=platform,
        )
    return accepted


async def _enforce_finish_sentence_parity(
    *,
    provider,
    content: str,
    master_sku: str,
    platform: str,
    endpoint: str,
) -> tuple[str, dict[str, str] | None]:
    """Apply regenerate-equivalent finish handling for Google/Bing descriptions."""
    finish_names = get_finish_list()
    fallback_finish_sentences = build_fallback_finish_sentences(finish_names)
    sanitized_content = strip_hardcoded_finish_names(
        strip_generic_finish_count_claims(content),
        finish_names,
    )
    normalized_content = normalize_base_description_with_finish_placeholder(
        sanitized_content
    )

    if not finish_sentence_regeneration_enabled():
        metrics_registry.increment(
            "generation_kill_switch_total",
            endpoint=endpoint,
            switch="finish_sentence_regen",
        )
        log_event(
            logger,
            logging.WARNING,
            "generation.finish_sentences.skipped",
            endpoint=endpoint,
            master_sku=master_sku,
            platform=platform,
            reason="FEEDOPS_DISABLE_FINISH_SENTENCE_REGEN",
        )
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_fallback_used",
            platform=platform,
        )
        return normalized_content, fallback_finish_sentences

    finish_schema = {
        "type": "object",
        "properties": {
            "finish_sentences": {
                "type": "object",
                "properties": {finish: {"type": "string"} for finish in finish_names},
                "required": finish_names,
            }
        },
        "required": ["finish_sentences"],
    }
    finish_prompt = _build_finish_sentences_user_prompt(
        base_description=sanitized_content,
        master_sku=master_sku,
        platform=platform,
    )
    finish_system_prompt = get_platform_system_prompt("finish")
    finish_prompt_hash = _assembled_prompt_hash(finish_system_prompt, finish_prompt)
    log_event(
        logger,
        logging.INFO,
        "generation.finish_sentences.request",
        endpoint=endpoint,
        master_sku=master_sku,
        platform=platform,
        system_prompt_source="platform_finish",
        prompt_hash_finish=finish_prompt_hash,
    )
    finish_response = await _generate_with_metrics(
        endpoint=f"{endpoint}_finish_sentences",
        provider=provider,
        prompt=finish_prompt,
        schema=finish_schema,
        system_prompt=finish_system_prompt,
        platform=platform,
        content_type="finish_sentences",
    )

    finish_payload = finish_response.get("finish_sentences", finish_response)
    validated_finish_sentences = _validate_finish_sentences_payload(
        finish_payload,
        base_description=sanitized_content,
        master_sku=master_sku,
        platform=platform,
    )
    if len(validated_finish_sentences) != len(get_finish_list()):
        logger.warning(
            "Finish sentence generation returned incomplete canonical coverage "
            "for %s/%s (%s/%s accepted)",
            master_sku,
            platform,
            len(validated_finish_sentences),
            len(get_finish_list()),
        )
        metrics_registry.increment(
            "validation_failure_total",
            type="finish_sentence_fallback_used",
            platform=platform,
        )
        return normalized_content, fallback_finish_sentences

    return normalized_content, validated_finish_sentences


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

        generated = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
        )
        prompt_hashes = generated.get("prompt_hashes", {})
        system_prompts = generated.get("system_prompts", {})
        user_prompts = generated.get("user_prompts", {})
        usage_by_platform = generated.get("usage_by_platform", {})
        latencies = generated.get("latency_by_platform", {})
        parse_by_platform = generated.get("parse_by_platform", {})
        retry_by_platform = generated.get("retry_by_platform", {})
        request_id = get_request_id()

        for platform in platforms:
            for content_type in content_types:
                field_key = _content_field_key(platform, content_type)
                content = str(generated.get(field_key, "")).strip()
                results.append(f"{platform}/{content_type}: {content[:100]}...")
                if request.dry_run:
                    continue
                telemetry = _extract_platform_telemetry(
                    platform=platform,
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
                    generation_model=provider.name,
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

        finish_sentences = generated.get("finish_sentences", {})
        if not request.dry_run and isinstance(finish_sentences, dict):
            for platform in ("google", "bing"):
                supabase.table("variant_finish_sentences").upsert(
                    {
                        "master_sku": canonical_master_sku,
                        "platform": platform,
                        "finish_sentences": finish_sentences,
                    },
                    on_conflict="master_sku,platform",
                ).execute()

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


async def _execute_regeneration_request(
    *,
    request: RegenerateRequest,
    request_id: str,
) -> RegenerateResponse:
    """Execute a single regeneration request and return the full response payload."""
    supabase = get_client()
    canonical_master_sku = resolve_canonical_master_sku(supabase, request.master_sku)
    request_idempotency_key = _regeneration_idempotency_key(
        request=request,
        canonical_master_sku=canonical_master_sku,
    )
    logger.info(
        "Regenerating %s for SKU: requested=%s canonical=%s",
        request.content_type,
        request.master_sku,
        canonical_master_sku,
    )
    log_event(
        logger,
        logging.INFO,
        "generation.regenerate.start",
        endpoint="regenerate",
        master_sku=canonical_master_sku,
        requested_master_sku=request.master_sku,
        platform=request.platform,
        content_type=request.content_type,
        request_id=request_id,
    )

    # Load product data from Supabase
    parent_sku = load_parent_sku_from_supabase(canonical_master_sku)
    if not parent_sku:
        raise HTTPException(status_code=404, detail=f"SKU not found: {request.master_sku}")

    # Get LLM provider
    provider = get_provider()
    prompt_hash = get_platform_system_prompt_hash(request.platform)

    # Load persistent corrections for this SKU (FIX-01: feedback layer)
    # Corrections are platform/content_type scoped so "all" platform corrections apply everywhere
    corrections: list[dict] = []
    try:
        corrections_resp = (
            supabase.table("sku_corrections")
            .select("*")
            .eq("master_sku", canonical_master_sku)
            .in_("platform", [request.platform, "all"])
            .in_("content_type", [request.content_type, "all"])
            .eq("is_active", True)
            .execute()
        )
        corrections = corrections_resp.data or []
        if corrections:
            logger.info(
                "Loaded %s persistent corrections for %s/%s/%s",
                len(corrections),
                canonical_master_sku,
                request.platform,
                request.content_type,
            )
    except Exception as e:
        logger.warning("Failed to load corrections for %s: %s", canonical_master_sku, e)

    # Build session feedback from structured fields (FIX-01)
    feedback_parts: list[str] = []
    if request.tone_style:
        feedback_parts.append(f"Tone/style: {request.tone_style}")
    if request.emphasis:
        feedback_parts.append(f"Emphasize: {', '.join(request.emphasis)}")
    if request.length_preference:
        feedback_parts.append(f"Length: {request.length_preference}")
    if request.feedback:
        feedback_parts.append(request.feedback)
    session_feedback = "\n".join(feedback_parts) if feedback_parts else None

    finish_sentences: dict[str, str] | None = None
    system_prompt = ""
    user_prompt = ""
    regen_latency_ms = 0
    feedback_lines: list[str] = []
    if corrections:
        correction_lines = []
        for correction in corrections:
            text = (
                correction.get("correction_text")
                or correction.get("text")
                or correction.get("correction")
            )
            if text:
                correction_lines.append(f"- {text}")
        if correction_lines:
            feedback_lines.append("Persistent Corrections:\n" + "\n".join(correction_lines))
    if session_feedback:
        feedback_lines.append("Reviewer Feedback:\n" + session_feedback)

    selected_platforms: list[str] = [request.platform]
    include_finish = (
        request.content_type == "description" and request.platform in {"google", "bing"}
    )
    if include_finish:
        selected_platforms.append("finish")

    generated = await generate_per_platform(
        parent_sku=parent_sku,
        provider=provider,
        prompt_version="v2",
        feedback_by_platform={request.platform: "\n\n".join(feedback_lines)}
        if feedback_lines
        else None,
        selected_platforms=selected_platforms,
    )
    field_key = _content_field_key(request.platform, request.content_type)
    content = str(generated.get(field_key, "")).strip()
    if not content:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "regenerate_missing_required_platform_field",
                "message": (
                    f"Missing required regenerated field '{field_key}' for "
                    f"{request.platform}/{request.content_type}."
                ),
                "platform": request.platform,
                "content_type": request.content_type,
            },
        )
    prompt_hash = str(
        generated.get("prompt_hashes", {}).get(
            request.platform, get_platform_system_prompt_hash(request.platform)
        )
    )
    system_prompt = str(generated.get("system_prompts", {}).get(request.platform, ""))
    user_prompt = str(generated.get("user_prompts", {}).get(request.platform, ""))
    usage_by_platform = generated.get("usage_by_platform", {})
    latency_by_platform = generated.get("latency_by_platform", {})
    retry_by_platform = generated.get("retry_by_platform", {})
    parse_by_platform = generated.get("parse_by_platform", {})
    regen_latency_ms = int(
        latency_by_platform.get(request.platform, 0) or 0
    )
    total_tokens_used = 0
    estimated_cost_usd = 0.0
    has_cost_samples = False
    has_usage_samples = False
    provider_attempt_count = 0
    parse_retry_count = 0
    if isinstance(usage_by_platform, dict):
        for _platform_name, usage_snapshot in usage_by_platform.items():
            if not isinstance(usage_snapshot, dict):
                continue
            raw_prompt_tokens = usage_snapshot.get("prompt_tokens")
            raw_completion_tokens = usage_snapshot.get("completion_tokens")
            if raw_prompt_tokens is None or raw_completion_tokens is None:
                continue
            prompt_tokens = int(raw_prompt_tokens or 0)
            completion_tokens = int(raw_completion_tokens or 0)
            total_tokens_used += prompt_tokens + completion_tokens
            has_usage_samples = True
            usage_cost = _estimate_openai_cost_usd_from_usage(usage_snapshot)
            if usage_cost is not None:
                has_cost_samples = True
                estimated_cost_usd += usage_cost
    tokens_used_for_lineage = total_tokens_used if has_usage_samples else None
    if isinstance(retry_by_platform, dict):
        for platform_name in selected_platforms:
            snapshot = retry_by_platform.get(platform_name)
            if not isinstance(snapshot, dict):
                continue
            provider_attempt_count += _safe_int(snapshot.get("attempt_count"), 0)
            parse_retry_count += _safe_int(snapshot.get("json_decode_retries"), 0)
    if include_finish:
        raw_finish = generated.get("finish_sentences")
        if isinstance(raw_finish, dict):
            finish_sentences = raw_finish

    persistence = _persist_regeneration_result(
        supabase=supabase,
        master_sku=canonical_master_sku,
        platform=request.platform,
        content_type=request.content_type,
        content=content,
        generation_model=provider.name,
        prompt_hash=prompt_hash,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        feedback_text=request.feedback,
        mode="with_feedback" if request.feedback else "simple",
        tokens_used=tokens_used_for_lineage,
        cost_usd=round(estimated_cost_usd, 6) if has_cost_samples else None,
        generation_diagnostics={
            "selected_platforms": list(selected_platforms),
            "usage_by_platform": usage_by_platform if isinstance(usage_by_platform, dict) else {},
            "latency_by_platform": latency_by_platform if isinstance(latency_by_platform, dict) else {},
            "parse_by_platform": parse_by_platform if isinstance(parse_by_platform, dict) else {},
            "retry_by_platform": retry_by_platform if isinstance(retry_by_platform, dict) else {},
        },
        latency_ms=regen_latency_ms,
        provider_attempt_count=provider_attempt_count,
        parse_retry_count=parse_retry_count,
        request_id=request_id,
        idempotency_key=request_idempotency_key,
    )

    if finish_sentences and persistence["state"] == "completed":
        try:
            supabase.table("variant_finish_sentences").upsert(
                {
                    "master_sku": canonical_master_sku,
                    "platform": request.platform,
                    "finish_sentences": finish_sentences,
                },
                on_conflict="master_sku,platform",
            ).execute()
        except Exception as e:
            logger.warning(
                "Failed to persist finish sentences for %s/%s: %s",
                canonical_master_sku,
                request.platform,
                e,
            )

    # Persist correction if save_as_correction=True and there's session feedback (FIX-01)
    if request.save_as_correction and session_feedback:
        try:
            # Determine correction type from structured fields (priority order)
            if request.tone_style:
                correction_type = "tone"
            elif request.emphasis:
                correction_type = "emphasis"
            elif request.length_preference:
                correction_type = "length"
            else:
                correction_type = "free_text"

            supabase.table("sku_corrections").upsert(
                {
                    "master_sku": canonical_master_sku,
                    "platform": request.platform,
                    "content_type": request.content_type,
                    "correction_text": session_feedback,
                    "correction_type": correction_type,
                    "is_active": True,
                },
                on_conflict="master_sku,platform,content_type,correction_type,correction_text",
            ).execute()
            logger.info(
                "Saved persistent correction for %s/%s/%s (type=%s)",
                canonical_master_sku,
                request.platform,
                request.content_type,
                correction_type,
            )
        except Exception as e:
            logger.warning("Failed to save correction for %s: %s", canonical_master_sku, e)

    _emit_generation_summary(
        endpoint="regenerate",
        request_id=request_id,
        master_sku=canonical_master_sku,
        platform=request.platform,
        content_type=request.content_type,
        mode="with_feedback" if request.feedback else "simple",
        result_state=str(persistence.get("state", "completed")),
        tokens_used=tokens_used_for_lineage,
        cost_usd=round(estimated_cost_usd, 6) if has_cost_samples else None,
        latency_ms=regen_latency_ms,
        provider_attempt_count=provider_attempt_count,
        parse_retry_count=parse_retry_count,
    )

    return RegenerateResponse(
        success=True,
        master_sku=canonical_master_sku,
        content_type=request.content_type,
        platform=request.platform,
        content=content,
        finish_sentences=finish_sentences,
        used_feedback=session_feedback is not None,
        prompt_hash=prompt_hash,
        model=provider.name,
        generated_content_id=(
            str(persistence.get("generated_content_id"))
            if persistence.get("generated_content_id")
            else None
        ),
        version=int(persistence.get("version", 0) or 0),
        state=str(persistence.get("state", "completed")),
        idempotent=bool(persistence.get("idempotent", False)),
        request_id=request_id,
    )


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

    except HTTPException:
        _emit_generation_summary(
            endpoint="regenerate",
            request_id=request_id,
            master_sku=request.master_sku,
            platform=request.platform,
            content_type=request.content_type,
            mode="with_feedback" if request.feedback else "simple",
            result_state="failed",
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
            process_batch_job,
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
            process_hybrid_batch_job,
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
# Background Task for Batch Processing
# =============================================================================


async def process_batch_job(
    job_id: str,
    skus: list[str],
    num_candidates: int,
    dry_run: bool,
    options: dict | None = None,
):
    """Background task to process batch optimization.

    Updates Supabase tables as it progresses through SKUs.
    """
    from datetime import datetime, timezone

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
    request_id = get_request_id()
    lineage_request_id = request_id if request_id and request_id != "-" else None
    content_types = []
    if normalized_options["titles"]:
        content_types.append("title")
    if normalized_options["descriptions"]:
        content_types.append("description")

    for sku in skus:
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
            generated = await generate_per_platform(
                parent_sku=parent_sku,
                provider=provider,
                prompt_version="v2",
            )
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
                    platform_telemetry = _extract_platform_telemetry(
                        platform=platform,
                        usage_by_platform=usage_by_platform,
                        latency_by_platform=latencies,
                        retry_by_platform=retry_by_platform,
                    )
                    for content_type in content_types:
                        field_key = _content_field_key(platform, content_type)
                        content = str(generated.get(field_key, "")).strip()
                        include_platform_telemetry = content_type == primary_content_type
                        _persist_generated_content_and_history(
                            supabase=supabase,
                            master_sku=canonical_sku,
                            platform=platform,
                            content_type=content_type,
                            content=content,
                            generation_model=provider.name,
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

                finish_sentences = generated.get("finish_sentences", {})
                if isinstance(finish_sentences, dict):
                    for platform in ("google", "bing"):
                        if platform in platforms:
                            supabase.table("variant_finish_sentences").upsert(
                                {
                                    "master_sku": canonical_sku,
                                    "platform": platform,
                                    "finish_sentences": finish_sentences,
                                },
                                on_conflict="master_sku,platform",
                            ).execute()

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


async def process_hybrid_batch_job(
    job_id: str,
    families: list,
    single_skus: list[str],
    options: dict,
    requested_skus: list[str] | None = None,
):
    """Background task for hybrid multi-SKU generation.

    Processes:
    1. Single SKUs - full generation
    2. Multi-SKU families:
       - Base SKU - full generation
       - Variant SKUs - adaptation from base content
    """
    from datetime import datetime, timezone

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
    request_id = get_request_id()
    lineage_request_id = request_id if request_id and request_id != "-" else None
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

    # Helper function for v2 full per-platform generation.
    async def generate_full_content_v2(sku: str):
        """Generate and persist per-platform package for one SKU."""
        canonical_sku = resolve_canonical_master_sku(supabase, sku)
        parent_sku = load_parent_sku_from_supabase(canonical_sku)
        if not parent_sku:
            raise ValueError(f"SKU not found: {canonical_sku}")

        generated = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
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
                telemetry = _extract_platform_telemetry(
                    platform=platform,
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
                    generation_model=provider.name,
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
                    idempotency_key=options.get("idempotency_key"),
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
        finish_sentences = generated.get("finish_sentences", {})
        if isinstance(finish_sentences, dict):
            for platform in ("google", "bing"):
                if platform in platforms and "description" in content_types:
                    supabase.table("variant_finish_sentences").upsert(
                        {
                            "master_sku": canonical_sku,
                            "platform": platform,
                            "finish_sentences": finish_sentences,
                        },
                        on_conflict="master_sku,platform",
                    ).execute()

    try:
        # Process single SKUs (full generation)
        logger.info(f"Processing {len(single_skus)} single SKUs")
        for sku in single_skus:
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
                await generate_full_content_v2(sku)
                logger.info("✓ Generated %s via per-platform v2 package", sku)
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

        # Process multi-SKU families (hybrid approach)
        logger.info(f"Processing {len(families)} multi-SKU families")
        for family in families:
            logger.info(f"Processing family: {family.master_skus}")

            # Step 1: Generate base SKU (full generation)
            base_sku = family.base_sku

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
                await generate_full_content_v2(base_sku)
                logger.info("✓ Generated BASE %s via per-platform v2 package", base_sku)
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

            # Step 2: Variant SKUs
            for variant_sku in family.variant_skus:
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
                    await generate_full_content_v2(variant_sku)
                    logger.info(
                        "✓ Generated VARIANT %s via per-platform v2 package",
                        variant_sku,
                    )
                except Exception as e:
                    variant_sku_failed = True
                    variant_sku_error = str(e)
                    logger.error(
                        "✗ Failed VARIANT %s via per-platform v2 package: %s",
                        variant_sku,
                        e,
                    )
                    _emit_generation_summary(
                        endpoint="process_hybrid_batch_job",
                        request_id=request_id,
                        job_id=job_id,
                        master_sku=variant_sku,
                        platform=None,
                        content_type=None,
                        mode="full_generation_v2",
                        result_state="failed",
                    )

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

# Lazy-loaded scorer with initialization lock
_intent_scorer = None
_intent_scorer_lock = threading.Lock()


class ScoreIntentRequest(BaseModel):
    """Request body for /score-intent endpoint."""
    queries: list[str] = Field(..., min_length=1, max_length=500)
    include_details: bool = False


class ScoreIntentItem(BaseModel):
    """Single scored query result."""
    query: str
    feed_alignment_score: float
    attribute_score: float
    specificity_score: float
    matched_attributes: dict | None = None


class ScoreIntentResponse(BaseModel):
    """Response body for /score-intent endpoint."""
    scores: list[ScoreIntentItem]
    model_version: str = "v1.0"
    scored_at: str


def _get_intent_scorer():
    """Get or lazily initialize the IntentScorer singleton."""
    global _intent_scorer
    if _intent_scorer is not None:
        return _intent_scorer

    with _intent_scorer_lock:
        # Double-check after acquiring lock
        if _intent_scorer is not None:
            return _intent_scorer

        from feedops.scoring.intent_scorer import IntentScorer
        logger.info("Initializing IntentScorer (first request)...")
        _intent_scorer = IntentScorer.from_supabase()
        logger.info("IntentScorer ready")
        return _intent_scorer


@app.post("/score-intent", response_model=ScoreIntentResponse)
async def api_score_intent(request: ScoreIntentRequest):
    """Score search queries for feed alignment.

    Combines attribute extraction (finishes, collections, product types,
    dimensions, model numbers) with TF-IDF specificity scoring.

    Feed alignment = 0.60 * attribute_score + 0.40 * specificity_score
    """
    from datetime import datetime, timezone

    try:
        scorer = _get_intent_scorer()
        results = scorer.score_terms(
            request.queries, include_details=request.include_details
        )

        scores = []
        for r in results:
            item = ScoreIntentItem(
                query=r["query"],
                feed_alignment_score=r["feed_alignment_score"],
                attribute_score=r["attribute_score"],
                specificity_score=r["specificity_score"],
                matched_attributes=r.get("matched_attributes"),
            )
            scores.append(item)

        return ScoreIntentResponse(
            scores=scores,
            model_version="v1.0",
            scored_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        logger.error("Intent scoring failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Scoring error: {e}")
