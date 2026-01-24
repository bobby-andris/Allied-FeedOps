"""HTML dashboard to compare baseline vs candidate runs."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from feedops.quality.evaluator import evaluate_exports_dir


@dataclass(frozen=True)
class ReportMeta:
    provider_model: str | None
    image_url: str | None
    token_usage: str | None
    estimated_cost: str | None
    evidence_markdown: str | None
    prompt_text: str | None
    status: str | None


def parse_report_text(text: str) -> ReportMeta:
    """Extract prompt/evidence metadata from a report markdown string."""
    def _match(pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    provider_model = _match(r"\*\*Provider/Model:\*\*\s*(.+)")
    image_url = _match(r"\*\*Image URL:\*\*\s*(.+)")
    token_usage = _match(r"\*\*Token Usage:\*\*\s*(.+)")
    estimated_cost = _match(r"\*\*Estimated Cost:\*\*\s*(.+)")
    status = _match(r"\*\*Status:\*\*\s*([A-Z]+)")

    evidence_markdown = None
    evidence_start = text.find("## Available Product Data")
    if evidence_start != -1:
        details_index = text.find("<details>", evidence_start)
        next_heading = text.find("\n## ", evidence_start + 1)
        end_candidates = [i for i in [details_index, next_heading] if i != -1]
        evidence_end = min(end_candidates) if end_candidates else len(text)
        evidence_markdown = text[evidence_start:evidence_end].strip()

    prompt_text = None
    if "<summary>Full Prompt</summary>" in text:
        after_summary = text.split("<summary>Full Prompt</summary>", 1)[-1]
        code_start = after_summary.find("```")
        if code_start != -1:
            code_body = after_summary[code_start + 3:]
            code_end = code_body.find("```")
            if code_end != -1:
                prompt_text = code_body[:code_end].strip()

    return ReportMeta(
        provider_model=provider_model,
        image_url=image_url,
        token_usage=token_usage,
        estimated_cost=estimated_cost,
        evidence_markdown=evidence_markdown,
        prompt_text=prompt_text,
        status=status,
    )


def load_latest_report(reports_dir: Path, safe_sku: str) -> ReportMeta | None:
    """Load the most recent report for a SKU, if available."""
    if not reports_dir:
        return None
    reports_dir = Path(reports_dir)
    candidates = list(reports_dir.glob(f"sku-{safe_sku}-*.md"))
    if not candidates:
        return None
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return parse_report_text(latest.read_text())


def _safe_sku_from_filename(path: Path, prefix: str) -> str | None:
    name = path.name
    if not name.startswith(prefix) or not name.endswith(".json"):
        return None
    return name[len(prefix):-len(".json")]


def load_exports_dir(exports_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Load exports into a per-SKU, per-platform mapping."""
    exports_dir = Path(exports_dir)
    sku_map: dict[str, dict[str, dict[str, Any]]] = {}
    for prefix, platform in [
        ("google-patch-", "google"),
        ("bing-patch-", "bing"),
        ("shopify-patch-", "shopify"),
    ]:
        for path in exports_dir.glob(f"{prefix}*.json"):
            sku = _safe_sku_from_filename(path, prefix)
            if not sku:
                continue
            sku_map.setdefault(sku, {})[platform] = json.loads(path.read_text())
    return sku_map


def build_score_map(exports_dir: Path) -> dict[str, dict[str, Any]]:
    """Return score results keyed by SKU from evaluate_exports_dir()."""
    results = evaluate_exports_dir(Path(exports_dir))
    return {row["sku"]: row for row in results}


def _html_escape(value: str | None) -> str:
    return html.escape(value) if value else ""


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned.lower() or "sku"


def _platform_block(label: str, data: dict[str, Any] | None, score: dict[str, Any] | None) -> str:
    if not data:
        return f"<div class=\"platform\"><h4>{label}</h4><p class=\"muted\">No data</p></div>"
    title = _html_escape(data.get("title"))
    description = _html_escape(data.get("description") or data.get("body_html"))
    composite = ""
    if score:
        composite = f"{score.get('composite', '')}%"
    return (
        "<div class=\"platform\">"
        f"<h4>{label}</h4>"
        f"<div class=\"score\">Heuristic: {composite}</div>"
        f"<div class=\"label\">Title</div><pre>{title}</pre>"
        f"<div class=\"label\">Description</div><pre>{description}</pre>"
        "</div>"
    )


