"""Pydantic request/response models for FeedOps Pipeline API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


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


# =============================================================================
# ScoreIntent Models (score-intent endpoint)
# =============================================================================


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
