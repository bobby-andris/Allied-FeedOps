"""Pydantic validation models for data collection workers.

This module provides validation models that enforce data quality at write time,
preventing invalid data (out-of-range CTR, clicks > impressions, empty queries)
from reaching the database.

Validation Rules:
- VALID-05: Non-empty strings, non-negative numeric values
- VALID-06: CTR 0-1, clicks <= impressions
- VALID-09: End date after start date

Used by: src/feedops/jobs/workers.py (pre-write validation)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any


# =============================================================================
# Validation Thresholds
# =============================================================================

VALIDATION_THRESHOLDS = {
    "baseline_freshness_days": 60,
    "search_terms_freshness_days": 7,
    "keyword_cache_ttl_days": 30,
    "job_success_threshold": 0.95,
    "baseline_contamination_days": 30,  # SKUs published within this window are ineligible
}


# =============================================================================
# Performance Metrics Validation
# =============================================================================


class ValidatedPerformanceMetrics(BaseModel):
    """Validates performance metrics before database writes.

    Enforces:
    - VALID-05: Non-negative numeric values
    - VALID-06: CTR in range 0-1, clicks <= impressions
    - VALID-09: End date after start date

    Used by: collect_performance_batch() in workers.py
    """

    model_config = ConfigDict(strict=False)  # Allow type coercion from API responses

    master_sku: str = Field(..., min_length=1, max_length=50)
    platform: str = Field(..., pattern=r"^(google|bing)$")
    avg_impressions: float = Field(..., ge=0.0)
    avg_clicks: float = Field(..., ge=0.0)
    avg_ctr: float = Field(..., ge=0.0, le=1.0)
    avg_conversions: float = Field(..., ge=0.0)
    avg_conversion_value: float = Field(..., ge=0.0)
    avg_cvr: float = Field(..., ge=0.0, le=1.0)
    avg_cost: float = Field(..., ge=0.0)
    avg_roas: float = Field(..., ge=0.0)
    baseline_start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    baseline_end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    metadata: dict[str, Any] = Field(default_factory=lambda: {"is_multi_sku_family": False})

    @field_validator("avg_clicks")
    @classmethod
    def clicks_lte_impressions(cls, v: float, info: Any) -> float:
        """Validate that clicks <= impressions (VALID-06)."""
        if "avg_impressions" in info.data:
            avg_impressions = info.data["avg_impressions"]
            if v > avg_impressions:
                raise ValueError(
                    f"avg_clicks ({v}) cannot exceed avg_impressions ({avg_impressions})"
                )
        return v

    @field_validator("baseline_end_date")
    @classmethod
    def end_date_after_start(cls, v: str, info: Any) -> str:
        """Validate that end_date > start_date (VALID-09)."""
        if "baseline_start_date" in info.data:
            start_date = info.data["baseline_start_date"]
            if v <= start_date:
                raise ValueError(
                    f"baseline_end_date ({v}) must be after baseline_start_date ({start_date})"
                )
        return v


# =============================================================================
# Search Terms Validation
# =============================================================================


class ValidatedSearchTerm(BaseModel):
    """Validates search term data before database writes.

    Enforces:
    - VALID-05: Non-empty query text, non-negative clicks/impressions
    - VALID-06: clicks <= impressions

    Used by: collect_search_terms_batch() in workers.py
    """

    model_config = ConfigDict(strict=False)

    query_text: str = Field(..., min_length=1)
    master_sku: str = Field(..., min_length=1)
    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)

    @field_validator("clicks")
    @classmethod
    def clicks_lte_impressions(cls, v: int, info: Any) -> int:
        """Validate that clicks <= impressions (VALID-06)."""
        if "impressions" in info.data:
            impressions = info.data["impressions"]
            if v > impressions:
                raise ValueError(
                    f"clicks ({v}) cannot exceed impressions ({impressions})"
                )
        return v


# =============================================================================
# Keyword Planner Validation
# =============================================================================


class ValidatedKeywordMetrics(BaseModel):
    """Validates Keyword Planner metrics before database writes.

    Enforces:
    - VALID-05: Non-empty keyword, valid competition values, 0-100 competition_index

    Used by: collect_keyword_planner_batch() in workers.py
    """

    model_config = ConfigDict(strict=False)

    keyword: str = Field(..., min_length=1)
    avg_monthly_searches: int | None = Field(None, ge=0)
    competition: str | None = Field(None, pattern=r"^(LOW|MEDIUM|HIGH|UNSPECIFIED)$")
    competition_index: int | None = Field(None, ge=0, le=100)


# =============================================================================
# Custom Labels Validation
# =============================================================================


class ValidatedCustomLabels(BaseModel):
    """Validates custom labels before database writes.

    Enforces:
    - VALID-05: Non-empty gmc_offer_id

    Used by: collect_custom_labels_batch() in workers.py
    """

    model_config = ConfigDict(strict=False)

    gmc_offer_id: str = Field(..., min_length=1)
    custom_labels: dict[str, str | None] = Field(default_factory=dict)
