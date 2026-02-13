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
- POST /search-insights/sync - Sync search terms from Google Ads
- GET /search-insights/sync/{job_id} - Get search term sync status
- POST /backfill/start - Create and start a backfill job
- GET /backfill/status/{job_id} - Get backfill job progress
- POST /backfill/resume/{job_id} - Resume failed/partial job
- GET /backfill/jobs - List backfill jobs
"""

from __future__ import annotations

import asyncio
import logging
import os
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
    get_category_guidance,
    format_gold_standard_examples,
    get_finish_list,
)
from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.finish_sentence_validation import (
    normalize_and_validate_finish_sentences,
)
from feedops.pipeline.finish_sentence_placeholder import (
    build_fallback_finish_sentences,
    normalize_base_description_with_finish_placeholder,
    strip_hardcoded_finish_names,
    strip_generic_finish_count_claims,
)
from feedops.pipeline.prompts import build_category_guidance
from feedops.providers import get_provider
from feedops.api.multi_sku_detection import (
    detect_multi_sku_families,
    extract_spec_difference,
)
from feedops.api.hybrid_generation import adapt_variant_content
from feedops.api.sku_alias import (
    resolve_canonical_master_sku,
    resolve_canonical_master_skus,
)
from feedops.api.runtime_controls import (
    ensure_generation_enabled,
    finish_sentence_regeneration_enabled,
)
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

app = FastAPI(
    title="FeedOps Pipeline API",
    description="Content generation pipeline for Allied Brass products",
    version=API_VERSION,
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

# Include search insights router
from feedops.api.search_insights import router as search_insights_router
app.include_router(search_insights_router)

# Include performance baseline router
from feedops.api.performance_baseline import router as performance_baseline_router
app.include_router(performance_baseline_router)

# Import backfill endpoints
from feedops.api.backfill import (
    StartBackfillRequest,
    BackfillJobResponse,
    BackfillJobListResponse,
    start_backfill,
    get_backfill_status,
    resume_backfill,
    list_backfill_jobs,
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
) -> str:
    """Build a unified user prompt for all API generation paths.

    System prompt remains canonical in Python code. Supabase prompt template
    data is used only for examples and category guidance.
    """
    category_guidance = get_category_guidance(parent_sku.category)
    if not category_guidance:
        category_guidance = build_category_guidance(parent_sku.category)

    examples = format_gold_standard_examples(
        platform=platform,
        content_type=content_type,
        max_examples=3,
    )
    examples_section = (
        f"Gold Standard Examples (data-only guidance):\n{examples}\n"
        if examples
        else ""
    )

    context_lines: list[str] = []
    if platform in {"google", "bing"}:
        context_lines.append(
            "Entity context: variant listing copy (finish-aware when variant finish context is available)."
        )
        if finish_code:
            context_lines.append(
                f"Requested variant finish code: {finish_code}. Integrate this variant context naturally."
            )
        context_lines.append(
            "Use finish names from evidence data only; do not invent unsupported finish language."
        )
    else:
        context_lines.append(
            "Entity context: master SKU storefront copy (finish-agnostic base copy for Shopify)."
        )

    finish_list = ", ".join(get_finish_list())
    context_lines.append(
        "Canonical finish vocabulary reference (use only when supported by evidence): "
        f"{finish_list}."
    )
    context_section = "\n".join(context_lines)

    category_section = f"Category Guidance:\n{category_guidance}\n" if category_guidance else ""
    feedback_section = f"Reviewer Feedback:\n{feedback}\n" if feedback else ""

    return f"""\
Product Evidence Table:
{evidence_markdown}

Target platform: {platform}
Content type to generate: {content_type}