def render_compare_html(
    *,
    baseline_dir: Path,
    candidate_dir: Path,
    baseline_scores: dict[str, dict[str, Any]],
    candidate_scores: dict[str, dict[str, Any]],
    baseline_exports: dict[str, dict[str, dict[str, Any]]],
    candidate_exports: dict[str, dict[str, dict[str, Any]]],
    baseline_reports: dict[str, ReportMeta | None],
    candidate_reports: dict[str, ReportMeta | None],
) -> str:
    skus = sorted(set(baseline_scores.keys()) | set(candidate_scores.keys()))

    def _avg(scores: list[float]) -> float:
        return round(sum(scores) / len(scores), 2) if scores else 0.0

    baseline_vals = [baseline_scores[s]["composite"] for s in skus if s in baseline_scores]
    candidate_vals = [candidate_scores[s]["composite"] for s in skus if s in candidate_scores]
    baseline_avg = _avg(baseline_vals)
    candidate_avg = _avg(candidate_vals)
    delta_avg = round(candidate_avg - baseline_avg, 2)

    rows = []
    panels = []
    for sku in skus:
        anchor_id = f"sku-{_slugify(sku)}"
        display_sku = _html_escape(sku)
        b_score = baseline_scores.get(sku, {}).get("composite")
        c_score = candidate_scores.get(sku, {}).get("composite")
        delta = None
        if b_score is not None and c_score is not None:
            delta = round(c_score - b_score, 2)

        delta_label = f"{delta:+.2f}%" if delta is not None else ""
        b_display = "" if b_score is None else f"{b_score:.2f}%"
        c_display = "" if c_score is None else f"{c_score:.2f}%"
        rows.append(
            "<tr>"
            f"<td><a href=\"#{anchor_id}\">{display_sku}</a></td>"
            f"<td data-value=\"{b_score or 0}\">{b_display}"
            "</td>"
            f"<td data-value=\"{c_score or 0}\">{c_display}"
            "</td>"
            f"<td data-value=\"{delta or 0}\">{delta_label}</td>"
            "</tr>"
        )

        b_exports = baseline_exports.get(sku, {})
        c_exports = candidate_exports.get(sku, {})
        b_report = baseline_reports.get(sku)
        c_report = candidate_reports.get(sku)

        panel_parts = [
            f"<details class=\"sku-panel\" id=\"{anchor_id}\">",
            f"<summary>{display_sku}</summary>",
            "<div class=\"grid\">",
            "<div class=\"col\">",
            "<h3>Baseline</h3>",
            _platform_block("Google", b_exports.get("google"), baseline_scores.get(sku, {}).get("google")),
            _platform_block("Bing", b_exports.get("bing"), baseline_scores.get(sku, {}).get("bing")),
            _platform_block("Shopify", b_exports.get("shopify"), baseline_scores.get(sku, {}).get("shopify")),
            _render_report_block(b_report),
            "</div>",
            "<div class=\"col\">",
            "<h3>Candidate</h3>",
            _platform_block("Google", c_exports.get("google"), candidate_scores.get(sku, {}).get("google")),
            _platform_block("Bing", c_exports.get("bing"), candidate_scores.get(sku, {}).get("bing")),
            _platform_block("Shopify", c_exports.get("shopify"), candidate_scores.get(sku, {}).get("shopify")),
            _render_report_block(c_report),
            "</div>",
            "</div>",
            "</details>",
        ]
        panels.append("".join(panel_parts))

    html_body = f"""
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>FeedOps Run Comparison</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif; margin: 24px; color: #111; }}
    h1 {{ margin-bottom: 4px; }}
    .muted {{ color: #666; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ cursor: pointer; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
    .col {{ border: 1px solid #eee; border-radius: 8px; padding: 12px; }}
    .platform pre {{ white-space: pre-wrap; background: #f8f8f8; padding: 8px; border-radius: 6px; }}
    .platform .label {{ font-size: 12px; color: #666; margin-top: 8px; }}
    .score {{ font-size: 12px; color: #444; margin-bottom: 6px; }}
    details.sku-panel {{ margin-top: 12px; }}
  </style>
  <script>
    function sortTable(n) {{
      const table = document.getElementById('sku-table');
      const rows = Array.from(table.rows).slice(1);
      const asc = table.getAttribute('data-sort') !== 'asc';
      rows.sort((a, b) => {{
        const aVal = parseFloat(a.cells[n].dataset.value || '0');
        const bVal = parseFloat(b.cells[n].dataset.value || '0');
        return asc ? aVal - bVal : bVal - aVal;
      }});
      rows.forEach(row => table.tBodies[0].appendChild(row));
      table.setAttribute('data-sort', asc ? 'asc' : 'desc');
    }}
  </script>
</head>
<body>
  <h1>FeedOps Run Comparison</h1>
  <div class=\"muted\">Generated: {datetime.now().isoformat()}</div>
  <p><strong>Baseline:</strong> {_html_escape(str(baseline_dir))}<br/>
     <strong>Candidate:</strong> {_html_escape(str(candidate_dir))}</p>
  <p><strong>Average composite:</strong> {baseline_avg:.2f}% → {candidate_avg:.2f}% ({delta_avg:+.2f}%)</p>
  <table id=\"sku-table\">
    <thead>
      <tr>
        <th onclick=\"sortTable(0)\">SKU</th>
        <th onclick=\"sortTable(1)\">Baseline</th>
        <th onclick=\"sortTable(2)\">Candidate</th>
        <th onclick=\"sortTable(3)\">Delta</th>
      </tr>
    </thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  {''.join(panels)}
</body>
</html>
"""
    return html_body


