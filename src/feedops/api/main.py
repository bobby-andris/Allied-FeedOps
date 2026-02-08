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
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from feedops.api.supabase_loader import (
    get_product_catalog_count,
    load_parent_sku_from_supabase,
)
from feedops.api.prompt_loader import (
    get_system_prompt,
    get_category_guidance,
    format_gold_standard_examples,
    get_finish_list,
)
from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.providers import get_provider
from feedops.api.multi_sku_detection import (
    detect_multi_sku_families,
    extract_spec_difference,
)
from feedops.api.hybrid_generation import adapt_variant_content

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

# Include search insights router
from feedops.api.search_insights import router as search_insights_router
app.include_router(search_insights_router)

# Include performance baseline router
from feedops.api.performance_baseline import router as performance_baseline_router
app.include_router(performance_baseline_router)


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
    used_feedback: bool
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
    skus: list[dict]


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
        logger.info(f"Optimizing SKU: {request.master_sku}")

        # Load from Supabase
        parent_sku = load_parent_sku_from_supabase(request.master_sku)
        if not parent_sku:
            raise HTTPException(
                status_code=404, detail=f"SKU not found: {request.master_sku}"
            )

        # Build evidence table
        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        # Get LLM provider
        provider = get_provider()
        supabase = get_client()

        results = []
        platforms = ["google", "bing", "shopify"]
        content_types = ["title", "description"]

        # Generate for each platform and content type
        for platform in platforms:
            for content_type in content_types:
                user_prompt = f"""
Product Evidence Table:
{evidence_markdown}

Target platform: {platform}
Content type to generate: {content_type}

Generate only the {content_type} for {platform}.
Return your response as JSON: {{"content": "your generated {content_type} here"}}
"""
                simple_schema = {
                    "type": "object",
                    "properties": {"content": {"type": "string"}},
                    "required": ["content"],
                }

                response = await provider.generate(
                    prompt=user_prompt,
                    schema=simple_schema,
                    system_prompt=get_system_prompt(),
                )

                content = response.get("content", "").strip()
                results.append(f"{platform}/{content_type}: {content[:100]}...")

                if not request.dry_run:
                    # Save to generated_content table
                    supabase.table("generated_content").upsert(
                        {
                            "master_sku": request.master_sku,
                            "platform": platform,
                            "content_type": content_type,
                            "candidate_content": content,
                            "generation_model": provider.name,
                        },
                        on_conflict="master_sku,platform,content_type",
                    ).execute()

        return OptimizeResponse(
            success=True,
            master_sku=request.master_sku,
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
        logger.info(
            f"Regenerating {request.content_type} for SKU: {request.master_sku}"
        )

        # Load product data from Supabase
        parent_sku = load_parent_sku_from_supabase(request.master_sku)
        if not parent_sku:
            raise HTTPException(
                status_code=404, detail=f"SKU not found: {request.master_sku}"
            )

        # Build evidence table
        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        # Get LLM provider
        provider = get_provider()

        # Build user prompt
        user_prompt = f"""
Product Evidence Table:
{evidence_markdown}

Target platform: {request.platform}
Content type to generate: {request.content_type}

{"FEEDBACK FROM REVIEWER:" + chr(10) + request.feedback if request.feedback else ""}

Generate only the {request.content_type} for {request.platform}.
{"Include the finish '" + request.finish_code + "' in the content." if request.finish_code else ""}
Return your response as JSON: {{"content": "your generated {request.content_type} here"}}
"""
        simple_schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }

        response = await provider.generate(
            prompt=user_prompt,
            schema=simple_schema,
            system_prompt=get_system_prompt(),
        )

        content = response.get("content", "").strip()

        # Save to regeneration_history
        try:
            supabase = get_client()
            system_prompt = get_system_prompt()
            prompt_hash = hashlib.sha256(
                (system_prompt + user_prompt).encode()
            ).hexdigest()[:16]

            supabase.table("regeneration_history").insert(
                {
                    "master_sku": request.master_sku,
                    "content_type": request.content_type,
                    "platform": request.platform,
                    "mode": "with_feedback" if request.feedback else "simple",
                    "feedback_text": request.feedback,
                    "new_content": content,
                    "model_version": provider.name,
                    "system_prompt": system_prompt[:5000],  # Truncate for DB
                    "user_prompt": user_prompt[:5000],
                    "prompt_hash": prompt_hash,
                }
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to log regeneration history: {e}")

        return RegenerateResponse(
            success=True,
            master_sku=request.master_sku,
            content_type=request.content_type,
            platform=request.platform,
            content=content,
            used_feedback=request.feedback is not None,
            model=provider.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regeneration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Batch Optimization
# =============================================================================


@app.post("/batch-optimize", response_model=BatchJobResponse, tags=["Generation"])
async def batch_optimize(
    request: BatchOptimizeRequest, background_tasks: BackgroundTasks
):
    """Queue batch optimization job for multiple SKUs.

    Creates a job record in Supabase and processes SKUs in the background.
    Use GET /batch-status/{job_id} to check progress.
    """
    try:
        supabase = get_client()

        # Create job in Supabase (using existing table from migration 006)
        job_result = (
            supabase.table("batch_generation_jobs")
            .insert(
                {
                    "status": "queued",
                    "total_skus": len(request.skus),
                    "completed_skus": 0,
                    "failed_skus": 0,
                    "options": {
                        "num_candidates": request.num_candidates,
                        "dry_run": request.dry_run,
                    },
                }
            )
            .execute()
        )

        job_id = job_result.data[0]["id"]

        # Create individual SKU records
        sku_records = [
            {"job_id": job_id, "master_sku": sku, "status": "pending"}
            for sku in request.skus
        ]
        supabase.table("batch_generation_job_skus").insert(sku_records).execute()

        # Queue background processing
        background_tasks.add_task(
            process_batch_job,
            job_id=job_id,
            skus=request.skus,
            num_candidates=request.num_candidates,
            dry_run=request.dry_run,
        )

        return BatchJobResponse(
            success=True,
            job_id=str(job_id),
            status="queued",
            total_skus=len(request.skus),
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
async def hybrid_generate(
    request: HybridGenerateRequest, background_tasks: BackgroundTasks
):
    """Generate content for multi-SKU families using hybrid approach.

    Detects multi-SKU product families (multiple master_skus sharing same product_id)
    and uses hybrid generation:
    - Base SKU: Full content generation
    - Variant SKUs: Adaptation from base content (60% cost savings)

    Creates a job record and processes in background without timeout limits.
    """
    try:
        supabase = get_client()

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
            f"Hybrid generation requested for {len(request.skus)} SKUs: {request.skus}"
        )

        # Detect multi-SKU families
        families = detect_multi_sku_families(supabase, request.skus)

        # Get single SKUs (not in any family)
        family_skus = set()
        for family in families:
            family_skus.update(family.master_skus)
        single_skus = [sku for sku in request.skus if sku not in family_skus]

        logger.info(
            f"Detected {len(families)} multi-SKU families and {len(single_skus)} single SKUs"
        )

        # Create job record
        job_result = (
            supabase.table("batch_generation_jobs")
            .insert(
                {
                    "status": "queued",
                    "total_skus": len(request.skus),
                    "completed_skus": 0,
                    "failed_skus": 0,
                    "options": {
                        "titles": options.get("titles", True),
                        "descriptions": options.get("descriptions", True),
                        "platforms": platforms,
                        "hybrid": True,
                    },
                }
            )
            .execute()
        )

        job_id = job_result.data[0]["id"]

        # Calculate strategy counts
        total_variants = sum(len(f.variant_skus) for f in families)
        base_skus_count = len(families) + len(single_skus)

        # Queue background processing
        background_tasks.add_task(
            process_hybrid_batch_job,
            job_id=job_id,
            families=families,
            single_skus=single_skus,
            options=options,
        )

        return HybridJobResponse(
            success=True,
            job_id=str(job_id),
            status="queued",
            total_skus=len(request.skus),
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
):
    """Background task to process batch optimization.

    Updates Supabase tables as it progresses through SKUs.
    """
    from datetime import datetime, timezone

    supabase = get_client()

    # Update job status to processing
    supabase.table("batch_generation_jobs").update(
        {"status": "processing", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).execute()

    completed = 0
    failed = 0

    for sku in skus:
        try:
            # Update SKU status
            supabase.table("batch_generation_job_skus").update(
                {
                    "status": "processing",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                }
            ).eq("job_id", job_id).eq("master_sku", sku).execute()

            # Load and generate for this SKU
            parent_sku = load_parent_sku_from_supabase(sku)
            if not parent_sku:
                raise ValueError(f"SKU not found: {sku}")

            # Build evidence and generate content
            evidence = build_evidence_table(parent_sku)
            evidence_markdown = format_evidence_markdown(evidence)

            provider = get_provider()

            # Generate for each platform
            for platform in ["google", "bing", "shopify"]:
                for content_type in ["title", "description"]:
                    user_prompt = f"""
Product Evidence Table:
{evidence_markdown}

Target platform: {platform}
Content type to generate: {content_type}

Generate only the {content_type} for {platform}.
Return your response as JSON: {{"content": "your generated {content_type} here"}}
"""
                    simple_schema = {
                        "type": "object",
                        "properties": {"content": {"type": "string"}},
                        "required": ["content"],
                    }

                    response = await provider.generate(
                        prompt=user_prompt,
                        schema=simple_schema,
                        system_prompt=get_system_prompt(),
                    )

                    content = response.get("content", "").strip()

                    if not dry_run:
                        # Save to generated_content
                        supabase.table("generated_content").upsert(
                            {
                                "master_sku": sku,
                                "platform": platform,
                                "content_type": content_type,
                                "candidate_content": content,
                                "generation_model": provider.name,
                            },
                            on_conflict="master_sku,platform,content_type",
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

    # Mark job complete
    final_status = "completed" if failed == 0 else "partial" if completed > 0 else "failed"
    supabase.table("batch_generation_jobs").update(
        {
            "status": final_status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", job_id).execute()

    logger.info(f"Batch job {job_id} finished: {completed} completed, {failed} failed")


async def process_hybrid_batch_job(
    job_id: str,
    families: list,
    single_skus: list[str],
    options: dict,
):
    """Background task for hybrid multi-SKU generation.

    Processes:
    1. Single SKUs - full generation
    2. Multi-SKU families:
       - Base SKU - full generation
       - Variant SKUs - adaptation from base content
    """
    from datetime import datetime, timezone

    supabase = get_client()

    # Update job status to processing
    supabase.table("batch_generation_jobs").update(
        {"status": "processing", "started_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", job_id).execute()

    completed = 0
    failed = 0

    platforms = options.get("platforms", ["google", "bing", "shopify"])
    content_types = []
    if options.get("titles"):
        content_types.append("title")
    if options.get("descriptions"):
        content_types.append("description")

    provider = get_provider()

    # Helper function for full generation
    async def generate_full_content(sku: str, platform: str, content_type: str):
        """Generate content using full pipeline."""
        parent_sku = load_parent_sku_from_supabase(sku)
        if not parent_sku:
            raise ValueError(f"SKU not found: {sku}")

        evidence = build_evidence_table(parent_sku)
        evidence_markdown = format_evidence_markdown(evidence)

        user_prompt = f"""
Product Evidence Table:
{evidence_markdown}

Target platform: {platform}
Content type to generate: {content_type}

Generate only the {content_type} for {platform}.
Return your response as JSON: {{"content": "your generated {content_type} here"}}
"""
        simple_schema = {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        }

        response = await provider.generate(
            prompt=user_prompt,
            schema=simple_schema,
            system_prompt=get_system_prompt(),
        )

        content = response.get("content", "").strip()

        # Save to generated_content
        supabase.table("generated_content").upsert(
            {
                "master_sku": sku,
                "platform": platform,
                "content_type": content_type,
                "candidate_content": content,
                "generation_model": provider.name,
            },
            on_conflict="master_sku,platform,content_type",
        ).execute()

        return content

    try:
        # Process single SKUs (full generation)
        logger.info(f"Processing {len(single_skus)} single SKUs")
        for sku in single_skus:
            for platform in platforms:
                for content_type in content_types:
                    try:
                        await generate_full_content(sku, platform, content_type)
                        completed += 1
                        logger.info(
                            f"✓ Generated {sku} / {platform} / {content_type}"
                        )
                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"✗ Failed {sku} / {platform} / {content_type}: {e}"
                        )

            # Update progress every SKU
            supabase.table("batch_generation_jobs").update(
                {"completed_skus": completed, "failed_skus": failed}
            ).eq("id", job_id).execute()

        # Process multi-SKU families (hybrid approach)
        logger.info(f"Processing {len(families)} multi-SKU families")
        for family in families:
            logger.info(f"Processing family: {family.master_skus}")

            # Step 1: Generate base SKU (full generation)
            base_sku = family.base_sku

            for platform in platforms:
                for content_type in content_types:
                    try:
                        await generate_full_content(base_sku, platform, content_type)
                        completed += 1
                        logger.info(
                            f"✓ Generated BASE {base_sku} / {platform} / {content_type}"
                        )
                    except Exception as e:
                        failed += 1
                        logger.error(
                            f"✗ Failed BASE {base_sku} / {platform} / {content_type}: {e}"
                        )

            # Update progress after base SKU
            supabase.table("batch_generation_jobs").update(
                {"completed_skus": completed, "failed_skus": failed}
            ).eq("id", job_id).execute()

            # Step 2: Adapt variant SKUs
            for variant_sku in family.variant_skus:
                base_spec, variant_spec = extract_spec_difference(
                    base_sku, variant_sku
                )

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
                                completed += 1
                                logger.info(
                                    f"✓ Adapted VARIANT {variant_sku} / {platform} / {content_type} (from {base_sku})"
                                )
                            else:
                                failed += 1
                                logger.error(
                                    f"✗ Failed VARIANT {variant_sku} / {platform} / {content_type}: {result.get('error')}"
                                )
                        except Exception as e:
                            failed += 1
                            logger.error(
                                f"✗ Exception for VARIANT {variant_sku} / {platform} / {content_type}: {e}"
                            )

                # Update progress after each variant SKU
                supabase.table("batch_generation_jobs").update(
                    {"completed_skus": completed, "failed_skus": failed}
                ).eq("id", job_id).execute()

        # Mark job complete
        final_status = (
            "completed" if failed == 0 else "partial" if completed > 0 else "failed"
        )
        supabase.table("batch_generation_jobs").update(
            {
                "status": final_status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", job_id).execute()

        logger.info(
            f"✓ Hybrid generation job {job_id} finished: {completed} completed, {failed} failed"
        )

    except Exception as e:
        logger.error(f"Hybrid generation processing error: {e}")

        supabase.table("batch_generation_jobs").update(
            {
                "status": "failed",
                "completed_skus": completed,
                "failed_skus": failed,
                "error_message": str(e)[:500],
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", job_id).execute()
