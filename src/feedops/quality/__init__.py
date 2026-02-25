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
from feedops.quality.eval_framework import (
    EvalReport,
    SKUEvalResult,
    evaluate_regression,
    render_report,
)
from feedops.quality.evaluator import (
    PromptEvalRecord,
    build_prompt_eval_record,
    evaluate_exports_dir,
    summarize_prompt_eval_records,
    write_prompt_eval_records,
    write_prompt_eval_summary_csv,
)
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
from feedops.quality.scoring import (
    compute_description_quality_index,
    compute_platform_quality_indices,
    compute_title_quality_index,
    score_brand_voice,
    score_description,
    score_title,
)

__all__ = [
    # Evaluator
    "evaluate_exports_dir",
    "PromptEvalRecord",
    "build_prompt_eval_record",
    "write_prompt_eval_records",
    "summarize_prompt_eval_records",
    "write_prompt_eval_summary_csv",
    # Eval framework (regression testing)
    "evaluate_regression",
    "render_report",
    "EvalReport",
    "SKUEvalResult",
    # Scoring
    "score_title",
    "score_description",
    "score_brand_voice",
    "compute_title_quality_index",
    "compute_description_quality_index",
    "compute_platform_quality_indices",
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
