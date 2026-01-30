"""Automated evaluation framework for prompt regression testing.

Evaluates generated exports against structural checks, heuristic scoring,
banned word detection, character limits, and platform-specific validations.
Designed to run after any prompt change to catch regressions before deployment.

Usage:
    from feedops.quality.eval_framework import evaluate_regression, render_report

    results = evaluate_regression(exports_dir)
    report = render_report(results)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from feedops.quality.scoring import (
    HeuristicScore,
    assess_soft_gates,
    score_bundle,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BANNED_WORDS = [
    "finest",
    "luxurious",
    "premium",
    "exclusive",
    "exceptional",
    "unparalleled",
    "superior",
    "exquisite",
    "ultimate",
]

BANNED_TITLE_STARTERS = [
    "premium",
    "luxury",
    "best",
    "high-quality",
    "top-rated",
]

# Per OpenAI & Google Merchant Center specs
CHAR_LIMITS = {
    "google_title": 150,
    "google_short_title": 70,
    "bing_title": 150,
    "shopify_title": 255,
    "shopify_meta_description": 155,
}

# Target ranges for description length
DESC_TARGET_RANGES = {
    "google_description": (600, 800),
    "bing_description": (700, 1000),
}

# Bing synonym families -- at least 2 synonyms from the product's family should
# appear in bing_description for good literal-match coverage.
BING_SYNONYM_FAMILIES = {
    "towel bar": ["towel bar", "towel rack", "towel holder", "towel rail"],
    "grab bar": ["grab bar", "safety bar", "bathroom grab bar", "support bar"],
    "toilet paper holder": [
        "toilet paper holder",
        "tissue holder",
        "toilet roll holder",
    ],
    "robe hook": ["robe hook", "towel hook", "bathroom hook", "wall hook"],
    "glass shelf": ["glass shelf", "bathroom shelf", "wall shelf", "floating shelf"],
    "paper towel holder": [
        "paper towel holder",
        "paper towel stand",
        "kitchen towel holder",
    ],
}

# Minimum heuristic composite score to pass regression
MIN_COMPOSITE_SCORE = 60.0

# Minimum percentage of SKUs that must pass all checks
MIN_PASS_RATE = 80.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of a single validation check."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class SKUEvalResult:
    """Evaluation result for a single SKU across all platforms."""

    sku: str
    checks: list[CheckResult] = field(default_factory=list)
    heuristic_scores: dict[str, float] = field(default_factory=dict)
    composite_score: float = 0.0
    all_passed: bool = False

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


@dataclass
class EvalReport:
    """Complete regression evaluation report."""

    exports_dir: str
    sku_results: list[SKUEvalResult] = field(default_factory=list)

    @property
    def total_skus(self) -> int:
        return len(self.sku_results)

    @property
    def passing_skus(self) -> int:
        return sum(1 for r in self.sku_results if r.all_passed)

    @property
    def pass_rate(self) -> float:
        if not self.sku_results:
            return 0.0
        return (self.passing_skus / self.total_skus) * 100

    @property
    def avg_composite(self) -> float:
        scores = [r.composite_score for r in self.sku_results if r.composite_score > 0]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def regression_passed(self) -> bool:
        return self.pass_rate >= MIN_PASS_RATE and self.avg_composite >= MIN_COMPOSITE_SCORE


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def _check_banned_words(text: str, field_name: str) -> CheckResult:
    """Check text for banned marketing words."""
    lower = text.lower()
    found = [w for w in BANNED_WORDS if w in lower]
    if found:
        return CheckResult(
            name=f"banned_words:{field_name}",
            passed=False,
            detail=f"Found banned words: {', '.join(found)}",
        )
    return CheckResult(name=f"banned_words:{field_name}", passed=True)


def _check_title_starter(title: str, field_name: str) -> CheckResult:
    """Check that title doesn't start with banned adjectives."""
    first_word = title.strip().split()[0].lower().rstrip(",") if title.strip() else ""
    for banned in BANNED_TITLE_STARTERS:
        if first_word == banned or title.strip().lower().startswith(banned):
            return CheckResult(
                name=f"title_starter:{field_name}",
                passed=False,
                detail=f"Title starts with banned adjective: '{banned}'",
            )
    return CheckResult(name=f"title_starter:{field_name}", passed=True)


