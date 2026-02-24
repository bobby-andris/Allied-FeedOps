#!/usr/bin/env python3
"""Batch per-platform generation for canonical and unseen SKU validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from openai import AsyncOpenAI

from ab_prompt_test import evaluate_platform_output, generate_per_platform, load_env_file
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.db.supabase_client import get_client
from feedops.pipeline.evidence import build_evidence_table, format_evidence_markdown

CANONICAL_TEST_SKUS = [
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

DEFAULT_PLATFORMS = ["google", "bing", "shopify", "finish"]
DEFAULT_MODEL = "gpt-5.2"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_MAX_COMPLETION_TOKENS = 8000
DEFAULT_PLATFORM_TIMEOUT_SEC = 210
DEFAULT_UNSEEN_SEED = 52

DEFAULT_OUTPUT_DIR = Path("/tmp/ab_test_outputs_25.3")
DEFAULT_RESULTS_PATH = (
    PROJECT_ROOT
    / ".planning"
    / "phases"
    / "25.3-prompt-rewrite"
    / "25.3-03-test-results.md"
)


def _fetch_distinct_master_skus(table_name: str) -> set[str]:
    """Fetch distinct master_sku values from a Supabase table using pagination."""
    client = get_client()
    page_size = 1000
    offset = 0
    results: set[str] = set()
    while True:
        query = (
            client.table(table_name)
            .select("master_sku")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = query.data or []
        if not rows:
            break
        for row in rows:
            sku = str(row.get("master_sku") or "").strip()
            if sku:
                results.add(sku)
        if len(rows) < page_size:
            break
        offset += page_size
    return results


def select_unseen_skus(
    *,
    unseen_count: int,
    unseen_seed: int,
    excluded_skus: set[str],
) -> list[str]:
    """Select deterministic unseen SKUs from product_catalog - generated_content."""
    if unseen_count <= 0:
        return []

    catalog_skus = _fetch_distinct_master_skus("product_catalog")
    generated_skus = _fetch_distinct_master_skus("generated_content")
    unseen_pool = sorted(catalog_skus - generated_skus - excluded_skus)

    if not unseen_pool:
        return []
    if unseen_count >= len(unseen_pool):
        return unseen_pool

    rng = random.Random(unseen_seed)
    return sorted(rng.sample(unseen_pool, unseen_count))


def resolve_run_skus(
    *,
    explicit_skus: list[str] | None,
    unseen_count: int,
    unseen_seed: int,
    include_canonical: bool,
) -> tuple[list[str], dict[str, Any]]:
    """Resolve final SKU list and metadata for this batch run."""
    if explicit_skus:
        skus = [sku.strip() for sku in explicit_skus if sku.strip()]
        return skus, {
            "mode": "explicit",
            "canonical_count": 0,
            "unseen_count": 0,
            "unseen_seed": unseen_seed,
        }

    if unseen_count <= 0:
        return list(CANONICAL_TEST_SKUS), {
            "mode": "canonical",
            "canonical_count": len(CANONICAL_TEST_SKUS),
            "unseen_count": 0,
            "unseen_seed": unseen_seed,
        }

    unseen = select_unseen_skus(
        unseen_count=unseen_count,
        unseen_seed=unseen_seed,
        excluded_skus=set(CANONICAL_TEST_SKUS),
    )
    if include_canonical:
        skus = list(CANONICAL_TEST_SKUS) + unseen
        mode = "combined"
    else:
        skus = unseen
        mode = "unseen"
    return skus, {
        "mode": mode,
        "canonical_count": len(CANONICAL_TEST_SKUS) if include_canonical else 0,
        "unseen_count": len(unseen),
        "unseen_seed": unseen_seed,
        "unseen_skus": unseen,
    }


async def generate_sku(
    client: AsyncOpenAI,
    sku: str,
    *,
    model: str,
    reasoning_effort: str,
    max_completion_tokens: int,
    platform_timeout_sec: int,
    selected_platforms: list[str],
) -> dict[str, Any]:
    """Generate all platform content for one SKU."""
    parent_sku = load_parent_sku_from_supabase(sku)
    if not parent_sku:
        return {"sku": sku, "error": f"SKU not found: {sku}", "platforms": {}}

    evidence = build_evidence_table(parent_sku)
    evidence_markdown = format_evidence_markdown(evidence)

    results: dict[str, Any] = {}

    async def _generate_platform(platform: str) -> tuple[str, dict[str, Any]]:
        try:
            generated = await asyncio.wait_for(
                generate_per_platform(
                    client=client,
                    parent_sku=parent_sku,
                    evidence=evidence,
                    evidence_markdown=evidence_markdown,
                    platform=platform,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=max_completion_tokens,
                ),
                timeout=platform_timeout_sec,
            )
            generated["checks"] = evaluate_platform_output(
                platform=platform,
                payload=generated["payload"],
                parent_sku=parent_sku,
            )
            passed = sum(1 for c in generated["checks"].values() if c.get("passed"))
            total = len(generated["checks"])
            failed_checks = [
                name for name, c in generated["checks"].items() if not c.get("passed")
            ]
            print(
                f"  {platform}: {passed}/{total} checks | "
                f"prompt={generated['usage']['prompt_tokens']} "
                f"completion={generated['usage']['completion_tokens']} "
                f"latency={generated['latency_sec']}s"
            )
            if failed_checks:
                print(f"  ⚠️  FAILED: {', '.join(failed_checks)}")
                print(f"  diagnostics={generated.get('diagnostics', {})}")
            return platform, generated
        except Exception as exc:
            print(f"  {platform}: ERROR — {type(exc).__name__}: {exc}")
            return platform, {
                "error": f"{type(exc).__name__}: {exc}",
                "checks": {"generation_succeeded": {"passed": False, "details": str(exc)}},
            }

    platform_results = await asyncio.gather(
        *[_generate_platform(platform) for platform in selected_platforms]
    )
    for platform, generated in platform_results:
        results[platform] = generated

    return {
        "sku": sku,
        "category": getattr(parent_sku, "category", ""),
        "collection": getattr(parent_sku, "collection", ""),
        "current_title": getattr(parent_sku, "current_title", ""),
        "platforms": results,
    }


def render_results(
    all_results: list[dict[str, Any]],
    *,
    model: str,
    reasoning_effort: str,
    selected_skus: list[str],
    selection_meta: dict[str, Any],
    selected_platforms: list[str],
) -> str:
    """Render batch test results as markdown."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    lines = [
        "# Batch Prompt Validation Results",
        "",
        f"- **Generated:** {timestamp}",
        f"- **Model:** {model}",
        f"- **Reasoning effort:** {reasoning_effort}",
        f"- **Selection mode:** {selection_meta.get('mode', 'unknown')}",
        f"- **SKUs tested:** {len(selected_skus)}",
        f"- **Platforms:** {', '.join(selected_platforms)}",
        "",
        "## Coverage",
        "",
        "| SKU | Category | Collection | Status |",
        "|---|---|---|---|",
    ]

    for result in all_results:
        status = "ERROR" if result.get("error") else "OK"
        if not result.get("error"):
            platform_errors = [
                p
                for p, pdata in result.get("platforms", {}).items()
                if p in selected_platforms and "error" in pdata
            ]
            if platform_errors:
                status = f"PARTIAL ({', '.join(platform_errors)} failed)"
        lines.append(
            f"| {result['sku']} | {result.get('category', '')} | "
            f"{result.get('collection', '') or 'None'} | {status} |"
        )

    lines.extend(
        [
            "",
            "## Constraint Summary",
            "",
            "| SKU | "
            + " | ".join(name.title() for name in selected_platforms)
            + " | Total |",
            "|---|"
            + "|".join("---|" for _ in selected_platforms)
            + "---|",
        ]
    )

    for result in all_results:
        row = [result["sku"]]
        total_pass = 0
        total_checks = 0
        for platform in selected_platforms:
            pdata = result.get("platforms", {}).get(platform, {})
            checks = pdata.get("checks", {})
            if "error" in pdata or not checks:
                row.append("ERR")
                continue
            passed = sum(1 for check in checks.values() if check.get("passed"))
            total = len(checks)
            total_pass += passed
            total_checks += total
            row.append(f"{passed}/{total}")
        row.append(f"{total_pass}/{total_checks}" if total_checks else "ERR")
        lines.append("| " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Token Usage",
            "",
            "| SKU | Prompt Tokens | Completion Tokens | Total | Latency (s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for result in all_results:
        prompt_total = 0
        completion_total = 0
        latency_total = 0.0
        for platform in selected_platforms:
            pdata = result.get("platforms", {}).get(platform, {})
            usage = pdata.get("usage", {})
            prompt_total += int(usage.get("prompt_tokens", 0) or 0)
            completion_total += int(usage.get("completion_tokens", 0) or 0)
            latency_total += float(pdata.get("latency_sec", 0) or 0)
        lines.append(
            f"| {result['sku']} | {prompt_total} | {completion_total} | "
            f"{prompt_total + completion_total} | {latency_total:.1f} |"
        )

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch per-platform prompt validation")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high"],
        default=DEFAULT_REASONING_EFFORT,
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=DEFAULT_MAX_COMPLETION_TOKENS,
    )
    parser.add_argument(
        "--platform-timeout-sec",
        type=int,
        default=DEFAULT_PLATFORM_TIMEOUT_SEC,
        help="Hard timeout per platform generation call in seconds.",
    )
    parser.add_argument(
        "--results-path",
        default=str(DEFAULT_RESULTS_PATH),
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
    )
    parser.add_argument(
        "--skus",
        nargs="*",
        default=None,
        help="Explicit SKU list (overrides canonical/unseen selection).",
    )
    parser.add_argument(
        "--unseen-count",
        type=int,
        default=0,
        help=(
            "Sample N unseen SKUs from product_catalog - generated_content - canonical_10. "
            "Default 0 keeps canonical-only mode."
        ),
    )
    parser.add_argument(
        "--unseen-seed",
        type=int,
        default=DEFAULT_UNSEEN_SEED,
    )
    parser.add_argument(
        "--include-canonical",
        action="store_true",
        help="When --unseen-count > 0, append canonical 10 SKUs to unseen sample.",
    )
    parser.add_argument(
        "--platforms",
        nargs="+",
        choices=["google", "bing", "shopify", "finish"],
        default=DEFAULT_PLATFORMS,
        help="Platforms to generate for this run (default: all).",
    )
    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    load_env_file(str(PROJECT_ROOT / ".env.vercel"))
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set. Source .env.vercel first.", file=sys.stderr)
        sys.exit(1)

    selected_skus, selection_meta = resolve_run_skus(
        explicit_skus=args.skus,
        unseen_count=max(0, args.unseen_count),
        unseen_seed=args.unseen_seed,
        include_canonical=args.include_canonical,
    )
    if not selected_skus:
        print("No SKUs selected for this run.", file=sys.stderr)
        sys.exit(1)

    run_timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    mode_suffix = str(selection_meta.get("mode", "run"))
    run_suffix = f"{mode_suffix}-{run_timestamp}"

    output_dir = Path(args.output_dir) / f"run-{run_suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.results_path == str(DEFAULT_RESULTS_PATH):
        default_stem = DEFAULT_RESULTS_PATH.stem
        results_path = DEFAULT_RESULTS_PATH.with_name(
            f"{default_stem}-{run_suffix}.md"
        )
    else:
        requested_results_path = Path(args.results_path)
        if requested_results_path.exists():
            results_path = requested_results_path.with_name(
                f"{requested_results_path.stem}-{run_suffix}{requested_results_path.suffix or '.md'}"
            )
        else:
            results_path = requested_results_path
    results_path.parent.mkdir(parents=True, exist_ok=True)

    print(
        "Running batch validation:\n"
        f"  mode={selection_meta.get('mode')}\n"
        f"  sku_count={len(selected_skus)}\n"
        f"  platforms={args.platforms}\n"
        f"  reasoning_effort={args.reasoning_effort}\n"
        f"  platform_timeout_sec={args.platform_timeout_sec}\n"
        f"  unseen_seed={args.unseen_seed}\n"
    )
    if selection_meta.get("unseen_skus"):
        print(f"  unseen_skus={selection_meta['unseen_skus']}\n")

    client = AsyncOpenAI(api_key=api_key)
    start_time = time.time()
    all_results: list[dict[str, Any]] = []

    for index, sku in enumerate(selected_skus, start=1):
        print(f"\n[{index}/{len(selected_skus)}] Generating {sku}...")
        sku_start = time.time()

        result = await generate_sku(
            client,
            sku,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            max_completion_tokens=args.max_completion_tokens,
            platform_timeout_sec=args.platform_timeout_sec,
            selected_platforms=args.platforms,
        )
        all_results.append(result)

        safe_sku = sku.replace("/", "-")
        (output_dir / f"{safe_sku}_all_platforms.json").write_text(
            json.dumps(result.get("platforms", {}), indent=2)
        )

        print(f"  Done in {time.time() - sku_start:.1f}s")

    elapsed = time.time() - start_time
    print(f"\nCompleted {len(selected_skus)} SKUs in {elapsed:.1f}s")

    report = render_results(
        all_results,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        selected_skus=selected_skus,
        selection_meta=selection_meta,
        selected_platforms=args.platforms,
    )
    results_path.write_text(report)

    summary_payload = {
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_completion_tokens": args.max_completion_tokens,
        "platform_timeout_sec": args.platform_timeout_sec,
        "selected_platforms": args.platforms,
        "selected_skus": selected_skus,
        "selection_meta": selection_meta,
        "results_path": str(results_path),
        "results": all_results,
    }
    summary_path = output_dir / f"batch_summary_{run_suffix}.json"
    summary_path.write_text(json.dumps(summary_payload, indent=2))

    print(f"Results markdown: {results_path}")
    print(f"Per-SKU raw outputs: {output_dir}")
    print(f"Structured summary: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())
