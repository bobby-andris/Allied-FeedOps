"""Sync lifestyle images to patch JSON files.

This script scans the images directory for lifestyle images that were generated
separately and links them to the corresponding patch JSON files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def extract_sku_from_image(filename: str) -> tuple[str, int, str] | None:
    """Extract SKU, variation number, and timestamp from image filename.

    Expected format: {SKU}_var{N}_{timestamp}.png
    Examples:
        - WP-2-22-GAL_var1_20260128_110735.png -> ("WP-2-22-GAL", 1, "20260128_110735")
        - 1066_var3_20260128_123548.png -> ("1066", 3, "20260128_123548")

    Returns:
        Tuple of (sku, variation_num, timestamp) or None if no match.
    """
    # Pattern: SKU_varN_YYYYMMDD_HHMMSS.png
    # SKU can contain letters, numbers, and hyphens
    pattern = r"^(.+)_var(\d+)_(\d{8}_\d{6})\.png$"
    match = re.match(pattern, filename)
    if match:
        sku = match.group(1)
        variation_num = int(match.group(2))
        timestamp = match.group(3)
        return sku, variation_num, timestamp
    return None


def scan_images_by_sku(images_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Scan images directory and group by SKU.

    Args:
        images_dir: Path to the images directory.

    Returns:
        Dict mapping SKU to list of image metadata dicts.
    """
    if not images_dir.exists():
        return {}

    images_by_sku: dict[str, list[dict[str, Any]]] = {}

    for image_path in sorted(images_dir.glob("*.png")):
        parsed = extract_sku_from_image(image_path.name)
        if not parsed:
            continue

        sku, variation_num, timestamp = parsed

        if sku not in images_by_sku:
            images_by_sku[sku] = []

        # Build relative path from repo root
        relative_path = str(image_path.relative_to(images_dir.parent.parent.parent))

        images_by_sku[sku].append(
            {
                "image_path": relative_path,
                "variation_num": variation_num,
                "generation_success": True,
                "prompt_used": "(Prompt not available - image linked retroactively)",
                "timestamp": timestamp,
                "error_message": None,
            }
        )

    # Sort each SKU's images by variation number
    for sku in images_by_sku:
        images_by_sku[sku].sort(key=lambda x: x["variation_num"])

    return images_by_sku


def update_patch_file(patch_path: Path, lifestyle_images: list[dict[str, Any]]) -> bool:
    """Update a patch JSON file with lifestyle_images array.

    Args:
        patch_path: Path to the patch JSON file.
        lifestyle_images: List of lifestyle image metadata dicts.

    Returns:
        True if file was updated, False if already had images or error.
    """
    if not patch_path.exists():
        return False

    try:
        with open(patch_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Error reading {patch_path.name}: {e}")
        return False

    # Check if already has lifestyle_images
    if "lifestyle_images" in data and data["lifestyle_images"]:
        return False

    # Add lifestyle_images
    data["lifestyle_images"] = lifestyle_images
    data["selected_lifestyle_image"] = None

    try:
        with open(patch_path, "w") as f:
            json.dump(data, f, indent=2)
        return True
    except OSError as e:
        print(f"  Error writing {patch_path.name}: {e}")
        return False


def sync_images_to_patches(exports_dir: Path) -> dict[str, Any]:
    """Sync lifestyle images to patch files.

    Scans the images/ subdirectory for lifestyle images and updates
    patch JSON files that don't already have lifestyle_images.

    Args:
        exports_dir: Path to the exports directory (e.g., lifestyle-eval-candidate/).

    Returns:
        Summary dict with counts of updated files.
    """
    images_dir = exports_dir / "images"
    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return {"skus_scanned": 0, "files_updated": 0, "files_skipped": 0}

    print(f"Scanning images in: {images_dir}")
    images_by_sku = scan_images_by_sku(images_dir)
    print(f"Found images for {len(images_by_sku)} SKUs")

    files_updated = 0
    files_skipped = 0
    skus_processed = []

    for sku, images in sorted(images_by_sku.items()):
        # Normalize SKU for filename (replace / with -)
        sku_filename = sku.replace("/", "-")

        platforms = ["google", "bing", "shopify"]
        sku_updated = False

        for platform in platforms:
            patch_path = exports_dir / f"{platform}-patch-{sku_filename}.json"

            if update_patch_file(patch_path, images):
                print(f"  ✅ Updated {patch_path.name} with {len(images)} images")
                files_updated += 1
                sku_updated = True
            elif patch_path.exists():
                files_skipped += 1

        if sku_updated:
            skus_processed.append(sku)

    return {
        "skus_scanned": len(images_by_sku),
        "skus_updated": len(skus_processed),
        "files_updated": files_updated,
        "files_skipped": files_skipped,
        "skus_processed": skus_processed,
    }


def main():
    """Run the sync from command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync lifestyle images to patch JSON files"
    )
    parser.add_argument(
        "--exports-dir",
        type=Path,
        default=Path("dashboard_data/lifestyle-eval-candidate"),
        help="Path to exports directory (default: dashboard_data/lifestyle-eval-candidate)",
    )
    args = parser.parse_args()

    result = sync_images_to_patches(args.exports_dir)

    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"SKUs scanned: {result['skus_scanned']}")
    print(f"SKUs updated: {result['skus_updated']}")
    print(f"Files updated: {result['files_updated']}")
    print(f"Files skipped (already had images): {result['files_skipped']}")

    if result["skus_processed"]:
        print(f"\nUpdated SKUs: {', '.join(result['skus_processed'])}")


if __name__ == "__main__":
    main()
