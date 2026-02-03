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

from feedops.db import get_connection, init_db, is_supabase_available

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
    if is_supabase_available():
        return _load_performance_data_supabase(platform, min_days, environment)
    else:
        return _load_performance_data_sqlite(platform, min_days, environment)


def _load_performance_data_supabase(
    platform: str,
    min_days: int,
    environment: str,
) -> pd.DataFrame:
    """Load performance data using Supabase table API + pandas merge."""
    from datetime import timezone

    from feedops.db.supabase_client import (
        get_all_performance_baselines,
        get_client,
        get_performance_snapshots,
    )

    client = get_client()

    # 1. Fetch publish_events
    query = (
        client.table("publish_events")
        .select("id, master_sku, platform, environment, published_at, quality_score, product_category")
        .eq("platform", platform)
        .eq("action", "publish")
        .eq("status", "success")
    )
    if environment != "all":
        query = query.eq("environment", environment)

    result = query.order("published_at", desc=True).limit(500).execute()

    if not result.data:
        return pd.DataFrame()

    df_events = pd.DataFrame(result.data).rename(columns={"id": "publish_id"})

    # Filter by min_days in Python (only if min_days > 0)
    if min_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_days)
        df_events["published_at_dt"] = pd.to_datetime(df_events["published_at"], utc=True)
        df_events = df_events[df_events["published_at_dt"] <= cutoff]
        df_events = df_events.drop(columns=["published_at_dt"])

        if df_events.empty:
            return pd.DataFrame()

    # 2. Fetch performance_snapshots
    snapshots = get_performance_snapshots(platform=platform, limit=2000)
    df_snapshots = pd.DataFrame(snapshots) if snapshots else pd.DataFrame()

    # 3. Fetch performance_baselines
    baselines = get_all_performance_baselines(platform=platform)
    df_baselines = pd.DataFrame(baselines) if baselines else pd.DataFrame()

    # 4. Merge events + snapshots on (master_sku, platform)
    if not df_snapshots.empty:
        snapshot_cols = ["master_sku", "platform", "snapshot_date", "impressions",
                         "clicks", "ctr", "conversions", "conversion_value", "cvr", "cost", "roas"]
        available_cols = [c for c in snapshot_cols if c in df_snapshots.columns]
        df = df_events.merge(
            df_snapshots[available_cols],
            on=["master_sku", "platform"],
            how="left"
        )
    else:
        df = df_events.copy()
        for col in ["snapshot_date", "impressions", "clicks", "ctr",
                    "conversions", "conversion_value", "cvr", "cost", "roas"]:
            df[col] = None

    # 5. Merge result + baselines
    if not df_baselines.empty:
        df_baselines = df_baselines.rename(columns={
            "avg_ctr": "baseline_ctr",
            "avg_cvr": "baseline_cvr",
            "avg_roas": "baseline_roas",
            "avg_impressions": "baseline_impressions",
            "avg_conversions": "baseline_conversions",
        })
        df = df.merge(df_baselines, on=["master_sku", "platform"], how="left")
    else:
        for col in ["baseline_ctr", "baseline_cvr", "baseline_roas",
                    "baseline_impressions", "baseline_conversions"]:
            df[col] = None

    return _add_delta_calculations(df)


