"""Evaluate generated export patches with heuristic scoring."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from feedops.quality.scoring import (
    HeuristicScore,
    compute_platform_quality_indices,
    score_bundle,
)


def _platform_content_keys(platform: str) -> tuple[str, str]:
    if platform == "google":
        return "google_title", "google_description"
    if platform == "bing":
        return "bing_title", "bing_description"
    if platform == "shopify":
        return "shopify_title", "shopify_description"
    if platform == "finish":
        return "", ""
    return "", ""


def _placeholder_integrity(platform: str, payload: dict[str, Any]) -> bool:
    title_key, description_key = _platform_content_keys(platform)
    if platform in {"google", "bing"}:
        title = str(payload.get(title_key, "") or "")
        description = str(payload.get(description_key, "") or "")
        return "{FINISH_NAME}" in title and "{FINISH_SENTENCE}" in description
    if platform == "shopify":
        combined = " ".join(
            [
                str(payload.get("shopify_title", "") or ""),
                str(payload.get("shopify_description", "") or ""),
                str(payload.get("shopify_meta_description", "") or ""),
            ]
        )
        return "{FINISH_NAME}" not in combined and "{FINISH_SENTENCE}" not in combined
    return True


def _is_placeholder_only_description(platform: str, description: str) -> bool:
    """Detect placeholder-only Google/Bing descriptions, even with punctuation wrappers."""
    if platform not in {"google", "bing"}:
        return False
    text = str(description or "").strip()
    if not text:
        return True
    if "{FINISH_SENTENCE}" not in text:
        return False
    residue = text.replace("{FINISH_SENTENCE}", "")
    return re.sub(r"[\W_]+", "", residue) == ""


@dataclass(frozen=True)
class PromptEvalRecord:
    """Canonical JSONL record for Phase 28 prompt quality evaluation."""

    run_id: str
    sku: str
    platform: str
    variant: str
    prompt_hash: str
    schema_hash: str
    prompt_tokens: int
    completion_tokens: int
    parse_mode: str
    missing_keys: list[str]
    title_len: int
    desc_len: int
    placeholder_integrity: bool
    policy_violations: list[str]
    quality_scores: dict[str, Any]


def build_prompt_eval_record(
    *,
    run_id: str,
    sku: str,
    platform: str,
    variant: str,
    prompt_hash: str,
    schema_hash: str,
    usage: dict[str, Any] | None,
    parse_details: dict[str, Any] | None,
    payload: dict[str, Any] | None,
    policy_violations: list[str] | None = None,
) -> PromptEvalRecord:
    """Build a Phase 28 PromptEvalRecord from generation outputs."""
    payload_dict = payload if isinstance(payload, dict) else {}
    usage_dict = usage if isinstance(usage, dict) else {}
    parse_dict = parse_details if isinstance(parse_details, dict) else {}
    violations = [v for v in (policy_violations or []) if isinstance(v, str) and v.strip()]

    title_key, desc_key = _platform_content_keys(platform)
    title_value = str(payload_dict.get(title_key, "") or "")
    desc_value = str(payload_dict.get(desc_key, "") or "")
    quality_scores = compute_platform_quality_indices(
        platform=platform,
        title=title_value,
        description=desc_value,
        html_description=(platform == "shopify"),
        policy_violations=violations,
    )
    if isinstance(quality_scores, dict):
        quality_scores["placeholder_only"] = _is_placeholder_only_description(
            platform, desc_value
        )

    return PromptEvalRecord(
        run_id=run_id,
        sku=sku,
        platform=platform,
        variant=variant,
        prompt_hash=str(prompt_hash or ""),
        schema_hash=str(schema_hash or ""),
        prompt_tokens=int(usage_dict.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage_dict.get("completion_tokens", 0) or 0),
        parse_mode=str(parse_dict.get("parse_mode", "unknown") or "unknown"),
        missing_keys=[
            str(key)
            for key in (parse_dict.get("missing_keys", []) or [])
            if str(key).strip()
        ],
        title_len=len(title_value.strip()),
        desc_len=len(desc_value.strip()),
        placeholder_integrity=_placeholder_integrity(platform, payload_dict),
        policy_violations=violations,
        quality_scores=quality_scores,
    )


def write_prompt_eval_records(path: Path, records: list[PromptEvalRecord]) -> None:
    """Write PromptEvalRecord rows as JSONL."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def summarize_prompt_eval_records(records: list[PromptEvalRecord]) -> list[dict[str, Any]]:
    """Aggregate PromptEvalRecord rows by (platform, variant)."""
    grouped: dict[tuple[str, str], list[PromptEvalRecord]] = {}
    for record in records:
        grouped.setdefault((record.platform, record.variant), []).append(record)

    rows: list[dict[str, Any]] = []
    for (platform, variant), bucket in sorted(grouped.items()):
        total = len(bucket)
        fallback_count = sum(1 for record in bucket if record.parse_mode != "strict_json")
        short_count = sum(1 for record in bucket if record.desc_len < 100)
        placeholder_failures = sum(
            1 for record in bucket if not record.placeholder_integrity
        )
        policy_failures = sum(1 for record in bucket if record.policy_violations)
        empty_or_placeholder = 0
        for record in bucket:
            if platform in {"google", "bing"}:
                placeholder_only = bool(
                    record.quality_scores.get("placeholder_only", False)
                )
                if placeholder_only:
                    empty_or_placeholder += 1
                # Backward-compat fallback for records created before
                # placeholder_only telemetry existed.
                elif record.desc_len == len("{FINISH_SENTENCE}"):
                    empty_or_placeholder += 1
                elif record.desc_len == 0:
                    empty_or_placeholder += 1
            elif platform == "shopify" and record.desc_len == 0:
                empty_or_placeholder += 1

        avg_title_quality = round(
            sum(
                float(
                    record.quality_scores
                    .get("title_quality_index", {})
                    .get("overall", 0)
                )
                for record in bucket
            )
            / max(total, 1),
            2,
        )
        avg_description_quality = round(
            sum(
                float(
                    record.quality_scores
                    .get("description_quality_index", {})
                    .get("overall", 0)
                )
                for record in bucket
            )
            / max(total, 1),
            2,
        )
        avg_title_len = round(sum(record.title_len for record in bucket) / max(total, 1), 1)
        avg_desc_len = round(sum(record.desc_len for record in bucket) / max(total, 1), 1)

        rows.append(
            {
                "platform": platform,
                "variant": variant,
                "records": total,
                "avg_title_quality_index": avg_title_quality,
                "avg_description_quality_index": avg_description_quality,
                "avg_title_len": avg_title_len,
                "avg_desc_len": avg_desc_len,
                "parse_fallback_rate": round(fallback_count / max(total, 1), 4),
                "short_content_rate": round(short_count / max(total, 1), 4),
                "placeholder_failure_rate": round(placeholder_failures / max(total, 1), 4),
                "policy_violation_rate": round(policy_failures / max(total, 1), 4),
                "empty_or_placeholder_rate": round(
                    empty_or_placeholder / max(total, 1), 4
                ),
            }
        )
    return rows


