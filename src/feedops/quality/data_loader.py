"""Data loading utilities for the review dashboard."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from feedops.config.columns import CSV_COLUMNS, POSITIONAL_RENAMES
from feedops.quality.evaluator import evaluate_exports_dir


@dataclass
class OriginalContent:
    """Original product content from catalog."""
    
    master_sku: str
    title: str
    description: str
    category: str = ""
    collection: str = ""
    image_url: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class ExportContent:
    """Content from an export patch file."""

    title: str
    description: str
    short_title: str = ""
    quality_score: float = 0.0
    approval_status: str = ""
    generated_at: str = ""
    image_url: str = ""
    lifestyle_images: list[dict[str, Any]] = field(default_factory=list)
    selected_lifestyle_image: int | None = None


@dataclass
class ReportMeta:
    """Metadata extracted from optimization report."""
    
    provider_model: str | None = None
    image_url: str | None = None
    token_usage: str | None = None
    estimated_cost: str | None = None
    evidence_markdown: str | None = None
    prompt_text: str | None = None
    status: str | None = None
    keywords: dict[str, Any] = field(default_factory=dict)
    enrichment: dict[str, Any] = field(default_factory=dict)


@dataclass
class SKUData:
    """Complete data for a single SKU across all sources."""
    
    sku: str
    original: OriginalContent | None = None
    baseline: dict[str, ExportContent] = field(default_factory=dict)  # platform -> content
    candidate: dict[str, ExportContent] = field(default_factory=dict)  # platform -> content
    baseline_scores: dict[str, Any] = field(default_factory=dict)
    candidate_scores: dict[str, Any] = field(default_factory=dict)
    baseline_report: ReportMeta | None = None
    candidate_report: ReportMeta | None = None
    composite_delta: float = 0.0


def load_catalog_originals(catalog_path: Path | str) -> dict[str, OriginalContent]:
    """Load original product content from catalog CSV.
    
    Args:
        catalog_path: Path to Product Catalog.csv
        
    Returns:
        Dict mapping master_sku to OriginalContent
    """
    path = Path(catalog_path)
    if not path.exists():
        return {}
    
    # Load with duplicate column handling
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    
    # Rename duplicate columns by position
    columns = list(df.columns)
    for pos, new_name in POSITIONAL_RENAMES.items():
        if pos < len(columns):
            columns[pos] = new_name
    df.columns = columns
    
    # Rename using mapping
    rename_map = {col: CSV_COLUMNS[col] for col in df.columns if col in CSV_COLUMNS}
    df = df.rename(columns=rename_map)
    
    # Group by master_sku to get unique products
    originals: dict[str, OriginalContent] = {}
    for master_sku, group in df.groupby("master_sku"):
        first_row = group.iloc[0]
        
        bullets = []
        for i in range(1, 7):
            bullet_col = f"bullet_{i}"
            if bullet_col in first_row and first_row[bullet_col]:
                bullets.append(first_row[bullet_col])
        
        originals[master_sku] = OriginalContent(
            master_sku=master_sku,
            title=first_row.get("current_title", ""),
            description=first_row.get("current_description", ""),
            category=first_row.get("category", ""),
            collection=first_row.get("collection", ""),
            image_url=first_row.get("main_image_url", ""),
            bullets=bullets,
        )
    
    return originals


def load_exports_dir(exports_dir: Path | str) -> dict[str, dict[str, ExportContent]]:
    """Load all exports from a directory.
    
    Args:
        exports_dir: Path to exports directory
        
    Returns:
        Dict mapping sku -> platform -> ExportContent
    """
    exports_dir = Path(exports_dir)
    if not exports_dir.exists():
        return {}
    
    exports: dict[str, dict[str, ExportContent]] = {}
    
    prefixes = [
        ("google-patch-", "google"),
        ("bing-patch-", "bing"),
        ("shopify-patch-", "shopify"),
    ]
    
    for prefix, platform in prefixes:
        for path in exports_dir.glob(f"{prefix}*.json"):
            # Extract SKU from filename
            name = path.name
            if not name.endswith(".json"):
                continue
            sku = name[len(prefix):-len(".json")]
            
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                continue
            
            # Get title and description
            title = data.get("title", "")
            if platform == "shopify":
                description = data.get("body_html", "")
            else:
                description = data.get("description", "")
            
            # Get metadata
            meta = data.get("_meta", {})

            # Get lifestyle images if available
            lifestyle_images = data.get("lifestyle_images", [])
            selected_lifestyle_image = data.get("selected_lifestyle_image")

            content = ExportContent(
                title=title,
                description=description,
                short_title=data.get("short_title", ""),
                quality_score=meta.get("quality_score", 0.0),
                approval_status=meta.get("approval_status", ""),
                generated_at=meta.get("generated_at", ""),
                lifestyle_images=lifestyle_images,
                selected_lifestyle_image=selected_lifestyle_image,
            )

            # Store _previous for original content reference
            previous = data.get("_previous", {})
            if previous:
                content.image_url = previous.get("image_url", "")

            exports.setdefault(sku, {})[platform] = content
    
    return exports


def parse_report_text(text: str) -> ReportMeta:
    """Extract metadata from a report markdown string."""
    
    def _match(pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None
    
    provider_model = _match(r"\*\*Provider/Model:\*\*\s*(.+)")
    image_url = _match(r"\*\*Image URL:\*\*\s*(.+)")
    token_usage = _match(r"\*\*Token Usage:\*\*\s*(.+)")
    estimated_cost = _match(r"\*\*Estimated Cost:\*\*\s*(.+)")
    status = _match(r"\*\*Status:\*\*\s*([A-Z]+)")
    
    # Extract evidence table
    evidence_markdown = None
    evidence_start = text.find("## Available Product Data")
    if evidence_start != -1:
        details_index = text.find("<details>", evidence_start)
        next_heading = text.find("\n## ", evidence_start + 1)
        end_candidates = [i for i in [details_index, next_heading] if i != -1]
        evidence_end = min(end_candidates) if end_candidates else len(text)
        evidence_markdown = text[evidence_start:evidence_end].strip()
    
    # Extract prompt
    prompt_text = None
    if "<summary>Full Prompt</summary>" in text:
        after_summary = text.split("<summary>Full Prompt</summary>", 1)[-1]
        code_start = after_summary.find("```")
        if code_start != -1:
            code_body = after_summary[code_start + 3:]
            code_end = code_body.find("```")
            if code_end != -1:
                prompt_text = code_body[:code_end].strip()
    
    # Parse keywords and enrichment from evidence
    keywords = {}
    enrichment = {}
    
    if evidence_markdown:
        # Parse table rows
        for line in evidence_markdown.split("\n"):
            if "|" not in line or "---" in line or "Attribute" in line:
                continue
            
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                attr = parts[1]
                value = parts[2]
                source = parts[3] if len(parts) > 3 else ""
                
                # Categorize into keywords or enrichment
                if "keyword" in attr.lower():
                    keywords[attr] = value
                elif "enrichment" in source.lower() or attr.startswith(("collection_", "design_", "feature_", "finish_", "competitive_", "key_")):
                    enrichment[attr] = value
    
    return ReportMeta(
        provider_model=provider_model,
        image_url=image_url,
        token_usage=token_usage,
        estimated_cost=estimated_cost,
        evidence_markdown=evidence_markdown,
        prompt_text=prompt_text,
        status=status,
        keywords=keywords,
        enrichment=enrichment,
    )


def load_latest_report(reports_dir: Path | str, safe_sku: str) -> ReportMeta | None:
    """Load the most recent report for a SKU."""
    if not reports_dir:
        return None
    
    reports_dir = Path(reports_dir)
    if not reports_dir.exists():
        return None
    
    # Try exact match and lowercase variants
    patterns = [
        f"sku-{safe_sku}-*.md",
        f"sku-{safe_sku.lower()}-*.md",
        f"sku-{safe_sku.upper()}-*.md",
    ]
    
    candidates = []
    for pattern in patterns:
        candidates.extend(reports_dir.glob(pattern))
    
    if not candidates:
        return None
    
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return parse_report_text(latest.read_text())


def _slugify(value: str) -> str:
    """Convert SKU to safe filename slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned.lower() or "sku"


