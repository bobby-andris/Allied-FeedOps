"""Load product data from Supabase product_catalog table.

This module provides functions to load ParentSKU objects from Supabase
instead of CSV files, enabling the API to run without bundling product data.
"""

from __future__ import annotations

import logging

from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.db.supabase_client import get_client
from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant

logger = logging.getLogger(__name__)


def _normalize_custom_labels(value) -> dict[str, str | None]:
    """Normalize variant_index.custom_labels payload into canonical camel-case keys."""
    if not isinstance(value, dict):
        return {}

    out: dict[str, str | None] = {}
    aliases = {
        "customLabel0": ("customLabel0", "custom_label_0"),
        "customLabel1": ("customLabel1", "custom_label_1"),
        "customLabel2": ("customLabel2", "custom_label_2"),
        "customLabel3": ("customLabel3", "custom_label_3"),
        "customLabel4": ("customLabel4", "custom_label_4"),
    }
    for canonical, keys in aliases.items():
        raw = None
        for key in keys:
            if key in value:
                raw = value.get(key)
                break
        cleaned = str(raw).strip() if raw not in (None, "") else None
        out[canonical] = cleaned if cleaned else None
    return out


def _load_custom_labels_from_variant_index(client, master_sku: str) -> list[dict]:
    """Load Merchant Center-like custom label payloads from variant_index."""
    try:
        result = (
            client.table("variant_index")
            .select("gmc_offer_id,custom_labels")
            .eq("master_sku", master_sku)
            .execute()
        )
    except Exception as exc:
        logger.warning("Failed loading custom labels from variant_index: %s", exc)
        return []

    rows = result.data or []
    merchant_center_items: list[dict] = []
    for row in rows:
        labels = _normalize_custom_labels(row.get("custom_labels"))
        if not any(labels.values()):
            continue
        merchant_center_items.append(
            {
                "offerId": row.get("gmc_offer_id"),
                **labels,
            }
        )
    return merchant_center_items


def load_parent_sku_from_supabase(master_sku: str) -> ParentSKU | None:
    """Load ParentSKU from Supabase product_catalog table.

    Args:
        master_sku: The master SKU to load (e.g., "1051").

    Returns:
        ParentSKU object with all variants, or None if not found.
    """
    client = get_client()
    canonical_master_sku = resolve_canonical_master_sku(client, master_sku)

    result = (
        client.table("product_catalog")
        .select("*")
        .eq("master_sku", canonical_master_sku)
        .order("position", desc=False)
        .execute()
    )

    if not result.data:
        logger.warning(f"SKU not found in product_catalog: {canonical_master_sku}")
        return None

    rows = result.data
    first = rows[0]

    # Build variants from all rows
    variants: list[Variant] = []
    for row in rows:
        # gmc_id is required in Variant model - use empty string if missing
        gmc_id = row.get("gmc_id") or ""

        variants.append(
            Variant(
                option_sku=row["option_sku"],
                finish=row["finish_name"],
                finish_code=row["finish_code"],
                gmc_id=gmc_id,
                upc=row.get("upc"),
                gtin=row.get("gtin"),
                amazon_asin=row.get("amazon_asin"),
                position=row.get("position") or 0,
                # Dimensions
                product_length=_to_float(row.get("product_length")),
                product_height=_to_float(row.get("product_height")),
                product_width=_to_float(row.get("product_width")),
                projection=_to_float(row.get("projection")),
                product_weight=_to_float(row.get("product_weight")),
                # Shipping (box dimensions)
                shipping_length=_to_float(row.get("box_length")),
                shipping_height=_to_float(row.get("box_height")),
                shipping_width=_to_float(row.get("box_width")),
                shipping_weight=_to_float(row.get("box_weight")),
                # Images
                main_image=row.get("main_image_filename"),
                main_image_url=row.get("main_image_url"),
                alt_image_1=row.get("alt_image_1"),
                alt_image_2=row.get("alt_image_2"),
                alt_image_3=row.get("alt_image_3"),
                alt_image_4=row.get("alt_image_4"),
            )
        )

    # Build ParentSKU from first row (shared fields) + all variants
    parent = ParentSKU(
        master_sku=canonical_master_sku,
        core_sku=first.get("core_sku"),
        category=first["category"],
        collection=first.get("collection"),
        style=first.get("style"),
        current_title=first["title"],
        current_description=first.get("narrative_copy") or first["title"],
        # Bullets
        bullet_1=first.get("bullet_1"),
        bullet_2=first.get("bullet_2"),
        bullet_3=first.get("bullet_3"),
        bullet_4=first.get("bullet_4"),
        bullet_5=first.get("bullet_5"),
        bullet_6=first.get("bullet_6"),
        # Specifications
        material=first.get("material"),
        shape=first.get("shape"),
        orientation=first.get("orientation"),
        tilting=first.get("tilting"),
        mounting_type=first.get("mounting_type"),
        assembly_required=first.get("assembly_required"),
        # Dimensions (product-level)
        center_to_center=_to_float(first.get("center_to_center")),
        diameter=_to_float(first.get("diameter")),
        screw_size=first.get("screw_size"),
        mirror_height=_to_float(first.get("mirror_height")),
        mirror_width=_to_float(first.get("mirror_width")),
        thickness=_to_float(first.get("thickness")),
        weight_capacity=_to_float(first.get("weight_capacity")),
        # Documents
        installation_url=first.get("installation_url"),
        specification_url=first.get("specification_url"),
        # Included items
        included_items=first.get("included_items"),
        item_number=first.get("item_number"),
        # Variants
        variants=variants,
        merchant_center_items=_load_custom_labels_from_variant_index(
            client, canonical_master_sku
        ),
        # Data source
        data_source="supabase",
    )

    logger.info(f"Loaded {canonical_master_sku} from Supabase: {len(variants)} variants")
    return parent


def get_product_catalog_count() -> int:
    """Get total count of rows in product_catalog table.

    Returns:
        Number of rows in product_catalog table.
    """
    client = get_client()
    result = client.table("product_catalog").select("id", count="exact").limit(1).execute()
    return result.count or 0


def _to_float(value) -> float | None:
    """Convert a value to float, handling None and Decimal."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
