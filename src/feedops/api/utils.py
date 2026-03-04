# Source: extracted from persistence.py:478 and job_management.py:72 (identical copies)
# Source: GenerationBudgetExceededError extracted from pipeline/generator.py:54
"""Shared API-layer primitives with no intra-package dependencies."""

from __future__ import annotations


def _require_request_id(request_id: str | None) -> str:
    """Enforce non-placeholder request IDs for lineage writes."""
    rid = (request_id or "").strip()
    if not rid or rid == "-":
        raise RuntimeError("Missing request_id for regeneration lineage write")
    return rid


class GenerationBudgetExceededError(RuntimeError):
    """Raised when estimated request cost exceeds configured per-request budget."""

    def __init__(
        self,
        *,
        cap_usd: float,
        estimated_cost_usd: float,
        platform: str,
    ) -> None:
        self.cap_usd = float(cap_usd)
        self.estimated_cost_usd = float(estimated_cost_usd)
        self.platform = platform
        super().__init__(
            "generation_request_budget_exceeded:"
            f" platform={platform} estimated_cost_usd={estimated_cost_usd:.6f}"
            f" cap_usd={cap_usd:.6f}"
        )
