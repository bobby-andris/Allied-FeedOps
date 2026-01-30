"""Tests for the automated eval framework."""

import json

import pytest

from feedops.quality.eval_framework import (
    CheckResult,
    EvalReport,
    SKUEvalResult,
    _check_banned_words,
    _check_brand_position,
    _check_char_limit,
    _check_bing_synonyms,
    _check_description_structure,
    _check_no_citations,
    _check_title_starter,
    evaluate_regression,
    evaluate_sku,
    render_report,
)


# ---------------------------------------------------------------------------
# Individual check tests
# ---------------------------------------------------------------------------


class TestBannedWords:
    def test_passes_clean_text(self):
        r = _check_banned_words("Solid brass towel bar", "title")
        assert r.passed

    def test_catches_banned_word(self):
        r = _check_banned_words("Premium towel bar", "title")
        assert not r.passed
        assert "premium" in r.detail

    def test_catches_multiple(self):
        r = _check_banned_words("The finest and most luxurious bar", "desc")
        assert not r.passed
        assert "finest" in r.detail
        assert "luxurious" in r.detail


class TestTitleStarter:
    def test_passes_clean_title(self):
        r = _check_title_starter("Towel Bar, 18-Inch, Allied Brass", "google_title")
        assert r.passed

    def test_catches_premium(self):
        r = _check_title_starter("Premium Towel Bar", "google_title")
        assert not r.passed

    def test_catches_luxury(self):
        r = _check_title_starter("Luxury Grab Bar", "google_title")
        assert not r.passed

    def test_catches_best(self):
        r = _check_title_starter("Best Paper Towel Holder", "google_title")
        assert not r.passed


class TestCharLimit:
    def test_passes_within_limit(self):
        r = _check_char_limit("Short title", "google_title", 150)
        assert r.passed

    def test_fails_over_limit(self):
        r = _check_char_limit("x" * 151, "google_title", 150)
        assert not r.passed
        assert "151" in r.detail


class TestBrandPosition:
    def test_passes_brand_last(self):
        r = _check_brand_position("Towel Bar, 18-Inch, Allied Brass", "title")
        assert r.passed

    def test_fails_brand_not_last(self):
        r = _check_brand_position("Allied Brass Towel Bar", "title")
        assert not r.passed

    def test_handles_pipe_separator(self):
        r = _check_brand_position("Towel Bar | Allied Brass", "title")
        assert r.passed


class TestNoCitations:
    def test_passes_clean(self):
        r = _check_no_citations("Solid brass construction", "desc")
        assert r.passed

    def test_catches_catalog_csv(self):
        r = _check_no_citations("From catalog_csv: value", "desc")
        assert not r.passed


class TestDescriptionStructure:
    def test_plain_text_passes_with_bullets_and_specs(self):
        desc = (
            "Great towel bar for your bathroom.\n\n"
            "- Solid brass construction\n"
            "- Wall mount installation\n"
            "- Includes hardware\n\n"
            "Specs:\n"
            "- Length: 18 in\n"
        )
        r = _check_description_structure(desc, "google_description")
        assert r.passed

    def test_plain_text_fails_missing_bullets(self):
        desc = "Great towel bar for your bathroom. Solid brass."
        r = _check_description_structure(desc, "google_description")
        assert not r.passed
        assert "bullet" in r.detail

    def test_html_passes_with_structure(self):
        desc = "<p>Hook</p><ul><li>Item 1</li><li>Item 2</li></ul>"
        r = _check_description_structure(desc, "shopify_body", is_html=True)
        assert r.passed

    def test_html_fails_missing_list(self):
        desc = "<p>Only a paragraph, no list.</p>"
        r = _check_description_structure(desc, "shopify_body", is_html=True)
        assert not r.passed
        assert "<ul><li>" in r.detail


class TestBingSynonyms:
    def test_passes_with_synonyms(self):
        desc = "This towel bar serves as a towel rack for your bathroom."
        r = _check_bing_synonyms(desc, "Towel Bars")
        assert r.passed

    def test_fails_without_synonyms(self):
        desc = "Great product for your bathroom space."
        r = _check_bing_synonyms(desc, "Towel Bars")
        assert not r.passed
        assert "synonym" in r.detail.lower()

    def test_passes_unknown_category(self):
        desc = "Some description."
        r = _check_bing_synonyms(desc, "Unknown Category")
        assert r.passed


# ---------------------------------------------------------------------------
# SKU evaluation tests
# ---------------------------------------------------------------------------


