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
    return name[len(prefix):-len(".json")]


def evaluate_exports_dir(exports_dir: Path) -> list[dict[str, Any]]:
    """Evaluate all platform patch exports in a directory.

    Returns a list of per-SKU result dicts suitable for printing or report generation.
    """
    exports_dir = Path(exports_dir)
    google_files = list(exports_dir.glob("google-patch-*.json"))
    bing_files = list(exports_dir.glob("bing-patch-*.json"))
    shopify_files = list(exports_dir.glob("shopify-patch-*.json"))

    skus: set[str] = set()
    for p in google_files:
        sku = _extract_sku_from_filename("google-patch-", p)
        if sku:
            skus.add(sku)
    for p in bing_files:
        sku = _extract_sku_from_filename("bing-patch-", p)
        if sku:
            skus.add(sku)
    for p in shopify_files:
        sku = _extract_sku_from_filename("shopify-patch-", p)
        if sku:
            skus.add(sku)

    results: list[dict[str, Any]] = []
    for sku in sorted(skus):
        row: dict[str, Any] = {"sku": sku}
        platform_scores: list[HeuristicScore] = []

        google_path = exports_dir / f"google-patch-{sku}.json"
        if google_path.exists():
            google = json.loads(google_path.read_text())
            title = google.get("title")
            description = google.get("description")
            if title and description:
                score = score_bundle(title=title, description=description)
                platform_scores.append(score)
                google_score = asdict(score)
                google_score["composite"] = score.composite
                row["google"] = google_score

        bing_path = exports_dir / f"bing-patch-{sku}.json"
        if bing_path.exists():
            bing = json.loads(bing_path.read_text())
            title = bing.get("title")
            description = bing.get("description")
            if title and description:
                score = score_bundle(title=title, description=description)
                platform_scores.append(score)
                bing_score = asdict(score)
                bing_score["composite"] = score.composite
                row["bing"] = bing_score

        shopify_path = exports_dir / f"shopify-patch-{sku}.json"
        if shopify_path.exists():
            shopify = json.loads(shopify_path.read_text())
            title = shopify.get("title")
            body_html = shopify.get("body_html")
            if title and body_html:
                score = score_bundle(
                    title=title,
                    description=body_html,
                    html_description=True,
                )
                platform_scores.append(score)
                shopify_score = asdict(score)
                shopify_score["composite"] = score.composite
                row["shopify"] = shopify_score

        if platform_scores:
            row["composite"] = round(
                sum(s.composite for s in platform_scores) / len(platform_scores), 2
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
    lines.append("Scores are heuristic proxies for CTR/CVR/brand voice (0-100 composite).")
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