def write_prompt_eval_summary_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write prompt evaluation summary rows to CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "platform",
        "variant",
        "records",
        "avg_title_quality_index",
        "avg_description_quality_index",
        "avg_title_len",
        "avg_desc_len",
        "parse_fallback_rate",
        "short_content_rate",
        "placeholder_failure_rate",
        "policy_violation_rate",
        "empty_or_placeholder_rate",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _extract_sku_from_filename(prefix: str, path: Path) -> str | None:
    name = path.name
    if not name.startswith(prefix) or not name.endswith(".json"):
        return None
    return name[len(prefix) : -len(".json")]


def evaluate_exports_dir(exports_dir: Path) -> list[dict[str, Any]]:
    """Evaluate all platform patch exports in a directory.

    When patch files contain pre-computed heuristic scores in ``_meta``
    (written by the optimization pipeline), those composites are preferred
    over re-scoring the exported variant text.  This ensures the dashboard
    displays the same scores as the batch report, since the pipeline scores
    *parent* content before finish-injection while the exported top-level
    title/description is post-injection variant text.

    Per-dimension breakdowns (ctr_proxy, cvr_proxy, brand_voice) are still
    computed live so the Quality Score Breakdown table remains populated.

    Returns a list of per-SKU result dicts suitable for printing or report
    generation.
    """
    exports_dir = Path(exports_dir)

    _PLATFORMS: list[tuple[str, str, str, bool]] = [
        # (platform, file_prefix, description_field, html_description)
        ("google", "google-patch-", "description", False),
        ("bing", "bing-patch-", "description", False),
        ("shopify", "shopify-patch-", "body_html", True),
    ]

    # Collect all SKUs across platforms
    skus: set[str] = set()
    for _plat, prefix, _desc_field, _html in _PLATFORMS:
        for p in exports_dir.glob(f"{prefix}*.json"):
            sku = _extract_sku_from_filename(prefix, p)
            if sku:
                skus.add(sku)

    results: list[dict[str, Any]] = []
    for sku in sorted(skus):
        row: dict[str, Any] = {"sku": sku}
        platform_composites: list[float] = []
        meta_heuristic: float | None = None  # pipeline weighted composite

        for platform, prefix, desc_field, is_html in _PLATFORMS:
            path = exports_dir / f"{prefix}{sku}.json"
            if not path.exists():
                continue

            data = json.loads(path.read_text())
            title = data.get("title")
            description = data.get(desc_field)
            if not title or not description:
                continue

            # Pre-computed scores from the pipeline (_meta)
            meta = data.get("_meta") or {}
            breakdown = meta.get("heuristic_score_breakdown") or {}
            meta_platform_score = breakdown.get(platform)

            # Pipeline weighted composite (identical across platform files)
            if meta_heuristic is None and meta.get("heuristic_score") is not None:
                meta_heuristic = meta["heuristic_score"]

            # Live score for per-dimension breakdown, with correct platform
            score = score_bundle(
                title=title,
                description=description,
                html_description=is_html,
                platform=platform,
            )
            score_dict = asdict(score)

            # Prefer pipeline composite over live re-score
            if meta_platform_score is not None:
                score_dict["composite"] = meta_platform_score
                platform_composites.append(meta_platform_score)
            else:
                score_dict["composite"] = score.composite
                platform_composites.append(score.composite)

            row[platform] = score_dict

        # Overall composite: prefer pipeline weighted score
        if meta_heuristic is not None:
            row["composite"] = meta_heuristic
        elif platform_composites:
            row["composite"] = round(
                sum(platform_composites) / len(platform_composites), 2
            )
        else:
            row["composite"] = 0.0

        results.append(row)

    return results


def render_markdown(results: list[dict[str, Any]]) -> str:
    """Render a compact markdown summary for a set of evaluation results."""
    lines: list[str] = []
    lines.append("# Export Quality Evaluation (Heuristic)")
    lines.append("")
    lines.append(
        "Scores are heuristic proxies for CTR/CVR/brand voice (0-100 composite)."
    )
    lines.append("")
    lines.append("| SKU | Composite | Google | Bing | Shopify |")
    lines.append("|-----|-----------:|------:|-----:|--------:|")
    for row in results:
        sku = row["sku"]
        composite = row.get("composite", 0.0)
        google = (row.get("google") or {}).get("composite")
        bing = (row.get("bing") or {}).get("composite")
        shopify = (row.get("shopify") or {}).get("composite")
        lines.append(
            f"| {sku} | {composite:0.2f}% |"
            f" {'' if google is None else f'{google:0.2f}%'} |"
            f" {'' if bing is None else f'{bing:0.2f}%'} |"
            f" {'' if shopify is None else f'{shopify:0.2f}%'} |"
        )
    lines.append("")
    return "\n".join(lines)
