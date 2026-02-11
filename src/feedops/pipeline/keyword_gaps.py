"""Keyword gap detection for MasterSKU evidence.

This module identifies high-volume search queries that are *not* well represented
in the current (Shopify) title for a master SKU. The output is intended for the
evidence table as search-intent guidance only (not as product facts).
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from feedops.models import ParentSKU
from feedops.pipeline.enrichment import Evidence
from feedops.pipeline import evidence as evidence_module


_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "by",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}
_UNIT_TOKENS = {
    "in",
    "inch",
    "inches",
    "lb",
    "lbs",
    "pound",
    "pounds",
}
_BRAND_STOP_TOKENS = {"allied"}
_CATEGORY_SYNONYM_TOKENS: dict[str, set[str]] = {
    "towel bar": {"towel", "bar", "rack", "holder", "rail"},
    "grab bar": {"grab", "bar", "safety", "support", "handrail"},
    "robe hook": {"robe", "hook", "hanger", "towel"},
    "toilet paper": {"toilet", "paper", "tissue", "holder"},
    "paper towel": {"paper", "towel", "holder", "rack"},
    "shelf": {"shelf", "shelving", "ledge", "organizer"},
    "mirror": {"mirror", "vanity", "tilt", "magnifying"},
}


@dataclass(frozen=True)
class KeywordGap:
    """A high-volume search query not covered by the current title."""

    query_text: str
    score: float
    metric: str
    missing_tokens: tuple[str, ...]


def _normalize_token(token: str) -> str:
    token = (token or "").strip().lower()
    if not token:
        return ""
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _significant_tokens(text: str) -> set[str]:
    tokens = [_normalize_token(t) for t in _WORD_RE.findall((text or "").lower())]
    return {
        t
        for t in tokens
        if t and t not in _STOP_WORDS and t not in _UNIT_TOKENS and t not in _BRAND_STOP_TOKENS
    }


def _format_compact_number(value: float) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(int(round(value)))


def _category_relevance_tokens(parent_sku: ParentSKU) -> set[str]:
    """Build category/product-type tokens used to filter irrelevant query gaps."""
    category_text = (parent_sku.category or "").lower()
    tokens = set(_significant_tokens(category_text))

    for marker, synonyms in _CATEGORY_SYNONYM_TOKENS.items():
        if marker in category_text:
            tokens.update(synonyms)

    # Fallback: use title-derived terms when category is sparse.
    if not tokens:
        tokens.update(_significant_tokens(parent_sku.current_title or ""))

    return tokens


def _is_category_relevant_query(query_text: str, relevance_tokens: set[str]) -> bool:
    """Return whether a query appears category-relevant for the current product family."""
    if not relevance_tokens:
        return True
    query_tokens = _significant_tokens(query_text)
    return bool(query_tokens & relevance_tokens)


def _score_and_metric(query: dict) -> tuple[float, str]:
    """Return (score, metric_label). Prefer avg_monthly_searches over impressions."""
    volume = query.get("avg_monthly_searches")
    try:
        volume_value = float(volume) if volume is not None else 0.0
    except Exception:
        volume_value = 0.0
    if volume_value > 0:
        return volume_value, f"{_format_compact_number(volume_value)} vol"

    impressions = query.get("total_impressions", query.get("impressions", 0))
    try:
        impressions_value = float(impressions) if impressions is not None else 0.0
    except Exception:
        impressions_value = 0.0
    return impressions_value, f"{_format_compact_number(impressions_value)} imp"


def compute_keyword_gaps_for_title(
    parent_sku: ParentSKU,
    queries: list[dict],
    *,
    title: str | None = None,
    max_gaps: int = 8,
) -> list[KeywordGap]:
    """Compute high-volume search queries that aren't covered by a title.

    Coverage is determined by token presence (order-insensitive) after removing
    common stop-words. Finish-specific queries are excluded.
    """
    if not queries:
        return []

    title_text = (title if title is not None else parent_sku.current_title) or ""
    title_tokens = _significant_tokens(title_text)
    relevance_tokens = _category_relevance_tokens(parent_sku)

    finish_phrases, finish_tokens = evidence_module._build_finish_filters(parent_sku)

    gaps_by_key: dict[str, KeywordGap] = {}
    for q in queries:
        text = str(q.get("query_text") or "").strip()
        if not text:
            continue

        if evidence_module._is_finish_specific_keyword(text, finish_phrases, finish_tokens):
            continue
        if not _is_category_relevant_query(text, relevance_tokens):
            continue

        score, metric = _score_and_metric(q)
        if score <= 0:
            continue

        query_tokens = _significant_tokens(text)
        if not query_tokens:
            continue

        missing = tuple(sorted(query_tokens - title_tokens))
        if not missing:
            continue

        key = " ".join(_WORD_RE.findall(text.lower()))
        existing = gaps_by_key.get(key)
        if existing is None or score > existing.score:
            gaps_by_key[key] = KeywordGap(
                query_text=text,
                score=score,
                metric=metric,
                missing_tokens=missing,
            )

    gaps = sorted(gaps_by_key.values(), key=lambda gap: gap.score, reverse=True)
    return gaps[:max_gaps]


def build_keyword_gap_evidence_rows(
    parent_sku: ParentSKU,
    queries: list[dict],
    *,
    max_gaps: int = 8,
) -> list[Evidence]:
    """Build Evidence row(s) summarizing title keyword gaps."""
    gaps = compute_keyword_gaps_for_title(parent_sku, queries, max_gaps=max_gaps)
    if not gaps:
        return []

    parts = [f'"{gap.query_text}" ({gap.metric})' for gap in gaps]
    return [
        Evidence(
            field="keyword_gaps_current_title",
            value=", ".join(parts),
            source="keyword_gaps",
        )
    ]
