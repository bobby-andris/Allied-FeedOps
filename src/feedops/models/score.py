"""Score model for quality rubric evaluation."""
from pydantic import BaseModel, computed_field, field_validator


class Score(BaseModel):
    """Quality score across 6 dimensions (0-10 each).

    Composite score = (sum of all scores) / 60 * 100

    Approval thresholds:
    - >= 80%: approved
    - 70-79%: revise (minor revision needed)
    - < 70%: rejected (major revision or human review)
    - factual_accuracy < 8: always rejected regardless of composite
    """

    specificity: int
    """0-10: Specific/verifiable claims vs generic claims."""

    benefit_coverage: int
    """0-10: Benefits addressed in first 150 characters."""

    keyword_inclusion: int
    """0-10: Target keywords in optimal positions."""

    format_adherence: int
    """0-10: Compliance with character limits and structure."""

    brand_voice: int
    """0-10: Premium, confident tone without superlatives."""

    factual_accuracy: int
    """0-10: Every claim traceable to product data. MUST be >= 8."""

    @field_validator(
        'specificity', 'benefit_coverage', 'keyword_inclusion',
        'format_adherence', 'brand_voice', 'factual_accuracy'
    )
    @classmethod
    def validate_score_range(cls, v: int) -> int:
        """Ensure scores are 0-10."""
        if not 0 <= v <= 10:
            raise ValueError(f"Score must be 0-10, got {v}")
        return v

    @computed_field
    @property
    def composite(self) -> float:
        """Calculate composite score as percentage (0-100)."""
        total = (
            self.specificity +
            self.benefit_coverage +
            self.keyword_inclusion +
            self.format_adherence +
            self.brand_voice +
            self.factual_accuracy
        )
        return round(total / 60 * 100, 2)

    @computed_field
    @property
    def approval_status(self) -> str:
        """Determine approval status based on composite and factual_accuracy.

        Returns:
            'approved': >= 80% composite AND factual_accuracy >= 8
            'revise': 70-79% composite AND factual_accuracy >= 8
            'rejected': < 70% composite OR factual_accuracy < 8
        """
        if self.factual_accuracy < 8:
            return "rejected"
        if self.composite >= 80:
            return "approved"
        if self.composite >= 70:
            return "revise"
        return "rejected"