def _check_char_limit(text: str, field_name: str, max_len: int) -> CheckResult:
    """Check that text is within character limit."""
    actual = len(text)
    if actual > max_len:
        return CheckResult(
            name=f"char_limit:{field_name}",
            passed=False,
            detail=f"{actual} chars exceeds {max_len} limit",
        )
    return CheckResult(name=f"char_limit:{field_name}", passed=True)


def _check_desc_length_range(
    text: str, field_name: str, min_len: int, max_len: int
) -> CheckResult:
    """Check description is within target range."""
    actual = len(text)
    if actual < min_len:
        return CheckResult(
            name=f"desc_length:{field_name}",
            passed=False,
            detail=f"{actual} chars below {min_len} target minimum",
        )
    if actual > max_len * 1.5:  # Allow 50% over target max (soft target)
        return CheckResult(
            name=f"desc_length:{field_name}",
            passed=False,
            detail=f"{actual} chars significantly exceeds {max_len} target maximum",
        )
    return CheckResult(name=f"desc_length:{field_name}", passed=True)


def _check_brand_position(title: str, field_name: str) -> CheckResult:
    """Check that 'Allied Brass' is the final segment of the title."""
    if not title.strip():
        return CheckResult(
            name=f"brand_position:{field_name}",
            passed=False,
            detail="Empty title",
        )
    # Split by common separators and check last segment
    parts = re.split(r"[,|–—-]\s*", title.strip())
    last = parts[-1].strip()
    if last.lower() == "allied brass":
        return CheckResult(name=f"brand_position:{field_name}", passed=True)
    return CheckResult(
        name=f"brand_position:{field_name}",
        passed=False,
        detail=f"Brand not last segment (last: '{last}')",
    )


def _check_no_citations(text: str, field_name: str) -> CheckResult:
    """Check for leaked source citations (catalog_csv, etc.)."""
    patterns = [r"catalog_csv", r"source_field", r"source_value", r"\[source\]"]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return CheckResult(
                name=f"no_citations:{field_name}",
                passed=False,
                detail=f"Found citation leak matching '{pattern}'",
            )
    return CheckResult(name=f"no_citations:{field_name}", passed=True)


def _check_title_min_length(title: str, field_name: str) -> CheckResult:
    """Flag Google/Bing titles under 60 chars."""
    length = len(title)
    if length < 60:
        return CheckResult(
            name=f"title_min_length:{field_name}",
            passed=False,
            detail=f"Title too short ({length} chars, min 60)",
        )
    return CheckResult(name=f"title_min_length:{field_name}", passed=True)


def _check_bullet_format(description: str, field_name: str) -> CheckResult:
    """Check for non-standard bullet characters and empty bullets."""
    issues = []
    lines = description.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("\u2022"):
            issues.append(f"line {i}: Unicode bullet character found (use '- ' instead)")
        if stripped in ("-", "- "):
            issues.append(f"line {i}: empty bullet")
    if issues:
        return CheckResult(
            name=f"bullet_format:{field_name}",
            passed=False,
            detail="; ".join(issues[:3]),  # limit detail length
        )
    return CheckResult(name=f"bullet_format:{field_name}", passed=True)


def _check_description_structure(
    description: str, field_name: str, is_html: bool = False
) -> CheckResult:
    """Check description has hook + bullets + specs structure."""
    issues = []
    if is_html:
        if "<ul>" not in description or "<li>" not in description:
            issues.append("missing <ul><li> highlights")
        if "<p>" not in description:
            issues.append("missing <p> opening hook")
    else:
        # Plain text: check for bullet points and specs section
        # Count both "- " and "•" bullets for structural completeness
        lines = description.split("\n")
        bullet_count = sum(
            1 for l in lines if l.strip().startswith(("- ", "\u2022"))
        )
        if bullet_count < 3:
            issues.append(f"only {bullet_count} bullet points (need 3+)")
        has_specs = any(
            re.search(r"specs|specification|details", l, re.IGNORECASE)
            for l in lines
        )
        if not has_specs:
            issues.append("no specs/details section header")

    if issues:
        return CheckResult(
            name=f"desc_structure:{field_name}",
            passed=False,
            detail="; ".join(issues),
        )
    return CheckResult(name=f"desc_structure:{field_name}", passed=True)


