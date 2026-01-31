"""Evaluate generated export patches with heuristic scoring."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from feedops.quality.scoring import HeuristicScore, score_bundle


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
