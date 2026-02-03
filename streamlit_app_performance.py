"""FeedOps Performance Dashboard.

Streamlit dashboard for monitoring and visualizing performance metrics
of FeedOps-optimized content across Google, Bing, and Shopify platforms.

Redesigned to clearly answer: "Are the optimizations working?" by showing
before/after comparisons with trend visualization.
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

# Verdict thresholds for SKU classification
WINNING_THRESHOLD = 10  # ROAS lift > 10% = winning
NEEDS_ATTENTION_THRESHOLD = -15  # ROAS lift < -15% = needs attention
MIN_DAYS_FOR_VERDICT = 7  # Minimum days since publish for verdict

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
                    "baseline_impressions", "baseline_conversions",
                    "baseline_start_date", "baseline_end_date"]:
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
def load_sku_time_series(master_sku: str, platform: str) -> pd.DataFrame:
    """Load time series snapshots for a specific SKU.

    Returns a DataFrame with daily performance data sorted by date (oldest first).
    """
    if is_supabase_available():
        from feedops.db.supabase_client import get_performance_time_series
        snapshots = get_performance_time_series(master_sku=master_sku, platform=platform)
    else:
        from feedops.db.schema import get_performance_snapshots
        db_path = get_db_path()
        snapshots = get_performance_snapshots(db_path, master_sku=master_sku, platform=platform)

    if not snapshots:
        return pd.DataFrame()

    df = pd.DataFrame(snapshots)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df = df.sort_values("snapshot_date")
    return df


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


def _classify_sku_verdict(
    roas_delta: float | None,
    days_since_publish: int | None,
    has_baseline: bool,
    has_current: bool,
) -> tuple[str, str, str]:
    """Classify a SKU's performance verdict.

    Returns:
        Tuple of (verdict, emoji, css_class):
        - verdict: "WINNING", "MONITORING", "NEEDS ATTENTION", "INSUFFICIENT DATA"
        - emoji: Emoji for display
        - css_class: CSS class for styling
    """
    # Check data sufficiency
    if not has_baseline or not has_current:
        return "INSUFFICIENT DATA", "⚪", "neutral"

    if days_since_publish is None or days_since_publish < MIN_DAYS_FOR_VERDICT:
        return "MONITORING", "🟡", "warning"

    if roas_delta is None:
        return "INSUFFICIENT DATA", "⚪", "neutral"

    if roas_delta > WINNING_THRESHOLD:
        return "WINNING", "🟢", "success"
    elif roas_delta < NEEDS_ATTENTION_THRESHOLD:
        return "NEEDS ATTENTION", "🔴", "error"
    else:
        return "MONITORING", "🟡", "warning"


def _format_date(date_str: str | None) -> str:
    """Format date string for display."""
    if not date_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return str(date_str)[:10] if date_str else "N/A"


def _format_metric_delta(current: float | None, baseline: float | None, is_pct: bool = False) -> tuple[str, str, str]:
    """Format a metric with delta for display.

    Returns:
        Tuple of (current_str, delta_str, delta_class):
        - current_str: Formatted current value
        - delta_str: Formatted delta (e.g., "+15.2%")
        - delta_class: CSS class for coloring ("positive", "negative", "neutral")
    """
    if current is None:
        return "N/A", "", "neutral"

    if is_pct:
        current_str = f"{current:.2%}" if current < 1 else f"{current:.1f}%"
    else:
        current_str = f"{current:,.2f}" if isinstance(current, float) else f"{current:,}"

    if baseline is None or baseline == 0:
        return current_str, "No baseline", "neutral"

    delta_pct = ((current - baseline) / baseline) * 100
    delta_str = f"{delta_pct:+.1f}%"

    if delta_pct > 0:
        delta_class = "positive"
    elif delta_pct < 0:
        delta_class = "negative"
    else:
        delta_class = "neutral"

    return current_str, delta_str, delta_class


def render_overall_tab(df: pd.DataFrame, stats: dict, platform: str):
    """Render the overall performance view with before/after comparison."""

    # Handle empty state
    if df.empty:
        st.info(
            "No performance data available yet. Run the following commands to populate:\n\n"
            "1. `feedops performance baseline --sku <SKU> --platform google --start <DATE> --end <DATE>`\n"
            "2. `feedops performance fetch --sku <SKU> --platform google --start <DATE> --end <DATE>`"
        )
        return

    # Deduplicate by SKU (take latest snapshot)
    df_unique = df.drop_duplicates(subset=["master_sku"], keep="first").copy()

    # Classify each SKU
    verdicts = []
    for _, row in df_unique.iterrows():
        has_baseline = pd.notna(row.get("baseline_roas")) or pd.notna(row.get("baseline_ctr"))
        has_current = pd.notna(row.get("roas")) or pd.notna(row.get("ctr"))
        verdict, emoji, css_class = _classify_sku_verdict(
            row.get("roas_delta_pct"),
            row.get("days_since_publish"),
            has_baseline,
            has_current,
        )
        verdicts.append({
            "verdict": verdict,
            "emoji": emoji,
            "css_class": css_class,
        })

    df_unique["verdict"] = [v["verdict"] for v in verdicts]
    df_unique["verdict_emoji"] = [v["emoji"] for v in verdicts]

    # Count verdicts
    winning_count = len(df_unique[df_unique["verdict"] == "WINNING"])
    monitoring_count = len(df_unique[df_unique["verdict"] == "MONITORING"])
    needs_attention_count = len(df_unique[df_unique["verdict"] == "NEEDS ATTENTION"])
    insufficient_count = len(df_unique[df_unique["verdict"] == "INSUFFICIENT DATA"])

    # === SUMMARY BANNER ===
    st.markdown("### Summary")
    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Published SKUs", stats["total_skus"])
    with summary_cols[1]:
        st.metric("🟢 Winning", winning_count, help="ROAS lift > +10%")
    with summary_cols[2]:
        st.metric("🟡 Monitoring", monitoring_count, help="ROAS between -15% and +10%, or < 7 days since publish")
    with summary_cols[3]:
        st.metric("🔴 Needs Attention", needs_attention_count, help="ROAS lift < -15%")

    st.divider()

    # === SKU DETAIL CARDS ===
    st.markdown("### SKU Performance Details")
    st.caption("Comparing baseline (pre-optimization) vs current (post-optimization) metrics")

    # Sort by verdict priority: Needs Attention first, then Monitoring, then Winning
    verdict_order = {"NEEDS ATTENTION": 0, "MONITORING": 1, "INSUFFICIENT DATA": 2, "WINNING": 3}
    df_sorted = df_unique.copy()
    df_sorted["verdict_order"] = df_sorted["verdict"].map(verdict_order)
    df_sorted = df_sorted.sort_values("verdict_order")

    for _, row in df_sorted.iterrows():
        sku = row["master_sku"]
        verdict = row["verdict"]
        emoji = row["verdict_emoji"]
        published_at = row.get("published_at")
        days_since = row.get("days_since_publish")
        category = row.get("product_category", "Unknown")

        # Determine container styling based on verdict
        if verdict == "NEEDS ATTENTION":
            border_color = "#ff4b4b"
        elif verdict == "WINNING":
            border_color = "#21c354"
        else:
            border_color = "#faca2b"

        # Create expandable card for each SKU
        with st.expander(f"{emoji} **SKU {sku}** — {verdict}", expanded=(verdict == "NEEDS ATTENTION")):
            # Header row with publish info
            info_cols = st.columns([2, 2, 2])
            with info_cols[0]:
                st.markdown(f"**Published:** {_format_date(published_at)}")
            with info_cols[1]:
                days_str = f"{days_since} days ago" if days_since is not None else "N/A"
                st.markdown(f"**Days Since:** {days_str}")
            with info_cols[2]:
                st.markdown(f"**Category:** {category or 'N/A'}")

            st.markdown("---")

            # === METRICS COMPARISON TABLE ===
            metric_cols = st.columns([2, 2, 2, 2])

            # Headers
            with metric_cols[0]:
                st.markdown("**Metric**")
            with metric_cols[1]:
                # Get baseline period dates if available
                baseline_start = row.get("baseline_start_date")
                baseline_end = row.get("baseline_end_date")
                if baseline_start and baseline_end:
                    st.markdown(f"**Baseline** ({baseline_start[:7]})")
                else:
                    st.markdown("**Baseline (Pre-Opt)**")
            with metric_cols[2]:
                st.markdown("**Current**")
            with metric_cols[3]:
                st.markdown("**Change**")

            # CTR Row
            ctr_cols = st.columns([2, 2, 2, 2])
            with ctr_cols[0]:
                st.markdown("CTR")
            with ctr_cols[1]:
                baseline_ctr = row.get("baseline_ctr")
                st.markdown(f"{baseline_ctr:.2%}" if pd.notna(baseline_ctr) else "N/A")
            with ctr_cols[2]:
                current_ctr = row.get("ctr")
                st.markdown(f"{current_ctr:.2%}" if pd.notna(current_ctr) else "N/A")
            with ctr_cols[3]:
                ctr_delta = row.get("ctr_delta_pct")
                if pd.notna(ctr_delta):
                    color = "green" if ctr_delta > 0 else "red" if ctr_delta < 0 else "gray"
                    st.markdown(f":{color}[{ctr_delta:+.1f}%]")
                else:
                    st.markdown("N/A")

            # Impressions Row
            imp_cols = st.columns([2, 2, 2, 2])
            with imp_cols[0]:
                st.markdown("Impressions")
            with imp_cols[1]:
                baseline_imp = row.get("baseline_impressions")
                st.markdown(f"{baseline_imp:,.0f}/day" if pd.notna(baseline_imp) else "N/A")
            with imp_cols[2]:
                current_imp = row.get("impressions")
                st.markdown(f"{current_imp:,.0f}" if pd.notna(current_imp) else "N/A")
            with imp_cols[3]:
                if pd.notna(baseline_imp) and pd.notna(current_imp) and baseline_imp > 0:
                    imp_delta = ((current_imp - baseline_imp) / baseline_imp) * 100
                    color = "green" if imp_delta > 0 else "red" if imp_delta < 0 else "gray"
                    st.markdown(f":{color}[{imp_delta:+.1f}%]")
                else:
                    st.markdown("N/A")

            # Conversions Row
            conv_cols = st.columns([2, 2, 2, 2])
            with conv_cols[0]:
                st.markdown("Conversions")
            with conv_cols[1]:
                baseline_conv = row.get("baseline_conversions")
                st.markdown(f"{baseline_conv:.1f}/day" if pd.notna(baseline_conv) else "N/A")
            with conv_cols[2]:
                current_conv = row.get("conversions")
                st.markdown(f"{current_conv:,.0f}" if pd.notna(current_conv) else "N/A")
            with conv_cols[3]:
                cvr_delta = row.get("cvr_delta_pct")
                if pd.notna(cvr_delta):
                    color = "green" if cvr_delta > 0 else "red" if cvr_delta < 0 else "gray"
                    st.markdown(f":{color}[{cvr_delta:+.1f}%]")
                else:
                    st.markdown("N/A")

            # ROAS Row
            roas_cols = st.columns([2, 2, 2, 2])
            with roas_cols[0]:
                st.markdown("**ROAS**")
            with roas_cols[1]:
                baseline_roas = row.get("baseline_roas")
                st.markdown(f"**{baseline_roas:.2f}**" if pd.notna(baseline_roas) else "N/A")
            with roas_cols[2]:
                current_roas = row.get("roas")
                st.markdown(f"**{current_roas:.2f}**" if pd.notna(current_roas) else "N/A")
            with roas_cols[3]:
                roas_delta = row.get("roas_delta_pct")
                if pd.notna(roas_delta):
                    color = "green" if roas_delta > 0 else "red" if roas_delta < 0 else "gray"
                    st.markdown(f":**{color}[{roas_delta:+.1f}%]**")
                else:
                    st.markdown("N/A")

            # Revenue Row
            rev_cols = st.columns([2, 2, 2, 2])
            with rev_cols[0]:
                st.markdown("Revenue")
            with rev_cols[1]:
                baseline_conv_value = row.get("baseline_conversions")
                # Note: we don't have baseline conversion value, just show N/A
                st.markdown("N/A (daily avg)")
            with rev_cols[2]:
                current_rev = row.get("conversion_value")
                st.markdown(f"${current_rev:,.2f}" if pd.notna(current_rev) else "N/A")
            with rev_cols[3]:
                st.markdown("—")

            # === TIME SERIES CHART ===
            st.markdown("---")
            st.markdown("**Performance Trend**")

            # Load time series data for this SKU
            ts_data = load_sku_time_series(sku, platform)

            if not ts_data.empty and len(ts_data) > 1:
                # Create chart with CTR over time
                chart_cols = st.columns(2)

                with chart_cols[0]:
                    st.markdown("*CTR Over Time*")
                    ctr_chart = ts_data[["snapshot_date", "ctr"]].copy()
                    ctr_chart = ctr_chart.set_index("snapshot_date")
                    ctr_chart = ctr_chart.rename(columns={"ctr": "CTR"})

                    # Add baseline reference line if available
                    baseline_ctr = row.get("baseline_ctr")
                    if pd.notna(baseline_ctr):
                        ctr_chart["Baseline"] = baseline_ctr

                    st.line_chart(ctr_chart, color=["#2196F3", "#ff9800"] if "Baseline" in ctr_chart.columns else "#2196F3")

                with chart_cols[1]:
                    st.markdown("*Impressions Over Time*")
                    imp_chart = ts_data[["snapshot_date", "impressions"]].copy()
                    imp_chart = imp_chart.set_index("snapshot_date")
                    imp_chart = imp_chart.rename(columns={"impressions": "Impressions"})

                    # Add baseline reference if available
                    baseline_imp = row.get("baseline_impressions")
                    if pd.notna(baseline_imp):
                        imp_chart["Baseline (daily avg)"] = baseline_imp

                    st.line_chart(imp_chart, color=["#4CAF50", "#ff9800"] if "Baseline (daily avg)" in imp_chart.columns else "#4CAF50")

                # Show publish date marker info
                if pd.notna(published_at):
                    st.caption(f"Published on {_format_date(published_at)} — baseline represents pre-optimization average")
            else:
                st.info("Time series data requires multiple snapshots. Run `feedops performance fetch` to collect more data points.")

    st.divider()

    # === PERFORMANCE TREND CHARTS ===
    st.markdown("### Performance Overview Charts")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**ROAS Change by SKU**")
        chart_data = df_unique[["master_sku", "roas_delta_pct"]].dropna()
        if not chart_data.empty:
            chart_data = chart_data.rename(columns={"master_sku": "SKU", "roas_delta_pct": "ROAS Δ%"})
            chart_data = chart_data.set_index("SKU")
            st.bar_chart(chart_data, color="#4CAF50")
        else:
            st.info("No ROAS data available")

    with col2:
        st.markdown("**CTR Change by SKU**")
        chart_data = df_unique[["master_sku", "ctr_delta_pct"]].dropna()
        if not chart_data.empty:
            chart_data = chart_data.rename(columns={"master_sku": "SKU", "ctr_delta_pct": "CTR Δ%"})
            chart_data = chart_data.set_index("SKU")
            st.bar_chart(chart_data, color="#2196F3")
        else:
            st.info("No CTR data available")

    st.divider()

    # === RECOMMENDATIONS SECTION ===
    st.markdown("### Recommendations")

    # Get SKUs by verdict
    needs_attention_skus = df_unique[df_unique["verdict"] == "NEEDS ATTENTION"]
    winning_skus = df_unique[df_unique["verdict"] == "WINNING"]
    monitoring_skus = df_unique[df_unique["verdict"] == "MONITORING"]

    if not needs_attention_skus.empty:
        st.markdown("#### 🔴 Action Required")
        for _, row in needs_attention_skus.iterrows():
            sku = row["master_sku"]
            roas_delta = row.get("roas_delta_pct", 0)
            ctr_delta = row.get("ctr_delta_pct", 0)
            days = row.get("days_since_publish", 0)

            st.markdown(f"**SKU {sku}**: ROAS dropped **{roas_delta:.1f}%** after {days} days.")

            # Provide specific recommendations based on metrics
            recommendations = []
            if pd.notna(ctr_delta) and ctr_delta < -20:
                recommendations.append("- CTR significantly down. Review title changes - may be less compelling.")
            if pd.notna(roas_delta) and roas_delta < -30:
                recommendations.append("- Consider rollback if decline continues after 14 days.")
            if days and days < 14:
                recommendations.append("- Still early. Monitor for another week before rollback decision.")
            else:
                recommendations.append("- Run A/B test comparing old vs new content if possible.")

            for rec in recommendations:
                st.markdown(rec)
            st.markdown("")

    if not monitoring_skus.empty:
        with st.expander(f"🟡 Monitoring ({len(monitoring_skus)} SKUs)", expanded=False):
            for _, row in monitoring_skus.iterrows():
                sku = row["master_sku"]
                roas_delta = row.get("roas_delta_pct")
                days = row.get("days_since_publish", 0)

                if pd.notna(roas_delta):
                    st.markdown(f"- **{sku}**: {roas_delta:+.1f}% ROAS ({days} days)")
                else:
                    st.markdown(f"- **{sku}**: Awaiting data ({days} days)")

    if not winning_skus.empty:
        with st.expander(f"🟢 Winners ({len(winning_skus)} SKUs)", expanded=False):
            for _, row in winning_skus.iterrows():
                sku = row["master_sku"]
                roas_delta = row.get("roas_delta_pct", 0)
                days = row.get("days_since_publish", 0)
                st.markdown(f"- **{sku}**: +{roas_delta:.1f}% ROAS lift after {days} days! Consider applying similar optimizations to related SKUs.")

    # Footer
    st.markdown("---")
    st.caption(
        "Data refreshes every 5 minutes. Run `feedops performance fetch` to update metrics. "
        "Verdicts require at least 7 days of data for meaningful comparison."
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
