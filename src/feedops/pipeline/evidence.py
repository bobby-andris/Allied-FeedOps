"""Evidence table builder for LLM prompts."""
import re
from feedops.models import ParentSKU
from feedops.integrations.keyword_bank import get_external_keywords
from feedops.integrations.google_ads import fetch_master_sku_keywords
# Import Evidence from enrichment to avoid duplication
from feedops.pipeline.enrichment import Evidence, enrich_product


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
        finishes = ", ".join(v.finish for v in parent_sku.variants)
        evidence.append(Evidence(
            field="available_finishes",
            value=finishes,
            source="available_finishes",  # Use attribute name for verifier compatibility
        ))

        # Add first variant dimensions as representative
        first_variant = parent_sku.variants[0]
        variant_fields = [
            ("product_length", "Length"),
            ("product_height", "Height"),
            ("product_width", "Width"),
            ("projection", "Projection"),
            ("product_weight", "Weight"),
            ("gtin", "GTIN"),
            ("upc", "UPC"),
            ("main_image_url", "Main Image URL"),
        ]
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
