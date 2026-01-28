"""FeedOps optimization pipeline."""

from feedops.pipeline.batch_selection import (
    BatchSelectionCriteria,
    SKUPerformance,
    get_batch_selection_summary,
    select_batch_by_performance,
)
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown
from feedops.pipeline.generator import build_prompt, generate_candidate
from feedops.pipeline.optimize import OptimizationResult, optimize_parent_sku
from feedops.pipeline.prompts import CANDIDATE_SCHEMA
from feedops.pipeline.reporter import generate_patch_preview, generate_report
from feedops.pipeline.verifier import verify_claims

__all__ = [
    "build_evidence_table",
    "format_evidence_markdown",
    "verify_claims",
    "build_prompt",
    "generate_candidate",
    "CANDIDATE_SCHEMA",
    "generate_report",
    "generate_patch_preview",
    "optimize_parent_sku",
    "OptimizationResult",
    # Batch selection
    "select_batch_by_performance",
    "BatchSelectionCriteria",
    "SKUPerformance",
    "get_batch_selection_summary",
]
