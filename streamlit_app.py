"""FeedOps Unified Dashboard.

Provides unified navigation between the Review Dashboard (for content approval)
and the Performance Dashboard (for monitoring published content).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st


def resolve_dashboard_paths(
    repo_root: Path | str,
) -> tuple[Path, Path, Path | None, Path | None, Path | None]:
    """Resolve paths for the review dashboard."""
    repo_root = Path(repo_root)
    data_root = repo_root / "dashboard_data"
    baseline_exports = data_root / "lifestyle-eval"
    candidate_exports = data_root / "lifestyle-eval-candidate"
    if not candidate_exports.exists():
        candidate_exports = baseline_exports

    catalog_path = data_root / "catalog.csv"
    baseline_reports = baseline_exports / "reports"
    candidate_reports = candidate_exports / "reports"

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
