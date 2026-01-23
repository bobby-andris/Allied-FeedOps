"""Candidate model for optimized title/description."""
from pydantic import BaseModel, field_validator
from feedops.models.claim import Claim
from feedops.models.score import Score


class Candidate(BaseModel):
    """An optimized title/description candidate.

    Constraints:
    - title: max 150 characters
    - description: min 500 characters recommended
    """

    title: str
    """Optimized product title (max 150 chars)."""

    description: str
    """Optimized product description (min 500 chars recommended)."""

    claims: list[Claim]
    """List of factual claims with source attribution."""

    self_score: Score
    """LLM's self-assessment against the rubric."""

    verified_score: Score | None = None
    """Score after claim verification (may differ from self_score)."""

    @field_validator('title')
    @classmethod
    def validate_title_length(cls, v: str) -> str:
        """Title must be <= 150 characters."""
        if len(v) > 150:
            raise ValueError(f"Title must be <= 150 characters, got {len(v)}")
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
