"""Multi-SKU family detection for performance data validation.

Multi-SKU families occur when multiple master_skus share the same Shopify product_id.
This causes Google Ads to aggregate performance data at the product_id level, which
needs to be flagged (not rejected) when capturing baseline metrics.

Example: DMF-2/2X, DMF-2/3X, DMF-2/4X all share product_id 4539975336068.

See: docs/architecture/multi-sku-pattern.md
"""

from __future__ import annotations

import logging
from typing import Any

from feedops.db.supabase_client import get_client

logger = logging.getLogger(__name__)


def detect_multi_sku_families(master_skus: list[str]) -> dict[str, list[str]]:
    """Detect multi-SKU families in a batch of master SKUs.

    Multi-SKU families are groups of master_skus that share the same shopify_product_id.
    Google Ads aggregates performance at the product_id level, so these need special
    handling when collecting baseline metrics.

    Args:
        master_skus: List of master SKU IDs to check

    Returns:
        Dict mapping each master_sku in a multi-SKU family to its sibling SKUs.
        Example: {
            "DMF-2/2X": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X"],
            "DMF-2/3X": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X"],
            "DMF-2/4X": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X"]
        }

    Notes:
        - Uses variant_index to find product_ids
        - Returns empty dict if no multi-SKU families found
        - SKUs without families are not included in result
    """
    if not master_skus:
        return {}

    supabase = get_client()

    # Step 1: Get product_ids for all master_skus in the batch
    result = supabase.table("variant_index").select(
        "master_sku, shopify_product_id"
    ).in_("master_sku", master_skus).execute()

    if not result.data:
        return {}

    # Build mapping of master_sku -> product_id
    sku_to_product_id: dict[str, str] = {}
    for row in result.data:
        master_sku = row.get("master_sku")
        product_id = row.get("shopify_product_id")
        if master_sku and product_id:
            # Keep first occurrence (all variants have same product_id)
            if master_sku not in sku_to_product_id:
                sku_to_product_id[master_sku] = product_id

    # Get unique product_ids
    product_ids = list(set(sku_to_product_id.values()))

    if not product_ids:
        return {}

    # Step 2: Get ALL master_skus for these product_ids
    all_skus_result = supabase.table("variant_index").select(
        "master_sku, shopify_product_id"
    ).in_("shopify_product_id", product_ids).execute()

    # Build mapping of product_id -> list of master_skus
    product_to_skus: dict[str, set[str]] = {}
    for row in all_skus_result.data:
        master_sku = row.get("master_sku")
        product_id = row.get("shopify_product_id")
        if master_sku and product_id:
            if product_id not in product_to_skus:
                product_to_skus[product_id] = set()
            product_to_skus[product_id].add(master_sku)

    # Step 3: Identify multi-SKU families (product_ids with >1 distinct master_sku)
    families: dict[str, list[str]] = {}
    for product_id, skus in product_to_skus.items():
        if len(skus) > 1:
            # This is a multi-SKU family
            sorted_skus = sorted(list(skus))
            # Add mapping for each SKU in the family
            for sku in skus:
                families[sku] = sorted_skus

    logger.info(
        f"Detected {len(families)} SKUs in multi-SKU families "
        f"({len(set(tuple(v) for v in families.values()))} families)"
    )

    return families


def is_multi_sku_family(master_sku: str) -> bool:
    """Quick check if a single SKU belongs to a multi-SKU family.

    Args:
        master_sku: Master SKU ID to check

    Returns:
        True if this SKU shares its product_id with other master_skus

    Notes:
        - More efficient than detect_multi_sku_families for single SKU checks
        - Uses count query instead of fetching all variants
    """
    supabase = get_client()

    # Get the product_id for this master_sku
    result = supabase.table("variant_index").select(
        "shopify_product_id"
    ).eq("master_sku", master_sku).limit(1).execute()

    if not result.data or not result.data[0].get("shopify_product_id"):
        return False

    product_id = result.data[0]["shopify_product_id"]

    # Count distinct master_skus for this product_id
    count_result = supabase.table("variant_index").select(
        "master_sku", count="exact"
    ).eq("shopify_product_id", product_id).execute()

    # Get distinct count by fetching data and deduplicating
    # (Supabase doesn't support COUNT(DISTINCT) directly)
    if count_result.data:
        unique_skus = set(row["master_sku"] for row in count_result.data)
        return len(unique_skus) > 1

    return False


def get_family_metadata(master_sku: str, family_members: list[str]) -> dict[str, Any]:
    """Generate metadata dict for multi-SKU family flagging.

    This metadata is stored in performance_baselines.metadata JSONB column
    to flag when performance data is aggregated at product_id level.

    Args:
        master_sku: The SKU being processed
        family_members: All SKUs in the family (including master_sku)

    Returns:
        Dict suitable for storing in JSONB metadata column:
        {
            "is_multi_sku_family": True,
            "family_members": ["DMF-2/2X", "DMF-2/3X", "DMF-2/4X"],
            "family_size": 3,
            "data_aggregation": "product_id_level"
        }

    Notes:
        - Used to document that metrics are shared across family
        - Helps with interpretation during analysis
        - family_members should be sorted for consistency
    """
    return {
        "is_multi_sku_family": True,
        "family_members": sorted(family_members),
        "family_size": len(family_members),
        "data_aggregation": "product_id_level",
    }
