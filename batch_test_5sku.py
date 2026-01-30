#!/usr/bin/env python3
"""Quick 5-SKU test of pipeline quality changes."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Disable lifestyle images for faster test
os.environ["LIFESTYLE_IMAGES_ENABLED"] = "false"

from feedops.pipeline.optimize import optimize_parent_sku


async def test_5_skus():
    """Run optimization for 5 test SKUs covering different category groups."""

    test_skus = [
        {"master_sku": "CL-41-30", "note": "Towel Bar (towel_storage guidance)"},
        {"master_sku": "MD-22", "note": "Retractable Hooks (niche_functional guidance)"},
        {"master_sku": "P-730-GB360", "note": "Grab Bar (safety_ada guidance)"},
        {"master_sku": "A-20", "note": "Cabinet Hardware (niche_functional guidance)"},
        {"master_sku": "1051", "note": "Paper Towel Holder (no category guidance)"},
    ]

    catalog_path = Path("data/catalog/Product Catalog.csv")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    exports_dir = f"dashboard_data/test-5sku-{timestamp}"
    output_dir = f"dashboard_data/test-5sku-{timestamp}/reports"

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(exports_dir).mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("5-SKU Quality Test Run")
    print("=" * 80)

    results = {"success": [], "failed": []}

    for i, sku_info in enumerate(test_skus, 1):
        master_sku = sku_info["master_sku"]
        note = sku_info["note"]

        print(f"\n[{i}/5] {master_sku} — {note}")
        print("-" * 60)

        try:
            result = await optimize_parent_sku(
                master_sku=master_sku,
                catalog_path=catalog_path,
                dry_run=False,
                output_dir=output_dir,
                exports_dir=exports_dir,
                num_candidates=3,
            )

            hs = result.candidate.heuristic_score_breakdown or {}
            results["success"].append({
                "master_sku": master_sku,
                "note": note,
                "quality_score": result.candidate.final_score.composite,
                "status": result.candidate.final_score.approval_status,
                "heuristic_score": result.heuristic_score,
                "google_score": hs.get("google"),
                "bing_score": hs.get("bing"),
                "shopify_score": hs.get("shopify"),
                "soft_gate_penalty": result.candidate.soft_gate_penalty,
                "selection_score_adjusted": result.candidate.selection_score_adjusted,
            })

            print(f"  Quality Score: {result.candidate.final_score.composite}%")
            print(f"  Status: {result.candidate.final_score.approval_status}")
            print(f"  Heuristic: {result.heuristic_score}")
            print(f"  Google: {hs.get('google')}  Bing: {hs.get('bing')}  Shopify: {hs.get('shopify')}")
            print(f"  Soft gate penalty: {result.candidate.soft_gate_penalty}")
            print(f"  Adjusted: {result.candidate.selection_score_adjusted}")

        except Exception as e:
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            results["failed"].append({
                "master_sku": master_sku,
                "note": note,
                "error": str(e),
            })

    # Summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Successful: {len(results['success'])}/5")
    print(f"Failed: {len(results['failed'])}/5")

    if results["success"]:
        avg = sum(r["quality_score"] for r in results["success"]) / len(results["success"])
        avg_h = sum(r["heuristic_score"] for r in results["success"] if r["heuristic_score"]) / len(results["success"])
        print(f"Avg Quality Score: {avg:.2f}%")
        print(f"Avg Heuristic Score: {avg_h:.2f}%")
        print()
        for r in results["success"]:
            print(f"  {r['master_sku']:15s}  Q={r['quality_score']:.1f}%  H={r['heuristic_score']:.1f}%  "
                  f"G={r['google_score']:.1f}  B={r['bing_score']:.1f}  S={r['shopify_score']:.1f}  "
                  f"penalty={r['soft_gate_penalty']}  adj={r['selection_score_adjusted']}")

    summary_path = Path(exports_dir) / "test-summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary: {summary_path}")
    print(f"Reports: {output_dir}")
    print(f"Exports: {exports_dir}")

    return results


if __name__ == "__main__":
    asyncio.run(test_5_skus())
