"""Segment rollout gating utilities for phased CTR-first deployment.

This module provides deterministic holdout assignment and checkpoint gating
for segment-by-segment FeedOps rollout decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib


CTR_PROMOTION_THRESHOLD = 0.06
LOW_QUALITY_DELTA_MAX = 0.08
CVR_MIN_DELTA = -0.03
CVR_MIN_CONVERSIONS = 30


@dataclass(frozen=True)
class RolloutCheckpoint:
    segment_key: str
    test_ctr: float
    holdout_ctr: float
    test_low_quality_share: float
    holdout_low_quality_share: float
    conversions: int
    test_cvr: float | None = None
    holdout_cvr: float | None = None


@dataclass(frozen=True)
class RolloutGateDecision:
    segment_key: str
    ctr_lift: float
    low_quality_delta: float
    cvr_delta: float | None
    cvr_gate_active: bool
    pass_ctr_gate: bool
    pass_safety_gate: bool
    pass_cvr_gate: bool
    ready_to_promote: bool


def assign_holdout(
    master_sku: str,
    segment_key: str,
    *,
    holdout_rate: float = 0.20,
    salt: str = "feedops-rollout-v1",
) -> bool:
    """Return deterministic holdout assignment for a SKU within a segment."""
    bounded_rate = min(max(holdout_rate, 0.0), 1.0)
    digest = hashlib.sha256(
        f"{salt}|{segment_key.strip().lower()}|{master_sku.strip().upper()}".encode("utf-8")
    ).hexdigest()
    bucket = int(digest[:8], 16) / float(0xFFFFFFFF)
    return bucket < bounded_rate


def _relative_delta(test_value: float, baseline_value: float) -> float:
    if baseline_value <= 0:
        return 0.0
    return (test_value - baseline_value) / baseline_value


def evaluate_rollout_checkpoint(checkpoint: RolloutCheckpoint) -> RolloutGateDecision:
    """Evaluate CTR-first promotion gates for one segment checkpoint."""
    ctr_lift = _relative_delta(checkpoint.test_ctr, checkpoint.holdout_ctr)
    low_quality_delta = (
        checkpoint.test_low_quality_share - checkpoint.holdout_low_quality_share
    )

    pass_ctr_gate = ctr_lift >= CTR_PROMOTION_THRESHOLD
    pass_safety_gate = low_quality_delta <= LOW_QUALITY_DELTA_MAX

    cvr_gate_active = checkpoint.conversions >= CVR_MIN_CONVERSIONS
    cvr_delta: float | None = None
    pass_cvr_gate = True
    if cvr_gate_active:
        test_cvr = float(checkpoint.test_cvr or 0.0)
        holdout_cvr = float(checkpoint.holdout_cvr or 0.0)
        cvr_delta = _relative_delta(test_cvr, holdout_cvr)
        pass_cvr_gate = cvr_delta >= CVR_MIN_DELTA

    ready_to_promote = pass_ctr_gate and pass_safety_gate and pass_cvr_gate

    return RolloutGateDecision(
        segment_key=checkpoint.segment_key,
        ctr_lift=ctr_lift,
        low_quality_delta=low_quality_delta,
        cvr_delta=cvr_delta,
        cvr_gate_active=cvr_gate_active,
        pass_ctr_gate=pass_ctr_gate,
        pass_safety_gate=pass_safety_gate,
        pass_cvr_gate=pass_cvr_gate,
        ready_to_promote=ready_to_promote,
    )


def should_trigger_rollback(history: list[RolloutGateDecision]) -> bool:
    """Apply rollback triggers from the rollout plan.

    Roll back when either:
    1. CTR gate fails for two consecutive checkpoints.
    2. CVR gate fails once when active (high-volume segment).
    """
    if not history:
        return False

    # CVR fail once in high-volume segment is an immediate rollback trigger.
    if any(decision.cvr_gate_active and not decision.pass_cvr_gate for decision in history):
        return True

    # CTR gate fail in two consecutive checkpoints.
    consecutive_ctr_failures = 0
    for decision in history:
        if not decision.pass_ctr_gate:
            consecutive_ctr_failures += 1
            if consecutive_ctr_failures >= 2:
                return True
        else:
            consecutive_ctr_failures = 0

    return False
