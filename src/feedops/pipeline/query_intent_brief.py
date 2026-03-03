"""Deterministic query-intent brief builder for paid feed generation."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable

from feedops.integrations.search_query_insights import (
    build_relevance_anchor_terms,
    curate_search_queries_by_relevance,
    fetch_search_queries_for_master_sku,
)
from feedops.models import ParentSKU
from feedops.pipeline import evidence as evidence_module
from feedops.pipeline.enrichment import Evidence
from feedops.pipeline.feature_flags import is_query_intent_brief_v1_enabled
from feedops.pipeline.keyword_placement import (
    _build_feature_signal_text,
    _distill_intent_term,
    _feature_supported,
    _material_matches,
    build_keyword_placement_plan,
)

_WORD_RE = re.compile(r"[a-z0-9]+")
_NOISE_PATTERNS = (
    re.compile(r"https?://|www\.", re.IGNORECASE),
    re.compile(
        r"\b(review|reviews|manual|instructions?|installation|specs?|dimensions?|replacement)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bnear me\b", re.IGNORECASE),
)
_COMPETITOR_PATTERNS = tuple(
    re.compile(rf"(?<!\w){re.escape(brand)}(?!\w)", re.IGNORECASE)
    for brand in evidence_module._COMPETITOR_BRANDS
)


def _normalize(text: str) -> str:
    return " ".join(_WORD_RE.findall((text or "").lower()))


def _dedupe_preserve(values: Iterable[str], *, limit: int | None = None) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        key = _normalize(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if limit is not None and len(out) >= limit:
            break
    return out


def _business_rank(row: dict) -> tuple[float, float, float, float, float, str]:
    return (
        float(row.get("total_conversion_value") or 0.0),
        float(row.get("total_conversions") or 0.0),
        float(row.get("total_clicks") or 0.0),
        float(row.get("total_impressions") or 0.0),
        float(row.get("avg_monthly_searches") or 0.0),
        str(row.get("query_text") or "").lower(),
    )


def _has_nontrivial_signal(row: dict) -> bool:
    return any(
        (
            float(row.get("total_conversion_value") or 0.0) > 0.0,
            float(row.get("total_conversions") or 0.0) > 0.0,
            float(row.get("total_clicks") or 0.0) > 0.0,
            float(row.get("total_impressions") or 0.0) >= 25.0,
            float(row.get("avg_monthly_searches") or 0.0) >= 10.0,
        )
    )


def _matches_any(patterns: Iterable[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _classify_exclusion(
    query_text: str,
    *,
    parent_sku: ParentSKU,
    evidence_rows: list[Evidence],
) -> str | None:
    normalized = (query_text or "").strip()
    if not normalized:
        return "empty"
    lowered = normalized.lower()
    if _matches_any(_COMPETITOR_PATTERNS, lowered):
        return "competitor"
    if _matches_any(_NOISE_PATTERNS, lowered):
        return "noise"

    finish_phrases, finish_tokens = evidence_module._build_finish_filters(parent_sku)
    if evidence_module._is_finish_specific_keyword(normalized, finish_phrases, finish_tokens):
        return "finish_specific"

    if not _material_matches(normalized, parent_sku.material):
        return "material_mismatch"

    signal_text = _build_feature_signal_text(parent_sku, evidence_rows)
    if not _feature_supported(normalized, signal_text):
        return "unsupported_feature"

    return None


@dataclass(frozen=True)
class QueryIntentDiagnostics:
    query_intent_brief_enabled: bool
    query_intent_data_sufficiency: bool
    query_intent_primary_count: int
    query_intent_source_query_count: int
    query_intent_disabled_reason: str | None = None
    query_intent_curated_query_count: int = 0
    query_intent_excluded_query_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "query_intent_brief_enabled": self.query_intent_brief_enabled,
            "query_intent_data_sufficiency": self.query_intent_data_sufficiency,
            "query_intent_primary_count": self.query_intent_primary_count,
            "query_intent_source_query_count": self.query_intent_source_query_count,
            "query_intent_disabled_reason": self.query_intent_disabled_reason,
            "query_intent_curated_query_count": self.query_intent_curated_query_count,
            "query_intent_excluded_query_count": self.query_intent_excluded_query_count,
        }


@dataclass(frozen=True)
class QueryIntentBrief:
    primary_intents: list[str]
    title_emphasis: list[str]
    description_emphasis: list[str]
    excluded_terms: list[str]
    data_sufficiency: bool
    reason_disabled: str | None
    source_counts: dict[str, int]
    diagnostics: QueryIntentDiagnostics


@dataclass(frozen=True)
class QueryIntentSection:
    content: str
    diagnostics: QueryIntentDiagnostics
    brief: QueryIntentBrief = field(repr=False)


def build_query_intent_brief(
    parent_sku: ParentSKU,
    evidence_rows: list[Evidence],
    *,
    master_query_rows: list[dict] | None = None,
) -> QueryIntentBrief:
    """Build a bounded paid-query intent brief from curated master-SKU queries."""
    if master_query_rows is None:
        master_query_rows = fetch_search_queries_for_master_sku(parent_sku.master_sku, limit=120)

    if not master_query_rows:
        diagnostics = QueryIntentDiagnostics(
            query_intent_brief_enabled=False,
            query_intent_data_sufficiency=False,
            query_intent_primary_count=0,
            query_intent_source_query_count=0,
            query_intent_disabled_reason="no_master_queries",
        )
        return QueryIntentBrief(
            primary_intents=[],
            title_emphasis=[],
            description_emphasis=[],
            excluded_terms=[],
            data_sufficiency=False,
            reason_disabled="no_master_queries",
            source_counts={"raw_master_queries": 0, "curated_master_queries": 0, "excluded_master_queries": 0},
            diagnostics=diagnostics,
        )

    anchor_terms = build_relevance_anchor_terms(
        parent_sku.category,
        parent_sku.collection,
        parent_sku.current_title,
        parent_sku.current_description,
        parent_sku.material,
        parent_sku.mounting_type,
        parent_sku.style,
    )
    curated_rows, _ = curate_search_queries_by_relevance(
        master_query_rows,
        anchor_terms,
        min_keep=3,
        max_keep=12,
    )
    curated_rows = sorted(curated_rows, key=_business_rank, reverse=True)

    excluded_terms: list[str] = []
    classified_curated_rows: list[dict] = []
    curated_by_norm = {
        _normalize(str(row.get("query_text") or "")): row for row in curated_rows
    }
    for row in sorted(master_query_rows, key=_business_rank, reverse=True):
        text = str(row.get("query_text") or "").strip()
        if not text:
            continue
        normalized = _normalize(text)
        if normalized in curated_by_norm:
            reason = _classify_exclusion(
                text,
                parent_sku=parent_sku,
                evidence_rows=evidence_rows,
            )
            if reason:
                excluded_terms.append(text)
            else:
                classified_curated_rows.append(curated_by_norm[normalized])
            continue
        reason = _classify_exclusion(
            text,
            parent_sku=parent_sku,
            evidence_rows=evidence_rows,
        )
        if reason:
            excluded_terms.append(text)

    plan = build_keyword_placement_plan(parent_sku, evidence_rows)

    ranked_primary_terms = _dedupe_preserve(
        filter(
            None,
            (
                _distill_intent_term(str(row.get("query_text") or ""))
                for row in classified_curated_rows
            ),
        ),
        limit=6,
    )
    primary_intents = _dedupe_preserve(
        ranked_primary_terms + list(plan.distilled_intent_terms),
        limit=3,
    )
    title_emphasis = _dedupe_preserve(
        [plan.title_anchor] + list(plan.title_support_terms) + primary_intents,
        limit=3,
    )
    description_emphasis = _dedupe_preserve(
        list(plan.description_terms) + primary_intents,
        limit=3,
    )
    excluded_terms = _dedupe_preserve(excluded_terms, limit=5)

    anchor_match = any(
        any(anchor in _normalize(str(row.get("query_text") or "")) for anchor in anchor_terms)
        for row in classified_curated_rows
    )
    data_sufficiency = (
        len(classified_curated_rows) >= 3
        and any(_has_nontrivial_signal(row) for row in classified_curated_rows)
        and anchor_match
        and bool(primary_intents)
    )
    reason_disabled = None if data_sufficiency else "insufficient_query_signal"

    diagnostics = QueryIntentDiagnostics(
        query_intent_brief_enabled=data_sufficiency,
        query_intent_data_sufficiency=data_sufficiency,
        query_intent_primary_count=len(primary_intents),
        query_intent_source_query_count=len(master_query_rows),
        query_intent_disabled_reason=reason_disabled,
        query_intent_curated_query_count=len(classified_curated_rows),
        query_intent_excluded_query_count=len(excluded_terms),
    )
    return QueryIntentBrief(
        primary_intents=primary_intents,
        title_emphasis=title_emphasis,
        description_emphasis=description_emphasis,
        excluded_terms=excluded_terms,
        data_sufficiency=data_sufficiency,
        reason_disabled=reason_disabled,
        source_counts={
            "raw_master_queries": len(master_query_rows),
            "curated_master_queries": len(classified_curated_rows),
            "excluded_master_queries": len(excluded_terms),
        },
        diagnostics=diagnostics,
    )


def build_query_intent_section(brief: QueryIntentBrief) -> QueryIntentSection:
    """Format the query-intent brief into a bounded prompt section."""
    if not brief.data_sufficiency:
        return QueryIntentSection(content="", diagnostics=brief.diagnostics, brief=brief)

    lines = [
        "<query_intent_brief>",
        "These demand-signal cues are additive guidance only.",
        "Use them only when they improve shopper clarity and paid-query relevance.",
        "Never override product evidence, invent unsupported features, or mirror raw search behavior.",
        "",
    ]
    if brief.primary_intents:
        lines.append("Primary shopper intents:")
        for term in brief.primary_intents:
            lines.append(f"- {term}")
        lines.append("")
    if brief.title_emphasis:
        lines.append("Title emphasis cues:")
        for term in brief.title_emphasis:
            lines.append(f"- {term}")
        lines.append("")
    if brief.description_emphasis:
        lines.append("Description emphasis cues:")
        for term in brief.description_emphasis:
            lines.append(f"- {term}")
        lines.append("")
    if brief.excluded_terms:
        lines.append("Avoid noisy or misleading query phrases:")
        for term in brief.excluded_terms:
            lines.append(f"- {term}")
        lines.append("")
    lines.append("</query_intent_brief>")
    return QueryIntentSection(
        content="\n".join(lines),
        diagnostics=brief.diagnostics,
        brief=brief,
    )


def build_query_intent_context(
    parent_sku: ParentSKU,
    evidence_rows: list[Evidence],
    *,
    master_query_rows: list[dict] | None = None,
) -> QueryIntentSection:
    """Build a prompt section + diagnostics for eligible Google/Bing tasks."""
    if not is_query_intent_brief_v1_enabled():
        brief = QueryIntentBrief(
            primary_intents=[],
            title_emphasis=[],
            description_emphasis=[],
            excluded_terms=[],
            data_sufficiency=False,
            reason_disabled="feature_flag_disabled",
            source_counts={"raw_master_queries": 0, "curated_master_queries": 0, "excluded_master_queries": 0},
            diagnostics=QueryIntentDiagnostics(
                query_intent_brief_enabled=False,
                query_intent_data_sufficiency=False,
                query_intent_primary_count=0,
                query_intent_source_query_count=0,
                query_intent_disabled_reason="feature_flag_disabled",
            ),
        )
        return QueryIntentSection(content="", diagnostics=brief.diagnostics, brief=brief)

    brief = build_query_intent_brief(
        parent_sku,
        evidence_rows,
        master_query_rows=master_query_rows,
    )
    return build_query_intent_section(brief)