def _render_report_block(report: ReportMeta | None) -> str:
    if not report:
        return "<div class=\"platform\"><h4>Inputs & Prompt</h4><p class=\"muted\">No report data</p></div>"
    return (
        "<div class=\"platform\">"
        "<h4>Inputs & Prompt</h4>"
        f"<div class=\"score\">Provider: {_html_escape(report.provider_model)} | "
        f"Status: {_html_escape(report.status)}</div>"
        f"<div class=\"score\">Image: {_html_escape(report.image_url)}</div>"
        f"<div class=\"score\">Token usage: {_html_escape(report.token_usage)}</div>"
        f"<div class=\"score\">Estimated cost: {_html_escape(report.estimated_cost)}</div>"
        "<details><summary>Evidence</summary>"
        f"<pre>{_html_escape(report.evidence_markdown)}</pre></details>"
        "<details><summary>Prompt</summary>"
        f"<pre>{_html_escape(report.prompt_text)}</pre></details>"
        "</div>"
    )


def compare_runs_to_html(
    *,
    baseline_exports_dir: Path,
    candidate_exports_dir: Path,
    baseline_reports_dir: Path | None = None,
    candidate_reports_dir: Path | None = None,
) -> str:
    baseline_exports = load_exports_dir(Path(baseline_exports_dir))
    candidate_exports = load_exports_dir(Path(candidate_exports_dir))
    baseline_scores = build_score_map(Path(baseline_exports_dir))
    candidate_scores = build_score_map(Path(candidate_exports_dir))

    all_skus = set(baseline_exports.keys()) | set(candidate_exports.keys())
    baseline_reports: dict[str, ReportMeta | None] = {}
    candidate_reports: dict[str, ReportMeta | None] = {}
    for sku in all_skus:
        baseline_reports[sku] = (
            load_latest_report(Path(baseline_reports_dir), sku)
            if baseline_reports_dir
            else None
        )
        candidate_reports[sku] = (
            load_latest_report(Path(candidate_reports_dir), sku)
            if candidate_reports_dir
            else None
        )

    return render_compare_html(
        baseline_dir=Path(baseline_exports_dir),
        candidate_dir=Path(candidate_exports_dir),
        baseline_scores=baseline_scores,
        candidate_scores=candidate_scores,
        baseline_exports=baseline_exports,
        candidate_exports=candidate_exports,
        baseline_reports=baseline_reports,
        candidate_reports=candidate_reports,
    )
