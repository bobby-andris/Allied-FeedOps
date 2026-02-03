"""FeedOps Unified Dashboard.

Provides unified navigation between the Review Dashboard (for content approval)
and the Performance Dashboard (for monitoring published content).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st


_APP_BUILD = "2026-02-03.2"


def _resolve_path_from_env(repo_root: Path, env_key: str, default: Path) -> Path:
    raw = os.environ.get(env_key)
    if not raw:
        return default
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate


def _dir_has_patch_jsons(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    return any(path.glob("*-patch-*.json"))


def resolve_dashboard_paths(
    repo_root: Path | str,
) -> tuple[Path, Path, Path | None, Path | None, Path | None]:
    """Resolve paths for the review dashboard."""
    repo_root = Path(repo_root)
    data_root = repo_root / "dashboard_data"
    baseline_exports_default = data_root / "lifestyle-eval"
    candidate_exports_default = data_root / "lifestyle-eval-candidate"

    baseline_exports = _resolve_path_from_env(
        repo_root, "FEEDOPS_BASELINE_DIR", baseline_exports_default
    )
    candidate_exports = _resolve_path_from_env(
        repo_root, "FEEDOPS_CANDIDATE_DIR", candidate_exports_default
    )
    if not _dir_has_patch_jsons(candidate_exports):
        candidate_exports = baseline_exports

    catalog_path_default = data_root / "catalog.csv"
    catalog_path = _resolve_path_from_env(repo_root, "FEEDOPS_CATALOG_PATH", catalog_path_default)

    baseline_reports_default = baseline_exports / "reports"
    candidate_reports_default = candidate_exports / "reports"
    baseline_reports = _resolve_path_from_env(
        repo_root, "FEEDOPS_BASELINE_REPORTS", baseline_reports_default
    )
    candidate_reports = _resolve_path_from_env(
        repo_root, "FEEDOPS_CANDIDATE_REPORTS", candidate_reports_default
    )

    return (
        baseline_exports,
        candidate_exports,
        catalog_path if catalog_path.exists() else None,
        baseline_reports if baseline_reports.exists() else None,
        candidate_reports if candidate_reports.exists() else None,
    )


def _ensure_src_on_path(repo_root: Path) -> None:
    """Ensure src directory is on Python path."""
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def get_db_path() -> Path:
    """Get database path from environment or default."""
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


def main() -> None:
    """Main unified dashboard entry point."""
    repo_root = Path(__file__).resolve().parent
    _ensure_src_on_path(repo_root)

    # Page config
    st.set_page_config(
        page_title="FeedOps Dashboard",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Sidebar navigation
    st.sidebar.title("FeedOps Dashboard")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigation",
        options=[
            "📋 Review Queue",
            "📊 Performance Monitoring",
        ],
        index=0,
        help="Switch between content review and performance monitoring",
    )

    st.sidebar.markdown("---")
    st.sidebar.caption("FeedOps Content Optimization System")
    st.sidebar.caption(f"Build: {_APP_BUILD}")

    # Render selected page
    if page == "📋 Review Queue":
        render_review_dashboard(repo_root)
    else:
        render_performance_dashboard()


def render_review_dashboard(repo_root: Path) -> None:
    """Render the content review dashboard."""
    from feedops.quality.review_dashboard import run_dashboard

    baseline, candidate, catalog, baseline_reports, candidate_reports = (
        resolve_dashboard_paths(repo_root)
    )
    st.sidebar.markdown("### Data Paths")
    st.sidebar.caption(f"Baseline exports: `{baseline}`")
    st.sidebar.caption(f"Candidate exports: `{candidate}`")
    if baseline_reports:
        st.sidebar.caption(f"Baseline reports: `{baseline_reports}`")
    if candidate_reports:
        st.sidebar.caption(f"Candidate reports: `{candidate_reports}`")
    run_dashboard(
        baseline_exports_dir=baseline,
        candidate_exports_dir=candidate,
        catalog_path=catalog,
        baseline_reports_dir=baseline_reports,
        candidate_reports_dir=candidate_reports,
    )


def render_performance_dashboard() -> None:
    """Render the performance monitoring dashboard."""
    from datetime import datetime

    import pandas as pd

    from feedops.db import get_connection, init_db

    # Initialize database
    db_path = get_db_path()
    if not db_path.exists():
        st.warning(
            "Database not found. Run `feedops performance baseline` and "
            "`feedops performance fetch` to populate data."
        )
        return

    init_db(db_path)

    st.title("📊 FeedOps Performance Dashboard")
    st.markdown("Monitor the impact of optimized content across platforms.")

    # Additional sidebar filters for performance
    st.sidebar.markdown("### Performance Filters")

    platform = st.sidebar.selectbox(
        "Platform",
        options=["google", "bing", "shopify"],
        index=0,
        help="Select the advertising platform to view",
        key="perf_platform",
    )

    min_days = st.sidebar.slider(
        "Min Days Since Publish",
        min_value=7,
        max_value=60,
        value=14,
        help="Only show SKUs published at least this many days ago",
        key="perf_min_days",
    )

    environment = st.sidebar.selectbox(
        "Environment",
        options=["all", "staging", "production"],
        index=0,
        help="Filter by deployment environment",
        key="perf_environment",
    )

    # Import the performance dashboard functions
    from streamlit_app_performance import (
        load_batch_performance,
        load_category_performance,
        load_performance_data,
        load_summary_stats,
        render_batch_tab,
        render_category_tab,
        render_overall_tab,
    )

    # Main tabs
    tab_overall, tab_category, tab_batch = st.tabs(
        ["📈 Overall", "📁 By Product Type", "📦 By Batch"]
    )

    with tab_overall:
        df = load_performance_data(platform, min_days, environment)
        stats = load_summary_stats(platform, min_days, environment)
        render_overall_tab(df, stats, platform)

    with tab_category:
        render_category_tab(platform, min_days, environment)

    with tab_batch:
        render_batch_tab(platform)


if __name__ == "__main__":
    main()
