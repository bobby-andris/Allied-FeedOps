"""Evidence table builder for LLM prompts."""
from dataclasses import dataclass
from feedops.models import ParentSKU
from feedops.integrations.google_ads import fetch_high_performing_keywords
from feedops.integrations.keyword_bank import get_external_keywords


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


@dataclass
class Evidence:
    """A single evidence row for the LLM prompt."""
    field: str
    value: str
    source: str


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
    keywords = fetch_high_performing_keywords(parent_sku.category)
    if keywords:
        evidence.append(Evidence(
            field="high_performing_keywords",
            value=", ".join(keywords),
            source="google_ads_mcp",
        ))

    # Optional: external keyword bank phrases (e.g., Apify SERP/Shopping research)
    external_keywords = get_external_keywords(parent_sku.category)
    if external_keywords:
        evidence.append(Evidence(
            field="external_keywords",
            value=", ".join(external_keywords),
            source="keyword_bank",
        ))

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
