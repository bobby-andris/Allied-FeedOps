"""Copy candidate patches to baseline for SKUs missing baseline data.

This script identifies SKUs in the candidate directory that don't have
corresponding baseline data and copies the candidate files to establish
a baseline for future comparisons.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any


def extract_sku_from_patch_filename(filename: str) -> str | None:
    """Extract SKU from patch filename.

    Expected format: {platform}-patch-{SKU}.json
    Examples:
        - google-patch-WP-2-22-GAL.json -> "WP-2-22-GAL"
        - bing-patch-1051.json -> "1051"

    Returns:
        SKU string or None if no match.
    """
    pattern = r"^(?:google|bing|shopify)-patch-(.+)\.json$"
    match = re.match(pattern, filename)
    if match:
        return match.group(1)
    return None


def get_skus_in_directory(directory: Path) -> set[str]:
    """Get all unique SKUs from patch files in a directory.

    Args:
        directory: Path to scan for patch files.

    Returns:
        Set of unique SKU strings.
    """
    skus = set()
    if not directory.exists():
        return skus

    for patch_file in directory.glob("*-patch-*.json"):
        sku = extract_sku_from_patch_filename(patch_file.name)
        if sku:
            skus.add(sku)

    return skus


def copy_candidate_to_baseline(
    candidate_dir: Path,
    baseline_dir: Path,
    sku: str,
) -> dict[str, Any]:
    """Copy candidate patch files to baseline for a single SKU.

    Args:
        candidate_dir: Path to candidate directory.
        baseline_dir: Path to baseline directory.
        sku: The SKU to copy.

    Returns:
        Dict with copy results.
    """
    platforms = ["google", "bing", "shopify"]
    copied = []
    failed = []

    for platform in platforms:
        src = candidate_dir / f"{platform}-patch-{sku}.json"
        dst = baseline_dir / f"{platform}-patch-{sku}.json"

        if src.exists():
            try:
                shutil.copy2(src, dst)
                copied.append(platform)
            except OSError as e:
                failed.append(f"{platform}: {e}")
        else:
            failed.append(f"{platform}: source not found")

    return {"sku": sku, "copied": copied, "failed": failed}


def copy_to_baseline(
    candidate_dir: Path,
    baseline_dir: Path,
    dry_run: bool = False,
    overwrite_existing: bool = False,
) -> dict[str, Any]:
    """Copy candidate patches to baseline for SKUs missing baseline.

    Args:
        candidate_dir: Path to candidate exports directory.
        baseline_dir: Path to baseline exports directory.
        dry_run: If True, only report what would be copied.
        overwrite_existing: If True, copy all candidate SKUs to baseline (replacing
            any existing baseline files).

    Returns:
        Summary dict with results.
    """
    print(f"Candidate directory: {candidate_dir}")
    print(f"Baseline directory: {baseline_dir}")
    print()

    # Ensure baseline directory exists
    if not dry_run:
        baseline_dir.mkdir(parents=True, exist_ok=True)

    # Get SKUs from both directories
    candidate_skus = get_skus_in_directory(candidate_dir)
    baseline_skus = get_skus_in_directory(baseline_dir)

    print(f"SKUs in candidate: {len(candidate_skus)}")
    print(f"SKUs in baseline: {len(baseline_skus)}")

    # Find SKUs to copy
    missing_skus = candidate_skus - baseline_skus
    if overwrite_existing:
        skus_to_copy = candidate_skus
        print(f"Overwrite enabled: copying {len(skus_to_copy)} SKUs to baseline")
    else:
        skus_to_copy = missing_skus
        print(f"SKUs missing from baseline: {len(missing_skus)}")

    if not skus_to_copy:
        print("\nNo SKUs need to be copied - baseline is up to date!")
        return {
            "candidate_count": len(candidate_skus),
            "baseline_count": len(baseline_skus),
            "missing_count": 0,
            "copied_count": 0,
            "skus_copied": [],
        }

    print(
        f"\n{'DRY RUN - ' if dry_run else ''}Copying {len(skus_to_copy)} SKUs to baseline...\n"
    )

    copied_skus = []
    for sku in sorted(skus_to_copy):
        if dry_run:
            print(f"  Would copy: {sku}")
            copied_skus.append(sku)
        else:
            result = copy_candidate_to_baseline(candidate_dir, baseline_dir, sku)
            if result["copied"]:
                print(f"  ✅ Copied {sku}: {', '.join(result['copied'])}")
                copied_skus.append(sku)
            if result["failed"]:
                print(f"  ⚠️  {sku} failures: {', '.join(result['failed'])}")

    # Also copy images if they exist
    candidate_images_dir = candidate_dir / "images"
    baseline_images_dir = baseline_dir / "images"

    images_copied = 0
    if candidate_images_dir.exists():
        if not dry_run:
            baseline_images_dir.mkdir(parents=True, exist_ok=True)

        for sku in copied_skus:
            # Find images for this SKU
            for image_file in candidate_images_dir.glob(f"{sku}_var*.png"):
                dst = baseline_images_dir / image_file.name
                if dry_run:
                    if overwrite_existing or not dst.exists():
                        print(f"  Would copy image: {image_file.name}")
                else:
                    if overwrite_existing or not dst.exists():
                        try:
                            shutil.copy2(image_file, dst)
                            images_copied += 1
                        except OSError:
                            pass

    if images_copied > 0:
        print(f"\n  Also copied {images_copied} lifestyle images to baseline")

    return {
        "candidate_count": len(candidate_skus),
        "baseline_count": len(baseline_skus),
        "missing_count": len(missing_skus),
        "copied_count": len(copied_skus),
        "images_copied": images_copied,
        "skus_copied": copied_skus,
    }


def main():
    """Run the copy from command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Copy candidate patches to baseline for missing SKUs"
    )
    parser.add_argument(
        "--candidate-dir",
        type=Path,
        default=Path("dashboard_data/lifestyle-eval-candidate"),
        help="Path to candidate exports directory",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("dashboard_data/lifestyle-eval"),
        help="Path to baseline exports directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be copied, don't actually copy",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Copy all candidate SKUs to baseline (replace existing baseline files)",
    )
    args = parser.parse_args()

    result = copy_to_baseline(
        args.candidate_dir,
        args.baseline_dir,
        dry_run=args.dry_run,
        overwrite_existing=args.overwrite,
    )

    print("\n" + "=" * 60)
    print("COPY COMPLETE" if not args.dry_run else "DRY RUN COMPLETE")
    print("=" * 60)
    print(f"Candidate SKUs: {result['candidate_count']}")
    print(f"Baseline SKUs (before): {result['baseline_count']}")
    print(f"SKUs copied: {result['copied_count']}")
    if result.get("images_copied"):
        print(f"Images copied: {result['images_copied']}")

    if result["skus_copied"]:
        print(f"\nCopied SKUs: {', '.join(result['skus_copied'][:20])}")
        if len(result["skus_copied"]) > 20:
            print(f"  ... and {len(result['skus_copied']) - 20} more")


if __name__ == "__main__":
    main()