def load_all_sku_data(
    *,
    baseline_exports_dir: Path | str,
    candidate_exports_dir: Path | str,
    catalog_path: Path | str | None = None,
    baseline_reports_dir: Path | str | None = None,
    candidate_reports_dir: Path | str | None = None,
) -> list[SKUData]:
    """Load complete data for all SKUs.
    
    Args:
        baseline_exports_dir: Path to baseline exports
        candidate_exports_dir: Path to candidate exports
        catalog_path: Optional path to Product Catalog.csv
        baseline_reports_dir: Optional path to baseline reports
        candidate_reports_dir: Optional path to candidate reports
        
    Returns:
        List of SKUData objects sorted by SKU
    """
    # Load exports
    baseline_exports = load_exports_dir(baseline_exports_dir)
    candidate_exports = load_exports_dir(candidate_exports_dir)
    
    # Load scores
    baseline_scores = {
        row["sku"]: row
        for row in evaluate_exports_dir(Path(baseline_exports_dir))
    }
    candidate_scores = {
        row["sku"]: row
        for row in evaluate_exports_dir(Path(candidate_exports_dir))
    }
    
    # Load originals
    originals = load_catalog_originals(catalog_path) if catalog_path else {}
    
    # Only include SKUs that have actual export data (not all catalog SKUs)
    # This prevents loading thousands of SKUs with no export data
    all_skus = sorted(
        set(baseline_exports.keys()) |
        set(candidate_exports.keys())
    )
    
    # Build SKUData for each
    results = []
    for sku in all_skus:
        # Try to find matching original (SKUs may have different formats)
        original = originals.get(sku)
        if not original:
            # Try common variations
            for orig_sku in originals:
                if _slugify(orig_sku) == _slugify(sku):
                    original = originals[orig_sku]
                    break
        
        # Load reports
        safe_sku = _slugify(sku)
        baseline_report = (
            load_latest_report(Path(baseline_reports_dir), safe_sku)
            if baseline_reports_dir else None
        )
        candidate_report = (
            load_latest_report(Path(candidate_reports_dir), safe_sku)
            if candidate_reports_dir else None
        )
        
        # Calculate delta
        b_composite = baseline_scores.get(sku, {}).get("composite", 0.0)
        c_composite = candidate_scores.get(sku, {}).get("composite", 0.0)
        delta = round(c_composite - b_composite, 2) if b_composite and c_composite else 0.0
        
        # Get image URL from various sources
        image_url = ""
        if original and original.image_url:
            image_url = original.image_url
        elif candidate_report and candidate_report.image_url:
            image_url = candidate_report.image_url
        elif baseline_report and baseline_report.image_url:
            image_url = baseline_report.image_url
        
        # Update original with image if found
        if original and image_url and not original.image_url:
            original.image_url = image_url
        
        results.append(SKUData(
            sku=sku,
            original=original,
            baseline=baseline_exports.get(sku, {}),
            candidate=candidate_exports.get(sku, {}),
            baseline_scores=baseline_scores.get(sku, {}),
            candidate_scores=candidate_scores.get(sku, {}),
            baseline_report=baseline_report,
            candidate_report=candidate_report,
            composite_delta=delta,
        ))
    
    return results


