#!/usr/bin/env python3
"""
Intent Score Calibration Script

Queries scored search terms from query_value_scores and correlates
intent scores with actual ROAS outcomes to validate/calibrate thresholds.

Usage:
  cd /path/to/Allied-FeedOps
  source .venv/bin/activate
  set -a && source .env.vercel && set +a
  python scripts/intent_score_calibration.py

Output: docs/analysis/intent-score-calibration-data.json
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime

try:
    from supabase import create_client
except ImportError:
    print("Install supabase-py: pip install supabase")
    sys.exit(1)


def main():
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    supabase = create_client(url, key)

    # Fetch all scored terms with model_inputs
    print("Fetching scored terms from query_value_scores...")
    all_scores = []
    offset = 0
    batch_size = 1000
    while True:
        result = (
            supabase.table("query_value_scores")
            .select("search_term, custom_label_0, recommended_tier, model_inputs, tier_fit_scores, scored_at")
            .eq("score_version", "v2-tier-scoring")
            .order("scored_at", desc=True)
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        if not result.data:
            break
        all_scores.extend(result.data)
        offset += batch_size
        if len(result.data) < batch_size:
            break

    print(f"Fetched {len(all_scores)} scored terms")

    if len(all_scores) == 0:
        print("No scored terms found. Run the tier-scoring API first.")
        sys.exit(1)

    # Parse model_inputs for each term
    analysis = {
        "total_terms": len(all_scores),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "buckets": {},
        "trigger_distribution": defaultdict(int),
        "tier_distribution": defaultdict(int),
        "zero_conversion_analysis": {
            "total_zero_conv": 0,
            "with_high_intent": 0,
            "with_high_intent_and_gate": 0,
        },
        "wasted_spend_analysis": {
            "threshold_5": {"count": 0, "total_spend": 0},
            "threshold_96": {"count": 0, "total_spend": 0},
        },
        "intent_score_roas_correlation": [],
    }

    # Intent score buckets: 0-0.25, 0.25-0.50, 0.50-0.65, 0.65-0.85, 0.85-1.0
    bucket_ranges = [
        (0, 0.25, "0.00-0.25"),
        (0.25, 0.50, "0.25-0.50"),
        (0.50, 0.65, "0.50-0.65"),
        (0.65, 0.85, "0.65-0.85"),
        (0.85, 1.0, "0.85-1.00"),
    ]
    for _, _, label in bucket_ranges:
        analysis["buckets"][label] = {
            "count": 0,
            "roas_values": [],
            "avg_roas": 0,
            "median_roas": 0,
            "with_conversions": 0,
            "zero_conversions": 0,
        }

    for score in all_scores:
        mi = score.get("model_inputs", {}) or {}
        current_tier = mi.get("currentTier", "UNKNOWN")
        actual_roas = mi.get("actualRoas", 0) or 0
        total_conv = mi.get("totalConversions", 0) or 0
        total_cost = mi.get("totalCostMicros", 0) or 0
        trigger = mi.get("trigger", "unknown")
        intent_data = mi.get("intentScore")
        unified_score = intent_data.get("unifiedScore", 0) if intent_data else 0

        analysis["trigger_distribution"][trigger] += 1
        analysis["tier_distribution"][current_tier] += 1

        cost_dollars = total_cost / 1_000_000

        # Bucket by intent score
        for lo, hi, label in bucket_ranges:
            if lo <= unified_score < hi or (hi == 1.0 and unified_score == 1.0):
                b = analysis["buckets"][label]
                b["count"] += 1
                b["roas_values"].append(actual_roas)
                if total_conv > 0:
                    b["with_conversions"] += 1
                else:
                    b["zero_conversions"] += 1
                break

        # ROAS correlation data point
        analysis["intent_score_roas_correlation"].append({
            "search_term": score["search_term"],
            "intent_score": unified_score,
            "actual_roas": actual_roas,
            "conversions": total_conv,
            "cost_dollars": cost_dollars,
            "tier": current_tier,
            "trigger": trigger,
        })

        # Zero-conversion analysis
        if total_conv == 0:
            analysis["zero_conversion_analysis"]["total_zero_conv"] += 1
            if unified_score >= 0.65:
                analysis["zero_conversion_analysis"]["with_high_intent"] += 1
                # Check gate: rCTR >= 1.5 OR wordCount >= 3
                behavioral = mi.get("behavioralSignals")
                r_ctr = behavioral.get("rCTR", 0) if behavioral else 0
                word_count = len(score["search_term"].split())
                if r_ctr >= 1.5 or word_count >= 3:
                    analysis["zero_conversion_analysis"]["with_high_intent_and_gate"] += 1

        # Wasted spend at different thresholds
        if total_conv == 0:
            if cost_dollars > 5:
                analysis["wasted_spend_analysis"]["threshold_5"]["count"] += 1
                analysis["wasted_spend_analysis"]["threshold_5"]["total_spend"] += cost_dollars
            if cost_dollars > 96.33:
                analysis["wasted_spend_analysis"]["threshold_96"]["count"] += 1
                analysis["wasted_spend_analysis"]["threshold_96"]["total_spend"] += cost_dollars

    # Compute bucket averages
    for label, b in analysis["buckets"].items():
        vals = b["roas_values"]
        if vals:
            b["avg_roas"] = sum(vals) / len(vals)
            sorted_vals = sorted(vals)
            mid = len(sorted_vals) // 2
            b["median_roas"] = sorted_vals[mid] if len(sorted_vals) % 2 == 1 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        del b["roas_values"]  # Don't save raw values to JSON

    # Convert defaultdicts to regular dicts
    analysis["trigger_distribution"] = dict(analysis["trigger_distribution"])
    analysis["tier_distribution"] = dict(analysis["tier_distribution"])

    # Save analysis
    output_path = "docs/analysis/intent-score-calibration-data.json"
    with open(output_path, "w") as f:
        json.dump(analysis, f, indent=2)
    print(f"Analysis saved to {output_path}")

    # Print summary
    print(f"\n=== Calibration Summary ===")
    print(f"Total terms: {analysis['total_terms']}")
    print(f"\nTier distribution: {analysis['tier_distribution']}")
    print(f"Trigger distribution: {analysis['trigger_distribution']}")
    print(f"\nIntent Score vs ROAS (by bucket):")
    for label, b in analysis["buckets"].items():
        print(f"  {label}: {b['count']} terms, avg ROAS={b['avg_roas']:.2f}, median={b['median_roas']:.2f}, zero-conv={b['zero_conversions']}")
    print(f"\nZero-conversion analysis:")
    zc = analysis["zero_conversion_analysis"]
    print(f"  Total zero-conv terms: {zc['total_zero_conv']}")
    print(f"  With intent >= 0.65: {zc['with_high_intent']}")
    print(f"  Passing gate (rCTR >= 1.5 OR words >= 3): {zc['with_high_intent_and_gate']}")
    print(f"\nWasted spend analysis:")
    ws = analysis["wasted_spend_analysis"]
    print(f"  At $5 threshold: {ws['threshold_5']['count']} terms, ${ws['threshold_5']['total_spend']:.0f} total spend")
    print(f"  At $96.33 threshold: {ws['threshold_96']['count']} terms, ${ws['threshold_96']['total_spend']:.0f} total spend")


if __name__ == "__main__":
    main()