def _load_performance_data_sqlite(
    platform: str,
    min_days: int,
    environment: str,
) -> pd.DataFrame:
    """Load performance data using SQLite raw SQL."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    # FIXED: JOIN on (master_sku, platform) instead of publish_event_id
    query = """
    SELECT
        p.id as publish_id,
        p.master_sku,
        p.platform,
        p.environment,
        p.published_at,
        p.quality_score,
        p.product_category,
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
    LEFT JOIN performance_snapshots ps
        ON p.master_sku = ps.master_sku AND p.platform = ps.platform
    LEFT JOIN performance_baselines pb
        ON p.master_sku = pb.master_sku AND p.platform = pb.platform
    WHERE p.platform = ?
      AND p.action = 'publish'
      AND p.status = 'success'
    """
    params = [platform]

    # Only filter by min_days if > 0
    if min_days > 0:
        query += " AND julianday('now') - julianday(p.published_at) >= ?"
        params.append(min_days)

    if environment != "all":
        query += " AND p.environment = ?"
        params.append(environment)

    query += " ORDER BY p.published_at DESC"

    try:
        df = pd.read_sql(query, conn, params=params)
        return _add_delta_calculations(df)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def _add_delta_calculations(df: pd.DataFrame) -> pd.DataFrame:
    """Add CTR/CVR/ROAS delta calculations to dataframe."""
    from datetime import timezone

    if df.empty:
        return df

    df["ctr_delta_pct"] = df.apply(
        lambda r: (
            ((r["ctr"] - r["baseline_ctr"]) / r["baseline_ctr"] * 100)
            if r.get("baseline_ctr") and r["baseline_ctr"] > 0
            else None
        ),
        axis=1,
    )
    df["cvr_delta_pct"] = df.apply(
        lambda r: (
            ((r["cvr"] - r["baseline_cvr"]) / r["baseline_cvr"] * 100)
            if r.get("baseline_cvr") and r["baseline_cvr"] > 0
            else None
        ),
        axis=1,
    )
    df["roas_delta_pct"] = df.apply(
        lambda r: (
            ((r["roas"] - r["baseline_roas"]) / r["baseline_roas"] * 100)
            if r.get("baseline_roas") and r["baseline_roas"] > 0
            else None
        ),
        axis=1,
    )
    df["days_since_publish"] = df["published_at"].apply(
        lambda x: (
            (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(str(x).replace("Z", "+00:00"))
            ).days
            if x
            else None
        )
    )

    return df


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
    if is_supabase_available():
        return _load_category_performance_supabase(platform, min_days, environment)
    else:
        return _load_category_performance_sqlite(platform, min_days, environment)


def _load_category_performance_supabase(
    platform: str, min_days: int, environment: str
) -> pd.DataFrame:
    """Load category performance using Supabase + pandas aggregation."""
    from datetime import timezone

    from feedops.db.supabase_client import (
        get_all_performance_baselines,
        get_client,
        get_performance_snapshots,
    )

    client = get_client()

    # 1. Fetch publish_events with category
    query = (
        client.table("publish_events")
        .select("id, master_sku, platform, environment, published_at, product_category")
        .eq("platform", platform)
        .eq("action", "publish")
        .eq("status", "success")
        .not_.is_("product_category", "null")
    )
    if environment != "all":
        query = query.eq("environment", environment)

    result = query.order("published_at", desc=True).limit(500).execute()

    if not result.data:
        return pd.DataFrame()

    df_events = pd.DataFrame(result.data)

    # Filter by min_days (only if > 0)
    if min_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=min_days)
        df_events["published_at_dt"] = pd.to_datetime(df_events["published_at"], utc=True)
        df_events = df_events[df_events["published_at_dt"] <= cutoff]

        if df_events.empty:
            return pd.DataFrame()

    # 2. Fetch snapshots and baselines
    snapshots = get_performance_snapshots(platform=platform, limit=2000)
    df_snapshots = pd.DataFrame(snapshots) if snapshots else pd.DataFrame()

    baselines = get_all_performance_baselines(platform=platform)
    df_baselines = pd.DataFrame(baselines) if baselines else pd.DataFrame()

    # 3. Merge events with snapshots
    if not df_snapshots.empty:
        df = df_events.merge(
            df_snapshots[["master_sku", "platform", "impressions", "clicks",
                         "ctr", "conversions", "conversion_value", "cvr", "roas"]],
            on=["master_sku", "platform"],
            how="left"
        )
    else:
        df = df_events.copy()
        for col in ["impressions", "clicks", "ctr", "conversions",
                    "conversion_value", "cvr", "roas"]:
            df[col] = None

    # 4. Merge with baselines
    if not df_baselines.empty:
        df_baselines = df_baselines.rename(columns={
            "avg_ctr": "baseline_ctr",
            "avg_roas": "baseline_roas",
        })
        df = df.merge(
            df_baselines[["master_sku", "platform", "baseline_ctr", "baseline_roas"]],
            on=["master_sku", "platform"],
            how="left"
        )
    else:
        df["baseline_ctr"] = None
        df["baseline_roas"] = None

    # 5. Group by category
    grouped = df.groupby("product_category").agg({
        "master_sku": "nunique",
        "roas": "mean",
        "ctr": "mean",
        "cvr": "mean",
        "impressions": "sum",
        "conversions": "sum",
        "conversion_value": "sum",
        "baseline_roas": "mean",
        "baseline_ctr": "mean",
    }).reset_index()

    grouped = grouped.rename(columns={
        "master_sku": "sku_count",
        "roas": "avg_roas",
        "ctr": "avg_ctr",
        "cvr": "avg_cvr",
        "impressions": "total_impressions",
        "conversions": "total_conversions",
        "conversion_value": "total_revenue",
        "baseline_roas": "avg_baseline_roas",
        "baseline_ctr": "avg_baseline_ctr",
    })

    return _add_category_deltas(grouped)


def _load_category_performance_sqlite(
    platform: str, min_days: int, environment: str
) -> pd.DataFrame:
    """Load category performance using SQLite raw SQL."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    # FIXED: JOIN on (master_sku, platform) instead of publish_event_id
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
    LEFT JOIN performance_snapshots ps
        ON p.master_sku = ps.master_sku AND p.platform = ps.platform
    LEFT JOIN performance_baselines pb
        ON p.master_sku = pb.master_sku AND p.platform = pb.platform
    WHERE p.platform = ?
      AND p.action = 'publish'
      AND p.status = 'success'
      AND p.product_category IS NOT NULL
    """
    params = [platform]

    # Only filter by min_days if > 0
    if min_days > 0:
        query += " AND julianday('now') - julianday(p.published_at) >= ?"
        params.append(min_days)

    if environment != "all":
        query += " AND p.environment = ?"
        params.append(environment)

    query += " GROUP BY p.product_category ORDER BY total_revenue DESC"

    try:
        df = pd.read_sql(query, conn, params=params)
        return _add_category_deltas(df)
    except Exception as e:
        st.error(f"Error loading category data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def _add_category_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Add ROAS and CTR delta calculations to category dataframe."""
    if df.empty:
        return df

    df["roas_delta_pct"] = df.apply(
        lambda r: (
            (
                (r["avg_roas"] - r["avg_baseline_roas"])
                / r["avg_baseline_roas"]
                * 100
            )
            if r.get("avg_baseline_roas") and r["avg_baseline_roas"] > 0
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
            if r.get("avg_baseline_ctr") and r["avg_baseline_ctr"] > 0
            else None
        ),
        axis=1,
    )

    return df