def _check_bing_synonyms(description: str, category: str | None) -> CheckResult:
    """Check Bing description includes product type synonyms."""
    if not category:
        return CheckResult(
            name="bing_synonyms",
            passed=True,
            detail="No category to check against",
        )
    lower_desc = description.lower()
    lower_cat = category.lower()

    # Find the matching synonym family
    for family_key, synonyms in BING_SYNONYM_FAMILIES.items():
        if family_key in lower_cat:
            found = [s for s in synonyms if s in lower_desc]
            if len(found) < 2:
                return CheckResult(
                    name="bing_synonyms",
                    passed=False,
                    detail=f"Only {len(found)} synonym(s) for '{family_key}' (need 2+): {found}",
                )
            return CheckResult(
                name="bing_synonyms",
                passed=True,
                detail=f"Found {len(found)} synonyms: {found}",
            )

    # No matching family found
    return CheckResult(
        name="bing_synonyms",
        passed=True,
        detail=f"No synonym family for category '{category}'",
    )


_TRUST_SIGNAL_PHRASES = [
    "lifetime warranty",
    "limited lifetime warranty",
    "virginia",
    "assembled in",
    "28 designer finishes",
    "28 finishes",
    "designer finishes",
    "matching accessories",
    "matching pieces",
]

_COMPETITIVE_PHRASES = [
    "solid brass",
    "brass construction",
    "outlasts",
    "die-cast zinc",
    "mass-market",
    "lesser materials",
    "won't corrode",
]


def _check_trust_signals(description: str, field_name: str) -> CheckResult:
    """Verify at least 1 trust signal appears in Shopify descriptions."""
    lower = description.lower()
    found = [p for p in _TRUST_SIGNAL_PHRASES if p in lower]
    if not found:
        return CheckResult(
            name=f"trust_signals:{field_name}",
            passed=False,
            detail="No trust signals found (warranty, Virginia, finishes, matching pieces)",
        )
    return CheckResult(
        name=f"trust_signals:{field_name}",
        passed=True,
        detail=f"Found {len(found)} trust signal(s)",
    )


def _check_competitive_language(description: str, field_name: str) -> CheckResult:
    """Verify 'solid brass' or competitive differentiation language appears."""
    lower = description.lower()
    found = [p for p in _COMPETITIVE_PHRASES if p in lower]
    if not found:
        return CheckResult(
            name=f"competitive_language:{field_name}",
            passed=False,
            detail="No competitive differentiation language found (solid brass, outlasts, etc.)",
        )
    return CheckResult(
        name=f"competitive_language:{field_name}",
        passed=True,
        detail=f"Found: {', '.join(found[:3])}",
    )


def _check_heuristic_score(score: HeuristicScore, platform: str) -> CheckResult:
    """Check heuristic composite score meets minimum."""
    if score.composite < MIN_COMPOSITE_SCORE:
        return CheckResult(
            name=f"heuristic_score:{platform}",
            passed=False,
            detail=f"{score.composite:.1f}% below {MIN_COMPOSITE_SCORE}% minimum",
        )
    return CheckResult(
        name=f"heuristic_score:{platform}",
        passed=True,
        detail=f"{score.composite:.1f}%",
    )


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------


