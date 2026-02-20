"""Evidence table builder for LLM prompts."""
import logging
import re
from feedops.models import ParentSKU
from feedops.integrations.keyword_bank import get_external_keywords
from feedops.integrations.google_ads import fetch_master_sku_keywords
from feedops.integrations.search_query_insights import (
    build_relevance_anchor_terms,
    curate_search_queries_by_relevance,
    fetch_search_queries_for_master_sku,
    fetch_variant_queries_for_master_sku,
    filter_search_queries_by_relevance,
    format_search_queries_for_evidence,
)
# Import Evidence from enrichment to avoid duplication
from feedops.pipeline.enrichment import Evidence, enrich_product
from feedops.pipeline.collection_descriptions import (
    get_collection_description,
    is_known_collection_name,
    sanitize_collection_description,
)
from feedops.pipeline.segment_strategy import resolve_segment_strategy
from feedops.pipeline.size_matrix import build_size_matrix
from feedops.pipeline.feature_flags import (
    is_intent_curator_v1_enabled,
    is_segment_strategy_v1_enabled,
)

logger = logging.getLogger(__name__)


_WORD_RE = re.compile(r"[a-z0-9]+")
_FINISH_MODIFIERS = {
    # Common finish adjectives/modifiers (not finish identifiers on their own).
    "antique",
    "brushed",
    "matte",
    "oil",
    "polished",
    "rubbed",
    "satin",
    "shaded",
    "spanish",
    "unlacquered",
    "venetian",
}


def _tokenize(text: str) -> list[str]:
    return _WORD_RE.findall((text or "").lower())


def _normalize_phrase(text: str) -> str:
    return " ".join(_tokenize(text))


def _dedupe_phrases(phrases: list[str]) -> list[str]:
    """Dedupe phrases by normalized form, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for p in phrases:
        p = str(p).strip()
        if not p:
            continue
        key = _normalize_phrase(p)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _build_finish_filters(parent_sku: ParentSKU) -> tuple[set[str], set[str]]:
    """Return (finish_phrases, finish_tokens) used to exclude finish-specific keywords."""
    finishes = [v.finish for v in parent_sku.variants if v.finish]
    finish_phrases = {_normalize_phrase(f) for f in finishes if _normalize_phrase(f)}

    material_tokens = set(_tokenize(parent_sku.material or ""))
    finish_tokens: set[str] = set()
    for f in finishes:
        tokens = [t for t in _tokenize(f) if t and t not in _FINISH_MODIFIERS]
        finish_tokens.update(tokens)

    # Don't treat material as "finish-specific" (e.g., keep "brass towel bar").
    finish_tokens.difference_update(material_tokens)
    return finish_phrases, finish_tokens


def _is_finish_specific_keyword(
    keyword: str,
    finish_phrases: set[str],
    finish_tokens: set[str],
) -> bool:
    normalized = _normalize_phrase(keyword)
    if normalized and any(fp in normalized for fp in finish_phrases):
        return True
    tokens = set(_tokenize(keyword))
    return bool(tokens & finish_tokens)


def _extract_custom_label_0_values(parent_sku: ParentSKU) -> list[str]:
    """Extract unique custom_label_0 values from Merchant Center payloads.

    Supports both normalized keys (customLabel0/custom_label_0) and nested
    attribute payloads used by some loaders.
    """
    seen: set[str] = set()
    values: list[str] = []
    for item in parent_sku.merchant_center_items or []:
        raw = item.get("customLabel0") or item.get("custom_label_0")
        if not raw and isinstance(item.get("attributes"), dict):
            attrs = item["attributes"]
            raw = attrs.get("customLabel0") or attrs.get("custom_label_0")
        if not raw and isinstance(item.get("custom_labels"), dict):
            labels = item["custom_labels"]
            raw = labels.get("customLabel0") or labels.get("custom_label_0")
        value = str(raw or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
    return values


def _format_number(value: object) -> str:
    """Format numeric values for evidence (avoid 18.0-style noise)."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    # Some loader paths may return numeric strings.
    try:
        f = float(str(value))
        if f.is_integer():
            return str(int(f))
        return str(f)
    except Exception:
        return str(value)


