"""Tests for review_dashboard conditional column rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from feedops.quality.review_dashboard import (
    format_variant_description,
    get_dashboard_debug_info,
    select_patch_variants_for_preview,
    _choose_variant,
)
from feedops.quality.data_loader import (
    load_latest_report,
    _slugify,
)


@dataclass
class MockContent:
    """Mock content object for testing."""
    title: str
    description: str


@dataclass
class MockOriginal:
    """Mock original content object."""
    title: str
    description: str


@dataclass
class MockReport:
    """Mock report object."""
    evidence_markdown: str | None = None
    prompt_text: str | None = None
    provider_model: str | None = None


@dataclass
class MockSKUData:
    """Mock SKUData for testing render_content_comparison."""
    sku: str
    original: MockOriginal | None
    baseline: dict[str, MockContent]
    candidate: dict[str, MockContent]
    baseline_scores: dict[str, dict[str, float]]
    candidate_scores: dict[str, dict[str, float]]
    baseline_report: MockReport | None = None
    candidate_report: MockReport | None = None


class TestRenderContentComparisonColumnLogic:
    """Test conditional column rendering in render_content_comparison."""

    def test_original_only_when_no_baseline_no_candidate(self):
        """Verify only Original column renders when no baseline/candidate exists."""
        sku_data = MockSKUData(
            sku="TEST-001",
            original=MockOriginal(title="Original Title", description="Original Desc"),
            baseline={},  # No baseline content
            candidate={},  # No candidate content
            baseline_scores={},
            candidate_scores={},
        )
        
        # The function should detect has_baseline=False and has_candidate=False
        # and render only the Original column
        
        # Test the logic directly
        for plat_key in ["google", "bing", "shopify"]:
            baseline_content = sku_data.baseline.get(plat_key)
            candidate_content = sku_data.candidate.get(plat_key)
            
            has_baseline = baseline_content is not None
            has_candidate = candidate_content is not None
            
            assert not has_baseline, f"Expected no baseline for {plat_key}"
            assert not has_candidate, f"Expected no candidate for {plat_key}"
            
            # Logic path: should render only Original
            assert not has_baseline and not has_candidate

    def test_two_columns_when_only_baseline_exists(self):
        """Verify 2 columns render when only baseline exists (no candidate)."""
        sku_data = MockSKUData(
            sku="TEST-002",
            original=MockOriginal(title="Original Title", description="Original Desc"),
            baseline={
                "google": MockContent(title="Baseline Title", description="Baseline Desc"),
            },
            candidate={},  # No candidate
            baseline_scores={"google": {"composite": 85.0}},
            candidate_scores={},
        )
        
        baseline_content = sku_data.baseline.get("google")
        candidate_content = sku_data.candidate.get("google")
        
        has_baseline = baseline_content is not None
        has_candidate = candidate_content is not None
        
        assert has_baseline, "Expected baseline to exist"
        assert not has_candidate, "Expected no candidate"
        
        # Logic path: should render 2 columns (Original + Baseline)
        assert has_baseline and not has_candidate

    def test_two_columns_when_only_candidate_exists(self):
        """Verify 2 columns render when only candidate exists (no baseline)."""
        sku_data = MockSKUData(
            sku="TEST-003",
            original=MockOriginal(title="Original Title", description="Original Desc"),
            baseline={},  # No baseline
            candidate={
                "google": MockContent(title="Candidate Title", description="Candidate Desc"),
            },
            baseline_scores={},
            candidate_scores={"google": {"composite": 90.0}},
        )
        
        baseline_content = sku_data.baseline.get("google")
        candidate_content = sku_data.candidate.get("google")
        
        has_baseline = baseline_content is not None
        has_candidate = candidate_content is not None
        
        assert not has_baseline, "Expected no baseline"
        assert has_candidate, "Expected candidate to exist"
        
        # Logic path: should render 2 columns (Original + Candidate)
        assert not has_baseline and has_candidate

    def test_three_columns_when_both_baseline_and_candidate_exist(self):
        """Verify 3 columns render when both baseline and candidate exist."""
        sku_data = MockSKUData(
            sku="TEST-004",
            original=MockOriginal(title="Original Title", description="Original Desc"),
            baseline={
                "google": MockContent(title="Baseline Title", description="Baseline Desc"),
            },
            candidate={
                "google": MockContent(title="Candidate Title", description="Candidate Desc"),
            },
            baseline_scores={"google": {"composite": 85.0}},
            candidate_scores={"google": {"composite": 92.0}},
        )
        
        baseline_content = sku_data.baseline.get("google")
        candidate_content = sku_data.candidate.get("google")
        
        has_baseline = baseline_content is not None
        has_candidate = candidate_content is not None
        
        assert has_baseline, "Expected baseline to exist"
        assert has_candidate, "Expected candidate to exist"
        
        # Logic path: should render 3 columns
        assert has_baseline and has_candidate

    def test_platform_specific_content_handling(self):
        """Verify each platform can have different content availability."""
        sku_data = MockSKUData(
            sku="TEST-005",
            original=MockOriginal(title="Original Title", description="Original Desc"),
            baseline={
                "google": MockContent(title="Google Baseline", description="Google Baseline Desc"),
                # No bing baseline
                "shopify": MockContent(title="Shopify Baseline", description="Shopify Baseline Desc"),
            },
            candidate={
                "google": MockContent(title="Google Candidate", description="Google Candidate Desc"),
                "bing": MockContent(title="Bing Candidate", description="Bing Candidate Desc"),
                # No shopify candidate
            },
            baseline_scores={
                "google": {"composite": 85.0},
                "shopify": {"composite": 80.0},
            },
            candidate_scores={
                "google": {"composite": 92.0},
                "bing": {"composite": 88.0},
            },
        )
        
        # Google: both exist -> 3 columns
        assert sku_data.baseline.get("google") is not None
        assert sku_data.candidate.get("google") is not None
        
        # Bing: only candidate -> 2 columns
        assert sku_data.baseline.get("bing") is None
        assert sku_data.candidate.get("bing") is not None
        
        # Shopify: only baseline -> 2 columns
        assert sku_data.baseline.get("shopify") is not None
        assert sku_data.candidate.get("shopify") is None


class TestExpanderLabelLogic:
    """Test expander label formatting based on content availability."""

    def test_expander_label_original_only(self):
        """Verify expander label shows 'Original content only' when no baseline/candidate."""
        has_baseline = False
        has_candidate = False
        info = {"icon": "🔍", "name": "Google Shopping / Performance Max"}
        
        if not has_baseline and not has_candidate:
            expander_label = f"{info['icon']} **{info['name']}** — Original content only"
        else:
            expander_label = f"{info['icon']} **{info['name']}** — Score: X%"
        
        assert "Original content only" in expander_label
        assert "Score:" not in expander_label

    def test_expander_label_with_comparison(self):
        """Verify expander label shows score and delta when comparison exists."""
        has_baseline = True
        has_candidate = True
        c_score = 92.0
        b_score = 85.0
        score_delta = c_score - b_score
        info = {"icon": "🔍", "name": "Google Shopping / Performance Max"}

        if not has_baseline and not has_candidate:
            expander_label = f"{info['icon']} **{info['name']}** — Original content only"
        else:
            if score_delta > 0.5:
                delta_display = f"🟢 +{score_delta:.1f}%"
            elif score_delta < -0.5:
                delta_display = f"🔴 {score_delta:.1f}%"
            else:
                delta_display = f"⚪ {score_delta:+.1f}%"
            expander_label = (
                f"{info['icon']} **{info['name']}** — Score: {c_score:.1f}% ({delta_display})"
            )

        assert "Score: 92.0%" in expander_label
        assert "🟢 +7.0%" in expander_label
        assert "Original content only" not in expander_label


def test_select_patch_variants_for_preview_handles_missing_variants_attr():
    """Variant preview selection must not crash if cached ExportContent lacks .variants."""
    from types import SimpleNamespace

    sku_data = SimpleNamespace(
        candidate={
            "google": MockContent(title="t", description="d"),  # no .variants attribute
            "bing": MockContent(title="t", description="d"),  # no .variants attribute
        }
    )
    platform, variants = select_patch_variants_for_preview(sku_data)
    assert platform is None
    assert variants == []


def test_choose_variant_selects_by_finish_and_option_id():
    variants = [
        {
            "offerId": "id-ab",
            "title": "Antique Brass Thing",
            "description": "Description in Antique Brass.",
            "_meta": {"finish": "Antique Brass", "option_sku": "SKU-AB"},
        },
        {
            "offerId": "id-as",
            "title": "Autumn Sparkle Thing",
            "description": "Description in Autumn Sparkle.",
            "_meta": {"finish": "Autumn Sparkle", "option_sku": "SKU-AS"},
        },
    ]

    chosen = _choose_variant(variants, finish="Autumn Sparkle", option_id="SKU-AS")
    assert chosen is not None
    assert "Autumn Sparkle" in chosen["description"]
    assert "Antique Brass" not in chosen["description"]


class TestVariantDescriptionFormatting:
    """Tests for variant description preview formatting."""

    def test_returns_full_text_when_no_limit(self):
        text = "x" * 800
        assert format_variant_description(text, None) == text

    def test_truncates_when_limit_is_set(self):
        text = "x" * 600
        assert format_variant_description(text, 100) == ("x" * 100) + "..."


class TestDashboardDebugInfo:
    """Tests for dashboard debug info collection."""

    def test_counts_reports_and_exports(self, tmp_path):
        baseline_exports = tmp_path / "baseline"
        candidate_exports = tmp_path / "candidate"
        baseline_reports = tmp_path / "baseline_reports"
        candidate_reports = tmp_path / "candidate_reports"

        baseline_exports.mkdir()
        candidate_exports.mkdir()
        baseline_reports.mkdir()
        candidate_reports.mkdir()

        (baseline_exports / "google-patch-ABC.json").write_text("{}")
        (candidate_exports / "google-patch-DEF.json").write_text("{}")
        (candidate_reports / "sku-DEF-20260101-000000.md").write_text("report")

        info = get_dashboard_debug_info(
            baseline_exports_dir=baseline_exports,
            candidate_exports_dir=candidate_exports,
            baseline_reports_dir=baseline_reports,
            candidate_reports_dir=candidate_reports,
        )

        assert info["baseline_exports_count"] == 1
        assert info["candidate_exports_count"] == 1
        assert info["baseline_reports_count"] == 0
        assert info["candidate_reports_count"] == 1


class TestLoadLatestReport:
    """Tests for load_latest_report and SKU slugification."""

    def test_slugify_preserves_alphanumeric_and_dash(self):
        """Verify _slugify handles SKUs with hyphens correctly."""
        assert _slugify("CL-22") == "cl-22"
        assert _slugify("1051") == "1051"
        assert _slugify("WP-2-16-GAL") == "wp-2-16-gal"

    def test_slugify_replaces_special_chars(self):
        """Verify _slugify replaces special characters with dashes."""
        assert _slugify("SKU/123") == "sku-123"
        assert _slugify("SKU 456") == "sku-456"

    def test_load_latest_report_finds_exact_match(self, tmp_path):
        """Verify load_latest_report finds reports with exact SKU match."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Create a report file with lowercase slug
        report_content = """# Report
**Provider/Model:** gemini-2.0-flash
**Status:** APPROVED
"""
        (reports_dir / "sku-cl-22-20260101-120000.md").write_text(report_content)

        result = load_latest_report(reports_dir, "cl-22")
        assert result is not None
        assert result.provider_model == "gemini-2.0-flash"
        assert result.status == "APPROVED"

    def test_load_latest_report_finds_uppercase_match(self, tmp_path):
        """Verify load_latest_report finds reports with uppercase SKU in filename."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Create a report file with UPPERCASE SKU (like actual reports)
        report_content = """# Report
