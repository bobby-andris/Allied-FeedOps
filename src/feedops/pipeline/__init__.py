"""FeedOps optimization pipeline.

This package exposes a convenience surface for imports, but uses lazy imports to
avoid circular import hazards (pipeline ↔ loaders ↔ db helpers).
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

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


_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    # evidence
    "build_evidence_table": ("feedops.pipeline.evidence", "build_evidence_table"),
    "format_evidence_markdown": ("feedops.pipeline.evidence", "format_evidence_markdown"),
    # verifier
    "verify_claims": ("feedops.pipeline.verifier", "verify_claims"),
    # generator
    "build_prompt": ("feedops.pipeline.generator", "build_prompt"),
    "generate_candidate": ("feedops.pipeline.generator", "generate_candidate"),
    # prompts
    "CANDIDATE_SCHEMA": ("feedops.pipeline.prompts", "CANDIDATE_SCHEMA"),
    # reporter
    "generate_report": ("feedops.pipeline.reporter", "generate_report"),
    "generate_patch_preview": ("feedops.pipeline.reporter", "generate_patch_preview"),
    # optimize
    "optimize_parent_sku": ("feedops.pipeline.optimize", "optimize_parent_sku"),
    "OptimizationResult": ("feedops.pipeline.optimize", "OptimizationResult"),
    # batch selection
    "select_batch_by_performance": ("feedops.pipeline.batch_selection", "select_batch_by_performance"),
    "BatchSelectionCriteria": ("feedops.pipeline.batch_selection", "BatchSelectionCriteria"),
    "SKUPerformance": ("feedops.pipeline.batch_selection", "SKUPerformance"),
    "get_batch_selection_summary": ("feedops.pipeline.batch_selection", "get_batch_selection_summary"),
}


def __getattr__(name: str) -> Any:  # pragma: no cover
    target = _LAZY_ATTRS.get(name)
    if not target:
        raise AttributeError(name)
    module_name, attr_name = target
    module = import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:  # pragma: no cover
    return sorted(set(__all__) | set(globals().keys()))
