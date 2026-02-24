"""Score model for quality rubric evaluation."""
from pydantic import BaseModel, computed_field, field_validator


class Score(BaseModel):
    """Quality score across 10 dimensions (0-10 each).

    Composite score = (sum of all scores) / 100 * 100

    Approval thresholds:
    - >= 80%: approved
    - 70-79%: revise (minor revision needed)
    - < 70%: rejected (major revision or human review)
    - factual_accuracy < 8: always rejected regardless of composite
    """

    hook_quality: int
    """0-10: First sentence engagement: 0=fragment/dump, 5=generic, 10=specific+engaging."""

    product_specificity: int
    """0-10: Could ONLY describe this product: 0=any competitor, 5=mentions brand generically, 10=unmistakable."""

    competitive_diff: int
    """0-10: Why THIS over cheaper alternative: 0=none, 5=generic brass mention, 10=advantage woven naturally."""

    keyword_integration: int
    """0-10: Keywords natural or stuffed: 0=stuffed/missing, 5=present but awkward, 10=invisible."""

    customer_scenario: int
    """0-10: Real buying situation: 0=spec dump, 5=generic upgrade, 10=specific resonant scenario."""

    emotional_resonance: int
    """0-10: Creates desire: 0=database export, 5=pleasant but forgettable, 10=genuine want."""

    factual_accuracy: int
    """0-10: All claims traceable to evidence: 10=yes, 0=fabricated specs. MUST be >= 8."""

    platform_compliance: int
    """0-10: Meets platform format/length rules: 10=perfect, 5=minor issues, 0=wrong format."""

    finish_integration: int
    """0-10: Finish as design choice or afterthought: 0=raw placeholder, 5=generic, 10=woven into narrative."""

    variety_score: int
    """0-10: Different from catalog peers: 0=identical pattern, 5=same skeleton, 10=unique structure."""

    @field_validator(
        'hook_quality', 'product_specificity', 'competitive_diff',
        'keyword_integration', 'customer_scenario', 'emotional_resonance',
        'factual_accuracy', 'platform_compliance', 'finish_integration', 'variety_score'
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
            self.hook_quality +
            self.product_specificity +
            self.competitive_diff +
            self.keyword_integration +
            self.customer_scenario +
            self.emotional_resonance +
            self.factual_accuracy +
            self.platform_compliance +
            self.finish_integration +
            self.variety_score
        )
        return round(total / 100 * 100, 2)

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