@st.cache_data(ttl=300)
def load_batch_performance(platform: str) -> pd.DataFrame:
    """Load performance data grouped by batch."""
    if is_supabase_available():
        return _load_batch_performance_supabase(platform)
    else:
        return _load_batch_performance_sqlite(platform)


def _load_batch_performance_supabase(platform: str) -> pd.DataFrame:
    """Load batch performance using Supabase + pandas aggregation."""
    from feedops.db.supabase_client import (
        get_all_batches,
        get_all_performance_baselines,
        get_client,
        get_performance_snapshots,
    )

    # 1. Fetch all batches
    batches = get_all_batches(limit=100)
    if not batches:
        return pd.DataFrame()

    df_batches = pd.DataFrame(batches)
    df_batches = df_batches.rename(columns={
        "name": "batch_label",
        "created_at": "batch_created",
        "executed_at": "batch_published",
        "status": "batch_status",
    })

    client = get_client()

    # 2. Fetch publish_events for platform
    result = (
        client.table("publish_events")
        .select("id, master_sku, platform, batch_id")
        .eq("platform", platform)
        .not_.is_("batch_id", "null")
        .execute()
    )
    df_events = pd.DataFrame(result.data) if result.data else pd.DataFrame()

    if df_events.empty:
        # Return batches with empty metrics
        for col in ["tracked_skus", "avg_roas", "avg_ctr", "avg_cvr",
                    "total_impressions", "total_conversions", "total_revenue",
                    "roas_lift_pct", "ctr_lift_pct"]:
            df_batches[col] = None
        return df_batches

    # 3. Fetch snapshots and baselines
    snapshots = get_performance_snapshots(platform=platform, limit=2000)
    df_snapshots = pd.DataFrame(snapshots) if snapshots else pd.DataFrame()

    baselines = get_all_performance_baselines(platform=platform)
    df_baselines = pd.DataFrame(baselines) if baselines else pd.DataFrame()

    # 4. Merge events with snapshots (using master_sku, platform)
    if not df_snapshots.empty:
        df_events = df_events.merge(
            df_snapshots[["master_sku", "platform", "impressions", "clicks",
                         "ctr", "conversions", "conversion_value", "cvr", "roas"]],
            on=["master_sku", "platform"],
            how="left"
        )
    else:
        for col in ["impressions", "clicks", "ctr", "conversions",
                    "conversion_value", "cvr", "roas"]:
            df_events[col] = None

    # 5. Merge with baselines
    if not df_baselines.empty:
        df_baselines = df_baselines.rename(columns={
            "avg_ctr": "baseline_ctr",
            "avg_roas": "baseline_roas",
        })
        df_events = df_events.merge(
            df_baselines[["master_sku", "platform", "baseline_ctr", "baseline_roas"]],
            on=["master_sku", "platform"],
            how="left"
        )
    else:
        df_events["baseline_ctr"] = None
        df_events["baseline_roas"] = None

    # 6. Aggregate by batch_id
    batch_stats = df_events.groupby("batch_id").agg({
        "master_sku": "nunique",
        "roas": "mean",
        "ctr": "mean",
        "cvr": "mean",
        "impressions": "sum",
        "conversions": "sum",
        "conversion_value": "sum",
        "baseline_roas": "mean",
        "baseline_ctr": "mean",
    }).reset_index()

    batch_stats = batch_stats.rename(columns={
        "master_sku": "tracked_skus",
        "roas": "avg_roas",
        "ctr": "avg_ctr",
        "cvr": "avg_cvr",
        "impressions": "total_impressions",
        "conversions": "total_conversions",
        "conversion_value": "total_revenue",
        "baseline_roas": "avg_baseline_roas",
        "baseline_ctr": "avg_baseline_ctr",
    })

    # 7. Merge batch metadata with stats
    df = df_batches.merge(batch_stats, on="batch_id", how="left")

    return _add_batch_deltas(df)


