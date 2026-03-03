#!/usr/bin/env python3
"""FeedOps multi-model evaluation script.

Runs a 3-way head-to-head comparison of GPT-5.2, Claude Sonnet, and Claude Opus
across a selected set of SKUs with multiple generation passes per model.

All results are written to CSV files — NO database writes occur.
The script calls generate_per_platform() directly (bypassing HTTP and DB persistence).

Usage:
    cd /path/to/Allied-FeedOps
    set -a && source .env.vercel && set +a
    PYTHONPATH=./src python scripts/run_model_evaluation.py \\
        --skus 920D-6 AP-41/18 DMF-2/2X \\
        --models gpt-5.2 claude-sonnet-4-6 claude-opus-4-6 \\
        --passes 3 \\
        --output-dir docs/evaluation

Required env vars:
    OPENAI_API_KEY      — for gpt-5.2
    ANTHROPIC_API_KEY   — for claude-* models
    SUPABASE_URL        — to load ParentSKU from product_catalog
    SUPABASE_KEY        — (or SUPABASE_SERVICE_ROLE_KEY)

Exit codes:
    0 — Evaluation completed (some rows may have errors, check CSV)
    1 — Fatal error (missing credentials, no SKUs loaded)
    2 — Setup/configuration error
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import difflib
import json
import logging
import os
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path

# ---------------------------------------------------------------------------
# Pricing table (verified 2026-03-03 from platform.openai.com and claude.ai)
# ---------------------------------------------------------------------------
PRICING: dict[str, dict[str, float]] = {
    "gpt-5.2": {
        "input_per_mtok": 1.75,
        "cached_per_mtok": 0.175,   # 90% discount on cached input
        "output_per_mtok": 14.0,
    },
    "claude-sonnet-4-6": {
        "input_per_mtok": 3.0,
        "cached_per_mtok": 0.30,    # 0.1x base price for cache reads
        "output_per_mtok": 15.0,
    },
    "claude-opus-4-6": {
        "input_per_mtok": 5.0,
        "cached_per_mtok": 0.50,    # 0.1x base price for cache reads
        "output_per_mtok": 25.0,
    },
}

# Model → env var configuration
MODEL_CONFIGS: dict[str, dict[str, str]] = {
    "gpt-5.2": {
        "FEEDOPS_PROVIDER": "openai",
        "FEEDOPS_OPENAI_MODEL": "gpt-5.2",
    },
    "claude-sonnet-4-6": {
        "FEEDOPS_PROVIDER": "claude",
        "FEEDOPS_CLAUDE_MODEL": "claude-sonnet-4-6",
    },
    "claude-opus-4-6": {
        "FEEDOPS_PROVIDER": "claude",
        "FEEDOPS_CLAUDE_MODEL": "claude-opus-4-6",
    },
}

# CSV output fields (one row per SKU x model x pass x platform)
CSV_FIELDS = [
    "sku",
    "model",
    "pass_num",
    "platform",
    "title",
    "description",
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "latency_ms",
    "cost_usd",
    "parse_mode",
    "json_retries",
    "api_retries",
    "has_approved_content",
    "error",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("eval")


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def calculate_cost_usd(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
) -> float:
    """Calculate cost in USD for a single generation call."""
    rates = PRICING.get(model)
    if not rates:
        # Unknown model — fall back to gpt-5.2 rates as approximation
        logger.warning("No pricing data for model=%s, using gpt-5.2 rates", model)
        rates = PRICING["gpt-5.2"]
    uncached = max(prompt_tokens - cached_tokens, 0)
    input_cost = (uncached / 1_000_000) * rates["input_per_mtok"]
    cached_cost = (cached_tokens / 1_000_000) * rates["cached_per_mtok"]
    output_cost = (completion_tokens / 1_000_000) * rates["output_per_mtok"]
    return round(input_cost + cached_cost + output_cost, 6)


def measure_consistency(outputs: list[str]) -> float:
    """Mean pairwise similarity across all pairs in outputs list (0.0-1.0)."""
    if len(outputs) < 2:
        return 1.0
    pairs = [
        (outputs[i], outputs[j])
        for i in range(len(outputs))
        for j in range(i + 1, len(outputs))
    ]
    scores = [difflib.SequenceMatcher(None, a, b).ratio() for a, b in pairs]
    return sum(scores) / len(scores)


def latency_stats(latencies_ms: list[int]) -> dict[str, object]:
    """Compute p50 and p95 latency from a list of measurements."""
    if not latencies_ms:
        return {"p50_ms": None, "p95_ms": None, "count": 0}
    sorted_lat = sorted(latencies_ms)
    p50 = statistics.median(sorted_lat)
    if len(sorted_lat) >= 2:
        # p95: 19/20 quantile
        p95 = statistics.quantiles(sorted_lat, n=20)[18]
    else:
        p95 = float(sorted_lat[-1])
    return {"p50_ms": int(p50), "p95_ms": int(p95), "count": len(latencies_ms)}


@contextmanager
def model_env(config: dict[str, str]):
    """Context manager that sets env vars for a model run then restores them."""
    keys = list(config.keys())
    saved = {k: os.environ.get(k) for k in keys}
    os.environ.update(config)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _get_supabase_credentials() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    )
    if not url or not key:
        print(
            "ERROR: SUPABASE_URL / SUPABASE_KEY not set. "
            "Run: set -a && source .env.vercel && set +a",
            file=sys.stderr,
        )
        sys.exit(2)
    return url.rstrip("/"), key


def _check_approved_content(supabase_url: str, supabase_key: str, master_sku: str) -> bool:
    """Return True if the SKU has any approved content in generated_content table."""
    import urllib.error
    import urllib.request

    sql = (
        f"SELECT COUNT(*) AS cnt FROM generated_content "
        f"WHERE master_sku = '{master_sku.replace(chr(39), chr(39)*2)}' "
        f"AND approved_content IS NOT NULL AND approved_content != ''"
    )
    endpoint = f"{supabase_url}/rest/v1/rpc/execute_sql"
    payload = json.dumps({"query": sql}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data:
                return int(data[0].get("cnt", 0)) > 0
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Core evaluation logic
# ---------------------------------------------------------------------------


async def run_single_pass(
    *,
    master_sku: str,
    model: str,
    pass_num: int,
    platforms: list[str],
    reasoning_effort: str,
    max_completion_tokens: int,
    has_approved_content: bool,
) -> list[dict]:
    """Run generate_per_platform for one SKU x model x pass. Returns CSV rows."""
    from feedops.providers.factory import get_provider
    from feedops.providers.base import close_provider
    from feedops.pipeline.generator import generate_per_platform
    from feedops.api.supabase_loader import load_parent_sku_from_supabase

    error_rows: list[dict] = []

    # Load ParentSKU
    parent_sku = load_parent_sku_from_supabase(master_sku)
    if parent_sku is None:
        msg = f"ParentSKU not found in product_catalog: {master_sku}"
        logger.error(msg)
        for platform in platforms:
            error_rows.append({
                "sku": master_sku,
                "model": model,
                "pass_num": pass_num,
                "platform": platform,
                "title": "",
                "description": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "latency_ms": 0,
                "cost_usd": 0.0,
                "parse_mode": "",
                "json_retries": 0,
                "api_retries": 0,
                "has_approved_content": has_approved_content,
                "error": msg,
            })
        return error_rows

    # Instantiate provider with current env (set by model_env context manager)
    provider = get_provider()
    rows: list[dict] = []

    try:
        result = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
            reasoning_effort=reasoning_effort,
            max_completion_tokens=max_completion_tokens,
            selected_platforms=platforms,
        )
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error("Generation failed for %s/%s/pass%d: %s", master_sku, model, pass_num, err_msg)
        for platform in platforms:
            rows.append({
                "sku": master_sku,
                "model": model,
                "pass_num": pass_num,
                "platform": platform,
                "title": "",
                "description": "",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "latency_ms": 0,
                "cost_usd": 0.0,
                "parse_mode": "",
                "json_retries": 0,
                "api_retries": 0,
                "has_approved_content": has_approved_content,
                "error": err_msg,
            })
        return rows
    finally:
        try:
            await close_provider(provider)
        except Exception:
            pass

    # Extract per-platform metrics
    usage_by_platform: dict[str, dict] = result.get("usage_by_platform") or {}
    latency_by_platform: dict[str, int] = result.get("latency_by_platform") or {}
    parse_by_platform: dict[str, str] = result.get("parse_by_platform") or {}
    retry_by_platform: dict[str, int] = result.get("retry_by_platform") or {}

    for platform in platforms:
        usage = usage_by_platform.get(platform) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cached_tokens = int(usage.get("cached_tokens", 0))
        latency_ms = int(latency_by_platform.get(platform, 0))
        parse_info = parse_by_platform.get(platform, "")
        if isinstance(parse_info, dict):
            parse_mode = str(parse_info.get("parse_mode", ""))
        else:
            parse_mode = str(parse_info)
        retry_info = retry_by_platform.get(platform, {})
        if isinstance(retry_info, dict):
            json_retries = int(retry_info.get("json_parse_retries", retry_info.get("attempt_count", 0)))
            api_retries = int(retry_info.get("api_retries", retry_info.get("attempt_count", 0)))
        else:
            json_retries = int(retry_info) if retry_info else 0
            api_retries = int(usage.get("api_retries", 0))

        cost_usd = calculate_cost_usd(model, prompt_tokens, completion_tokens, cached_tokens)

        # Extract content — keys are {platform}_title and {platform}_description
        title = str(result.get(f"{platform}_title", "") or "")
        description = str(result.get(f"{platform}_description", "") or "")

        rows.append({
            "sku": master_sku,
            "model": model,
            "pass_num": pass_num,
            "platform": platform,
            "title": title,
            "description": description,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "parse_mode": parse_mode,
            "json_retries": json_retries,
            "api_retries": api_retries,
            "has_approved_content": has_approved_content,
            "error": "",
        })

    return rows


async def run_evaluation(
    *,
    skus: list[str],
    models: list[str],
    passes: int,
    platforms: list[str],
    reasoning_effort: str,
    max_completion_tokens: int,
    output_dir: Path,
    sleep_between_calls: float,
) -> list[dict]:
    """Run the full evaluation loop. Returns all CSV rows."""
    supabase_url, supabase_key = _get_supabase_credentials()

    # Pre-check approved content for all SKUs
    logger.info("Checking approved content status for %d SKUs...", len(skus))
    approved_lookup: dict[str, bool] = {}
    for sku in skus:
        approved_lookup[sku] = _check_approved_content(supabase_url, supabase_key, sku)
        logger.info("  %s — approved_content: %s", sku, approved_lookup[sku])

    all_rows: list[dict] = []
    total_calls = len(skus) * len(models) * passes
    call_num = 0

    for sku_idx, sku in enumerate(skus, start=1):
        for model in models:
            if model not in MODEL_CONFIGS:
                logger.warning("Unknown model %s — skipping (no env config found)", model)
                continue

            config = MODEL_CONFIGS[model]

            for pass_num in range(1, passes + 1):
                call_num += 1
                print(
                    f"\nGenerating SKU {sku_idx}/{len(skus)} ({sku}) "
                    f"model={model} pass={pass_num}/{passes} "
                    f"[{call_num}/{total_calls}]",
                    flush=True,
                )

                with model_env(config):
                    rows = await run_single_pass(
                        master_sku=sku,
                        model=model,
                        pass_num=pass_num,
                        platforms=platforms,
                        reasoning_effort=reasoning_effort,
                        max_completion_tokens=max_completion_tokens,
                        has_approved_content=approved_lookup.get(sku, False),
                    )

                all_rows.extend(rows)

                # Print brief preview
                for row in rows:
                    if row["error"]:
                        print(f"  [{row['platform']}] ERROR: {row['error'][:80]}")
                    else:
                        title_preview = (row["title"] or "")[:60]
                        desc_len = len(row["description"] or "")
                        lat = row["latency_ms"]
                        cost = row["cost_usd"]
                        print(
                            f"  [{row['platform']}] latency={lat}ms "
                            f"cost=${cost:.4f} desc_len={desc_len} "
                            f'title="{title_preview}"'
                        )

                # Write partial results to CSV after each call (for crash recovery)
                _write_csv(output_dir / "raw_results.csv", all_rows)

                # Rate-limit safety between calls
                if call_num < total_calls:
                    time.sleep(sleep_between_calls)

    return all_rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    """Write all rows to CSV (overwrites existing file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Consistency analysis
# ---------------------------------------------------------------------------


def compute_consistency_analysis(rows: list[dict]) -> str:
    """Compute mean pairwise consistency across 3 passes per SKU x model x platform."""
    from collections import defaultdict

    # Group: (sku, model, platform) -> list of (pass_num, content)
    groups: dict[tuple, list[str]] = defaultdict(list)
    for row in rows:
        if row.get("error"):
            continue
        key = (row["sku"], row["model"], row["platform"])
        content = f"{row.get('title', '')} ||| {row.get('description', '')}"
        groups[key].append(content)

    lines = [
        "# Output Consistency Analysis",
        "",
        "Mean pairwise similarity across generation passes (0.0 = entirely different, 1.0 = identical).",
        "Computed using `difflib.SequenceMatcher.ratio()` on `title ||| description` concatenation.",
        "",
        "## Title Consistency",
        "",
        "| SKU | Model | Platform | Passes | Similarity |",
        "|-----|-------|----------|--------|------------|",
    ]

    # Per-combination results
    results: list[tuple[str, str, str, int, float]] = []
    for (sku, model, platform), contents in sorted(groups.items()):
        score = measure_consistency(contents)
        results.append((sku, model, platform, len(contents), score))
        lines.append(f"| {sku} | {model} | {platform} | {len(contents)} | {score:.3f} |")

    lines += ["", "## Summary by Model", ""]
    from collections import defaultdict
    model_scores: dict[str, list[float]] = defaultdict(list)
    for _, model, _, _, score in results:
        model_scores[model].append(score)

    lines += ["| Model | Mean Similarity | Std Dev | Samples |", "|-------|-----------------|---------|---------|"]
    for model, scores in sorted(model_scores.items()):
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        lines.append(f"| {model} | {mean:.3f} | {std:.3f} | {len(scores)} |")

    lines += ["", "## Interpretation", ""]
    lines += [
        "- **>0.90**: Very consistent — model produces nearly identical outputs across runs",
        "- **0.75-0.90**: Consistent — minor wording variation, same structure",
        "- **0.50-0.75**: Moderate variance — notable variation in phrasing",
        "- **<0.50**: High variance — substantially different outputs across runs",
        "",
        "Note: Run 1 may be slower (cold cache) than Runs 2-3 (warm cache). "
        "Latency data in raw_results.csv shows cache impact per pass.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------


def print_summary_statistics(rows: list[dict], models: list[str]) -> None:
    """Print p50/p95 latency and cost summary per model to stdout."""
    from collections import defaultdict

    latencies_by_model: dict[str, list[int]] = defaultdict(list)
    costs_by_model_sku: dict[tuple, list[float]] = defaultdict(list)
    errors_by_model: dict[str, int] = defaultdict(int)

    for row in rows:
        model = row["model"]
        if row.get("error"):
            errors_by_model[model] += 1
            continue
        lat = row.get("latency_ms", 0)
        if lat > 0:
            latencies_by_model[model].append(int(lat))
        costs_by_model_sku[(model, row["sku"])].append(float(row.get("cost_usd", 0)))

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    print("\nLatency per model (all platforms combined):")
    print(f"  {'Model':<25} {'p50 (ms)':>10} {'p95 (ms)':>10} {'Samples':>8}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*8}")
    for model in models:
        lats = latencies_by_model.get(model, [])
        if lats:
            stats = latency_stats(lats)
            print(f"  {model:<25} {stats['p50_ms']:>10} {stats['p95_ms']:>10} {stats['count']:>8}")
        else:
            print(f"  {model:<25} {'N/A':>10} {'N/A':>10} {'0':>8}")

    print("\nAverage cost per SKU per model (all passes x platforms):")
    print(f"  {'Model':<25} {'Avg Cost/SKU':>14} {'Total Cost':>12}")
    print(f"  {'-'*25} {'-'*14} {'-'*12}")
    for model in models:
        sku_costs = {}
        for (m, sku), costs in costs_by_model_sku.items():
            if m == model:
                sku_costs[sku] = sum(costs)
        if sku_costs:
            avg = statistics.mean(sku_costs.values())
            total = sum(sku_costs.values())
            print(f"  {model:<25} ${avg:>13.4f} ${total:>11.4f}")
        else:
            print(f"  {model:<25} {'N/A':>14} {'N/A':>12}")

    total_rows = len(rows)
    total_errors = sum(errors_by_model.values())
    print(f"\nTotal rows: {total_rows} | Errors: {total_errors} | Success rate: "
          f"{(total_rows - total_errors) / total_rows * 100:.1f}%")

    if total_errors > 0:
        print("\nErrors by model:")
        for model, count in sorted(errors_by_model.items()):
            if count > 0:
                print(f"  {model}: {count} errors")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="FeedOps multi-model evaluation — generates content for N SKUs across M models with P passes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--skus",
        nargs="+",
        required=True,
        metavar="SKU",
        help="Master SKUs to evaluate (space-separated, e.g. 920D-6 AP-41/18).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt-5.2", "claude-sonnet-4-6", "claude-opus-4-6"],
        metavar="MODEL",
        help="Models to compare (default: gpt-5.2 claude-sonnet-4-6 claude-opus-4-6).",
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=3,
        help="Generation passes per SKU x model (default: 3).",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/evaluation",
        metavar="DIR",
        help="Directory for all output files (default: docs/evaluation).",
    )
    parser.add_argument(
        "--platforms",
        default="google,bing,shopify",
        metavar="PLATFORMS",
        help="Comma-separated platforms to generate (default: google,bing,shopify).",
    )
    parser.add_argument(
        "--reasoning-effort",
        default="high",
        choices=["low", "medium", "high"],
        help="Reasoning effort for all models (default: high — locked decision from Phase 4).",
    )
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        default=6000,
        help="Max completion tokens per generation call (default: 6000).",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Sleep between generation calls for rate limit safety (default: 2.0s).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    if not platforms:
        print("ERROR: --platforms produced empty list.", file=sys.stderr)
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Validate model names
    unknown_models = [m for m in args.models if m not in MODEL_CONFIGS]
    if unknown_models:
        print(f"WARNING: Unknown models (no config entry): {unknown_models}", file=sys.stderr)
        print(f"Known models: {list(MODEL_CONFIGS.keys())}", file=sys.stderr)

    # Check required credentials
    missing_creds: list[str] = []
    needs_openai = any(MODEL_CONFIGS.get(m, {}).get("FEEDOPS_PROVIDER") == "openai" for m in args.models)
    needs_claude = any(MODEL_CONFIGS.get(m, {}).get("FEEDOPS_PROVIDER") == "claude" for m in args.models)
    if needs_openai and not os.environ.get("OPENAI_API_KEY"):
        missing_creds.append("OPENAI_API_KEY")
    if needs_claude and not os.environ.get("ANTHROPIC_API_KEY"):
        missing_creds.append("ANTHROPIC_API_KEY")
    if missing_creds:
        print(f"ERROR: Missing required env vars: {', '.join(missing_creds)}", file=sys.stderr)
        print("Run: set -a && source .env.vercel && set +a", file=sys.stderr)
        return 2

    total_calls = len(args.skus) * len(args.models) * args.passes
    total_rows = total_calls * len(platforms)
    est_minutes = total_calls * 3 / 60  # ~3 min per call rough estimate

    print("=" * 70)
    print("FeedOps Model Evaluation")
    print("=" * 70)
    print(f"  SKUs:             {args.skus}")
    print(f"  Models:           {args.models}")
    print(f"  Passes:           {args.passes}")
    print(f"  Platforms:        {platforms}")
    print(f"  Reasoning effort: {args.reasoning_effort}")
    print(f"  Output dir:       {output_dir.resolve()}")
    print(f"  Total calls:      {total_calls} ({total_rows} rows expected)")
    print(f"  Est. wall time:   ~{est_minutes:.0f} min (at 3 min/call)")
    print()

    start_time = time.time()

    try:
        all_rows = asyncio.run(
            run_evaluation(
                skus=args.skus,
                models=args.models,
                passes=args.passes,
                platforms=platforms,
                reasoning_effort=args.reasoning_effort,
                max_completion_tokens=args.max_completion_tokens,
                output_dir=output_dir,
                sleep_between_calls=args.sleep,
            )
        )
    except KeyboardInterrupt:
        print("\nInterrupted by user. Partial results already written to CSV.", file=sys.stderr)
        return 1

    # Write final CSV (already written incrementally, this is the final flush)
    csv_path = output_dir / "raw_results.csv"
    _write_csv(csv_path, all_rows)
    print(f"\nWrote {len(all_rows)} rows to {csv_path}")

    # Compute and write consistency analysis
    consistency_md = compute_consistency_analysis(all_rows)
    consistency_path = output_dir / "consistency_analysis.md"
    with open(consistency_path, "w", encoding="utf-8") as f:
        f.write(consistency_md)
    print(f"Wrote consistency analysis to {consistency_path}")

    # Print summary statistics
    print_summary_statistics(all_rows, args.models)

    elapsed = time.time() - start_time
    print(f"\nTotal wall time: {elapsed / 60:.1f} min")

    return 0


if __name__ == "__main__":
    sys.exit(main())
