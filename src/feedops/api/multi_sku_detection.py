"""
Multi-SKU Product Detection

Identifies product families where multiple master_skus share the same Shopify product_id.
Example: DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share product_id 4539975336068

Python port of dashboard/src/lib/multi-sku-detection.ts
"""

from dataclasses import dataclass
from typing import Optional
import re


@dataclass
class MultiSkuFamily:
    """Represents a product family with multiple SKU variants"""

    product_id: str
    master_skus: list[str]
    base_sku: str  # Typically the lowest variant (e.g., DMF-2/2X)
    variant_skus: list[str]  # Related SKUs that need adaptation


def extract_product_id(offer_id: str) -> Optional[str]:
    """
    Extract Shopify product_id from GMC offer_id.

    Format: shopify_us_{product_id}_{variant_id}
    Example: shopify_us_4539975336068_32103134298244 → 4539975336068
    """
    parts = offer_id.split("_")
    return parts[2] if len(parts) >= 4 else None


def get_related_master_skus(supabase, master_sku: str) -> list[str]:
    """
    Get all master_skus that share the same product_id as the given SKU.

    Args:
        supabase: Supabase client instance
        master_sku: The SKU to find related SKUs for

    Returns:
        List of master_skus sharing the same product_id (sorted alphabetically)
    """
    # Query variant_index for this SKU's offer_id
    variant_result = (
        supabase.table("variant_index")
        .select("gmc_offer_id")
        .eq("master_sku", master_sku)
        .limit(1)
        .execute()
    )

    if not variant_result.data:
        return [master_sku]

    product_id = extract_product_id(variant_result.data[0]["gmc_offer_id"])
    if not product_id:
        return [master_sku]

    # Find all SKUs with the same product_id
    related_result = (
        supabase.table("variant_index")
        .select("master_sku, gmc_offer_id")
        .ilike("gmc_offer_id", f"shopify_us_{product_id}_%")
        .execute()
    )

    if not related_result.data:
        return [master_sku]

    # Get unique master_skus
    unique_skus = sorted(set(v["master_sku"] for v in related_result.data))
    return unique_skus


def detect_multi_sku_families(supabase, master_skus: list[str]) -> list[MultiSkuFamily]:
    """
    Detect multi-SKU product families in a list of SKUs.

    Args:
        supabase: Supabase client instance
        master_skus: List of master SKUs to analyze

    Returns:
        List of MultiSkuFamily objects for products with multiple SKUs
    """
    families = []
    processed = set()

    for sku in master_skus:
        if sku in processed:
            continue

        related_skus = get_related_master_skus(supabase, sku)

        if len(related_skus) > 1:
            # Multi-SKU family detected
            variant_result = (
                supabase.table("variant_index")
                .select("gmc_offer_id")
                .eq("master_sku", related_skus[0])
                .limit(1)
                .execute()
            )

            product_id = (
                extract_product_id(variant_result.data[0]["gmc_offer_id"])
                if variant_result.data
                else "unknown"
            )

            # Base SKU is first alphabetically (e.g., DMF-2/2X before DMF-2/3X)
            base_sku = related_skus[0]
            variant_skus = related_skus[1:]

            families.append(
                MultiSkuFamily(
                    product_id=product_id,
                    master_skus=related_skus,
                    base_sku=base_sku,
                    variant_skus=variant_skus,
                )
            )

            # Mark all related SKUs as processed
            processed.update(related_skus)
        else:
            # Single-SKU product (no adaptation needed)
            processed.add(sku)

    return families


def is_multi_sku_product(supabase, master_sku: str) -> bool:
    """
    Check if a SKU is part of a multi-SKU family.

    Args:
        supabase: Supabase client instance
        master_sku: The SKU to check

    Returns:
        True if the SKU is part of a multi-SKU family, False otherwise
    """
    related_skus = get_related_master_skus(supabase, master_sku)
    return len(related_skus) > 1


def get_base_sku(supabase, master_sku: str) -> str:
    """
    Get the base SKU for a given variant SKU.

    Args:
        supabase: Supabase client instance
        master_sku: The variant SKU

    Returns:
        The base SKU (first alphabetically in the family)
    """
    related_skus = get_related_master_skus(supabase, master_sku)
    return related_skus[0]  # First alphabetically is the base


def extract_spec_difference(base_sku: str, variant_sku: str) -> tuple[str, str]:
    """
    Extract specification difference from SKU names.

    Finds numeric/spec differences like 2X vs 5X, 16-GAL vs 22-GAL, etc.

    Args:
        base_sku: The base SKU (e.g., "DMF-2/2X")
        variant_sku: The variant SKU (e.g., "DMF-2/5X")

    Returns:
        Tuple of (base_spec, variant_spec), e.g., ("2X", "5X")

    Example:
        extract_spec_difference("DMF-2/2X", "DMF-2/5X") → ("2X", "5X")
        extract_spec_difference("WP-2/16-GAL", "WP-2/22-GAL") → ("16", "22")
    """
    # Try to find numeric differences like 2X, 3X, 5X, 16-GAL, etc.
    pattern = r"(\d+(?:\.\d+)?[A-Z]*)"
    base_matches = re.findall(pattern, base_sku)
    variant_matches = re.findall(pattern, variant_sku)

    if base_matches and variant_matches:
        # Find the differing spec
        for i in range(min(len(base_matches), len(variant_matches))):
            if base_matches[i] != variant_matches[i]:
                return base_matches[i], variant_matches[i]

    # Fallback: return full SKU names
    return base_sku, variant_sku
