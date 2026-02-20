"""Search query insights integration for evidence table.

This module fetches search queries from Supabase (collected via Google Ads
search_term_view) and formats them as Evidence rows for LLM prompts.

The search data helps the LLM naturally incorporate high-volume keywords
that customers actually use when searching.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedops.pipeline.enrichment import Evidence

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

_EXCLUDED_BRAND_TERMS = {
    "amazon",
    "delta",
    "home depot",
    "homedepot",
    "ikea",
    "kohler",
    "lowes",
    "moen",
    "wayfair",
}


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def build_relevance_anchor_terms(*texts: str | None) -> set[str]:
    """Build normalized anchor terms used to keep query evidence relevant."""
    anchors: set[str] = set()
    for text in texts:
        for token in _tokenize(text or ""):
            if token in _STOPWORDS or len(token) < 3:
                continue
            anchors.add(token)
    return anchors


def _looks_like_query_noise(query_text: str) -> bool:
    """Reject terms that are not useful for LLM keyword guidance."""
    text = (query_text or "").strip().lower()
    if not text:
        return True
    if len(text) < 3 or len(text) > 100:
        return True
    if _URL_RE.search(text) or _PLACEHOLDER_RE.search(text):
        return True
    for brand in _EXCLUDED_BRAND_TERMS:
        if brand in text:
            return True
    tokens = [t for t in _tokenize(text) if t not in _STOPWORDS]
    if len(tokens) < 2:
        return True
    return False


def _metric_value(row: dict, *keys: str) -> float:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _normalize_metric(values: list[float]) -> list[float]:
    if not values:
        return []
    min_value = min(values)
    max_value = max(values)
    if max_value <= min_value:
        return [1.0 if v > 0 else 0.0 for v in values]
    denom = max_value - min_value
    return [(v - min_value) / denom for v in values]


def curate_search_queries_by_relevance(
    queries: list[dict],
    anchor_terms: set[str] | None = None,
    *,
    min_keep: int = 3,
    max_keep: int = 15,
) -> tuple[list[dict], dict[str, object]]:
    """Curate and rank query insights to reduce off-intent prompt noise.

    Score formula (fixed):
    score = 0.45*impressions_norm + 0.35*clicks_norm + 0.20*keyword_volume_norm + anchor_overlap_bonus
    anchor_overlap_bonus = +0.15 when >=2 anchor token overlaps
    """
    anchors = set(anchor_terms or set())
    deduped: list[dict] = []
    keep: list[dict] = []
    fallback: list[dict] = []
    seen: set[str] = set()
    reason_counts: dict[str, int] = {}
    dropped_noise = 0
    dropped_duplicates = 0

    for row in queries:
        text = (row.get("query_text") or "").strip()
        normalized = " ".join(_tokenize(text))
        if not normalized:
            continue
        if normalized in seen:
            dropped_duplicates += 1
            continue
        seen.add(normalized)

        if _looks_like_query_noise(text):
            dropped_noise += 1
            reason_counts["noise_or_competitor"] = (
                reason_counts.get("noise_or_competitor", 0) + 1
            )
            continue

        cleaned_tokens = {t for t in _tokenize(text) if t not in _STOPWORDS}
        if not cleaned_tokens:
            reason_counts["no_clean_tokens"] = reason_counts.get("no_clean_tokens", 0) + 1
            continue

        overlap_count = len(cleaned_tokens & anchors) if anchors else 0
        candidate = dict(row)
        candidate["query_text"] = text
        candidate["_cleaned_tokens"] = cleaned_tokens
        candidate["_overlap_count"] = overlap_count
        deduped.append(candidate)

    if not deduped:
        diagnostics = {
            "query_filter_kept_count": 0,
            "query_filter_dropped_count": dropped_noise + dropped_duplicates,
            "query_filter_reason_top": "no_valid_queries",
        }
        return [], diagnostics

    impressions = [
        _metric_value(row, "total_impressions", "impressions")
        for row in deduped
    ]
    clicks = [
        _metric_value(row, "total_clicks", "clicks")
        for row in deduped
    ]
    volumes = [
        _metric_value(row, "avg_monthly_searches", "keyword_volume", "search_volume")
        for row in deduped
    ]
    impressions_norm = _normalize_metric(impressions)
    clicks_norm = _normalize_metric(clicks)
    volumes_norm = _normalize_metric(volumes)

    for idx, row in enumerate(deduped):
        overlap_count = int(row.get("_overlap_count", 0))
        anchor_overlap_bonus = 0.15 if overlap_count >= 2 else 0.0
        score = (
            0.45 * impressions_norm[idx]
            + 0.35 * clicks_norm[idx]
            + 0.20 * volumes_norm[idx]
            + anchor_overlap_bonus
        )
        row["_relevance_score"] = round(score, 6)

        fallback.append(row)
        if not anchors or overlap_count >= 1:
            keep.append(row)
        else:
            reason_counts["anchor_mismatch"] = reason_counts.get("anchor_mismatch", 0) + 1

    keep.sort(
        key=lambda r: (
            float(r.get("_relevance_score", 0.0)),
            _metric_value(r, "total_clicks", "clicks"),
            _metric_value(r, "total_impressions", "impressions"),
        ),
        reverse=True,
    )
    fallback.sort(
        key=lambda r: (
            float(r.get("_relevance_score", 0.0)),
            _metric_value(r, "total_clicks", "clicks"),
            _metric_value(r, "total_impressions", "impressions"),
        ),
        reverse=True,
    )

    if len(keep) >= min_keep:
        curated = keep[:max_keep]
    else:
        curated = list(keep)
        for row in fallback:
            if row in curated:
                continue
            curated.append(row)
            if len(curated) >= min(max_keep, max(min_keep, len(fallback))):
                break

    cleaned_output: list[dict] = []
    for row in curated:
        item = dict(row)
        item.pop("_cleaned_tokens", None)
        item.pop("_overlap_count", None)
        item.pop("_relevance_score", None)
        cleaned_output.append(item)

    dropped_count = max(0, len(queries) - len(cleaned_output))
    top_reason = "none"
    if reason_counts:
        top_reason = max(reason_counts.items(), key=lambda kv: kv[1])[0]
    diagnostics = {
        "query_filter_kept_count": len(cleaned_output),
        "query_filter_dropped_count": dropped_count,
        "query_filter_reason_top": top_reason,
        "query_filter_noise_dropped": dropped_noise,
        "query_filter_duplicate_dropped": dropped_duplicates,
    }
    return cleaned_output, diagnostics


def filter_search_queries_by_relevance(
    queries: list[dict],
    anchor_terms: set[str] | None = None,
    *,
    min_keep: int = 3,
) -> list[dict]:
    """Filter and dedupe query insights to reduce off-intent prompt noise.

    The model should receive only query evidence that is likely relevant to the
    product category/custom_label intent cluster. We keep a small fallback set
    to avoid starving the prompt when anchor overlap is sparse.
    """
    curated, _diagnostics = curate_search_queries_by_relevance(
        queries,
        anchor_terms,
        min_keep=min_keep,
    )
    return curated


def fetch_search_queries_for_master_sku(
    master_sku: str,
    limit: int = 15,
    min_impressions: int = 10,
) -> list[dict]:
    """Fetch top search queries aggregated at master SKU level.

    Queries the search_queries_by_master_sku table which aggregates
    search terms across all variants of a master SKU.

    Args:
        master_sku: The master SKU to fetch queries for.
        limit: Maximum number of queries to return.
        min_impressions: Minimum total impressions threshold.

    Returns:
        List of dicts with query_text, total_impressions, total_clicks,
        avg_monthly_searches, and competition fields.
    """
    try:
        from feedops.db.supabase_client import get_client, is_supabase_available

        if not is_supabase_available():
            logger.debug("Supabase not available, skipping search query fetch")
            return []

        client = get_client()

        result = (
            client.table("search_queries_by_master_sku")
            .select(
                "query_text, total_impressions, total_clicks, "
                "avg_monthly_searches, competition"
            )
            .eq("master_sku", master_sku)
            .gte("total_impressions", min_impressions)
            .order("total_impressions", desc=True)
            .limit(limit)
            .execute()
        )

        return result.data if result.data else []

    except Exception as e:
        logger.warning(f"Failed to fetch search queries for {master_sku}: {e}")
        return []


def fetch_search_queries_for_variant(
    master_sku: str,
    finish_code: str,
    limit: int = 10,
) -> list[dict]:
    """Fetch search queries specific to a variant (finish).

    For Google/Bing variant-level content generation, fetches queries
    associated with specific finish codes.

    Args:
        master_sku: The master SKU.
        finish_code: The finish code (e.g., "PB", "SN").
        limit: Maximum number of queries to return.

    Returns:
        List of dicts with query_text, impressions, clicks fields.
    """
    try:
        from feedops.db.supabase_client import get_client, is_supabase_available

        if not is_supabase_available():
            logger.debug("Supabase not available, skipping variant query fetch")
            return []

        client = get_client()

        result = (
            client.table("search_queries")
            .select("query_text, impressions, clicks")
            .eq("master_sku", master_sku)
            .eq("finish_code", finish_code)
            .order("impressions", desc=True)
            .limit(limit)
            .execute()
        )

        return result.data if result.data else []

    except Exception as e:
        logger.warning(
            f"Failed to fetch variant queries for {master_sku}/{finish_code}: {e}"
        )
        return []


def fetch_variant_queries_for_master_sku(
    master_sku: str,
    limit: int = 120,
) -> list[dict]:
    """Fetch variant-level query rows across all finishes for a master SKU.

    This is used to build variant-aware query evidence without per-finish N+1 calls.
    """
    try:
        from feedops.db.supabase_client import get_client, is_supabase_available

        if not is_supabase_available():
            logger.debug("Supabase not available, skipping variant query fetch")
            return []

        client = get_client()
        result = (
            client.table("search_queries")
            .select("query_text, impressions, clicks, finish_code")
            .eq("master_sku", master_sku)
            .order("impressions", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data if result.data else []
    except Exception as e:
        logger.warning(f"Failed to fetch variant query pool for {master_sku}: {e}")
        return []


def format_search_queries_for_evidence(
    queries: list[dict],
    context: str = "master",
    max_rows: int | None = None,
) -> list["Evidence"]:
    """Convert search queries to Evidence rows for LLM prompt.

    Args:
        queries: List of query dicts from Supabase.
        context: Either "master" (SKU-level) or "variant" (finish-specific).

    Returns:
        List of Evidence rows to append to evidence table.
    """
    from feedops.pipeline.enrichment import Evidence

    if not queries:
        return []

    evidence_rows: list[Evidence] = []
    row_limit = max_rows if max_rows is not None else (12 if context == "master" else 6)

    if context == "master":
        # Format top queries with search volume when available
        query_parts: list[str] = []
        for q in queries[:row_limit]:
            text = q.get("query_text", "")
            if not text:
                continue

            volume = q.get("avg_monthly_searches")
            if volume and volume > 0:
                # Format with volume: "brass towel bar (2.4K vol)"
                if volume >= 1000:
                    vol_str = f"{volume / 1000:.1f}K"
                else:
                    vol_str = str(volume)
                query_parts.append(f'"{text}" ({vol_str} vol)')
            else:
                # No volume data, use impressions
                impressions = q.get("total_impressions", 0)
                if impressions >= 1000:
                    imp_str = f"{impressions / 1000:.1f}K"
                else:
                    imp_str = str(impressions)
                query_parts.append(f'"{text}" ({imp_str} imp)')

        if query_parts:
            evidence_rows.append(Evidence(
                field="search_queries_top",
                value=", ".join(query_parts),
                source="search_insights",
            ))

        # Extract themes from queries (material, style, function patterns)
        themes = _extract_query_themes(queries)
        if themes:
            evidence_rows.append(Evidence(
                field="search_query_themes",
                value=themes,
                source="search_insights",
            ))

    elif context == "variant":
        # Variant-specific queries (shorter format)
        query_parts: list[str] = []
        for q in queries[:row_limit]:
            text = q.get("query_text", "")
            if not text:
                continue
            impressions = q.get("impressions", q.get("total_impressions", 0))
            if impressions >= 1000:
                imp_str = f"{impressions / 1000:.1f}K"
            else:
                imp_str = str(impressions)
            finish_code = (q.get("finish_code") or "").strip()
            finish_suffix = f", {finish_code}" if finish_code else ""
            query_parts.append(f'"{text}" ({imp_str} imp{finish_suffix})')

        if query_parts:
            evidence_rows.append(Evidence(
                field="variant_top_queries",
                value=", ".join(query_parts),
                source="search_insights_variant",
            ))

    return evidence_rows


def _extract_query_themes(queries: list[dict]) -> str:
    """Extract common themes from search queries.

    Identifies patterns like:
    - Material mentions (brass, chrome, nickel)
    - Style mentions (antique, modern, vintage)
    - Function mentions (towel holder, grab bar)

    Returns a formatted string like:
    "Material: brass/gold, Style: antique/vintage, Function: towel holder"
    """
    # Material keywords
    materials = {"brass", "chrome", "nickel", "gold", "bronze", "copper", "stainless", "iron"}
    # Style keywords
    styles = {"antique", "modern", "vintage", "contemporary", "traditional", "classic", "rustic"}
    # Function/product type keywords
    functions = {
        "towel bar", "towel holder", "towel rack", "towel ring",
        "grab bar", "safety bar", "toilet paper holder", "tissue holder",
        "robe hook", "coat hook", "soap dish", "soap dispenser",
        "shelf", "mirror", "hardware", "bathroom accessories",
    }

    found_materials: set[str] = set()
    found_styles: set[str] = set()
    found_functions: set[str] = set()

    for q in queries:
        text = (q.get("query_text") or "").lower()

        # Check materials
        for mat in materials:
            if mat in text:
                found_materials.add(mat)

        # Check styles
        for style in styles:
            if style in text:
                found_styles.add(style)

        # Check functions (longer phrases first)
        for func in sorted(functions, key=len, reverse=True):
            if func in text:
                found_functions.add(func)
                break  # Only match one function per query

    theme_parts: list[str] = []

    if found_materials:
        theme_parts.append(f"Material: {'/'.join(sorted(found_materials)[:3])}")

    if found_styles:
        theme_parts.append(f"Style: {'/'.join(sorted(found_styles)[:2])}")

    if found_functions:
        theme_parts.append(f"Function: {'/'.join(sorted(found_functions)[:2])}")

    return ", ".join(theme_parts)


def get_search_insights_for_sku(master_sku: str) -> dict:
    """Get complete search insights summary for a SKU.

    Convenience function that combines queries and metrics.
    Useful for displaying on review pages.

    Args:
        master_sku: The master SKU to analyze.

    Returns:
        Dict with top_queries, themes, total_queries, total_impressions.
    """
    queries = fetch_search_queries_for_master_sku(master_sku, limit=20)

    if not queries:
        return {
            "top_queries": [],
            "themes": "",
            "total_queries": 0,
            "total_impressions": 0,
        }

    return {
        "top_queries": queries[:10],
        "themes": _extract_query_themes(queries),
        "total_queries": len(queries),
        "total_impressions": sum(q.get("total_impressions", 0) for q in queries),
    }
