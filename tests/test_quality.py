from pathlib import Path

from feedops.quality.evaluator import evaluate_exports_dir, render_markdown
from feedops.quality.scoring import score_brand_voice, score_description, score_title


def test_score_title_rewards_product_type_and_dimension():
    title = "18-Inch Wall Mount Towel Bar, Solid Brass | Skyline | Allied Brass"
    score, notes = score_title(title)
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


def test_score_description_plain_text_rewards_bullets_and_specs_sections():
    text = (
        "Add space-saving towel storage with this 24-inch wall mount towel bar crafted from solid brass. Designed for everyday bathroom use.\n\n"
        "Highlights:\n"
        "- 24-inch center-to-center towel bar\n"
        "- Solid brass construction\n"
        "- Concealed mounting hardware\n\n"
        "Specs:\n"
        "- Overall length: 26 in\n"
        "- Projection: 2.5 in\n"
        "- Warranty: Limited Lifetime Warranty\n"
    )
    score, _notes = score_description(text, html=False)
    assert score >= 9


def test_score_description_plain_text_accepts_specs_and_details_label():
    text = (
        "Refresh your bath with a 24-inch wall mount towel bar crafted from solid brass. Designed for everyday bathroom use with a clean, space-saving profile.\n\n"
        "- Solid brass construction\n"
        "- Concealed mounting\n"
        "- Hardware included\n\n"
        "Specs & details:\n"
        "- Center-to-center: 24 in\n"
        "- Projection: 2.5 in\n"
        "- Warranty: Limited Lifetime Warranty\n"
    )
    score, _notes = score_description(text, html=False)
    assert score >= 9


def test_score_brand_voice_penalizes_promotional_language():
    score, notes = score_brand_voice("BEST amazing product!!!")
    assert score <= 4
    assert any("Promotional" in n or "Exclamation" in n for n in notes)


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
