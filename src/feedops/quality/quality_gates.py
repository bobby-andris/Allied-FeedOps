"""Automated quality gates for candidate approval workflow.

Quality gates enforce minimum standards before content can be published:
- BLOCK: Content fails hard requirements and cannot be published
- REVIEW: Content needs human review before publishing
- APPROVE: Content meets all standards and can be auto-published

Thresholds are based on the scoring rubric in AGENTS.md and industry best practices.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from feedops.models import Candidate
from feedops.pipeline.validators import (
    ValidationResult,
    validate_candidate_content_full,
)


class GateStatus(Enum):
    """Quality gate decision status."""

    BLOCKED = "blocked"
    """Content fails hard requirements - cannot be published."""

    NEEDS_REVIEW = "needs_review"
    """Content needs human review before publishing."""

    APPROVED = "approved"
    """Content meets all standards - can be auto-published."""


@dataclass
class QualityGateResult:
    """Result of quality gate evaluation."""

    status: GateStatus
    """Final gate decision."""

    reasons: list[str]
    """Reasons for the decision."""

    score_composite: float
    """Composite quality score (0-100)."""

    score_factual_accuracy: int
    """Factual accuracy score (0-10)."""

    validation_errors: list[str]
    """Validation errors from content checks."""

    validation_warnings: list[str]
    """Validation warnings (soft issues)."""

    # Threshold tracking
    passed_factual_accuracy: bool
    """Whether factual accuracy meets minimum (8/10)."""

    passed_composite_minimum: bool
    """Whether composite score meets minimum (70%)."""

    passed_validation: bool
    """Whether content passed all validation checks."""

    auto_approve_eligible: bool
    """Whether content qualifies for auto-approval (85%+ and no errors)."""


# =============================================================================
# Quality Gate Thresholds
# =============================================================================

# Hard requirement: factual accuracy must be >= 8/10
# Rationale: Claims must be verifiable and accurate (AGENTS.md: "This score cannot be below 8")
MIN_FACTUAL_ACCURACY = 8

# Minimum composite score for publishing (70%)
# Below this requires major revision or human review
MIN_COMPOSITE_SCORE = 70.0

# Auto-approval threshold (85%)
# Content scoring above this with no validation errors can be auto-published
AUTO_APPROVE_THRESHOLD = 85.0

# Soft review threshold (80%)
# Content between 70-80% should be flagged for review but isn't blocked
SOFT_REVIEW_THRESHOLD = 80.0


def evaluate_quality_gates(
    candidate: Candidate,
    *,
    strict_factual_accuracy: bool = True,
    require_validation: bool = True,
    auto_approve_enabled: bool = True,
) -> QualityGateResult:
    """Evaluate a candidate against quality gates.

    Quality Gate Logic:
    1. BLOCKED if factual_accuracy < 8 (hard requirement)
    2. BLOCKED if validation has errors (prohibited content)
    3. NEEDS_REVIEW if composite < 70% (major issues)
    4. NEEDS_REVIEW if composite 70-85% (minor issues, human check)
    5. APPROVED if composite >= 85% and no validation errors

    Args:
        candidate: The candidate to evaluate
        strict_factual_accuracy: Block if factual accuracy < 8 (default True)
        require_validation: Run content validation checks (default True)
        auto_approve_enabled: Allow auto-approval for high scores (default True)

    Returns:
        QualityGateResult with decision and reasoning
    """
    reasons: list[str] = []
    validation_errors: list[str] = []
    validation_warnings: list[str] = []

    # Get scores
    score = candidate.final_score
    composite = score.composite
    factual = score.factual_accuracy

    # Run validation if enabled
    validation_result: Optional[ValidationResult] = None
    if require_validation:
        validation_result = validate_candidate_content_full(candidate)
        validation_errors = validation_result.errors
        validation_warnings = validation_result.warnings

    # Track threshold passes
    passed_factual = factual >= MIN_FACTUAL_ACCURACY
    passed_composite_min = composite >= MIN_COMPOSITE_SCORE
    passed_validation = len(validation_errors) == 0
    auto_approve_eligible = (
        composite >= AUTO_APPROVE_THRESHOLD
        and passed_validation
        and passed_factual
        and auto_approve_enabled
    )

    # Determine gate status
    status = GateStatus.APPROVED

    # Check for BLOCKED conditions
    if strict_factual_accuracy and not passed_factual:
        status = GateStatus.BLOCKED
        reasons.append(
            f"Factual accuracy score {factual}/10 is below minimum required {MIN_FACTUAL_ACCURACY}/10. "
            "All claims must be verifiable against source data."
        )

    if require_validation and not passed_validation:
        status = GateStatus.BLOCKED
        reasons.append(
            f"Content validation failed with {len(validation_errors)} error(s). "
            "Fix validation errors before publishing."
        )
        reasons.extend([f"- {err}" for err in validation_errors[:5]])  # Show first 5

    # If not blocked, check for NEEDS_REVIEW conditions
    if status != GateStatus.BLOCKED:
        if not passed_composite_min:
            status = GateStatus.NEEDS_REVIEW
            reasons.append(
                f"Composite score {composite}% is below minimum {MIN_COMPOSITE_SCORE}%. "
                "Major revision or human review required."
            )
        elif composite < AUTO_APPROVE_THRESHOLD:
            status = GateStatus.NEEDS_REVIEW
            reasons.append(
                f"Composite score {composite}% is between {MIN_COMPOSITE_SCORE}%-{AUTO_APPROVE_THRESHOLD}%. "
                "Human review recommended before publishing."
            )
        elif validation_warnings:
            status = GateStatus.NEEDS_REVIEW
            reasons.append(
                f"Content has {len(validation_warnings)} warning(s) that should be reviewed."
            )

    # Check for auto-approval
    if auto_approve_eligible and status == GateStatus.NEEDS_REVIEW:
        # High score can override soft review requirement
        if composite >= AUTO_APPROVE_THRESHOLD and passed_validation and passed_factual:
            status = GateStatus.APPROVED
            reasons = [
                f"Auto-approved: Composite score {composite}% meets threshold "
                f"({AUTO_APPROVE_THRESHOLD}%+) with no validation errors."
            ]

    # Add approval reason if approved
    if status == GateStatus.APPROVED and not reasons:
        reasons.append(
            f"Content approved: Composite score {composite}%, "
            f"factual accuracy {factual}/10, no validation errors."
        )

    return QualityGateResult(
        status=status,
        reasons=reasons,
        score_composite=composite,
        score_factual_accuracy=factual,
        validation_errors=validation_errors,
        validation_warnings=validation_warnings,
        passed_factual_accuracy=passed_factual,
        passed_composite_minimum=passed_composite_min,
        passed_validation=passed_validation,
        auto_approve_eligible=auto_approve_eligible,
    )


def should_block_publishing(candidate: Candidate) -> tuple[bool, list[str]]:
    """Quick check if candidate should be blocked from publishing.

    Args:
        candidate: The candidate to check

    Returns:
        Tuple of (should_block, reasons)
    """
    result = evaluate_quality_gates(candidate)
    return result.status == GateStatus.BLOCKED, result.reasons


def should_auto_approve(candidate: Candidate) -> tuple[bool, list[str]]:
    """Quick check if candidate qualifies for auto-approval.

    Args:
        candidate: The candidate to check

    Returns:
        Tuple of (can_auto_approve, reasons)
    """
    result = evaluate_quality_gates(candidate)
    return (
        result.status == GateStatus.APPROVED and result.auto_approve_eligible,
        result.reasons,
    )


def get_approval_status_label(candidate: Candidate) -> str:
    """Get human-readable approval status for a candidate.

    Args:
        candidate: The candidate to evaluate

    Returns:
        Status label string
    """
    result = evaluate_quality_gates(candidate)

    if result.status == GateStatus.BLOCKED:
        return "BLOCKED"
    elif result.status == GateStatus.NEEDS_REVIEW:
        return "NEEDS_REVIEW"
    elif result.auto_approve_eligible:
        return "AUTO_APPROVED"
    else:
        return "APPROVED"


def format_gate_result_summary(result: QualityGateResult) -> str:
    """Format quality gate result as human-readable summary.

    Args:
        result: QualityGateResult to format

    Returns:
        Formatted summary string
    """
    lines = [
        f"Quality Gate: {result.status.value.upper()}",
        f"Composite Score: {result.score_composite}%",
        f"Factual Accuracy: {result.score_factual_accuracy}/10",
        "",
        "Threshold Checks:",
        f"  - Factual Accuracy >= {MIN_FACTUAL_ACCURACY}: {'PASS' if result.passed_factual_accuracy else 'FAIL'}",
        f"  - Composite >= {MIN_COMPOSITE_SCORE}%: {'PASS' if result.passed_composite_minimum else 'FAIL'}",
        f"  - Validation: {'PASS' if result.passed_validation else 'FAIL'}",
        f"  - Auto-Approve Eligible: {'YES' if result.auto_approve_eligible else 'NO'}",
    ]

    if result.reasons:
        lines.append("")
        lines.append("Decision Reasons:")
        for reason in result.reasons:
            lines.append(f"  {reason}")

    if result.validation_errors:
        lines.append("")
        lines.append(f"Validation Errors ({len(result.validation_errors)}):")
        for err in result.validation_errors[:5]:
            lines.append(f"  - {err}")
        if len(result.validation_errors) > 5:
            lines.append(f"  ... and {len(result.validation_errors) - 5} more")

    if result.validation_warnings:
        lines.append("")
        lines.append(f"Validation Warnings ({len(result.validation_warnings)}):")
        for warn in result.validation_warnings[:3]:
            lines.append(f"  - {warn}")
        if len(result.validation_warnings) > 3:
            lines.append(f"  ... and {len(result.validation_warnings) - 3} more")

    return "\n".join(lines)