class TestEvaluateSKU:
    def test_no_exports_found(self, tmp_path):
        result = evaluate_sku("FAKE-SKU", tmp_path)
        assert not result.all_passed
        assert any("No exports found" in c.detail for c in result.checks)

    def test_valid_google_export(self, tmp_path):
        google_patch = {
            "title": "Paper Towel Holder, 14-Inch Freestanding, Solid Brass, Allied Brass",
            "short_title": "Paper Towel Holder, 14-Inch",
            "description": (
                "Keep paper towels within reach and your countertop clutter-free.\n\n"
                "- Solid brass construction for lasting durability\n"
                "- Freestanding design requires no drilling\n"
                "- Weighted base prevents tipping\n\n"
                "Specs & Details:\n"
                "- Dimensions: 5 x 14 x 5 in\n"
                "- Material: Solid brass\n"
                "- Warranty: Limited Lifetime Warranty\n"
                "- Assembly: None required\n\n"
                "Crafted from solid brass and backed by a limited lifetime warranty, "
                "this paper towel holder keeps your kitchen organized with style. "
                "Choose from 28 designer finishes to coordinate with your kitchen hardware."
            ),
        }
        (tmp_path / "google-patch-TEST.json").write_text(json.dumps(google_patch))

        result = evaluate_sku("TEST", tmp_path)
        # Should have data_present + title checks + description checks + heuristic
        assert result.checks
        assert result.composite_score > 0
        # Title checks should pass (brand last, within limit, no banned words)
        title_checks = [c for c in result.checks if "google_title" in c.name]
        assert all(c.passed for c in title_checks), [
            f"{c.name}: {c.detail}" for c in title_checks if not c.passed
        ]

    def test_shopify_html_checks(self, tmp_path):
        shopify_patch = {
            "title": "Paper Towel Holder, Freestanding, Allied Brass",
            "body_html": (
                "<p>Keep your kitchen tidy with this freestanding paper towel holder.</p>"
                "<ul><li>Solid brass</li><li>Weighted base</li><li>No drilling</li></ul>"
                "<p>Specs: 5 x 14 x 5 in. Lifetime warranty.</p>"
            ),
            "metafields_global_description_tag": "Freestanding paper towel holder in solid brass.",
        }
        (tmp_path / "shopify-patch-TEST.json").write_text(json.dumps(shopify_patch))

        result = evaluate_sku("TEST", tmp_path)
        shopify_checks = [c for c in result.checks if "shopify" in c.name]
        assert len(shopify_checks) > 0
        html_check = [c for c in result.checks if "shopify_body" in c.name and "structure" in c.name]
        assert html_check and html_check[0].passed


# ---------------------------------------------------------------------------
# Regression evaluation tests
# ---------------------------------------------------------------------------


class TestEvaluateRegression:
    def test_discovers_skus_from_directory(self, tmp_path):
        for sku in ["SKU-A", "SKU-B"]:
            (tmp_path / f"google-patch-{sku}.json").write_text(
                json.dumps({
                    "title": f"Towel Bar, 18-Inch, Allied Brass",
                    "description": (
                        "Upgrade your bathroom with this towel bar.\n\n"
                        "- Solid brass\n- Wall mount\n- Hardware included\n\n"
                        "Specs:\n- Length: 18 in\n- Warranty: Lifetime\n"
                        "- Material: Solid brass\n- Mounting: Concealed\n"
                        "Crafted from solid brass for lasting durability."
                    ),
                })
            )

        report = evaluate_regression(tmp_path)
        assert report.total_skus == 2
        assert report.avg_composite > 0

    def test_uses_sku_list(self, tmp_path):
        (tmp_path / "google-patch-1051.json").write_text(
            json.dumps({
                "title": "Paper Towel Holder, 14-Inch, Allied Brass",
                "description": (
                    "Keep paper towels handy and countertop clear.\n\n"
                    "- Solid brass construction\n- Freestanding design\n"
                    "- Weighted base\n\nSpecs:\n- Dimensions: 5x14x5 in\n"
                    "- Material: Brass\n- Warranty: Lifetime\n"
                    "Assembled in Virginia."
                ),
            })
        )

        sku_list = [{"master_sku": "1051", "category": "Paper Towel Holders"}]
        report = evaluate_regression(tmp_path, sku_list=sku_list)
        assert report.total_skus == 1
        assert report.sku_results[0].sku == "1051"


class TestRenderReport:
    def test_renders_markdown(self):
        report = EvalReport(
            exports_dir="/test/dir",
            sku_results=[
                SKUEvalResult(
                    sku="SKU-1",
                    checks=[CheckResult(name="test", passed=True)],
                    heuristic_scores={"google": 75.0},
                    composite_score=75.0,
                    all_passed=True,
                ),
            ],
        )
        md = render_report(report)
        assert "PASSED" in md
        assert "SKU-1" in md
        assert "75.0%" in md

    def test_renders_failures(self):
        report = EvalReport(
            exports_dir="/test/dir",
            sku_results=[
                SKUEvalResult(
                    sku="BAD-1",
                    checks=[
                        CheckResult(name="banned_words", passed=False, detail="Found: premium"),
                    ],
                    composite_score=40.0,
                    all_passed=False,
                ),
            ],
        )
        md = render_report(report)
        assert "FAILED" in md
        assert "BAD-1" in md
        assert "premium" in md
