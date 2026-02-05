"""Search query insights integration for evidence table.

This module fetches search queries from Supabase (collected via Google Ads
search_term_view) and formats them as Evidence rows for LLM prompts.

The search data helps the LLM naturally incorporate high-volume keywords
that customers actually use when searching.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from feedops.pipeline.enrichment import Evidence

logger = logging.getLogger(__name__)


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


def format_search_queries_for_evidence(
    queries: list[dict],
    context: str = "master",
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

    if context == "master":
        # Format top queries with search volume when available
        query_parts: list[str] = []
        for q in queries[:10]:  # Top 10 for evidence
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
        for q in queries[:5]:  # Top 5 for variants
            text = q.get("query_text", "")
            if not text:
                continue
            impressions = q.get("impressions", 0)
            if impressions >= 1000:
                imp_str = f"{impressions / 1000:.1f}K"
            else:
                imp_str = str(impressions)
            query_parts.append(f'"{text}" ({imp_str} imp)')

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