def _load_batch_performance_sqlite(platform: str) -> pd.DataFrame:
    """Load batch performance using SQLite raw SQL."""
    db_path = get_db_path()
    if not db_path.exists():
        return pd.DataFrame()

    conn = get_connection(db_path)

    # FIXED: JOIN on (master_sku, platform) instead of publish_event_id
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
    LEFT JOIN performance_snapshots ps
        ON pe.master_sku = ps.master_sku AND pe.platform = ps.platform
    LEFT JOIN performance_baselines baseline
        ON pe.master_sku = baseline.master_sku AND pe.platform = baseline.platform
    GROUP BY pb.batch_id
    ORDER BY pb.created_at DESC
    """

    try:
        df = pd.read_sql(query, conn, params=[platform])
        return _add_batch_deltas(df)
    except Exception as e:
        st.error(f"Error loading batch data: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


def _add_batch_deltas(df: pd.DataFrame) -> pd.DataFrame:
    """Add ROAS and CTR lift calculations to batch dataframe."""
    if df.empty:
        return df

    df["roas_lift_pct"] = df.apply(
        lambda r: (
            (
                (r["avg_roas"] - r["avg_baseline_roas"])
                / r["avg_baseline_roas"]
                * 100
            )
            if r.get("avg_baseline_roas") and r["avg_baseline_roas"] > 0
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
            if r.get("avg_baseline_ctr") and r["avg_baseline_ctr"] > 0
            else None
        ),
        axis=1,
    )

    return df


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

    # Show backend status in sidebar
    if is_supabase_available():
        st.sidebar.success("Connected to Supabase")
    else:
        st.sidebar.info("Using local SQLite database")

    # Sidebar filters
    st.sidebar.header("Filters")

    platform = st.sidebar.selectbox(
        "Platform",
        options=["google", "bing", "shopify"],
        index=0,
        help="Select the advertising platform to view",
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
        df = load_performance_data(platform, 0, environment)
        stats = load_summary_stats(platform, 0, environment)
        render_overall_tab(df, stats, platform)

    with tab_category:
        render_category_tab(platform, 0, environment)

    with tab_batch:
        render_batch_tab(platform)


if __name__ == "__main__":
    main()