_INCH_FIELDS = {
    "center_to_center",
    "diameter",
    "mirror_height",
    "mirror_width",
    "thickness",
    "product_length",
    "product_height",
    "product_width",
    "projection",
}

_POUND_FIELDS = {
    "weight_capacity",
    "product_weight",
}


# Evidence class is now imported from enrichment.py


def build_evidence_table(parent_sku: ParentSKU) -> list[Evidence]:
    """Convert ParentSKU to structured evidence table.

    Args:
        parent_sku: The parent SKU with all variants.

    Returns:
        List of Evidence rows for prompt injection.
    """
    evidence = []

    # Add ParentSKU fields
    parent_fields = [
        ("master_sku", "MasterSKU"),
        ("category", "Category"),
        ("collection", "Collection"),
        ("current_title", "Current Title"),
        ("current_description", "Current Description"),
        ("material", "Material"),
        ("style", "Style"),
        ("shape", "Shape"),
        ("orientation", "Orientation"),
        ("tilting", "Tilting"),
        ("mounting_type", "Mounting Type"),
        ("assembly_required", "Assembly Required"),
        ("center_to_center", "Center to Center"),
        ("diameter", "Diameter"),
        ("screw_size", "Screw Size"),
        ("mirror_height", "Mirror Height"),
        ("mirror_width", "Mirror Width"),
        ("thickness", "Thickness"),
        ("weight_capacity", "Weight Capacity"),
        ("included_items", "Included"),
        ("bullet_1", "Bullet 1"),
        ("bullet_2", "Bullet 2"),
        ("bullet_3", "Bullet 3"),
        ("bullet_4", "Bullet 4"),
        ("bullet_5", "Bullet 5"),
        ("bullet_6", "Bullet 6"),
    ]

    for field_name, display_name in parent_fields:
        value = getattr(parent_sku, field_name, None)
        if field_name == "collection" and not is_known_collection_name(value):
            continue
        if value is not None and value != "":
            formatted = str(value)
            if field_name in _INCH_FIELDS:
                formatted = f"{_format_number(value)} in"
            if field_name in _POUND_FIELDS:
                formatted = f"{_format_number(value)} lb"
            evidence.append(Evidence(
                field=field_name,
                value=formatted,
                source=field_name,  # Use attribute name for verifier compatibility
            ))

    # Add finish options from variants
    if parent_sku.variants:
        seen_finishes: set[str] = set()
        finishes_list: list[str] = []
        for v in parent_sku.variants:
            finish = (v.finish or "").strip()
            if not finish:
                continue
            key = finish.casefold()
            if key in seen_finishes:
                continue
            seen_finishes.add(key)
            finishes_list.append(finish)
        finishes = ", ".join(finishes_list)
        evidence.append(Evidence(
            field="available_finishes",
            value=finishes,
            source="available_finishes",  # Use attribute name for verifier compatibility
        ))

        # For multi-size products, avoid injecting a single variant's length/height/width
        # as if it applies to the entire family. Instead, provide an explicit size list.
        size_matrix = build_size_matrix(parent_sku)
        if size_matrix:
            sizes = [row.get("size_label") for row in size_matrix if row.get("size_label")]
            if sizes:
                evidence.append(
                    Evidence(
                        field="available_sizes",
                        value=", ".join(sizes),
                        source="available_sizes",
                    )
                )

        # Add first variant identifiers/images as representative. Only include dimensions
        # when the product is not multi-size.
        first_variant = parent_sku.variants[0]
        variant_fields: list[tuple[str, str]] = [
            ("gtin", "GTIN"),
            ("upc", "UPC"),
            ("main_image_url", "Main Image URL"),
        ]
        if not size_matrix:
            variant_fields = [
                ("product_length", "Length"),
                ("product_height", "Height"),
                ("product_width", "Width"),
                ("projection", "Projection"),
                ("product_weight", "Weight"),
            ] + variant_fields
        for field_name, display_name in variant_fields:
            value = getattr(first_variant, field_name, None)
            if value is not None:
                formatted = str(value)
                if field_name in _INCH_FIELDS:
                    formatted = f"{_format_number(value)} in"
                if field_name in _POUND_FIELDS:
                    formatted = f"{_format_number(value)} lb"
                evidence.append(Evidence(
                    field=field_name,
                    value=formatted,
                    source=field_name,  # Use attribute name for verifier compatibility
                ))

    custom_label_0_values = _extract_custom_label_0_values(parent_sku)
    if custom_label_0_values:
        evidence.append(
            Evidence(
                field="custom_label_0",
                value=", ".join(custom_label_0_values),
                source="merchant_center_items.customLabel0",
            )
        )

    if is_known_collection_name(parent_sku.collection):
        collection_desc = get_collection_description(parent_sku.collection)
        if collection_desc:
            cleaned_collection_desc = sanitize_collection_description(collection_desc)
            if cleaned_collection_desc:
                evidence.append(
                    Evidence(
                        field="collection_description",
                        value=cleaned_collection_desc,
                        source="collection_descriptions_csv",
                    )
                )

    # Optional: add high-performing keywords from Google Ads MCP (if available)
    item_ids = [v.item_id for v in parent_sku.variants] if parent_sku.variants else []
    ads_keywords = fetch_master_sku_keywords(
        parent_sku.item_group_id,
        item_ids=item_ids,
        category=parent_sku.category,
    )

    # Optional: external keyword bank phrases (e.g., Apify SERP/Shopping research)
    external_keywords = get_external_keywords(
        category=parent_sku.category,
        master_sku=parent_sku.master_sku,
    )
    if external_keywords:
        evidence.append(Evidence(
            field="external_keywords",
            value=", ".join(external_keywords),
            source="keyword_bank",
        ))

    # MasterSKU-level keyword intent: aggregate across all variants and exclude finish-specific terms.
    keyword_candidates = _dedupe_phrases(list(ads_keywords or []) + list(external_keywords or []))
    if keyword_candidates:
        finish_phrases, finish_tokens = _build_finish_filters(parent_sku)
        filtered = [
            k for k in keyword_candidates
            if not _is_finish_specific_keyword(k, finish_phrases, finish_tokens)
        ]
        if filtered:
            evidence.append(Evidence(
                field="keyword_intent_master",
                value=", ".join(filtered),
                source="keyword_intent_master",
            ))

    segment_strategy_enabled = is_segment_strategy_v1_enabled()
    segment_strategy = resolve_segment_strategy(
        custom_label_0_values,
        enabled=segment_strategy_enabled,
    )

    # Search query insights: actual search terms customers use (from Google Ads)
    search_queries: list[dict] = []
    search_queries_for_keyword_gaps: list[dict] = []
    try:
        anchor_terms = build_relevance_anchor_terms(
            parent_sku.category,
            parent_sku.current_title,
            parent_sku.material,
            parent_sku.mounting_type,
            ", ".join(custom_label_0_values),
        )
        master_query_rows = fetch_search_queries_for_master_sku(
            parent_sku.master_sku, limit=40
        )
        variant_query_rows = fetch_variant_queries_for_master_sku(
            parent_sku.master_sku, limit=120
        )
        if is_intent_curator_v1_enabled():
            search_queries, master_diagnostics = curate_search_queries_by_relevance(
                master_query_rows,
                anchor_terms,
                min_keep=3,
                max_keep=12,
            )
            search_queries_for_keyword_gaps = list(search_queries)
            variant_queries, variant_diagnostics = curate_search_queries_by_relevance(
                variant_query_rows,
                anchor_terms,
                min_keep=3,
                max_keep=6,
            )
        else:
            search_queries = filter_search_queries_by_relevance(
                master_query_rows,
                anchor_terms,
                min_keep=3,
            )[:12]
            search_queries_for_keyword_gaps = list(search_queries)
            variant_queries = filter_search_queries_by_relevance(
                variant_query_rows,
                anchor_terms,
                min_keep=3,
            )[:6]
            master_diagnostics = {
                "query_filter_kept_count": len(search_queries),
                "query_filter_dropped_count": max(
                    0, len(master_query_rows) - len(search_queries)
                ),
                "query_filter_reason_top": "legacy_filter",
            }
            variant_diagnostics = {
                "query_filter_kept_count": len(variant_queries),
                "query_filter_dropped_count": max(
                    0, len(variant_query_rows) - len(variant_queries)
                ),
                "query_filter_reason_top": "legacy_filter",
            }

        def _inject_segment_fallback(
            rows: list[dict],
            *,
            max_keep: int,
            impression_key: str,
        ) -> list[dict]:
            if len(rows) >= 3:
                return rows[:max_keep]
            seen = {_normalize_phrase(str(r.get("query_text", ""))) for r in rows}
            for fallback in segment_strategy.fallback_queries:
                norm = _normalize_phrase(fallback)
                if not norm or norm in seen:
                    continue
                rows.append(
                    {
                        "query_text": fallback,
                        impression_key: 0,
                        "total_clicks": 0,
                        "avg_monthly_searches": 0,
                    }
                )
                seen.add(norm)
                if len(rows) >= max_keep:
                    break
            return rows

        if segment_strategy_enabled and segment_strategy.fallback_queries:
            search_queries = _inject_segment_fallback(
                search_queries, max_keep=12, impression_key="total_impressions"
            )
            variant_queries = _inject_segment_fallback(
                variant_queries, max_keep=6, impression_key="impressions"
            )

        if search_queries:
            evidence.extend(
                format_search_queries_for_evidence(
                    search_queries,
                    "master",
                    max_rows=12,
                )
            )
        if variant_queries:
            evidence.extend(
                format_search_queries_for_evidence(
                    variant_queries,
                    "variant",
                    max_rows=6,
                )
            )

        kept_count = int(master_diagnostics.get("query_filter_kept_count", 0)) + int(
            variant_diagnostics.get("query_filter_kept_count", 0)
        )
        dropped_count = int(
            master_diagnostics.get("query_filter_dropped_count", 0)
        ) + int(variant_diagnostics.get("query_filter_dropped_count", 0))
        master_dropped = int(master_diagnostics.get("query_filter_dropped_count", 0))
        variant_dropped = int(variant_diagnostics.get("query_filter_dropped_count", 0))
        if master_dropped >= variant_dropped:
            reason_top = f"master:{master_diagnostics.get('query_filter_reason_top', 'none')}"
        else:
            reason_top = f"variant:{variant_diagnostics.get('query_filter_reason_top', 'none')}"

        evidence.extend(
            [
                Evidence(
                    field="query_filter_kept_count",
                    value=str(kept_count),
                    source="search_insights_diagnostics",
                ),
                Evidence(
                    field="query_filter_dropped_count",
                    value=str(dropped_count),
                    source="search_insights_diagnostics",
                ),
                Evidence(
                    field="query_filter_reason_top",
                    value=reason_top,
                    source="search_insights_diagnostics",
                ),
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to fetch search queries: {e}")

    # Keyword gaps: high-volume category-relevant terms missing from the current title.
    # Search-intent guidance only (not product specification claims).
    try:
        if search_queries_for_keyword_gaps:
            from feedops.pipeline.keyword_gaps import build_keyword_gap_evidence_rows

            evidence.extend(
                build_keyword_gap_evidence_rows(parent_sku, search_queries_for_keyword_gaps)
            )
    except Exception as e:
        logger.warning(f"Failed to build keyword gap evidence: {e}")

    # Competitor evidence: category language patterns and source mix.
    # Strictly sanitized to avoid speculative "better than competitors" phrasing.
    try:
        if parent_sku.category:
            from feedops.pipeline.competitor_evidence import (
                build_competitor_evidence,
                build_competitor_evidence_rows,
            )

            competitor = build_competitor_evidence(parent_sku.category)
            evidence.extend(build_competitor_evidence_rows(competitor))
    except Exception as e:
        logger.warning(f"Failed to build competitor evidence: {e}")

    # On-the-fly enrichment: design context, functional features, competitive positioning
    enrichment = enrich_product(parent_sku)
    evidence.extend(enrichment.to_evidence_rows())

    return evidence


def format_evidence_markdown(evidence: list[Evidence]) -> str:
    """Format evidence as markdown table for prompt.

    Args:
        evidence: List of Evidence rows.

    Returns:
        Markdown table string.
    """
    lines = [
        "## Available Product Data",
        "",
        "| Attribute | Value | Source |",
        "|-----------|-------|--------|",
    ]

    for e in evidence:
        # Escape pipe characters in values
        value = str(e.value).replace("|", "\\|")
        lines.append(f"| {e.field} | {value} | {e.source} |")

    return "\n".join(lines)
