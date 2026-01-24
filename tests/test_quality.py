from pathlib import Path

from feedops.quality.evaluator import evaluate_exports_dir


def test_evaluate_exports_dir_scores_temp_exports(tmp_path: Path):
    (tmp_path / "google-patch-ABC.json").write_text(
        """{
  "offerId": "x",
  "title": "18-Inch Wall Mount Towel Bar Solid Brass | Allied Brass",
  "short_title": "18-Inch Towel Bar",
  "description": "Upgrade your bath with a solid brass towel bar. Center-to-center: 18 in. Projection: 2.5 in. Warranty: Limited Lifetime Warranty." 
}"""
    )
    results = evaluate_exports_dir(tmp_path)
    assert len(results) == 1
    assert results[0]["sku"] == "ABC"
    assert results[0]["composite"] > 0


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
