import json

from feedops.quality.data_loader import load_all_sku_data


def test_load_all_sku_data_falls_back_to_previous_for_original(tmp_path):
    baseline_dir = tmp_path / "baseline"
    candidate_dir = tmp_path / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()

    baseline_patch = {
        "title": "Baseline Title",
        "description": "Baseline Description",
        "_previous": {"title": "Orig Title", "description": "Orig Description"},
    }
    candidate_patch = {
        "title": "Candidate Title",
        "description": "Candidate Description",
    }

    (baseline_dir / "google-patch-ABC-123.json").write_text(json.dumps(baseline_patch))
    (candidate_dir / "google-patch-ABC-123.json").write_text(json.dumps(candidate_patch))

    results = load_all_sku_data(
        baseline_exports_dir=baseline_dir,
        candidate_exports_dir=candidate_dir,
        catalog_path=None,
        baseline_reports_dir=None,
        candidate_reports_dir=None,
    )
    sku_data = next(r for r in results if r.sku == "ABC-123")
    assert sku_data.original is not None
    assert sku_data.original.title == "Orig Title"
    assert sku_data.original.description == "Orig Description"

