#!/usr/bin/env python3
"""Batch optimization for remaining 16 SKUs that failed due to quota."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Load .env file FIRST before any other imports
from dotenv import load_dotenv

load_dotenv()

# Disable images for now - run content only first
os.environ["LIFESTYLE_IMAGES_ENABLED"] = "false"
os.environ["LIFESTYLE_IMAGES_NUM_VARIATIONS"] = "3"
os.environ["LIFESTYLE_IMAGES_OUTPUT_DIR"] = "data/lifestyle_images"

from feedops.pipeline.optimize import optimize_parent_sku


async def batch_optimize():
    """Run optimization for the 16 SKUs that failed due to quota."""

    # The 16 SKUs that failed in the previous batch
    remaining_skus = [
        "WP-2/22-GAL",
        "WP-GTB-2",
        "CL-22",
        "A-20",
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

    eval_skus = [{"master_sku": sku, "category": "Pilot"} for sku in remaining_skus]

    catalog_path = Path("data/catalog/Product Catalog.csv")
    exports_dir = "dashboard_data/lifestyle-eval-candidate"
    output_dir = "dashboard_data/lifestyle-eval-candidate/reports"

    # Create output directories
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(exports_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("Batch Optimization - Remaining 16 SKUs")
    print("=" * 80)
    print(f"Total SKUs: {len(eval_skus)}")
    print(f"Images per SKU: 3")
    print(f"Expected total images: {len(eval_skus) * 3}")
    print(f"Output: {exports_dir}")
    print(f"Reports: {output_dir}")
    print("=" * 80)
    print()

    results = {
        "success": [],
        "failed": [],
        "total_images": 0,
        "start_time": datetime.now().isoformat(),
    }

    for i, sku_info in enumerate(eval_skus, 1):
        master_sku = sku_info["master_sku"]
        category = sku_info["category"]

        print(f"\n[{i}/{len(eval_skus)}] Processing: {master_sku} ({category})")
        print("-" * 60)

        try:
            result = await optimize_parent_sku(
                master_sku=master_sku,
                catalog_path=catalog_path,
                dry_run=False,
                output_dir=output_dir,
                exports_dir=exports_dir,
            )

            # Count successful images
            num_images = 0
            if result.candidate.lifestyle_images:
                num_images = sum(
                    1
                    for img in result.candidate.lifestyle_images
                    if img.generation_success
                )
                results["total_images"] += num_images

            results["success"].append(
                {
                    "master_sku": master_sku,
                    "category": category,
                    "quality_score": result.candidate.final_score.composite,
                    "status": result.candidate.final_score.approval_status,
                    "lifestyle_images": num_images,
                }
            )

            print(f"  ✅ Quality Score: {result.candidate.final_score.composite}%")
            print(f"  ✅ Status: {result.candidate.final_score.approval_status}")
            print(f"  🖼️  Images: {num_images}/3")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results["failed"].append(
                {
                    "master_sku": master_sku,
                    "category": category,
                    "error": str(e),
                }
            )

    # Summary
    results["end_time"] = datetime.now().isoformat()

    print("\n" + "=" * 80)
    print("BATCH COMPLETE")
    print("=" * 80)
    print(f"Successful: {len(results['success'])}/{len(eval_skus)}")
    print(f"Failed: {len(results['failed'])}/{len(eval_skus)}")
    print(f"Total lifestyle images: {results['total_images']}")

    if results["failed"]:
        print("\nFailed SKUs:")
        for failed in results["failed"]:
            print(f"  - {failed['master_sku']}: {failed['error']}")

    # Calculate average quality score
    if results["success"]:
        avg_score = sum(r["quality_score"] for r in results["success"]) / len(
            results["success"]
        )
        print(f"\nAverage Quality Score: {avg_score:.2f}%")

    # Save results summary
    summary_path = (
        Path(output_dir)
        / f"batch-remaining-summary-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    )
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")

    print("\n" + "=" * 80)
    print("Next: View results in Streamlit dashboard:")
    print("  streamlit run streamlit_app.py")
    print("=" * 80)

    return results


if __name__ == "__main__":
    asyncio.run(batch_optimize())
