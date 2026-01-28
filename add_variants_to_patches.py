#!/usr/bin/env python3
"""
Add variant data to existing patches by fetching from Shopify.

This script:
1. For each patch, fetches ALL variants from the Shopify product
2. Includes variants for all sizes (18", 24", 30", 36") since they're the same product
3. For Google/Bing: Generates size-specific titles/descriptions
4. For Shopify: Uses size-agnostic content since product page shows all sizes
5. Adds variants array to the patch
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)

PATCHES_DIR = Path("dashboard_data/lifestyle-eval-candidate")


def get_sku_from_patch(patch: dict) -> str:
    """Extract master SKU from patch."""
    return patch.get("_meta", {}).get("master_sku", "")


def fetch_all_variants_for_product(sku: str) -> list[dict]:
    """Fetch ALL variant data from Shopify for a product.

    Returns ALL variants including different sizes since they belong to the
    same Shopify product and should be included in the feed.

    Args:
        sku: The master SKU (e.g., CL-41-18) - used to find the product

    Returns:
        List of variant dicts with option_sku, finish, size, and gmc_id
    """
    from feedops.integrations.shopify_catalog import fetch_shopify_product

    product = fetch_shopify_product(sku)
    if not product:
        return []

    variants = product.get("variants", {}).get("nodes", [])
    result = []

    product_id = product.get("legacyResourceId") or ""

    for v in variants:
        option_sku = v.get("sku", "")
        if not option_sku:
            continue

        # Extract finish and size from selectedOptions
        finish = ""
        size = ""
        for opt in v.get("selectedOptions", []):
            opt_name = opt.get("name", "").lower()
            if opt_name == "finish":
                finish = opt.get("value", "")
            elif opt_name == "size":
                size = opt.get("value", "")

        if not finish:
            finish = v.get("title", "")

        # Get variant GMC ID
        variant_id = v.get("legacyResourceId") or ""
        gmc_id = ""
        if product_id and variant_id:
            gmc_id = f"shopify_US_{product_id}_{variant_id}"

        result.append(
            {
                "option_sku": option_sku,
                "finish": finish,
                "size": size,
                "gmc_id": gmc_id,
            }
        )

    return result


def generate_variant_content(
    base_title: str,
    base_description: str,
    finish: str,
    size: str,
    platform: str,
) -> tuple[str, str]:
    """Generate variant-specific title and description.

    Args:
        base_title: Base title from master SKU
        base_description: Base description from master SKU
        finish: Variant's finish (e.g., "Polished Chrome")
        size: Variant's size (e.g., "18 Inch") - used for Google/Bing, not Shopify
        platform: Target platform (google, bing, shopify)

    Returns:
        Tuple of (variant_title, variant_description)
    """
    from feedops.pipeline.finish_injection import (
        generate_variant_description,
        generate_variant_title,
    )

    # For Google/Bing, include size in title and description
    # For Shopify, don't include size (product page shows all sizes)
    variant_title = generate_variant_title(
        base_title=base_title,
        finish_name=finish,
        size=size if platform in ("google", "bing") else None,
        platform=platform,
    )
    variant_description = generate_variant_description(
        base_description=base_description,
        finish_name=finish,
        platform=platform,
        size=size if platform in ("google", "bing") else None,
    )

    return variant_title, variant_description


def add_variants_to_patch(patch_path: Path, force_refresh: bool = False) -> int:
    """Add variants to a single patch. Returns number of variants added."""
    try:
        patch = json.loads(patch_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    # Check if already has variants (skip unless force_refresh)
    if patch.get("variants") and not force_refresh:
        return 0

    sku = get_sku_from_patch(patch)
    if not sku:
        return 0

    # Determine platform
    platform = "google"
    if "bing-patch" in patch_path.name:
        platform = "bing"
    elif "shopify-patch" in patch_path.name:
        platform = "shopify"

    # Fetch ALL variants from Shopify (all sizes, all finishes)
    variants = fetch_all_variants_for_product(sku)
    if not variants:
        return 0

    # Get base content
    if platform == "google":
        base_title = patch.get("title", "")
        base_description = patch.get("description", "")
    elif platform == "bing":
        base_title = patch.get("title", "")
        base_description = patch.get("description", "")
    else:  # shopify
        base_title = patch.get("title", "")
        base_description = patch.get("body_html", "")

    if not base_title:
        return 0

    # Generate variant patches
    variants_data = []
    for v in variants:
        variant_title, variant_description = generate_variant_content(
            base_title=base_title,
            base_description=base_description,
            finish=v["finish"],
            size=v.get("size", ""),
            platform=platform,
        )

        variant_patch = {
            "option_sku": v["option_sku"],
            "finish": v["finish"],
            "size": v.get("size", ""),
            "title": variant_title,
            "description": variant_description,
        }

        if platform == "google" and v.get("gmc_id"):
            variant_patch["offerId"] = v["gmc_id"]
            variant_patch["gmc_id"] = v["gmc_id"]
        elif platform == "bing":
            variant_patch["sku"] = v["option_sku"]

        variants_data.append(variant_patch)

    # Update patch
    patch["variants"] = variants_data
    patch_path.write_text(json.dumps(patch, indent=2))

    return len(variants_data)


def main():
    """Add variants to all patches."""
    import argparse

    parser = argparse.ArgumentParser(description="Add variants to patches")
    parser.add_argument(
        "--force", action="store_true", help="Force refresh existing variants"
    )
    parser.add_argument("--sku", type=str, help="Process only a specific SKU")
    args = parser.parse_args()

    print("Adding variants to patches (ALL sizes included)...")
    print("(This fetches from Shopify API - may take a while)")

    total_patches = 0
    total_variants = 0
    skipped = 0

    # Process one platform at a time to avoid duplicate Shopify calls
    for prefix in ["google-patch-"]:  # Only Google for now, then sync
        print(f"\nProcessing {prefix}...")

        for patch_path in sorted(PATCHES_DIR.glob(f"{prefix}*.json")):
            sku = patch_path.stem.replace(prefix, "")

            # Filter by SKU if specified
            if args.sku and sku != args.sku:
                continue

            print(f"  {sku}...", end=" ")

            count = add_variants_to_patch(patch_path, force_refresh=args.force)
            if count > 0:
                total_patches += 1
                total_variants += count
                print(f"✅ {count} variants")

                # Also update bing and shopify patches
                for other_prefix in ["bing-patch-", "shopify-patch-"]:
                    other_path = PATCHES_DIR / f"{other_prefix}{sku}.json"
                    if other_path.exists():
                        # Load google patch to get variant data
                        google_patch = json.loads(patch_path.read_text())
                        other_patch = json.loads(other_path.read_text())

                        # Generate platform-specific content for variants
                        base_title = other_patch.get("title", "")
                        base_desc = other_patch.get(
                            "description", ""
                        ) or other_patch.get("body_html", "")
                        platform = "bing" if "bing" in other_prefix else "shopify"

                        variants_data = []
                        for gv in google_patch.get("variants", []):
                            vt, vd = generate_variant_content(
                                base_title=base_title,
                                base_description=base_desc,
                                finish=gv["finish"],
                                size=gv.get("size", ""),
                                platform=platform,
                            )
                            vp = {
                                "option_sku": gv["option_sku"],
                                "finish": gv["finish"],
                                "size": gv.get("size", ""),
                                "title": vt,
                                "description": vd,
                            }
                            if platform == "bing":
                                vp["sku"] = gv["option_sku"]
                            variants_data.append(vp)

                        other_patch["variants"] = variants_data
                        other_path.write_text(json.dumps(other_patch, indent=2))
            else:
                skipped += 1
                print("⏭️ skipped")

    print(
        f"\nDone. Patches updated: {total_patches}, Variants added: {total_variants}, Skipped: {skipped}"
    )


if __name__ == "__main__":
    main()
