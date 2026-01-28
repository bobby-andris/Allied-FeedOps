"""Quality evaluation utilities (offline heuristic scoring)."""

from feedops.quality.data_loader import (
    ExportContent,
    OriginalContent,
    ReportMeta,
    SKUData,
    get_summary_stats,
    load_all_sku_data,
    load_catalog_originals,
    load_exports_dir,
)
from feedops.quality.evaluator import evaluate_exports_dir
from feedops.quality.quality_gates import (
    AUTO_APPROVE_THRESHOLD,
    MIN_COMPOSITE_SCORE,
    MIN_FACTUAL_ACCURACY,
    GateStatus,
    QualityGateResult,
    evaluate_quality_gates,
    format_gate_result_summary,
    get_approval_status_label,
    should_auto_approve,
    should_block_publishing,
)
from feedops.quality.scoring import score_brand_voice, score_description, score_title

__all__ = [
    # Evaluator
    "evaluate_exports_dir",
    # Scoring
    "score_title",
    "score_description",
    "score_brand_voice",
    # Data loader
    "load_all_sku_data",
    "load_catalog_originals",
    "load_exports_dir",
    "get_summary_stats",
    "SKUData",
    "OriginalContent",
    "ExportContent",
    "ReportMeta",
    # Quality gates
    "evaluate_quality_gates",
    "should_block_publishing",
    "should_auto_approve",
    "get_approval_status_label",
    "format_gate_result_summary",
    "GateStatus",
    "QualityGateResult",
    "MIN_FACTUAL_ACCURACY",
    "MIN_COMPOSITE_SCORE",
    "AUTO_APPROVE_THRESHOLD",
]