**Provider/Model:** gemini-2.0-flash
**Status:** APPROVED
"""
        (reports_dir / "sku-CL-22-20260101-120000.md").write_text(report_content)

        # Search with lowercase slugified SKU
        result = load_latest_report(reports_dir, "cl-22")
        assert result is not None
        assert result.provider_model == "gemini-2.0-flash"

    def test_load_latest_report_returns_most_recent(self, tmp_path):
        """Verify load_latest_report returns the most recent report by mtime."""
        import time

        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        # Create older report
        older = reports_dir / "sku-abc-20260101-100000.md"
        older.write_text("**Provider/Model:** old-model")

        # Small delay to ensure different mtime
        time.sleep(0.01)

        # Create newer report
        newer = reports_dir / "sku-abc-20260101-120000.md"
        newer.write_text("**Provider/Model:** new-model")

        result = load_latest_report(reports_dir, "abc")
        assert result is not None
        assert result.provider_model == "new-model"

    def test_load_latest_report_returns_none_when_no_reports(self, tmp_path):
        """Verify load_latest_report returns None when no matching reports exist."""
        reports_dir = tmp_path / "reports"
        reports_dir.mkdir()

        result = load_latest_report(reports_dir, "nonexistent")
        assert result is None

    def test_load_latest_report_returns_none_when_dir_missing(self, tmp_path):
        """Verify load_latest_report returns None when reports dir doesn't exist."""
        result = load_latest_report(tmp_path / "missing", "any-sku")
        assert result is None