def _load_patch(path: Path) -> dict[str, Any] | None:
    """Load and parse a JSON patch file."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def evaluate_sku(
    sku: str,
    exports_dir: Path,
    category: str | None = None,
) -> SKUEvalResult:
    """Evaluate a single SKU's exports against all checks."""
    result = SKUEvalResult(sku=sku)

    google = _load_patch(exports_dir / f"google-patch-{sku}.json")
    bing = _load_patch(exports_dir / f"bing-patch-{sku}.json")
    shopify = _load_patch(exports_dir / f"shopify-patch-{sku}.json")

    if not any([google, bing, shopify]):
        result.checks.append(
            CheckResult(name="data_present", passed=False, detail="No exports found")
        )
        return result

    result.checks.append(CheckResult(name="data_present", passed=True))

    # --- Google checks ---
    if google:
        g_title = google.get("title", "")
        g_short = google.get("short_title", "")
        g_desc = google.get("description", "")

        if g_title:
            result.checks.append(_check_char_limit(g_title, "google_title", 150))
            result.checks.append(_check_title_min_length(g_title, "google_title"))
            result.checks.append(_check_title_starter(g_title, "google_title"))
            result.checks.append(_check_brand_position(g_title, "google_title"))
            result.checks.append(_check_banned_words(g_title, "google_title"))
            result.checks.append(_check_no_citations(g_title, "google_title"))
        if g_short:
            result.checks.append(_check_char_limit(g_short, "google_short_title", 70))
        if g_desc:
            result.checks.append(_check_banned_words(g_desc, "google_description"))
            result.checks.append(_check_no_citations(g_desc, "google_description"))
            result.checks.append(
                _check_desc_length_range(g_desc, "google_description", 600, 800)
            )
            # Google descriptions are attribute-dense feed fuel (not structured
            # conversion copy), so skip bullet/specs structure check.
            result.checks.append(_check_bullet_format(g_desc, "google_description"))

        if g_title and g_desc:
            g_score = score_bundle(title=g_title, description=g_desc, platform="google")
            result.heuristic_scores["google"] = g_score.composite
            result.checks.append(_check_heuristic_score(g_score, "google"))

    # --- Bing checks ---
    if bing:
        b_title = bing.get("title", "")
        b_desc = bing.get("description", "")

        if b_title:
            result.checks.append(_check_char_limit(b_title, "bing_title", 150))
            result.checks.append(_check_title_min_length(b_title, "bing_title"))
            result.checks.append(_check_title_starter(b_title, "bing_title"))
            result.checks.append(_check_brand_position(b_title, "bing_title"))
            result.checks.append(_check_banned_words(b_title, "bing_title"))
            result.checks.append(_check_no_citations(b_title, "bing_title"))
        if b_desc:
            result.checks.append(_check_banned_words(b_desc, "bing_description"))
            result.checks.append(_check_no_citations(b_desc, "bing_description"))
            result.checks.append(
                _check_desc_length_range(b_desc, "bing_description", 700, 1000)
            )
            # Bing descriptions are attribute-dense feed fuel (not structured
            # conversion copy), so skip bullet/specs structure check.
            result.checks.append(_check_bing_synonyms(b_desc, category))
            result.checks.append(_check_bullet_format(b_desc, "bing_description"))

        if b_title and b_desc:
            b_score = score_bundle(title=b_title, description=b_desc, platform="bing")
            result.heuristic_scores["bing"] = b_score.composite
            result.checks.append(_check_heuristic_score(b_score, "bing"))

    # --- Shopify checks ---
    if shopify:
        s_title = shopify.get("title", "")
        s_body = shopify.get("body_html", "")
        s_meta = shopify.get("metafields_global_description_tag", "")

        if s_title:
            result.checks.append(_check_char_limit(s_title, "shopify_title", 255))
            result.checks.append(_check_title_starter(s_title, "shopify_title"))
            result.checks.append(_check_banned_words(s_title, "shopify_title"))
            result.checks.append(_check_no_citations(s_title, "shopify_title"))
        if s_body:
            result.checks.append(_check_banned_words(s_body, "shopify_body"))
            result.checks.append(_check_no_citations(s_body, "shopify_body"))
            result.checks.append(
                _check_description_structure(s_body, "shopify_body", is_html=True)
            )
            result.checks.append(_check_trust_signals(s_body, "shopify_body"))
            result.checks.append(_check_competitive_language(s_body, "shopify_body"))
        if s_meta:
            result.checks.append(
                _check_char_limit(s_meta, "shopify_meta_description", 155)
            )

        if s_title and s_body:
            s_score = score_bundle(
                title=s_title, description=s_body, html_description=True, platform="shopify"
            )
            result.heuristic_scores["shopify"] = s_score.composite
            result.checks.append(_check_heuristic_score(s_score, "shopify"))

    # Compute composite across platforms
    if result.heuristic_scores:
        result.composite_score = sum(result.heuristic_scores.values()) / len(
            result.heuristic_scores
        )

    result.all_passed = all(c.passed for c in result.checks)
    return result


