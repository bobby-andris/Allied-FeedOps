"""FeedOps monitoring package.

Provides performance monitoring, statistical significance testing,
and automated review functionality.
"""

from feedops.monitoring.auto_review import (
    auto_review_performance,
    format_review_report,
    generate_review_summary,
)
from feedops.monitoring.significance import (
    assess_test_readiness,
    calculate_required_sample_size,
    test_ctr_significance,
    test_significance,
)
from feedops.monitoring.segment_rollout import (
    RolloutCheckpoint,
    RolloutGateDecision,
    assign_holdout,
    evaluate_rollout_checkpoint,
    should_trigger_rollback,
)

__all__ = [
    "test_significance",
    "test_ctr_significance",
    "calculate_required_sample_size",
    "assess_test_readiness",
    "auto_review_performance",
    "generate_review_summary",
    "format_review_report",
    "RolloutCheckpoint",
    "RolloutGateDecision",
    "assign_holdout",
    "evaluate_rollout_checkpoint",
    "should_trigger_rollback",
]
