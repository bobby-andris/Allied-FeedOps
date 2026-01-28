#!/usr/bin/env python3
"""
Batch AI Image Selection Script

Runs AI image selection for all SKUs that have lifestyle images
and updates the dashboard patches with the selected images.
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

load_dotenv()

# Configuration
PATCHES_DIR = Path("dashboard_data/lifestyle-eval-candidate")
DELAY_BETWEEN_SKUS = 5  # seconds between SKUs to avoid rate limiting
DELAY_BETWEEN_IMAGES = 2  # seconds between image evaluations


def get_skus_with_lifestyle_images() -> list[str]:
    """Get all SKUs that have lifestyle images in their patches."""
    skus_with_images = []

    for patch_file in PATCHES_DIR.glob("google-patch-*.json"):
        try:
            patch = json.loads(patch_file.read_text())
            lifestyle_images = patch.get("lifestyle_images", [])

            # Check if there are successful images
            successful = [
                img
                for img in lifestyle_images
                if isinstance(img, dict) and img.get("generation_success")
            ]

            if successful:
                sku = patch.get("_meta", {}).get("master_sku")
                if sku:
                    skus_with_images.append(sku)
        except (json.JSONDecodeError, OSError):
            continue

    return sorted(skus_with_images)


def load_patch(sku: str, platform: str) -> dict | None:
    """Load a patch file for the SKU."""
    patch_file = PATCHES_DIR / f"{platform}-patch-{sku}.json"
    if not patch_file.exists():
        return None
    try:
        return json.loads(patch_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_patch(sku: str, platform: str, patch: dict) -> None:
    """Save a patch file for the SKU."""
    patch_file = PATCHES_DIR / f"{platform}-patch-{sku}.json"
    patch_file.write_text(json.dumps(patch, indent=2))


def get_reference_image_url(sku: str) -> str | None:
    """Get reference image URL from Shopify."""
    try:
        from feedops.integrations.shopify_catalog import fetch_shopify_product

        product = fetch_shopify_product(sku)
        if product:
            featured_media = product.get("featuredMedia", {})
            if featured_media and featured_media.get("image"):
                return featured_media["image"].get("url", "")
    except Exception as e:
        print(f"    Could not fetch from Shopify: {e}")
    return None


def run_ai_selection_for_sku(sku: str, api_key: str) -> dict:
    """Run AI image selection for a single SKU."""
    from feedops.pipeline.lifestyle_images import (
        LifestyleImageResult,
        select_best_lifestyle_image,
    )

    result = {
        "sku": sku,
        "success": False,
        "selected_variation": None,
        "score": None,
        "error": None,
    }

    # Load the Google patch to get lifestyle images
    google_patch = load_patch(sku, "google")
    if not google_patch:
        result["error"] = "No Google patch found"
        return result

    # Get lifestyle images from patch
    lifestyle_images = google_patch.get("lifestyle_images", [])
    if not lifestyle_images:
        result["error"] = "No lifestyle images in patch"
        return result

    # Get latest images per variation
    latest_by_variation: dict[int, dict] = {}
    for img in lifestyle_images:
        if not isinstance(img, dict) or not img.get("generation_success"):
            continue
        var_num = img.get("variation_num", 1)
        existing = latest_by_variation.get(var_num)
        if not existing or img.get("timestamp", "") > existing.get("timestamp", ""):
            latest_by_variation[var_num] = img

    if not latest_by_variation:
        result["error"] = "No successful images found"
        return result

    # Convert to LifestyleImageResult objects
    image_results = []
    for var_num, img_data in sorted(latest_by_variation.items()):
        img_path = img_data["image_path"]
        # Resolve path
        full_path = Path(img_path)
        if not full_path.is_absolute():
            full_path = Path.cwd() / img_path

        if not full_path.exists():
            print(f"    ⚠️ Image not found: {img_path}")
            continue

        image_result = LifestyleImageResult(
            image_path=str(full_path),
            variation_num=var_num,
            generation_success=True,
            prompt_used=img_data.get("prompt_used", ""),
            timestamp=img_data.get("timestamp", ""),
        )
        image_results.append(image_result)

    if not image_results:
        result["error"] = "No valid images found on disk"
        return result

    # Get reference image URL
    ref_url = google_patch.get("_previous", {}).get("image_url", "")
    if not ref_url:
        ref_url = get_reference_image_url(sku)

    if not ref_url:
        # Use a fallback - first image as reference isn't ideal but works
        result["error"] = "No reference image URL found"
        return result

    # Get category from patch metadata
    category = google_patch.get("_meta", {}).get("category", "Bathroom Hardware")

    # Run AI selection with delays between evaluations
    print(f"    Scoring {len(image_results)} images...")

    best_variation = None
    best_score = None

    for i, img_result in enumerate(image_results):
        if i > 0:
            time.sleep(DELAY_BETWEEN_IMAGES)  # Delay between image evaluations

        from feedops.pipeline.lifestyle_images import score_lifestyle_image

        score = score_lifestyle_image(
            image_path=img_result.image_path,
            reference_image_url=ref_url,
            category=category,
            api_key=api_key,
        )

        if score.evaluation_success:
            print(
                f"      Var {img_result.variation_num}: {score.composite_score:.1f} "
                f"(Acc:{score.product_accuracy}, Comp:{score.composition_quality}, "
                f"Bg:{score.background_appropriateness}, Aes:{score.aesthetic_appeal})"
            )

            if best_score is None or score.composite_score > best_score:
                best_score = score.composite_score
                best_variation = img_result.variation_num
        else:
            print(f"      Var {img_result.variation_num}: ❌ {score.error_message}")

    if best_variation is not None:
        # Update all patches with selected image
        for platform in ["google", "bing", "shopify"]:
            patch = load_patch(sku, platform)
            if patch:
                patch["selected_lifestyle_image"] = best_variation
                save_patch(sku, platform, patch)

        result["success"] = True
        result["selected_variation"] = best_variation
        result["score"] = best_score
        print(f"    🏆 Selected variation {best_variation} (score: {best_score:.1f})")
    else:
        result["error"] = "All evaluations failed"

    return result


def main():
    """Run AI image selection for all SKUs with lifestyle images."""
    print("=" * 70)
    print("BATCH AI IMAGE SELECTION")
    print("=" * 70)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return

    # Get SKUs with lifestyle images
    skus = get_skus_with_lifestyle_images()
    print(f"\nFound {len(skus)} SKUs with lifestyle images")

    if not skus:
        print("No SKUs to process")
        return

    # Process each SKU
    results = []
    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, sku in enumerate(skus, 1):
        print(f"\n[{i}/{len(skus)}] Processing {sku}...")

        # Check if already has a selected image
        patch = load_patch(sku, "google")
        if patch and patch.get("selected_lifestyle_image") is not None:
            print(
                f"    Already has selected image: variation {patch['selected_lifestyle_image']}"
            )
            # Re-run anyway to potentially find a better image

        try:
            result = run_ai_selection_for_sku(sku, api_key)
            results.append(result)

            if result["success"]:
                success_count += 1
            elif result["error"] in [
                "No lifestyle images in patch",
                "No successful images found",
            ]:
                skip_count += 1
            else:
                fail_count += 1

        except Exception as e:
            print(f"    ❌ Error: {e}")
            results.append(
                {
                    "sku": sku,
                    "success": False,
                    "error": str(e),
                }
            )
            fail_count += 1

        # Delay between SKUs to avoid rate limiting
        if i < len(skus):
            print(f"    Waiting {DELAY_BETWEEN_SKUS}s before next SKU...")
            time.sleep(DELAY_BETWEEN_SKUS)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total SKUs processed: {len(skus)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Failed: {fail_count}")
    print(f"  ⏭️ Skipped: {skip_count}")

    # List successful selections
    print("\n✅ Successful selections:")
    for r in results:
        if r.get("success"):
            print(
                f"  {r['sku']}: Variation {r['selected_variation']} (score: {r['score']:.1f})"
            )

    # List failures
    if fail_count > 0:
        print("\n❌ Failed:")
        for r in results:
            if not r.get("success") and r.get("error") not in [
                "No lifestyle images in patch",
                "No successful images found",
                "No reference image URL found",
            ]:
                print(f"  {r['sku']}: {r.get('error')}")

    print("\n" + "=" * 70)
    print("BATCH COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
