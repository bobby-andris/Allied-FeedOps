#!/usr/bin/env python3
"""Full 40-SKU batch run with 3 candidates for quality evaluation."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Disable lifestyle images — content quality only
os.environ["LIFESTYLE_IMAGES_ENABLED"] = "false"

from feedops.pipeline.optimize import optimize_parent_sku


async def batch_40_skus():
    """Run optimization for all 40 pilot SKUs with 3 candidates each."""

    pilot_skus = [
        "920D-6", "CL-41-30", "P-550-WPT", "QN-31/30", "SH-84",
        "CV-407-8SM", "CL-29", "FT-16", "MB-20", "CL-11",
        "1051", "WP-GLT-24", "CL-41-18", "HTL-3", "TS-4L",
        "MA-26", "WP-61", "CS-1", "WP-2TB/16-GAL", "PR-99",
        "P-730-GB360", "BSK-275LA", "WP-1TB/16", "WP-2/22-GAL", "WP-GTB-2",
        "CL-22", "A-20", "CL-5-16", "WP-2/16-GAL", "MD-22",
        "P-200-18-TB", "SQ-20", "RC-5/16TB", "DMF-2/2X", "TS-25",
        "1066", "CL-24C", "DT-32", "NS-5/16", "TS-28",
    ]

    catalog_path = Path("data/catalog/Product Catalog.csv")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    exports_dir = f"dashboard_data/batch-40sku-{timestamp}"
    output_dir = f"dashboard_data/batch-40sku-{timestamp}/reports"

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    Path(exports_dir).mkdir(parents=True, exist_ok=True)

    total = len(pilot_skus)
    print("=" * 80)
    print(f"40-SKU Quality Batch Run ({total} SKUs, 3 candidates each)")
    print(f"Output: {exports_dir}")
    print("=" * 80)

    results = {"success": [], "failed": [], "start_time": datetime.now().isoformat()}

    for i, master_sku in enumerate(pilot_skus, 1):
        print(f"\n[{i}/{total}] {master_sku}")
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
                "quality_score": result.candidate.final_score.composite,
                "status": result.candidate.final_score.approval_status,
                "heuristic_score": result.heuristic_score,
                "google_score": hs.get("google"),
                "bing_score": hs.get("bing"),
                "shopify_score": hs.get("shopify"),
                "soft_gate_penalty": result.candidate.soft_gate_penalty,
                "selection_score_adjusted": result.candidate.selection_score_adjusted,
            })

            print(f"  Q={result.candidate.final_score.composite}%  "
                  f"H={result.heuristic_score}  "
                  f"G={hs.get('google')}  B={hs.get('bing')}  S={hs.get('shopify')}  "
                  f"penalty={result.candidate.soft_gate_penalty}  "
                  f"status={result.candidate.final_score.approval_status}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results["failed"].append({
                "master_sku": master_sku,
                "error": str(e),
            })

    results["end_time"] = datetime.now().isoformat()

    # Summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print(f"Successful: {len(results['success'])}/{total}")
    print(f"Failed: {len(results['failed'])}/{total}")

    if results["success"]:
        scores = results["success"]
        avg_q = sum(r["quality_score"] for r in scores) / len(scores)
        avg_h = sum(r["heuristic_score"] for r in scores if r["heuristic_score"]) / max(1, sum(1 for r in scores if r["heuristic_score"]))
        avg_g = sum(r["google_score"] for r in scores if r["google_score"]) / max(1, sum(1 for r in scores if r["google_score"]))
        avg_b = sum(r["bing_score"] for r in scores if r["bing_score"]) / max(1, sum(1 for r in scores if r["bing_score"]))
        avg_s = sum(r["shopify_score"] for r in scores if r["shopify_score"]) / max(1, sum(1 for r in scores if r["shopify_score"]))
        avg_pen = sum(r["soft_gate_penalty"] for r in scores) / len(scores)

        print(f"\nAvg Quality Score:   {avg_q:.2f}%")
        print(f"Avg Heuristic Score: {avg_h:.2f}%")
        print(f"Avg Google:          {avg_g:.2f}")
        print(f"Avg Bing:            {avg_b:.2f}")
        print(f"Avg Shopify:         {avg_s:.2f}")
        print(f"Avg Soft Gate Pen:   {avg_pen:.2f}")

        # Sort by heuristic for display
        sorted_scores = sorted(scores, key=lambda r: r["heuristic_score"] or 0)
        print(f"\nBottom 5 by Heuristic:")
        for r in sorted_scores[:5]:
            print(f"  {r['master_sku']:15s}  Q={r['quality_score']:.1f}%  H={r['heuristic_score']:.1f}%  "
                  f"G={r['google_score']:.1f}  B={r['bing_score']:.1f}  S={r['shopify_score']:.1f}  "
                  f"penalty={r['soft_gate_penalty']}")

        print(f"\nTop 5 by Heuristic:")
        for r in sorted_scores[-5:]:
            print(f"  {r['master_sku']:15s}  Q={r['quality_score']:.1f}%  H={r['heuristic_score']:.1f}%  "
                  f"G={r['google_score']:.1f}  B={r['bing_score']:.1f}  S={r['shopify_score']:.1f}  "
                  f"penalty={r['soft_gate_penalty']}")

        print(f"\nAll SKUs (sorted by heuristic):")
        for r in sorted_scores:
            print(f"  {r['master_sku']:15s}  Q={r['quality_score']:.1f}%  H={r['heuristic_score']:.1f}%  "
                  f"G={r['google_score']:.1f}  B={r['bing_score']:.1f}  S={r['shopify_score']:.1f}  "
                  f"penalty={r['soft_gate_penalty']}  adj={r['selection_score_adjusted']}")

    if results["failed"]:
        print(f"\nFailed SKUs:")
        for r in results["failed"]:
            print(f"  {r['master_sku']}: {r['error']}")

    summary_path = Path(exports_dir) / "batch-summary.json"
    with open(summary_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary: {summary_path}")
    print(f"Reports: {output_dir}")
    print(f"Exports: {exports_dir}")

    return results


if __name__ == "__main__":
    asyncio.run(batch_40_skus())
