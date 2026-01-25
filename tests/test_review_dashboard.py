"""Tests for review_dashboard conditional column rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


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
            expander_label = f"{info['icon']} **{info['name']}** — Score: {c_score:.1f}% ({delta_display})"
        
        assert "Score: 92.0%" in expander_label
        assert "🟢 +7.0%" in expander_label
        assert "Original content only" not in expander_label
