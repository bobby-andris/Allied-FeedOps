"""Evidence table builder for LLM prompts."""
from dataclasses import dataclass
from feedops.models import ParentSKU


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
            evidence.append(Evidence(
                field=field_name,
                value=str(value),
                source=f"catalog_csv.{display_name}",
            ))

    # Add finish options from variants
    if parent_sku.variants:
        finishes = ", ".join(v.finish for v in parent_sku.variants)
        evidence.append(Evidence(
            field="available_finishes",
            value=finishes,
            source="catalog_csv.Finish (variants)",
        ))

        # Add first variant dimensions as representative
        first_variant = parent_sku.variants[0]
        variant_fields = [
            ("product_length", "Length"),
            ("product_height", "Height"),
            ("product_width", "Width"),
            ("projection", "Projection"),
            ("product_weight", "Weight"),
        ]
        for field_name, display_name in variant_fields:
            value = getattr(first_variant, field_name, None)
            if value is not None:
                evidence.append(Evidence(
                    field=field_name,
                    value=str(value),
                    source=f"catalog_csv.{display_name}",
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
        # Truncate long values
        if len(value) > 80:
            value = value[:77] + "..."
        lines.append(f"| {e.field} | {value} | {e.source} |")

    return "\n".join(lines)
