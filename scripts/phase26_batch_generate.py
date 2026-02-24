#!/usr/bin/env python3
"""Phase 26-02: Batch generate v2 content for 10 test SKUs.

Iterates over all 10 evaluation SKUs, running per-platform generation
via the ab_prompt_test harness, then consolidates outputs and quality scores.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.ab_prompt_test import (
    BANNED_WORDS,
    COMPETITOR_BRANDS,
    evaluate_platform_output,
    load_env_file,
    run_platform_tests,
)

TEST_SKUS = [
    "1025U",
    "1016",
    "102",
    "1020-3",
    "1024",
    "1020",
    "DMF-2/2X",
    "WP-2/16-GAL",
    "1098",
    "CL-22",
]

PLATFORMS = ["google", "bing"]

SCORE_WEIGHTS = {
    "hook_quality": 0.15,
    "product_specificity": 0.15,
    "competitive_diff": 0.12,
    "keyword_integration": 0.10,
    "customer_scenario": 0.10,
    "emotional_resonance": 0.10,
    "factual_accuracy": 0.10,
    "platform_compliance": 0.08,
    "finish_integration": 0.05,
    "variety_score": 0.05,
}

OUTPUT_DIR = PROJECT_ROOT / ".planning" / "phases" / "26-human-evaluation-test-batch"


def compute_composite(self_score: dict) -> float:
    """Compute weighted composite from self_score dict (max 100)."""
    total = 0.0
    for criterion, weight in SCORE_WEIGHTS.items():
        value = self_score.get(criterion, 5)
        total += value * weight * 10  # scale 0-10 -> 0-100 contribution
    return round(total, 1)


def check_constraints(payload: dict, platform: str) -> list[str]:
    """Check banned words, competitor brands, finish in title, description length."""
    issues = []

    # Gather text fields
    if platform == "google":
        title = payload.get("google_title", "")
        desc = payload.get("google_description", "")
    elif platform == "bing":
        title = payload.get("bing_title", "")
        desc = payload.get("bing_description", "")
    else:
        return issues

    all_text = f"{title} {desc}".lower()

    # Banned words
    for word in BANNED_WORDS:
        if word in all_text:
            issues.append(f"Banned word: {word}")

    # Competitor brands
    for brand in COMPETITOR_BRANDS:
        if brand in all_text:
            issues.append(f"Competitor brand: {brand}")

    # Title starts with {FINISH_NAME}
    if not title.startswith("{FINISH_NAME}"):
        issues.append(f"Title does not start with {{FINISH_NAME}}: {title[:60]}")

    # Description has {FINISH_SENTENCE}
    if "{FINISH_SENTENCE}" not in desc:
        issues.append("Description missing {FINISH_SENTENCE} placeholder")

    # Description length 700-900
    desc_len = len(desc)
    if desc_len < 700:
        issues.append(f"Description too short: {desc_len} chars (min 700)")
    elif desc_len > 900:
        issues.append(f"Description too long: {desc_len} chars (max 900)")

    # No "28 finishes"
    if "28 finishes" in all_text or "28 finish" in all_text:
        issues.append("Contains '28 finishes' reference")

    return issues


async def generate_all():
    """Generate v2 content for all test SKUs."""
    load_env_file(str(PROJECT_ROOT / ".env.vercel"))
    os.environ["FEEDOPS_PROMPT_VERSION"] = "v2"

    all_results = {}
    model = "gpt-5.2"
    reasoning = "high"
    max_tokens = 8000

    for sku in TEST_SKUS:
        print(f"\n{'='*60}")
        print(f"Generating SKU: {sku}")
        print(f"{'='*60}")

        try:
            parent_sku, results = await run_platform_tests(
                sku=sku,
                selected_platforms=PLATFORMS,
                model=model,
                reasoning_effort=reasoning,
                max_completion_tokens=max_tokens,
                platform_timeout_sec=240,
            )

            sku_data = {
                "master_sku": sku,
                "category": getattr(parent_sku, "category", ""),
                "current_title": getattr(parent_sku, "current_title", ""),
                "platforms": {},
            }

            for platform, result in results.items():
                payload = result.get("payload", {})
                self_score = payload.get("self_score", {})
                composite = compute_composite(self_score)
                constraints = check_constraints(payload, platform)

                sku_data["platforms"][platform] = {
                    "payload": payload,
                    "self_score": self_score,
                    "composite_score": composite,
                    "constraint_issues": constraints,
                    "usage": result.get("usage", {}),
                    "latency_sec": result.get("latency_sec", 0),
                    "checks": {
                        name: {
                            "passed": check.get("passed", False),
                            "details": str(check.get("details", ""))[:200],
                        }
                        for name, check in result.get("checks", {}).items()
                    },
                }

                print(f"  {platform}: composite={composite}, constraints={len(constraints)} issues")
                for issue in constraints:
                    print(f"    - {issue}")

            all_results[sku] = sku_data

        except Exception as exc:
            print(f"  ERROR: {exc}")
            all_results[sku] = {
                "master_sku": sku,
                "error": str(exc),
                "platforms": {},
            }

    return all_results


def write_outputs_json(results: dict):
    """Write raw v2 outputs to JSON file."""
    output_path = OUTPUT_DIR / "26-02-v2-outputs.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nOutputs written to: {output_path}")
    return output_path


def write_quality_scores(results: dict):
    """Write quality score report."""
    output_path = OUTPUT_DIR / "26-02-quality-scores.md"

    lines = [
        "# Phase 26-02: V2 Quality Scores",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"**SKUs:** {len(results)}",
        "**Model:** gpt-5.2 (reasoning: high)",
        "**Pipeline:** v2 per-platform",
        "",
        "## Per-SKU Composite Scores",
        "",
        "| SKU | Category | Google | Bing | Avg | Constraint Issues |",
        "|-----|----------|--------|------|-----|-------------------|",
    ]

    google_scores = []
    bing_scores = []
    all_avgs = []
    all_constraint_issues = 0

    for sku in TEST_SKUS:
        data = results.get(sku, {})
        if "error" in data:
            lines.append(f"| {sku} | ERROR | - | - | - | {data.get('error', '')[:50]} |")
            continue

        category = data.get("category", "")
        google_data = data.get("platforms", {}).get("google", {})
        bing_data = data.get("platforms", {}).get("bing", {})

        g_score = google_data.get("composite_score", 0)
        b_score = bing_data.get("composite_score", 0)
        avg = round((g_score + b_score) / 2, 1)

        g_issues = len(google_data.get("constraint_issues", []))
        b_issues = len(bing_data.get("constraint_issues", []))
        total_issues = g_issues + b_issues
        all_constraint_issues += total_issues

        google_scores.append(g_score)
        bing_scores.append(b_score)
        all_avgs.append(avg)

        lines.append(f"| {sku} | {category} | {g_score} | {b_score} | {avg} | {total_issues} |")

    # Overall averages
    if all_avgs:
        overall_google = round(sum(google_scores) / len(google_scores), 1)
        overall_bing = round(sum(bing_scores) / len(bing_scores), 1)
        overall_avg = round(sum(all_avgs) / len(all_avgs), 1)
    else:
        overall_google = overall_bing = overall_avg = 0

    lines.extend([
        "",
        f"**Overall Google Average:** {overall_google}",
        f"**Overall Bing Average:** {overall_bing}",
        f"**Overall Average:** {overall_avg}",
        f"**Total Constraint Issues:** {all_constraint_issues}",
        "",
    ])

    # EVAL-05 gate
    gate_pass = overall_avg > 85
    lines.extend([
        "## EVAL-05 Gate",
        "",
        f"**Target:** >85 overall average",
        f"**Result:** {overall_avg}",
        f"**Status:** {'PASS' if gate_pass else 'FAIL'}",
        "",
    ])

    # Per-criterion averages
    lines.extend([
        "## Per-Criterion Averages",
        "",
        "| Criterion | Weight | Google Avg | Bing Avg | Combined |",
        "|-----------|--------|------------|----------|----------|",
    ])

    criterion_google = {c: [] for c in SCORE_WEIGHTS}
    criterion_bing = {c: [] for c in SCORE_WEIGHTS}

    for sku in TEST_SKUS:
        data = results.get(sku, {})
        if "error" in data:
            continue
        g_score = data.get("platforms", {}).get("google", {}).get("self_score", {})
        b_score = data.get("platforms", {}).get("bing", {}).get("self_score", {})
        for c in SCORE_WEIGHTS:
            if c in g_score:
                criterion_google[c].append(g_score[c])
            if c in b_score:
                criterion_bing[c].append(b_score[c])

    for criterion, weight in SCORE_WEIGHTS.items():
        g_vals = criterion_google[criterion]
        b_vals = criterion_bing[criterion]
        g_avg = round(sum(g_vals) / len(g_vals), 1) if g_vals else 0
        b_avg = round(sum(b_vals) / len(b_vals), 1) if b_vals else 0
        combined = round((g_avg + b_avg) / 2, 1) if g_vals and b_vals else 0
        lines.append(f"| {criterion} | {int(weight*100)}% | {g_avg}/10 | {b_avg}/10 | {combined}/10 |")

    lines.append("")

    # Constraint issues detail
    lines.extend([
        "## Constraint Issues Detail",
        "",
    ])
    for sku in TEST_SKUS:
        data = results.get(sku, {})
        if "error" in data:
            continue
        for platform in PLATFORMS:
            issues = data.get("platforms", {}).get(platform, {}).get("constraint_issues", [])
            if issues:
                lines.append(f"**{sku} ({platform}):**")
                for issue in issues:
                    lines.append(f"- {issue}")
                lines.append("")

    if all_constraint_issues == 0:
        lines.append("No constraint issues found across all SKUs and platforms.")
        lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Quality scores written to: {output_path}")
    return output_path


if __name__ == "__main__":
    results = asyncio.run(generate_all())
    write_outputs_json(results)
    write_quality_scores(results)
    print("\nDone!")
