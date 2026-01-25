from __future__ import annotations

from pathlib import Path
import sys


def resolve_dashboard_paths(repo_root: Path | str) -> tuple[Path, Path, Path | None, Path | None, Path | None]:
    repo_root = Path(repo_root)
    data_root = repo_root / "dashboard_data"
    exports_dir = data_root / "lifestyle-eval"
    catalog_path = data_root / "catalog.csv"
    reports_dir = data_root / "lifestyle-eval" / "reports"
    return (
        exports_dir, 
        exports_dir, 
        catalog_path if catalog_path.exists() else None,
        reports_dir if reports_dir.exists() else None,
        reports_dir if reports_dir.exists() else None,
    )


def _ensure_src_on_path(repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    _ensure_src_on_path(repo_root)

    from feedops.quality.review_dashboard import run_dashboard

    baseline, candidate, catalog, baseline_reports, candidate_reports = resolve_dashboard_paths(repo_root)
    run_dashboard(
        baseline_exports_dir=baseline,
        candidate_exports_dir=candidate,
        catalog_path=catalog,
        baseline_reports_dir=baseline_reports,
        candidate_reports_dir=candidate_reports,
    )


if __name__ == "__main__":
    main()
