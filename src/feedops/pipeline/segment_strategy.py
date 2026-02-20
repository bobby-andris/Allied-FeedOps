"""Segment strategy rules derived from custom_label_0.

This module provides a deterministic mapping from merchandising segment labels
(custom_label_0) to language guidance used during generation and intent curation.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_SEGMENT_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SegmentStrategy:
    id: str
    name: str
    primary_nouns: tuple[str, ...]
    allowed_modifiers: tuple[str, ...]
    forbidden_terms: tuple[str, ...]
    synonym_priority: tuple[str, ...]
    fallback_queries: tuple[str, ...]


DEFAULT_STRATEGY = SegmentStrategy(
    id="segment_generic_hardware",
    name="Generic Hardware",
    primary_nouns=("bathroom hardware", "wall mounted hardware"),
    allowed_modifiers=("solid brass", "wall-mounted", "durable"),
    forbidden_terms=("cheap", "decor only", "novelty"),
    synonym_priority=("bathroom hardware", "bath accessories"),
    fallback_queries=(
        "solid brass bathroom hardware",
        "wall mounted bath accessories",
        "durable bathroom fixtures",
    ),
)


def normalize_segment_key(value: str | None) -> str:
    return " ".join(_SEGMENT_TOKEN_RE.findall((value or "").lower()))


_STRATEGY_BY_MATCH: list[tuple[tuple[str, ...], SegmentStrategy]] = [
    (
        ("towel bar", "towel bars"),
        SegmentStrategy(
            id="segment_towel_bars",
            name="Towel Bars",
            primary_nouns=("towel bar", "towel rack", "wall mounted towel holder"),
            allowed_modifiers=("solid brass", "wall-mounted", "concealed mounting"),
            forbidden_terms=("paper towel", "kitchen roll", "adhesive"),
            synonym_priority=("towel bar", "towel rack", "towel holder"),
            fallback_queries=(
                "solid brass towel bar",
                "wall mounted towel rack",
                "bathroom towel holder brass",
            ),
        ),
    ),
    (
        ("toilet paper holder", "toilet paper holders", "tissue holder"),
        SegmentStrategy(
            id="segment_toilet_paper_holders",
            name="Toilet Paper Holders",
            primary_nouns=("toilet paper holder", "tissue holder", "tp holder"),
            allowed_modifiers=("wall-mounted", "solid brass", "rollerless"),
            forbidden_terms=("paper towel", "napkin", "kitchen"),
            synonym_priority=("toilet paper holder", "tissue holder", "tp holder"),
            fallback_queries=(
                "solid brass toilet paper holder",
                "wall mounted tissue holder",
                "decorative toilet paper holder",
            ),
        ),
    ),
    (
        ("grab bar", "grab bars", "ada"),
        SegmentStrategy(
            id="segment_grab_bars",
            name="Grab Bars",
            primary_nouns=("grab bar", "safety bar", "ada grab bar"),
            allowed_modifiers=("ADA compliant", "secure support", "wall-mounted"),
            forbidden_terms=("decor only", "non load bearing", "temporary"),
            synonym_priority=("grab bar", "safety bar", "ADA grab bar"),
            fallback_queries=(
                "ada compliant grab bar",
                "decorative safety grab bar",
                "solid brass bathroom grab bar",
            ),
        ),
    ),
    (
        ("robe hook", "robe hooks", "towel hook"),
        SegmentStrategy(
            id="segment_hooks",
            name="Hooks",
            primary_nouns=("robe hook", "towel hook", "bathroom hook"),
            allowed_modifiers=("wall-mounted", "solid brass", "compact"),
            forbidden_terms=("command hook", "adhesive", "plastic"),
            synonym_priority=("robe hook", "towel hook", "bathroom hook"),
            fallback_queries=(
                "solid brass robe hook",
                "wall mounted towel hook",
                "decorative bathroom hook",
            ),
        ),
    ),
    (
        ("shower basket", "shower baskets", "shower caddy"),
        SegmentStrategy(
            id="segment_shower_baskets",
            name="Shower Baskets",
            primary_nouns=("shower basket", "shower caddy", "bath caddy"),
            allowed_modifiers=("ventilated", "wall-mounted", "solid brass"),
            forbidden_terms=("plastic caddy", "overdoor", "suction"),
            synonym_priority=("shower basket", "shower caddy", "bath caddy"),
            fallback_queries=(
                "solid brass shower basket",
                "wall mounted shower caddy",
                "bathroom shower organizer brass",
            ),
        ),
    ),
]


def get_segment_strategy(custom_label_0_values: list[str] | tuple[str, ...] | None) -> SegmentStrategy:
    """Return the best segment strategy for the provided custom_label_0 values."""
    values = [normalize_segment_key(v) for v in (custom_label_0_values or []) if str(v).strip()]
    if not values:
        return DEFAULT_STRATEGY

    haystack = " | ".join(values)
    for needles, strategy in _STRATEGY_BY_MATCH:
        for needle in needles:
            if needle in haystack:
                return strategy

    return DEFAULT_STRATEGY


def resolve_segment_strategy(
    custom_label_0_values: list[str] | tuple[str, ...] | None,
    *,
    enabled: bool = True,
) -> SegmentStrategy:
    """Resolve strategy with feature-flag semantics.

    When disabled, always return the generic default strategy as a safe rollback
    behavior regardless of labels present in evidence.
    """
    if not enabled:
        return DEFAULT_STRATEGY
    return get_segment_strategy(custom_label_0_values)


def format_segment_strategy_guidance(strategy: SegmentStrategy) -> str:
    """Format strategy details for prompt injection."""
    return (
        f"Segment strategy: {strategy.name} ({strategy.id})\n"
        f"- Primary nouns: {', '.join(strategy.primary_nouns)}\n"
        f"- Preferred modifiers: {', '.join(strategy.allowed_modifiers)}\n"
        f"- Avoid terms: {', '.join(strategy.forbidden_terms)}\n"
        f"- Synonym priority (Google/Bing): {', '.join(strategy.synonym_priority)}"
    )
