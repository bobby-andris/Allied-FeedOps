"""Candidate model for platform-specific optimized content."""
from pydantic import BaseModel, field_validator
from feedops.models.claim import Claim
from feedops.models.score import Score


class Candidate(BaseModel):
    """An optimized candidate with platform-specific outputs."""

    # Google Shopping
    google_title: str
    """Google Shopping title (max 150 chars)."""

    google_short_title: str
    """Google short title for overlays (max 70 chars)."""

    google_description: str
    """Google Shopping description (min 500 chars recommended)."""

    # Bing/Microsoft Shopping
    bing_title: str
    """Bing Shopping title (max 150 chars)."""

    bing_description: str
    """Bing Shopping description (min 500 chars recommended)."""

    # Shopify
    shopify_title: str
    """Shopify product title (max 255 chars)."""

    shopify_description: str
    """Shopify HTML description."""

    claims: list[Claim]
    """List of factual claims with source attribution."""

    self_score: Score
    """LLM's self-assessment against the rubric."""

    verified_score: Score | None = None
    """Score after claim verification (may differ from self_score)."""

    heuristic_score: float | None = None
    """Heuristic selection score (weighted composite)."""

    heuristic_score_breakdown: dict[str, float] | None = None
    """Per-platform heuristic composite scores."""

    selection_score_adjusted: float | None = None
    """Adjusted selection score after soft-gate penalties."""

    selection_weights: dict[str, float] | None = None
    """Weights used when selecting the candidate."""

    soft_gate_penalty: float | None = None
    """Soft-gate penalty applied during selection."""

    soft_gate_warnings: list[str] | None = None
    """Soft-gate warning messages for structural misses."""

    soft_gate_miss_counts: dict[str, int] | None = None
    """Per-platform soft-gate miss counts."""

    candidate_index: int | None = None
    """Index of this candidate in the generation batch."""

    num_candidates: int | None = None
    """Total number of candidates generated for selection."""

    @field_validator("google_title")
    @classmethod
    def validate_google_title_length(cls, v: str) -> str:
        """Google title must be <= 150 characters."""
        if len(v) > 150:
            raise ValueError("Google title must be <= 150 characters")
        return v

    @field_validator("bing_title")
    @classmethod
    def validate_bing_title_length(cls, v: str) -> str:
        """Bing title must be <= 150 characters."""
        if len(v) > 150:
            raise ValueError("Bing title must be <= 150 characters")
        return v

    @field_validator("google_short_title")
    @classmethod
    def validate_google_short_title_length(cls, v: str) -> str:
        """Google short title must be <= 70 characters."""
        if len(v) > 70:
            raise ValueError("Google short title must be <= 70 characters")
        return v

    @field_validator("shopify_title")
    @classmethod
    def validate_shopify_title_length(cls, v: str) -> str:
        """Shopify title must be <= 255 characters."""
        if len(v) > 255:
            raise ValueError("Shopify title must be <= 255 characters")
        return v

    @property
    def verified_claims(self) -> list[Claim]:
        """Return only verified claims."""
        return [c for c in self.claims if c.verified]

    @property
    def rejected_claims(self) -> list[Claim]:
        """Return rejected claims."""
        return [c for c in self.claims if not c.verified and c.rejection_reason]

    @property
    def final_score(self) -> Score:
        """Return verified_score if available, else self_score."""
        return self.verified_score or self.self_score
