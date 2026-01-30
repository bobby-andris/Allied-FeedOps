from pathlib import Path

from feedops.models import Candidate, Score
from feedops.quality.evaluator import evaluate_exports_dir, render_markdown
from feedops.quality.scoring import (
    assess_soft_gates,
    score_brand_voice,
    score_bundle,
    score_candidate,
    score_description,
    score_title,
)


def test_score_title_rewards_product_type_and_dimension():
    title = "18-Inch Wall Mount Towel Bar, Solid Brass | Skyline | Allied Brass"
    score, notes, _zone = score_title(title)
    assert score >= 6
    assert "No primary dimension detected" not in " ".join(notes)


def test_score_description_html_rewards_structure():
    html = (
        "<p>Upgrade your bathroom with a solid brass 18-inch towel bar.</p>"
        "<ul><li>Solid brass</li><li>Wall mount</li><li>Includes hardware</li></ul>"
        "<p>Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty.</p>"
    )
    score, notes = score_description(html, html=True)
    assert score >= 6
    assert "Missing <ul><li> highlights block" not in " ".join(notes)


def test_assess_soft_gates_warns_on_missing_dimension():
    assessment = assess_soft_gates(
        title="Wall Mount Towel Bar Solid Brass | Allied Brass",
        description=(
            "Upgrade your bathroom with solid brass storage built to last.\n\n"
            "- Solid brass construction\n"
            "- Concealed mounting hardware\n"
            "- Wall mount installation\n\n"
            "Specs:\n"
            "- Center-to-center: 18 in\n"
            "- Overall length: 20 in\n"
            "- Projection: 2.5 in\n"
        ),
        html_description=False,
    )

    assert assessment.miss_count == 1
    assert any("dimension" in warning.lower() for warning in assessment.warnings)


def test_assess_soft_gates_warns_on_missing_bullets_and_specs():
    assessment = assess_soft_gates(
        title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        description="Upgrade your bathroom with a solid brass towel bar.",
        html_description=False,
    )

    assert assessment.miss_count == 2
    assert any("bullets" in warning.lower() for warning in assessment.warnings)
    assert any("spec" in warning.lower() for warning in assessment.warnings)


def test_score_brand_voice_penalizes_promotional_language():
    score, notes = score_brand_voice("BEST amazing product!!!")
    assert score <= 4
    assert any("Promotional" in n or "Exclamation" in n for n in notes)


def test_score_candidate_weighted_composite_matches_platform_scores():
    candidate = Candidate(
        google_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        google_short_title="18-Inch Towel Bar",
        google_description="Add space-saving towel storage with this 18-inch wall mount towel bar crafted from solid brass. "
        "Highlights:\n- 18-inch center-to-center\n- Solid brass construction\n- Concealed mounting hardware\n"
        "Specs:\n- Overall length: 20 in\n- Projection: 2.5 in\n- Warranty: Limited Lifetime Warranty\n",
        bing_title="18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
        bing_description=(
            "Organize towels with a wall mounted towel bar crafted from solid brass.\n"
            "- 18-inch center-to-center\n"
            "- Solid brass construction\n"
            "- Concealed mounting hardware\n"
            "Specs:\n- Overall length: 20 in\n- Projection: 2.5 in\n- Warranty: Limited Lifetime Warranty\n"
        ),
        shopify_title="18-Inch Solid Brass Towel Bar | Allied Brass",
        shopify_description=(
            "<p>Upgrade your bathroom with a solid brass towel bar built for daily use.</p>"
            "<ul><li>Solid brass construction</li><li>Wall mount</li><li>Hardware included</li></ul>"
            "<p>Center-to-center: 18 in. Overall length: 20 in. Projection: 2.5 in.</p>"
        ),
        claims=[],
        self_score=Score(
            specificity=5,
            benefit_coverage=5,
            keyword_inclusion=5,
            format_adherence=5,
            brand_voice=5,
            factual_accuracy=5,
        ),
    )
    weights = {"google": 0.7, "bing": 0.15, "shopify": 0.15}
    result = score_candidate(candidate, weights=weights)

    google_score = score_bundle(
        title=candidate.google_title,
        description=candidate.google_description,
        platform="google",
    )
    bing_score = score_bundle(
        title=candidate.bing_title,
        description=candidate.bing_description,
        platform="bing",
    )
    shopify_score = score_bundle(
        title=candidate.shopify_title,
        description=candidate.shopify_description,
        html_description=True,
        platform="shopify",
    )
    expected = round(
        (
            google_score.composite * weights["google"]
            + bing_score.composite * weights["bing"]
            + shopify_score.composite * weights["shopify"]
        )
        / sum(weights.values()),
        2,
    )

    assert result.google.composite == google_score.composite
    assert result.bing.composite == bing_score.composite
    assert result.shopify.composite == shopify_score.composite
    assert result.weighted_composite == expected
    assert result.soft_gate_penalty == 0.0
    assert result.adjusted_weighted_composite == expected


def test_evaluate_exports_dir_scores_temp_exports(tmp_path: Path):
    (tmp_path / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Upgrade your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty." 
}"""
    )
    (tmp_path / "bing-patch-ABC.json").write_text(
        """{
  "sku": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "description": "Organize towels with a wall mounted towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty."
}"""
    )
    (tmp_path / "shopify-patch-ABC.json").write_text(
        """{
  "productId": "x",
  "title": "18-Inch Solid Brass Towel Bar | Allied Brass",
  "body_html": "<p>Upgrade your bathroom.</p><ul><li>Solid brass</li></ul><p>Center-to-center: 18 in</p>"
}"""
    )
    results = evaluate_exports_dir(tmp_path)
    assert len(results) == 1
    assert results[0]["sku"] == "ABC"
    assert results[0]["composite"] > 0
    assert results[0]["google"]["composite"] > 0

    md = render_markdown(results)
    assert "| ABC |" in md


def test_evaluate_exports_dir_skips_incomplete_entries(tmp_path: Path):
    (tmp_path / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "Incomplete title only"
}"""
    )
    results = evaluate_exports_dir(tmp_path)
    assert results[0]["sku"] == "ABC"
    assert results[0]["composite"] == 0.0
    assert "google" not in results[0]


def test_evaluate_exports_dir_skips_missing_shopify_body(tmp_path: Path):
    (tmp_path / "shopify-patch-ABC.json").write_text(
        """{
  "productId": "x",
  "title": "Incomplete shopify title"
}"""
    )
    results = evaluate_exports_dir(tmp_path)
    assert results[0]["sku"] == "ABC"
    assert results[0]["composite"] == 0.0
    assert "shopify" not in results[0]
