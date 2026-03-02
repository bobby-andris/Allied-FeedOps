"""
Multi-SKU Product Detection

Identifies product families where multiple master_skus share the same Shopify product_id.
Example: DMF-2/2X, DMF-2/3X, DMF-2/4X, DMF-2/5X all share product_id 4539975336068

Python port of dashboard/src/lib/multi-sku-detection.ts
"""

from dataclasses import dataclass, field
from typing import Optional
import re
import logging

from feedops.api.sku_alias import resolve_canonical_master_sku

logger = logging.getLogger(__name__)


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
    canonical_master_sku = resolve_canonical_master_sku(
        supabase,
        master_sku,
        tables=("variant_index",),
    )

    # Query variant_index for this SKU's offer_id
    variant_result = (
        supabase.table("variant_index")
        .select("gmc_offer_id")
        .eq("master_sku", canonical_master_sku)
        .limit(1)
        .execute()
    )

    if not variant_result.data:
        return [canonical_master_sku]

    product_id = extract_product_id(variant_result.data[0]["gmc_offer_id"])
    if not product_id:
        return [canonical_master_sku]

    # Find all SKUs with the same product_id
    related_result = (
        supabase.table("variant_index")
        .select("master_sku, gmc_offer_id")
        .ilike("gmc_offer_id", f"shopify_us_{product_id}_%")
        .execute()
    )

    if not related_result.data:
        return [canonical_master_sku]

    # Get unique master_skus
    unique_skus = sorted(set(v["master_sku"] for v in related_result.data))
    return unique_skus


def extract_sku_prefix(master_sku: str) -> Optional[tuple[str, str]]:
    """
    Extract a family prefix and spec suffix from a master SKU.

    The prefix is the product family identifier; the spec is the size/variant suffix.
    Returns None if no meaningful split can be made (single-segment SKUs).

    Examples:
        "DY-41-24"      → ("DY-41", "24")
        "DY-41-18"      → ("DY-41", "18")
        "FR-1/16GTB"    → ("FR-1", "16GTB")
        "FR-1/22GTB"    → ("FR-1", "22GTB")
        "P-230-24-TS"   → ("P-230", "24-TS")
        "DMF-2/2X"      → ("DMF-2", "2X")
        "WP-2/16-GAL"   → ("WP-2", "16-GAL")
        "920D-6"        → None (single product, no family)
        "AP-26"         → None (too short to split meaningfully)
    """
    # Try slash-separated first: prefix/spec (e.g., FR-1/16GTB, DMF-2/2X, WP-2/16-GAL)
    if "/" in master_sku:
        slash_idx = master_sku.rfind("/")
        prefix = master_sku[:slash_idx]
        spec = master_sku[slash_idx + 1:]
        if prefix and spec:
            return (prefix, spec)

    # Try hyphen-separated: find the last hyphen before a numeric segment
    # Pattern: PREFIX-NUM... where NUM starts the spec (size/variant)
    # Examples: DY-41-24 → DY-41 + 24, P-230-24-TS → P-230 + 24-TS
    # We need at least 2 hyphen segments to form a prefix
    parts = master_sku.split("-")
    if len(parts) < 3:
        return None

    # Find split point: last hyphen where the next part starts with a digit
    # and there are at least 2 parts before it (to form a meaningful prefix)
    for i in range(len(parts) - 1, 1, -1):
        if parts[i] and parts[i][0].isdigit():
            prefix = "-".join(parts[:i])
            spec = "-".join(parts[i:])
            return (prefix, spec)

    return None


def detect_prefix_families(master_skus: list[str]) -> list[MultiSkuFamily]:
    """
    Detect product families by SKU prefix pattern matching.

    Groups SKUs that share the same prefix (e.g., DY-41-18 and DY-41-24 both
    have prefix "DY-41"). This catches families that don't share a Shopify
    product_id (different products in different sizes).

    Args:
        master_skus: List of master SKUs to analyze

    Returns:
        List of MultiSkuFamily objects for prefix-based families (>1 member)
    """
    # Group by prefix
    prefix_groups: dict[str, list[str]] = {}
    for sku in master_skus:
        result = extract_sku_prefix(sku)
        if result is None:
            continue
        prefix, _ = result
        prefix_groups.setdefault(prefix, []).append(sku)

    families = []
    for prefix, skus in prefix_groups.items():
        if len(skus) < 2:
            continue

        sorted_skus = sorted(skus)
        families.append(
            MultiSkuFamily(
                product_id=f"prefix:{prefix}",
                master_skus=sorted_skus,
                base_sku=sorted_skus[0],
                variant_skus=sorted_skus[1:],
            )
        )

    return families


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

    # Phase 1: product_id-based detection (high confidence)
    for sku in [
        resolve_canonical_master_sku(supabase, candidate, tables=("variant_index",))
        for candidate in master_skus
    ]:
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

    # Phase 2: prefix-based detection for SKUs not already in a product_id family
    grouped_skus = {sku for f in families for sku in f.master_skus}
    ungrouped = [sku for sku in master_skus if sku not in grouped_skus]

    if ungrouped:
        prefix_families = detect_prefix_families(ungrouped)
        for pf in prefix_families:
            logger.info(
                "Prefix family detected: %s → %s",
                pf.product_id,
                pf.master_skus,
            )
            families.append(pf)

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
