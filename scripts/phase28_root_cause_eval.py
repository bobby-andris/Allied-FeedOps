#!/usr/bin/env python3
"""Phase 28 root-cause evaluation runner for platform prompt quality.

This runner executes controlled variants over a SKU corpus, emits PromptEvalRecord
JSONL artifacts, writes summary CSVs, computes paired deltas with bootstrap CIs,
and renders a root-cause report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import statistics
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Ensure project root imports resolve when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

try:
    from pyparsing.warnings import (
        PyparsingDeprecationWarning,
        PyparsingDiagnosticWarning,
    )
except Exception:  # pragma: no cover - fallback for environments without pyparsing
    PyparsingDeprecationWarning = Warning
    PyparsingDiagnosticWarning = Warning

try:
    from pydantic.warnings import PydanticDeprecatedSince212
except Exception:  # pragma: no cover - fallback for environments without pydantic warnings
    PydanticDeprecatedSince212 = Warning

warnings.filterwarnings(
    "ignore",
    message="'enablePackrat' deprecated - use 'enable_packrat'",
    category=PyparsingDeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    category=PyparsingDeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="warn_ungrouped_named_tokens_in_collection.*",
    category=PyparsingDiagnosticWarning,
)
warnings.filterwarnings(
    "ignore",
    category=PydanticDeprecatedSince212,
)

from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.api.prompt_builder import get_prompt_experiment_variant
from feedops.pipeline.generator import generate_per_platform
from feedops.providers.factory import get_provider
from feedops.quality.evaluator import (
    PromptEvalRecord,
    build_prompt_eval_record,
    summarize_prompt_eval_records,
    write_prompt_eval_records,
    write_prompt_eval_summary_csv,
)

logger = logging.getLogger(__name__)

try:
    from ab_prompt_test import evaluate_platform_output as _evaluate_platform_output
except Exception as exc:  # pragma: no cover - exercised via integration tests
    _evaluate_platform_output = None
    _AB_PROMPT_IMPORT_ERROR = exc
else:
    _AB_PROMPT_IMPORT_ERROR = None
_POLICY_WARNING_EMITTED = False


def load_env_file(path: str) -> None:
    """Load environment variables from a dotenv-style file."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


RELIABILITY_THRESHOLDS = {
    "parse_fallback_rate": 0.01,
    "short_content_rate": 0.02,
    "empty_or_placeholder_rate": 0.0,
}
_VARIANT_ENV_KEY = "FEEDOPS_PROMPT_EXPERIMENT_VARIANT"


@dataclass(frozen=True)
class SKUEntry:
    master_sku: str
    category: str
    tier: str


def _now_run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())


def _load_sku_corpus(path: Path) -> list[SKUEntry]:
    rows = json.loads(path.read_text())
    corpus: list[SKUEntry] = []
    for row in rows:
        master_sku = str(row.get("master_sku", "")).strip()
        category = str(row.get("category", "")).strip()
        tier = str(row.get("tier", "unclassified")).strip() or "unclassified"
        if not master_sku or not category:
            continue
        corpus.append(SKUEntry(master_sku=master_sku, category=category, tier=tier))
    return corpus


