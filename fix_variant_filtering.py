#!/usr/bin/env python3
"""
Fix variant filtering in existing patches.

This script:
1. For each patch with variants
2. Filters variants to only those matching the master SKU pattern
3. Re-fetches from Shopify with correct filtering
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.stdout.reconfigure(line_buffering=True)

PATCHES_DIR = Path("dashboard_data/lifestyle-eval-candidate")


def get_sku_from_patch(patch: dict) -> str:
    """Extract master SKU from patch."""
    return patch.get("_meta", {}).get("master_sku", "")


def filter_variants_by_sku(variants: list[dict], master_sku: str) -> list[dict]:
    """Filter variants to only include those matching the master SKU."""
    sku_pattern = f"{master_sku}-"
    return [v for v in variants if v.get("option_sku", "").startswith(sku_pattern)]


def main():
    print("Fixing variant filtering in patches...")

    fixed = 0
    unchanged = 0

    for prefix in ["google-patch-", "bing-patch-", "shopify-patch-"]:
        for patch_path in sorted(PATCHES_DIR.glob(f"{prefix}*.json")):
            try:
                patch = json.loads(patch_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            master_sku = get_sku_from_patch(patch)
            if not master_sku:
                continue

            variants = patch.get("variants", [])
            if not variants:
                continue

            # Filter variants
            filtered = filter_variants_by_sku(variants, master_sku)

            if len(filtered) == len(variants):
                unchanged += 1
                continue

            # Update patch with filtered variants
            patch["variants"] = filtered
            patch_path.write_text(json.dumps(patch, indent=2))
            fixed += 1
            print(f"  ✅ {patch_path.name}: {len(variants)} → {len(filtered)} variants")

    print(f"\nDone. Fixed: {fixed}, Unchanged: {unchanged}")


if __name__ == "__main__":
    main()