{context_section}
{category_section}
{examples_section}{feedback_section}Generate only the {content_type} for {platform}.
Return your response as JSON: {{"content": "your generated {content_type} here"}}
"""


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
):
    """Persist generated content and linked history in one canonical path."""
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

    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "new_content": content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:5000],
        "user_prompt": user_prompt[:5000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()


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
    finish_response = await _generate_with_metrics(
        endpoint=f"{endpoint}_finish_sentences",
        provider=provider,
        prompt=finish_prompt,
        schema=finish_schema,
        system_prompt=get_system_prompt(),
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
        prompt_hash = get_system_prompt_hash()
        system_prompt = get_system_prompt()

        results = []
        platforms = ["google", "bing", "shopify"]
        content_types = ["title", "description"]

        # Generate for each platform and content type
        for platform in platforms:
            for content_type in content_types:
                user_prompt = _build_generation_user_prompt(
                    parent_sku=parent_sku,
                    evidence_markdown=evidence_markdown,
                    platform=platform,
                    content_type=content_type,
                )
                simple_schema = {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                }

                response = await _generate_with_metrics(
                    endpoint="optimize_single_sku",
                    provider=provider,
                    prompt=user_prompt,
                    schema=simple_schema,
                    system_prompt=system_prompt,
                    platform=platform,
                    content_type=content_type,
                )

                content = response.get("content", "").strip()
                finish_sentences: dict[str, str] | None = None
                if content_type == "description" and platform in {"google", "bing"}:
                    content, finish_sentences = await _enforce_finish_sentence_parity(
                        provider=provider,
                        content=content,
                        master_sku=canonical_master_sku,
                        platform=platform,
                        endpoint="optimize_single_sku",
                    )
                results.append(f"{platform}/{content_type}: {content[:100]}...")

                if not request.dry_run:
                    _persist_generated_content_and_history(
                        supabase=supabase,
                        master_sku=canonical_master_sku,
                        platform=platform,
                        content_type=content_type,
                        content=content,
                        generation_model=provider.name,
                        prompt_hash=prompt_hash,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        mode="full_generation",
                    )
                    if finish_sentences:
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


@app.post("/regenerate", response_model=RegenerateResponse, tags=["Generation"])
async def regenerate_content(request: RegenerateRequest):
    """Regenerate specific content with optional human feedback.

    Uses the Python pipeline's comprehensive prompts and evidence building
    for high-quality content generation.
    """
    try:
        ensure_generation_enabled(operation="regenerate_content")
        supabase = get_client()
        canonical_master_sku = resolve_canonical_master_sku(
            supabase, request.master_sku
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
        )

        # Load product data from Supabase
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

        prompt_hash = get_system_prompt_hash()

        # Build user prompt
        user_prompt = _build_generation_user_prompt(
            parent_sku=parent_sku,
            evidence_markdown=evidence_markdown,
            platform=request.platform,
            content_type=request.content_type,
            feedback=request.feedback,
            finish_code=request.finish_code,
        )
        simple_schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }

        response = await _generate_with_metrics(
            endpoint="regenerate",
            provider=provider,
            prompt=user_prompt,
            schema=simple_schema,
            system_prompt=get_system_prompt(),
            platform=request.platform,
            content_type=request.content_type,
        )

        content = response.get("content", "").strip()
        finish_sentences: dict[str, str] | None = None

        if request.content_type == "description" and request.platform in {"google", "bing"}:
            content, finish_sentences = await _enforce_finish_sentence_parity(
                provider=provider,
                content=content,
                master_sku=canonical_master_sku,
                platform=request.platform,
                endpoint="regenerate",
            )

        # Save to regeneration_history
        try:
            system_prompt = get_system_prompt()
            supabase.table("generated_content").upsert(
                {
                    "master_sku": canonical_master_sku,
                    "platform": request.platform,
                    "content_type": request.content_type,
                    "candidate_content": content,
                    "generation_model": provider.name,
                    "generation_prompt_hash": prompt_hash,
                },
                on_conflict="master_sku,platform,content_type",
            ).execute()
            generated_content_id = _lookup_generated_content_id(
                supabase=supabase,
                master_sku=canonical_master_sku,
                platform=request.platform,
                content_type=request.content_type,
            )

            supabase.table("regeneration_history").insert(
                {
                    "master_sku": canonical_master_sku,
                    "content_type": request.content_type,
                    "platform": request.platform,
                    "mode": "with_feedback" if request.feedback else "simple",
                    "feedback_text": request.feedback,
                    "new_content": content,
                    "model_version": provider.name,
                    "system_prompt": system_prompt[:5000],  # Truncate for DB
                    "user_prompt": user_prompt[:5000],
                    "prompt_hash": prompt_hash,
                    "generated_content_id": generated_content_id,
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to log regeneration history: {e}")

        if finish_sentences:
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

        return RegenerateResponse(
            success=True,
            master_sku=canonical_master_sku,
            content_type=request.content_type,
            platform=request.platform,
            content=content,
            finish_sentences=finish_sentences,
            used_feedback=request.feedback is not None,
            prompt_hash=prompt_hash,
            model=provider.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        options = request.options
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
                        "expanded_total_skus": expanded_total_skus,
                        "expanded_completed_skus": 0,
                        "expanded_failed_skus": 0,
                    },
                }
            )
            .execute()
        )

        job_id = job_result.data[0]["id"]

        # Calculate strategy counts
        total_variants = sum(len(f.variant_skus) for f in families)
        base_skus_count = len(families) + len(single_skus)

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
    content_types = []
    if normalized_options["titles"]:
        content_types.append("title")
    if normalized_options["descriptions"]:
        content_types.append("description")

    for sku in skus:
        try:
            canonical_sku = resolve_canonical_master_sku(supabase, sku)
            # Update SKU status
            supabase.table("batch_generation_job_skus").update(
                {
                    "status": "processing",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("job_id", job_id).eq("master_sku", sku).execute()

            # Load and generate for this SKU
            parent_sku = load_parent_sku_from_supabase(canonical_sku)
            if not parent_sku:
                raise ValueError(f"SKU not found: {canonical_sku}")

            # Build evidence and generate content
            evidence = build_evidence_table(parent_sku)
            evidence_markdown = format_evidence_markdown(evidence)

            provider = get_provider()
            prompt_hash = get_system_prompt_hash()
            system_prompt = get_system_prompt()

            # Generate for each platform
            for platform in platforms:
                for content_type in content_types:
                    user_prompt = _build_generation_user_prompt(
                        parent_sku=parent_sku,
                        evidence_markdown=evidence_markdown,
                        platform=platform,
                        content_type=content_type,
                    )
                    simple_schema = {
                        "type": "object",
                        "properties": {"content": {"type": "string"}},
                        "required": ["content"],
                    }

                    response = await _generate_with_metrics(
                        endpoint="process_batch_job",
                        provider=provider,
                        prompt=user_prompt,
                        schema=simple_schema,
                        system_prompt=system_prompt,
                        platform=platform,
                        content_type=content_type,
                    )

                    content = response.get("content", "").strip()
                    finish_sentences: dict[str, str] | None = None
                    if content_type == "description" and platform in {"google", "bing"}:
                        content, finish_sentences = await _enforce_finish_sentence_parity(
                            provider=provider,
                            content=content,
                            master_sku=canonical_sku,
                            platform=platform,
                            endpoint="process_batch_job",
                        )

                    if not dry_run:
                        _persist_generated_content_and_history(
                            supabase=supabase,
                            master_sku=canonical_sku,
                            platform=platform,
                            content_type=content_type,
                            content=content,
                            generation_model=provider.name,
                            prompt_hash=prompt_hash,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            mode="full_generation",
                        )
                        if finish_sentences:
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
            supabase.table("batch_generation_job_skus").update(
                {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("job_id", job_id).eq("master_sku", sku).execute()

        except Exception as e:
            failed += 1
            logger.error(f"Batch SKU {sku} failed: {e}")

            # Update SKU as failed
            supabase.table("batch_generation_job_skus").update(
                {
                    "status": "failed",
                    "error_message": str(e)[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("job_id", job_id).eq("master_sku", sku).execute()

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
    content_types = []
    if options.get("titles"):
        content_types.append("title")
    if options.get("descriptions"):
        content_types.append("description")

    provider = get_provider()
    prompt_hash = get_system_prompt_hash()
    system_prompt = get_system_prompt()

    def _build_job_options() -> dict:
        return {
            "titles": options.get("titles", True),
            "descriptions": options.get("descriptions", True),
            "platforms": platforms,
            "hybrid": True,
            "expanded_total_skus": expanded_total,
            "expanded_completed_skus": expanded_completed,
            "expanded_failed_skus": expanded_failed,
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

    # Helper function for full generation
    async def generate_full_content(sku: str, platform: str, content_type: str):
        """Generate content using full pipeline."""
        canonical_sku = resolve_canonical_master_sku(supabase, sku)
        parent_sku = load_parent_sku_from_supabase(canonical_sku)
        if not parent_sku:
            raise ValueError(f"SKU not found: {canonical_sku}")

        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        user_prompt = _build_generation_user_prompt(
            parent_sku=parent_sku,
            evidence_markdown=evidence_markdown,
            platform=platform,
            content_type=content_type,
        )
        simple_schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }

        response = await _generate_with_metrics(
            endpoint="process_hybrid_batch_job",
            provider=provider,
            prompt=user_prompt,
            schema=simple_schema,
            system_prompt=system_prompt,
            platform=platform,
            content_type=content_type,
        )

        content = response.get("content", "").strip()
        finish_sentences: dict[str, str] | None = None
        if content_type == "description" and platform in {"google", "bing"}:
            content, finish_sentences = await _enforce_finish_sentence_parity(
                provider=provider,
                content=content,
                master_sku=canonical_sku,
                platform=platform,
                endpoint="process_hybrid_batch_job",
            )

        _persist_generated_content_and_history(
            supabase=supabase,
            master_sku=canonical_sku,
            platform=platform,
            content_type=content_type,
            content=content,
            generation_model=provider.name,
            prompt_hash=prompt_hash,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            mode="full_generation",
        )
        if finish_sentences:
            supabase.table("variant_finish_sentences").upsert(
                {
                    "master_sku": canonical_sku,
                    "platform": platform,
                    "finish_sentences": finish_sentences,
                },
                on_conflict="master_sku,platform",
            ).execute()

        return content

    try:
        # Process single SKUs (full generation)
        logger.info(f"Processing {len(single_skus)} single SKUs")
        for sku in single_skus:
            sku_failed = False
            for platform in platforms:
                for content_type in content_types:
                    try:
                        await generate_full_content(sku, platform, content_type)
                        logger.info(
                            f"✓ Generated {sku} / {platform} / {content_type}"
                        )
                    except Exception as e:
                        sku_failed = True
                        logger.error(
                            f"✗ Failed {sku} / {platform} / {content_type}: {e}"
                        )

            _record_sku_result(sku, success=not sku_failed)
            _update_job_progress()

        # Process multi-SKU families (hybrid approach)
        logger.info(f"Processing {len(families)} multi-SKU families")
        for family in families:
            logger.info(f"Processing family: {family.master_skus}")

            # Step 1: Generate base SKU (full generation)
            base_sku = family.base_sku

            base_sku_failed = False
            for platform in platforms:
                for content_type in content_types:
                    try:
                        await generate_full_content(base_sku, platform, content_type)
                        logger.info(
                            f"✓ Generated BASE {base_sku} / {platform} / {content_type}"
                        )
                    except Exception as e:
                        base_sku_failed = True
                        logger.error(
                            f"✗ Failed BASE {base_sku} / {platform} / {content_type}: {e}"
                        )

            _record_sku_result(base_sku, success=not base_sku_failed)
            _update_job_progress()

            # Step 2: Adapt variant SKUs
            for variant_sku in family.variant_skus:
                base_spec, variant_spec = extract_spec_difference(
                    base_sku, variant_sku
                )
                variant_sku_failed = False

                for platform in platforms:
                    for content_type in content_types:
                        try:
                            result = await adapt_variant_content(
                                supabase,
                                base_sku,
                                variant_sku,
                                platform,
                                content_type,
                                base_spec,
                                variant_spec,
                            )

                            if result["success"]:
                                logger.info(
                                    f"✓ Adapted VARIANT {variant_sku} / {platform} / {content_type} (from {base_sku})"
                                )
                            else:
                                variant_sku_failed = True
                                logger.error(
                                    f"✗ Failed VARIANT {variant_sku} / {platform} / {content_type}: {result.get('error')}"
                                )
                        except Exception as e:
                            variant_sku_failed = True
                            logger.error(
                                f"✗ Exception for VARIANT {variant_sku} / {platform} / {content_type}: {e}"
                            )

                _record_sku_result(variant_sku, success=not variant_sku_failed)
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

    except Exception as e:
        logger.error(f"Hybrid generation processing error: {e}")
        _update_job_progress(
            status="failed",
            completed_at=datetime.now(timezone.utc).isoformat(),
            error_message=str(e),
            enforce_invariant=False,
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
