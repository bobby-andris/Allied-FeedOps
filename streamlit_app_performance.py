"""FeedOps Performance Dashboard.

Streamlit dashboard for monitoring and visualizing performance metrics
of FeedOps-optimized content across Google, Bing, and Shopify platforms.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src is in path
src_path = Path(__file__).parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from feedops.db import get_connection, init_db

# Page config
st.set_page_config(
    page_title="FeedOps Performance Dashboard",
    page_icon="📊",
    layout="wide",
)


def get_db_path() -> Path:
    """Get database path from environment or default."""
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


@st.cache_data(ttl=300)
def load_performance_data(
    platform: str,
    min_days: int,
    environment: str,
) -> pd.DataFrame:
    """Load performance data from database."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    query = """
    SELECT
        p.id as publish_id,
        p.master_sku,
        p.platform,
        p.environment,
        p.published_at,
        p.quality_score,
        ps.snapshot_date,
        ps.impressions,
        ps.clicks,
        ps.ctr,
        ps.conversions,
        ps.conversion_value,
        ps.cvr,
        ps.cost,
        ps.roas,
        pb.avg_ctr as baseline_ctr,
        pb.avg_cvr as baseline_cvr,
        pb.avg_roas as baseline_roas,
        pb.avg_impressions as baseline_impressions,
        pb.avg_conversions as baseline_conversions
    FROM publish_events p
    LEFT JOIN performance_snapshots ps ON p.id = ps.publish_event_id
    LEFT JOIN performance_baselines pb ON p.master_sku = pb.master_sku AND p.platform = pb.platform
    WHERE p.platform = ?
      AND p.action = 'publish'
      AND p.status = 'success'
      AND julianday('now') - julianday(p.published_at) >= ?
    """
    params = [platform, min_days]

    if environment != "all":
        query += " AND p.environment = ?"
        params.append(environment)

    query += " ORDER BY p.published_at DESC"

    try:
        df = pd.read_sql(query, conn, params=params)
        conn.close()

        # Calculate deltas
        if not df.empty:
            df["ctr_delta_pct"] = df.apply(
                lambda r: (
                    ((r["ctr"] - r["baseline_ctr"]) / r["baseline_ctr"] * 100)
                    if r["baseline_ctr"] and r["baseline_ctr"] > 0
                    else None
                ),
                axis=1,
            )
            df["cvr_delta_pct"] = df.apply(
                lambda r: (
                    ((r["cvr"] - r["baseline_cvr"]) / r["baseline_cvr"] * 100)
                    if r["baseline_cvr"] and r["baseline_cvr"] > 0
                    else None
                ),
                axis=1,
            )
            df["roas_delta_pct"] = df.apply(
                lambda r: (
                    ((r["roas"] - r["baseline_roas"]) / r["baseline_roas"] * 100)
                    if r["baseline_roas"] and r["baseline_roas"] > 0
                    else None
                ),
                axis=1,
            )
            df["days_since_publish"] = df["published_at"].apply(
                lambda x: (
                    (
                        datetime.now()
                        - datetime.fromisoformat(x.replace("Z", "+00:00"))
                    ).days
                    if x
                    else None
                )
            )

        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        conn.close()
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_summary_stats(platform: str, min_days: int, environment: str) -> dict:
    """Load summary statistics."""
    df = load_performance_data(platform, min_days, environment)

    if df.empty:
        return {
            "total_skus": 0,
            "avg_ctr_lift": None,
            "avg_cvr_lift": None,
            "avg_roas_lift": None,
            "positive_roas_pct": None,
        }

    # Deduplicate by SKU (take latest snapshot)
    df_unique = df.drop_duplicates(subset=["master_sku"], keep="first")

    total_skus = len(df_unique)

    # Calculate averages (only for rows with baseline data)
    ctr_lifts = df_unique["ctr_delta_pct"].dropna()
    cvr_lifts = df_unique["cvr_delta_pct"].dropna()
    roas_lifts = df_unique["roas_delta_pct"].dropna()

    avg_ctr_lift = ctr_lifts.mean() if len(ctr_lifts) > 0 else None
    avg_cvr_lift = cvr_lifts.mean() if len(cvr_lifts) > 0 else None
    avg_roas_lift = roas_lifts.mean() if len(roas_lifts) > 0 else None

    positive_roas = len(roas_lifts[roas_lifts > 0])
    positive_roas_pct = (
        positive_roas / len(roas_lifts) * 100 if len(roas_lifts) > 0 else None
    )

    return {
        "total_skus": total_skus,
        "avg_ctr_lift": avg_ctr_lift,
        "avg_cvr_lift": avg_cvr_lift,
        "avg_roas_lift": avg_roas_lift,
        "positive_roas_pct": positive_roas_pct,
    }


@st.cache_data(ttl=300)
def load_category_performance(
    platform: str, min_days: int, environment: str
) -> pd.DataFrame:
    """Load performance data grouped by product category."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    query = """
    SELECT
        p.product_category,
        COUNT(DISTINCT p.master_sku) as sku_count,
        AVG(ps.roas) as avg_roas,
        AVG(ps.ctr) as avg_ctr,
        AVG(ps.cvr) as avg_cvr,
        SUM(ps.impressions) as total_impressions,
        SUM(ps.conversions) as total_conversions,
        SUM(ps.conversion_value) as total_revenue,
        AVG(pb.avg_roas) as avg_baseline_roas,
        AVG(pb.avg_ctr) as avg_baseline_ctr
    FROM publish_events p
    LEFT JOIN performance_snapshots ps ON p.id = ps.publish_event_id
    LEFT JOIN performance_baselines pb ON p.master_sku = pb.master_sku AND p.platform = pb.platform
    WHERE p.platform = ?
      AND p.action = 'publish'
      AND p.status = 'success'
      AND p.product_category IS NOT NULL
      AND julianday('now') - julianday(p.published_at) >= ?
    """
    params = [platform, min_days]

    if environment != "all":
        query += " AND p.environment = ?"
        params.append(environment)

    query += " GROUP BY p.product_category ORDER BY total_revenue DESC"

    try:
        df = pd.read_sql(query, conn, params=params)
        conn.close()

        if not df.empty:
            df["roas_delta_pct"] = df.apply(
                lambda r: (
                    (
                        (r["avg_roas"] - r["avg_baseline_roas"])
                        / r["avg_baseline_roas"]
                        * 100
                    )
                    if r["avg_baseline_roas"] and r["avg_baseline_roas"] > 0
                    else None
                ),
                axis=1,
            )
            df["ctr_delta_pct"] = df.apply(
                lambda r: (
                    (
                        (r["avg_ctr"] - r["avg_baseline_ctr"])
                        / r["avg_baseline_ctr"]
                        * 100
                    )
                    if r["avg_baseline_ctr"] and r["avg_baseline_ctr"] > 0
                    else None
                ),
                axis=1,
            )

        return df
    except Exception as e:
        st.error(f"Error loading category data: {e}")
        conn.close()
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_batch_performance(platform: str) -> pd.DataFrame:
    """Load performance data grouped by batch."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    query = """
    SELECT
        pb.batch_id,
        pb.name as batch_label,
        pb.created_at as batch_created,
        pb.executed_at as batch_published,
        pb.status as batch_status,
        pb.sku_count,
        pb.success_count,
        pb.failed_count,
        COUNT(DISTINCT pe.master_sku) as tracked_skus,
        AVG(ps.roas) as avg_roas,
        AVG(ps.ctr) as avg_ctr,
        AVG(ps.cvr) as avg_cvr,
        SUM(ps.impressions) as total_impressions,
        SUM(ps.conversions) as total_conversions,
        SUM(ps.conversion_value) as total_revenue,
        AVG(baseline.avg_roas) as avg_baseline_roas,
        AVG(baseline.avg_ctr) as avg_baseline_ctr
    FROM publish_batches pb
    LEFT JOIN publish_events pe ON pb.batch_id = pe.batch_id AND pe.platform = ?
    LEFT JOIN performance_snapshots ps ON pe.id = ps.publish_event_id
    LEFT JOIN performance_baselines baseline ON pe.master_sku = baseline.master_sku AND pe.platform = baseline.platform
    GROUP BY pb.batch_id
    ORDER BY pb.created_at DESC
    """

    try:
        df = pd.read_sql(query, conn, params=[platform])
        conn.close()

        if not df.empty:
            df["roas_lift_pct"] = df.apply(
                lambda r: (
                    (
                        (r["avg_roas"] - r["avg_baseline_roas"])
                        / r["avg_baseline_roas"]
                        * 100
                    )
                    if r["avg_baseline_roas"] and r["avg_baseline_roas"] > 0
                    else None
                ),
                axis=1,
            )
            df["ctr_lift_pct"] = df.apply(
                lambda r: (
                    (
                        (r["avg_ctr"] - r["avg_baseline_ctr"])
                        / r["avg_baseline_ctr"]
                        * 100
                    )
                    if r["avg_baseline_ctr"] and r["avg_baseline_ctr"] > 0
                    else None
                ),
                axis=1,
            )

        return df
    except Exception as e:
        st.error(f"Error loading batch data: {e}")
        conn.close()
        return pd.DataFrame()


def render_overall_tab(df: pd.DataFrame, stats: dict, platform: str):
    """Render the overall performance view."""
    # Summary metrics row
    st.header("Summary Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Total SKUs", stats["total_skus"])

    with col2:
        if stats["avg_ctr_lift"] is not None:
            st.metric(
                "Avg CTR Lift",
                f"{stats['avg_ctr_lift']:.1f}%",
                delta=f"{stats['avg_ctr_lift']:.1f}%",
            )
        else:
            st.metric("Avg CTR Lift", "N/A")

    with col3:
        if stats["avg_cvr_lift"] is not None:
            st.metric(
                "Avg CVR Lift",
                f"{stats['avg_cvr_lift']:.1f}%",
                delta=f"{stats['avg_cvr_lift']:.1f}%",
            )
        else:
            st.metric("Avg CVR Lift", "N/A")

    with col4:
        if stats["avg_roas_lift"] is not None:
            st.metric(
                "Avg ROAS Lift",
                f"{stats['avg_roas_lift']:.1f}%",
                delta=f"{stats['avg_roas_lift']:.1f}%",
            )
        else:
            st.metric("Avg ROAS Lift", "N/A")

    with col5:
        if stats["positive_roas_pct"] is not None:
            st.metric("% Positive ROAS", f"{stats['positive_roas_pct']:.0f}%")
        else:
            st.metric("% Positive ROAS", "N/A")

    if df.empty:
        st.info(
            "No performance data available yet. Run the following commands to populate:\n\n"
            "1. `feedops performance baseline --sku <SKU> --platform google --start <DATE> --end <DATE>`\n"
            "2. `feedops performance fetch --sku <SKU> --platform google --start <DATE> --end <DATE>`"
        )
        return

    # Performance table
    st.header("SKU Performance")

    # Prepare display dataframe
    df_display = df.drop_duplicates(subset=["master_sku"], keep="first").copy()

    # Select and rename columns for display
    display_cols = [
        "master_sku",
        "environment",
        "days_since_publish",
        "ctr_delta_pct",
        "cvr_delta_pct",
        "roas_delta_pct",
        "impressions",
        "conversions",
        "conversion_value",
    ]

    df_display = df_display[[c for c in display_cols if c in df_display.columns]]

    # Rename for display
    df_display = df_display.rename(
        columns={
            "master_sku": "SKU",
            "environment": "Env",
            "days_since_publish": "Days",
            "ctr_delta_pct": "CTR Δ%",
            "cvr_delta_pct": "CVR Δ%",
            "roas_delta_pct": "ROAS Δ%",
            "impressions": "Impressions",
            "conversions": "Conversions",
            "conversion_value": "Revenue",
        }
    )

    # Style the dataframe
    def color_delta(val):
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        return ""

    styled_df = df_display.style.applymap(
        color_delta, subset=["CTR Δ%", "CVR Δ%", "ROAS Δ%"]
    ).format(
        {
            "CTR Δ%": "{:.1f}%",
            "CVR Δ%": "{:.1f}%",
            "ROAS Δ%": "{:.1f}%",
            "Revenue": "${:,.2f}",
            "Impressions": "{:,.0f}",
            "Conversions": "{:,.0f}",
        },
        na_rep="N/A",
    )

    st.dataframe(styled_df, width="stretch", hide_index=True)

    # Charts
    st.header("Performance Trends")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("ROAS Change by SKU")
        if "roas_delta_pct" in df_display.columns:
            chart_data = df_display[["SKU", "ROAS Δ%"]].dropna()
            if not chart_data.empty:
                chart_data = chart_data.set_index("SKU")
                st.bar_chart(chart_data, color="#4CAF50")
            else:
                st.info("No ROAS data available")

    with col2:
        st.subheader("CTR Change by SKU")
        if "ctr_delta_pct" in df_display.columns:
            chart_data = df_display[["SKU", "CTR Δ%"]].dropna()
            if not chart_data.empty:
                chart_data = chart_data.set_index("SKU")
                st.bar_chart(chart_data, color="#2196F3")
            else:
                st.info("No CTR data available")

    # Recommendations section
    st.header("Recommendations")

    # Identify underperformers
    underperformers = (
        df_display[df_display["ROAS Δ%"] < -15]
        if "ROAS Δ%" in df_display.columns
        else pd.DataFrame()
    )
    winners = (
        df_display[df_display["ROAS Δ%"] > 10]
        if "ROAS Δ%" in df_display.columns
        else pd.DataFrame()
    )
    monitors = (
        df_display[(df_display["ROAS Δ%"] >= -15) & (df_display["ROAS Δ%"] <= 10)]
        if "ROAS Δ%" in df_display.columns
        else pd.DataFrame()
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### ✅ Winners")
        st.markdown(f"**{len(winners)} SKUs** with ROAS > +10%")
        if not winners.empty:
            for _, row in winners.iterrows():
                st.markdown(f"- {row['SKU']}: **{row['ROAS Δ%']:+.1f}%**")

    with col2:
        st.markdown("### 👀 Monitor")
        st.markdown(f"**{len(monitors)} SKUs** with ROAS between -15% and +10%")
        if not monitors.empty and len(monitors) <= 10:
            for _, row in monitors.iterrows():
                delta = row["ROAS Δ%"]
                if pd.notna(delta):
                    st.markdown(f"- {row['SKU']}: {delta:+.1f}%")

    with col3:
        st.markdown("### ⚠️ Consider Rollback")
        st.markdown(f"**{len(underperformers)} SKUs** with ROAS < -15%")
        if not underperformers.empty:
            for _, row in underperformers.iterrows():
                st.markdown(f"- {row['SKU']}: **{row['ROAS Δ%']:+.1f}%**")

    # Footer
    st.markdown("---")
    st.markdown(
        "*Data refreshes every 5 minutes. Run `feedops performance fetch` to update metrics.*"
    )


def render_category_tab(platform: str, min_days: int, environment: str):
    """Render the 'By Product Type' breakdown view."""
    st.header("Performance by Product Type")

    df = load_category_performance(platform, min_days, environment)

    if df.empty:
        st.info(
            "No category performance data available. Make sure SKUs have "
            "`product_category` set when publishing."
        )
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Categories Tracked", len(df))
    with col2:
        total_skus = df["sku_count"].sum()
        st.metric("Total SKUs", int(total_skus))
    with col3:
        total_revenue = df["total_revenue"].sum()
        st.metric("Total Revenue", f"${total_revenue:,.2f}")

    st.divider()

    # Category performance table
    st.subheader("Category Performance")

    display_df = df.copy()
    display_df = display_df.rename(
        columns={
            "product_category": "Category",
            "sku_count": "SKUs",
            "avg_roas": "Avg ROAS",
            "avg_ctr": "Avg CTR",
            "total_impressions": "Impressions",
            "total_conversions": "Conversions",
            "total_revenue": "Revenue",
            "roas_delta_pct": "ROAS Δ%",
            "ctr_delta_pct": "CTR Δ%",
        }
    )

    cols_to_show = [
        "Category",
        "SKUs",
        "Impressions",
        "Conversions",
        "Revenue",
        "Avg ROAS",
        "ROAS Δ%",
        "Avg CTR",
        "CTR Δ%",
    ]
    display_df = display_df[[c for c in cols_to_show if c in display_df.columns]]

    def color_delta(val):
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        return ""

    styled_df = display_df.style.applymap(
        color_delta,
        subset=["ROAS Δ%", "CTR Δ%"] if "ROAS Δ%" in display_df.columns else [],
    ).format(
        {
            "ROAS Δ%": "{:.1f}%",
            "CTR Δ%": "{:.1f}%",
            "Revenue": "${:,.2f}",
            "Impressions": "{:,.0f}",
            "Conversions": "{:,.0f}",
            "Avg ROAS": "{:.2f}",
            "Avg CTR": "{:.4f}",
        },
        na_rep="N/A",
    )

    st.dataframe(styled_df, width="stretch", hide_index=True)

    # Charts
    st.subheader("Category Charts")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Revenue by Category**")
        if "Revenue" in display_df.columns and "Category" in display_df.columns:
            chart_data = display_df[["Category", "Revenue"]].dropna()
            if not chart_data.empty:
                chart_data = chart_data.set_index("Category")
                st.bar_chart(chart_data, color="#4CAF50")

    with col2:
        st.markdown("**ROAS Lift by Category**")
        if "ROAS Δ%" in display_df.columns and "Category" in display_df.columns:
            chart_data = display_df[["Category", "ROAS Δ%"]].dropna()
            if not chart_data.empty:
                chart_data = chart_data.set_index("Category")
                st.bar_chart(chart_data, color="#2196F3")


def render_batch_tab(platform: str):
    """Render the 'By Batch' breakdown view."""
    st.header("Performance by Batch")

    df = load_batch_performance(platform)

    if df.empty:
        st.info(
            "No batch performance data available. Create batches in the "
            "Review Dashboard and publish them to see performance tracking."
        )
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Batches", len(df))
    with col2:
        total_skus = df["sku_count"].sum()
        st.metric("Total SKUs in Batches", int(total_skus))
    with col3:
        published = len(df[df["batch_status"] == "published"])
        st.metric("Published Batches", published)

    st.divider()

    # Batch performance table
    st.subheader("Batch Performance")

    display_df = df.copy()
    display_df = display_df.rename(
        columns={
            "batch_id": "Batch ID",
            "batch_label": "Label",
            "batch_status": "Status",
            "sku_count": "SKUs",
            "tracked_skus": "Tracked",
            "avg_roas": "Avg ROAS",
            "avg_ctr": "Avg CTR",
            "total_impressions": "Impressions",
            "total_conversions": "Conversions",
            "total_revenue": "Revenue",
            "roas_lift_pct": "ROAS Δ%",
            "ctr_lift_pct": "CTR Δ%",
            "batch_created": "Created",
        }
    )

    cols_to_show = [
        "Batch ID",
        "Label",
        "Status",
        "SKUs",
        "Tracked",
        "Revenue",
        "ROAS Δ%",
        "CTR Δ%",
        "Created",
    ]
    display_df = display_df[[c for c in cols_to_show if c in display_df.columns]]

    # Format created date
    if "Created" in display_df.columns:
        display_df["Created"] = display_df["Created"].apply(
            lambda x: x[:10] if x else "N/A"
        )

    def color_delta(val):
        if pd.isna(val):
            return ""
        if val > 0:
            return "color: green"
        elif val < 0:
            return "color: red"
        return ""

    styled_df = display_df.style.applymap(
        color_delta,
        subset=["ROAS Δ%", "CTR Δ%"] if "ROAS Δ%" in display_df.columns else [],
    ).format(
        {
            "ROAS Δ%": "{:.1f}%",
            "CTR Δ%": "{:.1f}%",
            "Revenue": "${:,.2f}",
        },
        na_rep="N/A",
    )

    st.dataframe(styled_df, width="stretch", hide_index=True)

    # Charts
    st.subheader("Batch Performance Over Time")

    if "ROAS Δ%" in display_df.columns and "Batch ID" in display_df.columns:
        chart_data = display_df[["Batch ID", "ROAS Δ%"]].dropna()
        if not chart_data.empty:
            chart_data = chart_data.set_index("Batch ID")
            st.bar_chart(chart_data, color="#9C27B0")
        else:
            st.info("No ROAS lift data available yet")


def main():
    """Main dashboard function."""
    st.title("📊 FeedOps Performance Dashboard")
    st.markdown("Monitor the impact of optimized content across platforms.")

    # Initialize database if needed
    db_path = get_db_path()
    if not db_path.exists():
        st.warning(
            "Database not found. Run `feedops performance baseline` and "
            "`feedops performance fetch` to populate data."
        )
        return

    init_db(db_path)

    # Sidebar filters
    st.sidebar.header("Filters")

    platform = st.sidebar.selectbox(
        "Platform",
        options=["google", "bing", "shopify"],
        index=0,
        help="Select the advertising platform to view",
    )

    min_days = st.sidebar.slider(
        "Min Days Since Publish",
        min_value=7,
        max_value=60,
        value=14,
        help="Only show SKUs published at least this many days ago",
    )

    environment = st.sidebar.selectbox(
        "Environment",
        options=["all", "staging", "production"],
        index=0,
        help="Filter by deployment environment",
    )

    # Main tabs
    tab_overall, tab_category, tab_batch = st.tabs(
        ["📈 Overall", "📁 By Product Type", "📦 By Batch"]
    )

    with tab_overall:
        # Load data for overall view
        df = load_performance_data(platform, min_days, environment)
        stats = load_summary_stats(platform, min_days, environment)
        render_overall_tab(df, stats, platform)

    with tab_category:
        render_category_tab(platform, min_days, environment)

    with tab_batch:
        render_batch_tab(platform)


if __name__ == "__main__":
    main()
