from pathlib import Path


def test_resolve_dashboard_paths_uses_candidate_dir_when_present(tmp_path: Path) -> None:
    data_dir = tmp_path / "dashboard_data"
    baseline_dir = data_dir / "lifestyle-eval"
    candidate_dir = data_dir / "lifestyle-eval-candidate"
    (baseline_dir / "reports").mkdir(parents=True)
    (candidate_dir / "reports").mkdir(parents=True)
    # Candidate directory should be treated as active when it contains export patches.
    (candidate_dir / "google-patch-TEST.json").write_text("{}")
    catalog_path = data_dir / "catalog.csv"
    catalog_path.write_text("MasterSKU,Category\n")

    from streamlit_app import resolve_dashboard_paths

    baseline, candidate, catalog, baseline_reports, candidate_reports = resolve_dashboard_paths(tmp_path)

    assert baseline == baseline_dir
    assert candidate == candidate_dir
    assert catalog == catalog_path
    assert baseline_reports == baseline_dir / "reports"
    assert candidate_reports == candidate_dir / "reports"


def test_resolve_dashboard_paths_falls_back_to_baseline(tmp_path: Path) -> None:
    data_dir = tmp_path / "dashboard_data"
    baseline_dir = data_dir / "lifestyle-eval"
    baseline_dir.mkdir(parents=True)
    catalog_path = data_dir / "catalog.csv"
    catalog_path.write_text("MasterSKU,Category\n")

    from streamlit_app import resolve_dashboard_paths

    baseline, candidate, catalog, baseline_reports, candidate_reports = resolve_dashboard_paths(tmp_path)

    assert baseline == baseline_dir
    assert candidate == baseline_dir
    assert catalog == catalog_path
    assert baseline_reports is None
    assert candidate_reports is None