def sync_lifestyle_images(
    exports_dir: Path | str,
    *,
    images_subdir: str = "images",
    repo_root: Path | str | None = None,
) -> dict[str, int]:
    """Copy lifestyle images into exports dir and rewrite paths.

    Args:
        exports_dir: Export patch directory to scan (google/bing/shopify patches).
        images_subdir: Folder under exports_dir to store images.
        repo_root: Repo root used to resolve relative paths.

    Returns:
        Dict with counts of scanned/updated files and image copy stats.
    """
    exports_dir = Path(exports_dir)
    repo_root = Path(repo_root) if repo_root is not None else Path.cwd()
    images_dir = exports_dir / images_subdir
    images_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "files_scanned": 0,
        "files_updated": 0,
        "images_copied": 0,
        "images_missing": 0,
    }

    prefixes = ("google-patch-", "bing-patch-", "shopify-patch-")

    def _resolve_image_path(image_path: str) -> Path | None:
        if not image_path:
            return None
        raw_path = Path(image_path).expanduser()
        if raw_path.is_absolute():
            return raw_path if raw_path.exists() else None
        for candidate in (repo_root / raw_path, exports_dir / raw_path):
            if candidate.exists():
                return candidate
        return None

    for prefix in prefixes:
        for patch_path in exports_dir.glob(f"{prefix}*.json"):
            stats["files_scanned"] += 1
            try:
                data = json.loads(patch_path.read_text())
            except (json.JSONDecodeError, OSError):
                continue

            lifestyle_images = data.get("lifestyle_images", [])
            if not lifestyle_images:
                continue

            updated = False
            for img in lifestyle_images:
                if not isinstance(img, dict):
                    continue
                src_path = _resolve_image_path(img.get("image_path", ""))
                if not src_path:
                    stats["images_missing"] += 1
                    continue

                target_path = images_dir / src_path.name
                if not target_path.exists():
                    shutil.copy2(src_path, target_path)
                    stats["images_copied"] += 1

                try:
                    new_path = str(target_path.relative_to(repo_root))
                except ValueError:
                    new_path = str(target_path)

                if img.get("image_path") != new_path:
                    img["image_path"] = new_path
                    updated = True

            if updated:
                patch_path.write_text(json.dumps(data, indent=2))
                stats["files_updated"] += 1

    return stats