def evaluate_regression(
    exports_dir: Path | str,
    sku_list: list[dict[str, str]] | None = None,
) -> EvalReport:
    """Evaluate all SKU exports for regression.

    Args:
        exports_dir: Directory containing platform patch JSON files.
        sku_list: Optional list of {"master_sku": ..., "category": ...} dicts.
            If None, discovers SKUs from filenames in exports_dir.

    Returns:
        EvalReport with per-SKU results and aggregate stats.
    """
    exports_dir = Path(exports_dir)
    report = EvalReport(exports_dir=str(exports_dir))

    if sku_list:
        for entry in sku_list:
            sku = entry["master_sku"].replace("/", "-")
            category = entry.get("category")
            result = evaluate_sku(sku, exports_dir, category=category)
            report.sku_results.append(result)
    else:
        # Discover SKUs from filenames
        skus: set[str] = set()
        for pattern in ["google-patch-*.json", "bing-patch-*.json", "shopify-patch-*.json"]:
            for path in exports_dir.glob(pattern):
                prefix = pattern.split("*")[0]
                name = path.name
                if name.startswith(prefix) and name.endswith(".json"):
                    sku = name[len(prefix) : -len(".json")]
                    skus.add(sku)

        for sku in sorted(skus):
            result = evaluate_sku(sku, exports_dir)
            report.sku_results.append(result)

    return report


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_report(report: EvalReport) -> str:
    """Render evaluation report as markdown."""
    lines: list[str] = []
    status = "PASSED" if report.regression_passed else "FAILED"
    lines.append(f"# Regression Evaluation: {status}")
    lines.append("")
    lines.append(f"**Exports directory:** `{report.exports_dir}`")
    lines.append(f"**SKUs evaluated:** {report.total_skus}")
    lines.append(f"**Pass rate:** {report.pass_rate:.1f}% ({report.passing_skus}/{report.total_skus})")
    lines.append(f"**Avg composite score:** {report.avg_composite:.1f}%")
    lines.append(f"**Thresholds:** pass rate >= {MIN_PASS_RATE}%, avg composite >= {MIN_COMPOSITE_SCORE}%")
    lines.append("")

    if not report.regression_passed:
        lines.append("## Failures")
        lines.append("")
        for result in report.sku_results:
            failed = [c for c in result.checks if not c.passed]
            if not failed:
                continue
            lines.append(f"### {result.sku} ({result.composite_score:.1f}%)")
            for check in failed:
                lines.append(f"- **{check.name}**: {check.detail}")
            lines.append("")

    # Summary table
    lines.append("## Per-SKU Summary")
    lines.append("")
    lines.append("| SKU | Status | Composite | Google | Bing | Shopify | Failures |")
    lines.append("|-----|--------|----------:|-------:|-----:|--------:|---------:|")
    for result in report.sku_results:
        status_icon = "PASS" if result.all_passed else "FAIL"
        g = result.heuristic_scores.get("google")
        b = result.heuristic_scores.get("bing")
        s = result.heuristic_scores.get("shopify")
        lines.append(
            f"| {result.sku} | {status_icon} "
            f"| {result.composite_score:.1f}% "
            f"| {f'{g:.1f}%' if g else '-'} "
            f"| {f'{b:.1f}%' if b else '-'} "
            f"| {f'{s:.1f}%' if s else '-'} "
            f"| {result.fail_count} |"
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run regression evaluation from command line."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Run regression evaluation on generated exports."
    )
    parser.add_argument(
        "exports_dir",
        help="Directory containing platform patch JSON files",
    )
    parser.add_argument(
        "--sku-list",
        help="JSON file with [{master_sku, category}] entries",
    )
    parser.add_argument(
        "--output",
        help="Output markdown file path (default: stdout)",
    )
    args = parser.parse_args()

    sku_list = None
    if args.sku_list:
        sku_list = json.loads(Path(args.sku_list).read_text())

    report = evaluate_regression(args.exports_dir, sku_list=sku_list)
    markdown = render_report(report)

    if args.output:
        Path(args.output).write_text(markdown)
        print(f"Report written to {args.output}")
    else:
        print(markdown)

    sys.exit(0 if report.regression_passed else 1)


if __name__ == "__main__":
    main()
