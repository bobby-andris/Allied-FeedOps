"""Helpers for merging variant-level truth across data sources."""

from __future__ import annotations

from feedops.models.parent_sku import ParentSKU


def merge_catalog_variant_truth(shopify_parent: ParentSKU, catalog_parent: ParentSKU) -> ParentSKU:
    """Merge CSV variant truth (dimensions, bullets) into a Shopify-derived ParentSKU.

    Keep Shopify as the source of truth for current on-site title/description, while
    ensuring we have reliable per-variant dimensions (from the catalog) for size tables
    and sizing guardrails.
    """
    gmc_ids = {v.gmc_id for v in shopify_parent.variants if v.gmc_id}
    catalog_variants = catalog_parent.variants
    if gmc_ids:
        filtered = [v for v in catalog_variants if v.gmc_id in gmc_ids]
        if filtered:
            catalog_variants = filtered

    merged = catalog_parent.model_copy(deep=True)
    merged = merged.model_copy(
        update={
            # Prefer curated catalog classification when present.
            "category": catalog_parent.category or shopify_parent.category,
            "collection": catalog_parent.collection or shopify_parent.collection,
            # Preserve Shopify current content.
            "current_title": shopify_parent.current_title,
            "current_description": shopify_parent.current_description,
            # Prefer Shopify material when available (often metafield-driven).
            "material": shopify_parent.material or catalog_parent.material,
            "variants": catalog_variants,
            "merchant_center_items": shopify_parent.merchant_center_items,
            "data_source": (
                f"{(shopify_parent.data_source or 'shopify')}" + "+csv_variant_truth"
            ),
        }
    )
    return merged