def get_summary_stats(sku_data: list[SKUData]) -> dict[str, Any]:
    """Calculate summary statistics for a list of SKUs.
    
    Returns dict with:
        - total_skus: int
        - avg_baseline: float
        - avg_candidate: float
        - avg_delta: float
        - improved_count: int
        - declined_count: int
        - unchanged_count: int
        - categories: list[str]
        - collections: list[str]
    """
    if not sku_data:
        return {
            "total_skus": 0,
            "avg_baseline": 0.0,
            "avg_candidate": 0.0,
            "avg_delta": 0.0,
            "improved_count": 0,
            "declined_count": 0,
            "unchanged_count": 0,
            "categories": [],
            "collections": [],
        }
    
    baseline_scores = []
    candidate_scores = []
    improved = 0
    declined = 0
    unchanged = 0
    categories = set()
    collections = set()
    
    for data in sku_data:
        b_score = data.baseline_scores.get("composite", 0.0)
        c_score = data.candidate_scores.get("composite", 0.0)
        
        if b_score:
            baseline_scores.append(b_score)
        if c_score:
            candidate_scores.append(c_score)
        
        if data.composite_delta > 0.5:
            improved += 1
        elif data.composite_delta < -0.5:
            declined += 1
        else:
            unchanged += 1
        
        if data.original:
            if data.original.category:
                categories.add(data.original.category)
            if data.original.collection:
                collections.add(data.original.collection)
    
    avg_baseline = round(sum(baseline_scores) / len(baseline_scores), 2) if baseline_scores else 0.0
    avg_candidate = round(sum(candidate_scores) / len(candidate_scores), 2) if candidate_scores else 0.0
    
    return {
        "total_skus": len(sku_data),
        "avg_baseline": avg_baseline,
        "avg_candidate": avg_candidate,
        "avg_delta": round(avg_candidate - avg_baseline, 2),
        "improved_count": improved,
        "declined_count": declined,
        "unchanged_count": unchanged,
        "categories": sorted(categories),
        "collections": sorted(collections),
    }
