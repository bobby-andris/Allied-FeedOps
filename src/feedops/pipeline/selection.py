"""Candidate selection utilities for multi-generation runs."""
from __future__ import annotations

from dataclasses import dataclass
import re

from feedops.models import Candidate
from feedops.pipeline.validators import CUSTOMER_FIELDS, PARENTHETICAL_CITATION_PATTERN, validate_candidate_content
from feedops.quality.scoring import CandidateHeuristicScore, score_candidate


DEFAULT_NUM_CANDIDATES = 3
DEFAULT_WEIGHTS = {"google": 0.7, "bing": 0.15, "shopify": 0.15}


@dataclass
class RankedCandidate:
    candidate: Candidate
    heuristic: CandidateHeuristicScore
    validation_errors: list[str]
    index: int


def parse_num_candidates(env_value: str | None) -> int:
    """Parse candidate count from env/CLI."""
    if not env_value:
        return DEFAULT_NUM_CANDIDATES
    try:
        value = int(env_value)
    except (TypeError, ValueError):
        return DEFAULT_NUM_CANDIDATES
    return value if value > 0 else DEFAULT_NUM_CANDIDATES


def parse_candidate_weights(raw: str | None) -> dict[str, float]:
    """Parse weights from 'google=0.7,bing=0.15,shopify=0.15' string."""
    if not raw:
        return DEFAULT_WEIGHTS.copy()

    weights: dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if key not in DEFAULT_WEIGHTS:
            continue
        try:
            amount = float(value.strip())
        except ValueError:
            continue
        if amount > 1:
            amount = amount / 100
        if amount < 0:
            amount = 0
        weights[key] = amount

    total = sum(weights.values())
    if total <= 0:
        return DEFAULT_WEIGHTS.copy()

    return {k: v / total for k, v in weights.items()}


def sanitize_candidate_content(candidate: Candidate) -> Candidate:
    """Strip catalog_csv citations from customer-facing fields."""
    def _sanitize(value: str) -> str:
        cleaned = PARENTHETICAL_CITATION_PATTERN.sub("", value)
        cleaned = cleaned.replace("catalog_csv.", "")
        cleaned = re.sub(r" {2,}", " ", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    updates = {field: _sanitize(getattr(candidate, field)) for field in CUSTOMER_FIELDS}
    return candidate.model_copy(update=updates)


def rank_candidates(
    candidates: list[Candidate],
    weights: dict[str, float],
) -> list[RankedCandidate]:
    ranked: list[RankedCandidate] = []
    for idx, candidate in enumerate(candidates):
        heuristic = score_candidate(candidate, weights=weights)
        validation_errors = validate_candidate_content(candidate)
        candidate_index = candidate.candidate_index if candidate.candidate_index is not None else idx
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                heuristic=heuristic,
                validation_errors=validation_errors,
                index=candidate_index,
            )
        )
    return ranked


def _rank_sort_key(entry: RankedCandidate) -> tuple[bool, float, float, int]:
    return (
        bool(entry.validation_errors),
        -entry.heuristic.adjusted_weighted_composite,
        -entry.heuristic.google.composite,
        entry.index,
    )


def select_best_candidate(
    candidates: list[Candidate],
    weights: dict[str, float],
) -> tuple[Candidate, list[RankedCandidate]]:
    """Select best candidate using validation-first + weighted heuristics."""
    if not candidates:
        raise ValueError("No candidates to select from")

    ranked = rank_candidates(candidates, weights)
    ranked_sorted = sorted(ranked, key=_rank_sort_key)
    best = ranked_sorted[0]
    selected = best.candidate

    if best.validation_errors:
        sanitized = sanitize_candidate_content(selected)
        sanitized_errors = validate_candidate_content(sanitized)
        ranked_sorted[0] = RankedCandidate(
            candidate=sanitized,
            heuristic=best.heuristic,
            validation_errors=sanitized_errors,
            index=best.index,
        )
        selected = sanitized

    return selected, ranked_sorted
