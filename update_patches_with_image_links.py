#!/usr/bin/env python3
"""
Update existing patches with lifestyle_image_link field.

This script:
1. Reads all patch files
2. For patches with selected_lifestyle_image, finds the corresponding image path
3. Adds lifestyle_image_link field to the patch
"""

import json
from pathlib import Path

PATCHES_DIR = Path("dashboard_data/lifestyle-eval-candidate")


def update_patch_with_image_link(patch_path: Path) -> bool:
    """Update a single patch with lifestyle_image_link."""
    try:
        patch = json.loads(patch_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False

    # Check if already has lifestyle_image_link
    if patch.get("lifestyle_image_link"):
        return False  # Already set

    # Get selected image
    selected_num = patch.get("selected_lifestyle_image")
    lifestyle_images = patch.get("lifestyle_images", [])

    if selected_num is None or not lifestyle_images:
        return False

    # Find the selected image
    image_path = None
    for img in lifestyle_images:
        if not isinstance(img, dict):
            continue
        if img.get("variation_num") == selected_num:
            if img.get("generation_success") and img.get("image_path"):
                image_path = img["image_path"]
            break

    if not image_path:
        return False

    # Update patch
    patch["lifestyle_image_link"] = image_path
    patch_path.write_text(json.dumps(patch, indent=2))
    return True


def main():
    """Update all patches with lifestyle_image_link."""
    print("Updating patches with lifestyle_image_link...")

    updated_count = 0
    skipped_count = 0

    for prefix in ["google-patch-", "bing-patch-", "shopify-patch-"]:
        for patch_path in PATCHES_DIR.glob(f"{prefix}*.json"):
            if update_patch_with_image_link(patch_path):
                updated_count += 1
                print(f"  ✅ Updated: {patch_path.name}")
            else:
                skipped_count += 1

    print(f"\nDone. Updated: {updated_count}, Skipped: {skipped_count}")


if __name__ == "__main__":
    main()