def _select_screening_subset(corpus: list[SKUEntry], size: int = 16) -> list[SKUEntry]:
    if len(corpus) <= size:
        return corpus
    buckets: dict[str, list[SKUEntry]] = {}
    for entry in corpus:
        buckets.setdefault(entry.tier, []).append(entry)
    per_bucket = max(1, size // max(len(buckets), 1))
    selected: list[SKUEntry] = []
    for tier in sorted(buckets):
        selected.extend(buckets[tier][:per_bucket])
    if len(selected) < size:
        seen = {entry.master_sku for entry in selected}
        for entry in corpus:
            if entry.master_sku in seen:
                continue
            selected.append(entry)
            if len(selected) >= size:
                break
    return selected[:size]


def _normalize_variants(raw_variants: list[str]) -> list[str]:
    """Canonicalize and deduplicate variant labels using prompt builder rules."""
    normalized: list[str] = []
    seen: set[str] = set()
    original_value = os.environ.get(_VARIANT_ENV_KEY)
    try:
        for raw_variant in raw_variants:
            candidate = str(raw_variant).strip().lower()
            if not candidate:
                continue
            os.environ[_VARIANT_ENV_KEY] = candidate
            canonical = get_prompt_experiment_variant()
            if canonical != candidate:
                logger.warning(
                    "Variant '%s' normalized to '%s' for execution",
                    candidate,
                    canonical,
                )
            if canonical in seen:
                continue
            seen.add(canonical)
            normalized.append(canonical)
    finally:
        if original_value is None:
            os.environ.pop(_VARIANT_ENV_KEY, None)
        else:
            os.environ[_VARIANT_ENV_KEY] = original_value
    return normalized or ["control"]


def _platform_payload(
    generated: dict[str, Any],
    platform: str,
) -> dict[str, Any]:
    raw_by_platform = generated.get("raw_by_platform", {})
    payload = raw_by_platform.get(platform, {})
    if isinstance(payload, dict):
        return payload
    return {}


def _policy_violations(
    *,
    platform: str,
    payload: dict[str, Any],
    parent_sku: Any,
) -> list[str]:
    global _POLICY_WARNING_EMITTED
    if _evaluate_platform_output is None:
        if not _POLICY_WARNING_EMITTED:
            logger.warning(
                "Policy checks unavailable because ab_prompt_test import failed: %s",
                _AB_PROMPT_IMPORT_ERROR,
            )
            _POLICY_WARNING_EMITTED = True
        return []
    checks = _evaluate_platform_output(platform, payload, parent_sku)
    violations: list[str] = []
    for check_name, check in checks.items():
        if check.get("passed"):
            continue
        violations.append(f"{check_name}: {check.get('details')}")
    return violations


def _bootstrap_ci(values: list[float], *, samples: int = 2000) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    rng = random.Random(42)
    estimates: list[float] = []
    for _ in range(samples):
        draw = [values[rng.randrange(0, len(values))] for _ in range(len(values))]
        estimates.append(sum(draw) / len(draw))
    estimates.sort()
    lower_idx = int(samples * 0.025)
    upper_idx = int(samples * 0.975)
    return (round(estimates[lower_idx], 3), round(estimates[upper_idx], 3))


def _paired_variant_deltas(records: list[PromptEvalRecord]) -> list[dict[str, Any]]:
    control: dict[tuple[str, str], dict[str, float]] = {}
    variants: dict[tuple[str, str, str], dict[str, float]] = {}

    grouped: dict[tuple[str, str, str], list[PromptEvalRecord]] = {}
    for record in records:
        grouped.setdefault((record.variant, record.platform, record.sku), []).append(record)

    for (variant, platform, sku), bucket in grouped.items():
        title_avg = sum(
            float(r.quality_scores["title_quality_index"]["overall"]) for r in bucket
        ) / len(bucket)
        desc_avg = sum(
            float(r.quality_scores["description_quality_index"]["overall"]) for r in bucket
        ) / len(bucket)
        if variant == "control":
            control[(platform, sku)] = {"title": title_avg, "description": desc_avg}
        else:
            variants[(variant, platform, sku)] = {"title": title_avg, "description": desc_avg}

    rows: list[dict[str, Any]] = []
    by_variant_platform: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for (variant, platform, sku), score in variants.items():
        control_score = control.get((platform, sku))
        if not control_score:
            continue
        by_variant_platform.setdefault((variant, platform), []).append(
            (
                score["title"] - control_score["title"],
                score["description"] - control_score["description"],
            )
        )

    for (variant, platform), deltas in sorted(by_variant_platform.items()):
        title_deltas = [d[0] for d in deltas]
        desc_deltas = [d[1] for d in deltas]
        title_ci = _bootstrap_ci(title_deltas)
        desc_ci = _bootstrap_ci(desc_deltas)
        rows.append(
            {
                "variant": variant,
                "platform": platform,
                "paired_skus": len(deltas),
                "title_delta": round(statistics.mean(title_deltas), 3),
                "title_ci_low": title_ci[0],
                "title_ci_high": title_ci[1],
                "description_delta": round(statistics.mean(desc_deltas), 3),
                "description_ci_low": desc_ci[0],
                "description_ci_high": desc_ci[1],
            }
        )
    return rows


def _reliability_gate_status(summary_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for row in summary_rows:
        parse_ok = float(row.get("parse_fallback_rate", 1)) < RELIABILITY_THRESHOLDS["parse_fallback_rate"]
        short_ok = float(row.get("short_content_rate", 1)) < RELIABILITY_THRESHOLDS["short_content_rate"]
        empty_ok = float(row.get("empty_or_placeholder_rate", 1)) <= RELIABILITY_THRESHOLDS["empty_or_placeholder_rate"]
        statuses.append(
            {
                "variant": row["variant"],
                "platform": row["platform"],
                "pass": parse_ok and short_ok and empty_ok,
                "parse_ok": parse_ok,
                "short_ok": short_ok,
                "empty_ok": empty_ok,
            }
        )
    return statuses


def _write_report(
    *,
    report_path: Path,
    run_id: str,
    variants: list[str],
    corpus_size: int,
    replicates: int,
    summary_rows: list[dict[str, Any]],
    delta_rows: list[dict[str, Any]],
) -> None:
    gate_rows = _reliability_gate_status(summary_rows)
    gate_lookup = {(row["variant"], row["platform"]): row for row in gate_rows}

    lines: list[str] = []
    lines.append("# Phase 28 Root-Cause Report")
    lines.append("")
    lines.append(f"- Run ID: `{run_id}`")
    lines.append(f"- Variants: `{', '.join(variants)}`")
    lines.append(f"- Corpus size: `{corpus_size}`")
    lines.append(f"- Replicates: `{replicates}`")
    lines.append("")

    lines.append("## Reliability Summary")
    lines.append("")
    lines.append("| Variant | Platform | Parse Fallback | Short Content | Empty/Placeholder | Gate |")
    lines.append("|---|---|---:|---:|---:|---|")
    for row in summary_rows:
        gate = gate_lookup.get((row["variant"], row["platform"]), {})
        lines.append(
            f"| {row['variant']} | {row['platform']} | "
            f"{row['parse_fallback_rate']:.2%} | {row['short_content_rate']:.2%} | "
            f"{row['empty_or_placeholder_rate']:.2%} | "
            f"{'PASS' if gate.get('pass') else 'FAIL'} |"
        )
    lines.append("")

    lines.append("## Paired Delta vs Control")
    lines.append("")
    if not delta_rows:
        lines.append("No non-control variants were included, so no paired deltas were computed.")
        lines.append("")
    else:
        lines.append("| Variant | Platform | Paired SKUs | Title Δ | Title CI (95%) | Description Δ | Description CI (95%) |")
        lines.append("|---|---|---:|---:|---|---:|---|")
        for row in delta_rows:
            lines.append(
                f"| {row['variant']} | {row['platform']} | {row['paired_skus']} | "
                f"{row['title_delta']:+.2f} | [{row['title_ci_low']:+.2f}, {row['title_ci_high']:+.2f}] | "
                f"{row['description_delta']:+.2f} | [{row['description_ci_low']:+.2f}, {row['description_ci_high']:+.2f}] |"
            )
        lines.append("")

        lines.append("## Causal Ranking")
        lines.append("")
        by_variant: dict[str, list[dict[str, Any]]] = {}
        for row in delta_rows:
            by_variant.setdefault(row["variant"], []).append(row)
        ranked: list[tuple[float, str, str]] = []
        for variant, rows in by_variant.items():
            gb_rows = [r for r in rows if r["platform"] in {"google", "bing"}]
            if not gb_rows:
                continue
            score = sum(
                float(r["title_delta"]) + float(r["description_delta"]) for r in gb_rows
            ) / (2 * len(gb_rows))
            classification = "Contributing"
            if all(
                float(r["title_delta"]) >= 8
                and float(r["description_delta"]) >= 8
                and float(r["title_ci_low"]) > 0
                and float(r["description_ci_low"]) > 0
                for r in gb_rows
            ):
                classification = "Primary"
            elif any(
                float(r["title_delta"]) >= 8 or float(r["description_delta"]) >= 8
                for r in gb_rows
            ):
                classification = "Secondary"
            ranked.append((score, variant, classification))
        ranked.sort(reverse=True)
        if not ranked:
            lines.append("No ranked variants yet (run control + at least one ablation).")
        else:
            for score, variant, classification in ranked:
                lines.append(f"- `{variant}`: {classification} (combined delta score `{score:+.2f}`)")
        lines.append("")

    lines.append("## Next Actions")
    lines.append("")
    lines.append("- Keep only factors classified as Primary/Secondary that also pass reliability gates.")
    lines.append("- Build finalist by combining independently positive factors.")
    lines.append("- Re-run full 48-SKU validation before rollout.")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


async def run_evaluation(
    *,
    run_id: str,
    corpus: list[SKUEntry],
    variants: list[str],
    platforms: list[str],
    replicates: int,
    reasoning_effort: str,
    max_completion_tokens: int,
) -> list[PromptEvalRecord]:
    provider = get_provider()
    records: list[PromptEvalRecord] = []
    os.environ["FEEDOPS_PROMPT_VERSION"] = "v2"

    for variant in variants:
        os.environ["FEEDOPS_PROMPT_EXPERIMENT_VARIANT"] = variant
        for entry in corpus:
            parent_sku = load_parent_sku_from_supabase(entry.master_sku)
            if not parent_sku:
                print(f"[WARN] Missing SKU in catalog: {entry.master_sku}")
                continue
            for rep in range(replicates):
                generated = await generate_per_platform(
                    parent_sku=parent_sku,
                    provider=provider,
                    prompt_version="v2",
                    reasoning_effort=reasoning_effort,
                    max_completion_tokens=max_completion_tokens,
                    selected_platforms=tuple(platforms),
                )
                prompt_hashes = generated.get("prompt_hashes", {}) or {}
                schema_hashes = generated.get("schema_hashes", {}) or {}
                usage_map = generated.get("usage_by_platform", {}) or {}
                parse_map = generated.get("parse_by_platform", {}) or {}

                for platform in platforms:
                    payload = _platform_payload(generated, platform)
                    policy = _policy_violations(
                        platform=platform,
                        payload=payload,
                        parent_sku=parent_sku,
                    )
                    record = build_prompt_eval_record(
                        run_id=run_id,
                        sku=entry.master_sku,
                        platform=platform,
                        variant=variant,
                        prompt_hash=str(prompt_hashes.get(platform, "")),
                        schema_hash=str(schema_hashes.get(platform, "")),
                        usage=usage_map.get(platform, {}),
                        parse_details=parse_map.get(platform, {}),
                        payload=payload,
                        policy_violations=policy,
                    )
                    records.append(record)
                print(
                    f"[{variant}] {entry.master_sku} rep={rep + 1}/{replicates} done "
                    f"(platforms={','.join(platforms)})"
                )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 28 root-cause prompt evaluation")
    parser.add_argument(
        "--sample-file",
        default=str(PROJECT_ROOT / "samples" / "eval-skus-phase28.json"),
        help="Path to phase28 SKU corpus JSON",
    )
    parser.add_argument(
        "--variants",
        default="control",
        help="Comma-separated variant list (e.g. control,a1_placeholder_burden_relaxed)",
    )
    parser.add_argument(
        "--platforms",
        default="google,bing,shopify",
        help="Comma-separated platforms to evaluate",
    )
    parser.add_argument("--replicates", type=int, default=3, help="Replicates per SKU/platform")
    parser.add_argument(
        "--screening",
        action="store_true",
        help="Use 16-SKU screening subset instead of full corpus",
    )
    parser.add_argument(
        "--sku-limit",
        type=int,
        default=0,
        help="Optional cap for quick dry-runs/testing",
    )
    parser.add_argument("--reasoning-effort", default="high", choices=["low", "medium", "high"])
    parser.add_argument("--max-completion-tokens", type=int, default=16000)
    parser.add_argument(
        "--output-root",
        default=str(PROJECT_ROOT / "artifacts" / "prompt-quality"),
        help="Root output directory for JSONL/CSV artifacts",
    )
    parser.add_argument(
        "--report-path",
        default=str(PROJECT_ROOT / "docs" / "experiments" / "phase28-root-cause-report.md"),
        help="Root-cause report markdown output path",
    )
    parser.add_argument("--run-id", default="", help="Optional run id override")
    parser.add_argument("--dry-run", action="store_true", help="Only print planned run settings")
    return parser.parse_args()


def main() -> None:
    load_env_file(str(PROJECT_ROOT / ".env.vercel"))
    args = parse_args()

    sample_file = Path(args.sample_file)
    corpus = _load_sku_corpus(sample_file)
    if args.screening:
        corpus = _select_screening_subset(corpus, size=16)
    if args.sku_limit > 0:
        corpus = corpus[: args.sku_limit]

    raw_variants = [item.strip() for item in args.variants.split(",") if item.strip()]
    variants = _normalize_variants(raw_variants)
    platforms = [item.strip().lower() for item in args.platforms.split(",") if item.strip()]
    run_id = args.run_id.strip() or _now_run_id()

    print(
        "Phase 28 evaluation run:\n"
        f"  run_id={run_id}\n"
        f"  sample_file={sample_file}\n"
        f"  corpus_size={len(corpus)}\n"
        f"  variants={variants}\n"
        f"  platforms={platforms}\n"
        f"  replicates={args.replicates}\n"
        f"  reasoning_effort={args.reasoning_effort}\n"
        f"  max_completion_tokens={args.max_completion_tokens}\n"
        f"  output_root={args.output_root}"
    )
    if args.dry_run:
        return

    records = asyncio.run(
        run_evaluation(
            run_id=run_id,
            corpus=corpus,
            variants=variants,
            platforms=platforms,
            replicates=args.replicates,
            reasoning_effort=args.reasoning_effort,
            max_completion_tokens=args.max_completion_tokens,
        )
    )

    output_dir = Path(args.output_root) / run_id
    records_path = output_dir / "records.jsonl"
    write_prompt_eval_records(records_path, records)
    summary_rows = summarize_prompt_eval_records(records)
    summary_csv_path = output_dir / "summary.csv"
    write_prompt_eval_summary_csv(summary_csv_path, summary_rows)
    delta_rows = _paired_variant_deltas(records)
    _write_report(
        report_path=Path(args.report_path),
        run_id=run_id,
        variants=variants,
        corpus_size=len(corpus),
        replicates=args.replicates,
        summary_rows=summary_rows,
        delta_rows=delta_rows,
    )

    print(f"\nPromptEvalRecord JSONL: {records_path}")
    print(f"Summary CSV: {summary_csv_path}")
    print(f"Report: {args.report_path}")


if __name__ == "__main__":
    main()
