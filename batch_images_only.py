#!/usr/bin/env python3
"""Generate lifestyle images for all 40 pilot SKUs (images only, no content regeneration)."""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

# Load .env file FIRST before any other imports
from dotenv import load_dotenv

load_dotenv()

from feedops.loaders.unified_loader import load_parent_sku_unified
from feedops.pipeline.lifestyle_images import (
    LifestyleImageGenerator,
    get_customer_focused_scene,
    get_product_inventory,
    get_technical_specs,
)


def generate_images_for_sku(
    generator: LifestyleImageGenerator,
    master_sku: str,
    num_variations: int = 3,
) -> dict:
    """Generate lifestyle images for a single SKU."""
    try:
        # Load product data
        parent_sku = load_parent_sku_unified(master_sku)
        if not parent_sku:
            return {
                "master_sku": master_sku,
                "success": False,
                "error": "Product not found",
                "images": 0,
            }

        # Get product image URLs
        product_image_urls = []
        if parent_sku.variants:
            variant = parent_sku.variants[0]
            for url in [
                variant.main_image_url,
                variant.alt_image_1,
                variant.alt_image_2,
                variant.alt_image_3,
                variant.alt_image_4,
            ]:
                if url and url not in product_image_urls:
                    product_image_urls.append(url)

        if not product_image_urls:
            return {
                "master_sku": master_sku,
                "success": False,
                "error": "No product images",
                "images": 0,
            }

        # Build prompts
        inventory = get_product_inventory(parent_sku.category, parent_sku.current_title)
        style = parent_sku.style or "modern"
        scene = get_customer_focused_scene(
            category=parent_sku.category,
            style=style,
            product_title=parent_sku.current_title,
        )
        technical = get_technical_specs(style)

        # Generate images
        results = generator.generate_for_product(
            product_image_urls=product_image_urls,
            master_sku=master_sku,
            inventory=inventory,
            scene=scene,
            technical=technical,
            category=parent_sku.category,
            num_variations=num_variations,
        )

        # Count successes
        success_count = sum(1 for r in results if r.generation_success)

        return {
            "master_sku": master_sku,
            "success": success_count > 0,
            "images": success_count,
            "total_attempted": len(results),
            "error": None if success_count > 0 else "All image generations failed",
        }

    except Exception as e:
        return {
            "master_sku": master_sku,
            "success": False,
            "error": str(e),
            "images": 0,
        }


def main():
    """Generate images for all 40 pilot SKUs."""

    # The 40 pilot SKUs
    pilot_skus = [
        "920D-6",
        "CL-41-30",
        "P-550-WPT",
        "QN-31/30",
        "SH-84",
        "CV-407-8SM",
        "CL-29",
        "FT-16",
        "MB-20",
        "CL-11",
        "1051",
        "WP-GLT-24",
        "CL-41-18",
        "HTL-3",
        "TS-4L",
        "MA-26",
        "WP-61",
        "CS-1",
        "WP-2TB/16-GAL",
        "PR-99",
        "P-730-GB360",
        "BSK-275LA",
        "WP-1TB/16",
        "WP-2/22-GAL",
        "WP-GTB-2",
        "CL-22",
        "A-20",
        "CL-5-16",
        "WP-2/16-GAL",
        "MD-22",
        "P-200-18-TB",
        "SQ-20",
        "RC-5/16TB",
        "DMF-2/2X",
        "TS-25",
        "1066",
        "CL-24C",
        "DT-32",
        "NS-5/16",
        "TS-28",
    ]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        return

    output_dir = Path("data/lifestyle_images")
    output_dir.mkdir(parents=True, exist_ok=True)

    generator = LifestyleImageGenerator(api_key=api_key, output_dir=output_dir)

    print("=" * 80)
    print("Lifestyle Image Generation - 40 Pilot SKUs")
    print("=" * 80)
    print(f"Total SKUs: {len(pilot_skus)}")
    print(f"Images per SKU: 3")
    print(f"Expected total: {len(pilot_skus) * 3}")
    print(f"Output: {output_dir}")
    print("=" * 80)
    print()

    results = {
        "success": [],
        "failed": [],
        "total_images": 0,
        "start_time": datetime.now().isoformat(),
    }

    for i, sku in enumerate(pilot_skus, 1):
        print(f"\n[{i}/{len(pilot_skus)}] Generating images for: {sku}")
        print("-" * 60)

        result = generate_images_for_sku(generator, sku, num_variations=3)

        if result["success"]:
            results["success"].append(result)
            results["total_images"] += result["images"]
            print(f"  ✅ Generated {result['images']}/3 images")
        else:
            results["failed"].append(result)
            print(f"  ❌ Failed: {result['error']}")

    results["end_time"] = datetime.now().isoformat()

    print("\n" + "=" * 80)
    print("IMAGE GENERATION COMPLETE")
    print("=" * 80)
    print(f"Successful SKUs: {len(results['success'])}/{len(pilot_skus)}")
    print(f"Failed SKUs: {len(results['failed'])}/{len(pilot_skus)}")
    print(f"Total images generated: {results['total_images']}")

    if results["failed"]:
        print("\nFailed SKUs:")
        for f in results["failed"][:5]:
            print(f"  - {f['master_sku']}: {f['error']}")
        if len(results["failed"]) > 5:
            print(f"  ... and {len(results['failed']) - 5} more")

    # Save summary
    summary_path = (
        Path("dashboard_data/lifestyle-eval-candidate/reports")
        / f"image-batch-summary-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
