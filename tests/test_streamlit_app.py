from pathlib import Path


def test_resolve_dashboard_paths_uses_repo_layout(tmp_path: Path) -> None:
    data_dir = tmp_path / "dashboard_data"
    exports_dir = data_dir / "lifestyle-eval"
    exports_dir.mkdir(parents=True)
    catalog_path = data_dir / "catalog.csv"
    catalog_path.write_text("MasterSKU,Category\n")

    from streamlit_app import resolve_dashboard_paths

    baseline, candidate, catalog = resolve_dashboard_paths(tmp_path)

    assert baseline == exports_dir
    assert candidate == exports_dir
    assert catalog == catalog_path
