"""Streamlit dashboard for reviewing optimized product content."""

from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

from feedops.cli.defaults import (
    BASELINE_EXPORTS_DIR,
    BASELINE_REPORTS_DIR,
    CANDIDATE_EXPORTS_DIR,
    CANDIDATE_REPORTS_DIR,
)
from feedops.db import (
    get_all_batches,
    get_approved_for_batch,
    get_pending_approvals,
    get_published_skus,
    get_revision_queue,
    get_sku_approval,
    init_db,
    is_supabase_available,
    save_sku_approval,
)
from feedops.pipeline.finish_injection import (
    generate_variant_description,
    generate_variant_keywords,
    generate_variant_title,
)

try:
    from feedops.pipeline.validators import validate_variant_title_uniqueness
except Exception:  # pragma: no cover
    validate_variant_title_uniqueness = None
from feedops.quality.collection_badge import get_collection_badge
from feedops.quality.data_loader import SKUData, get_summary_stats, load_all_sku_data
from feedops.quality.shopify_live import load_shopify_live_snapshot

# Default database path
DEFAULT_DB_PATH = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))

_DASHBOARD_DATA_SCHEMA_VERSION = "v3"


def _render_collection_badge(collection: str | None) -> None:
    badge = get_collection_badge(collection)
    if badge.kind == "designer":
        st.caption(f"✅ {badge.message}")
    elif badge.kind == "merchandising":
        st.caption(f"⚠️ {badge.message}")
    else:
        st.caption(f"ℹ️ {badge.message}")


def _latest_mtime(path: Path | str | None, patterns: tuple[str, ...]) -> float:
    """Return a cache-busting mtime for a directory and its matching children."""
    if not path:
        return 0.0
    root = Path(path)
    if not root.exists():
        return 0.0
    latest = 0.0
    try:
        latest = max(latest, root.stat().st_mtime)
    except OSError:
        pass
    for pattern in patterns:
        for candidate in root.glob(pattern):
            try:
                latest = max(latest, candidate.stat().st_mtime)
            except OSError:
                continue
    return latest


def load_available_finishes() -> list[str]:
    """Load available finish names from finishes.txt."""
    finishes_path = Path(__file__).parent.parent.parent.parent / "data" / "finishes.txt"
    if not finishes_path.exists():
        return []
    finishes = []
    for line in finishes_path.read_text().strip().split("\n"):
        if ":" in line:
            finish_name = line.split(":")[0]
            finishes.append(finish_name)
    return sorted(finishes)


_ALL_FINISHES_SENTINEL = "__ALL_FINISHES__"
_ALL_FINISHES_LABEL = "All finishes"


def _display_selected_finish(selected_finish: str | None) -> str | None:
    if selected_finish == _ALL_FINISHES_SENTINEL:
        return _ALL_FINISHES_LABEL
    return selected_finish


def _coerce_non_negative_int(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if not isinstance(value, int):
        return default
    if value < 0:
        return default
    return value


def _clamp_index(index: int, length: int) -> int:
    if length <= 0:
        return 0
    if index < 0:
        return 0
    if index >= length:
        return length - 1
    return index


def _find_variation_index(
    lifestyle_images: list[dict[str, Any]], variation_num: int
) -> int | None:
    for idx, img in enumerate(lifestyle_images):
        if img.get("variation_num") == variation_num:
            return idx
    return None


def _update_selected_lifestyle_image_in_patches(
    *,
    exports_dir: Path,
    master_sku: str,
    selected_variation_num: int,
) -> None:
    """Persist selected lifestyle image to patch JSONs so preview/publish can follow it.

    Best-effort: failures should not break the dashboard UI.
    """
    prefixes = ("google-patch-", "bing-patch-", "shopify-patch-")
    for prefix in prefixes:
        patch_path = exports_dir / f"{prefix}{master_sku}.json"
        if not patch_path.exists():
            continue
        try:
            data = json.loads(patch_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("selected_lifestyle_image") != selected_variation_num:
            data["selected_lifestyle_image"] = selected_variation_num
            try:
                patch_path.write_text(json.dumps(data, indent=2))
            except OSError:
                continue


def run_dashboard(
    baseline_exports_dir: str | Path,
    candidate_exports_dir: str | Path,
    catalog_path: str | Path | None = None,
    baseline_reports_dir: str | Path | None = None,
    candidate_reports_dir: str | Path | None = None,
) -> None:
    """Run the Streamlit review dashboard.

    Args:
        baseline_exports_dir: Path to baseline exports
        candidate_exports_dir: Path to candidate exports
        catalog_path: Optional path to Product Catalog.csv
        baseline_reports_dir: Optional path to baseline reports
        candidate_reports_dir: Optional path to candidate reports
    """
    st.set_page_config(
        page_title="FeedOps Content Review",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.session_state["feedops_baseline_exports_dir"] = str(baseline_exports_dir)
    st.session_state["feedops_candidate_exports_dir"] = str(candidate_exports_dir)
    st.session_state["feedops_catalog_path"] = str(catalog_path) if catalog_path else ""

    # Custom CSS for better styling
    st.markdown(
        """
    <style>
    .score-improved { color: #22c55e; font-weight: bold; }
    .score-declined { color: #ef4444; font-weight: bold; }
    .score-unchanged { color: #6b7280; }
    .sku-card { 
        border: 1px solid #e5e7eb; 
        border-radius: 8px; 
        padding: 16px; 
        margin-bottom: 16px;
        background-color: #ffffff;
    }
    .version-label {
        font-size: 12px;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .content-box {
        background-color: #f9fafb;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .keyword-chip {
        display: inline-block;
        background-color: #dbeafe;
        color: #1e40af;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin: 2px;
    }
    .enrichment-chip {
        display: inline-block;
        background-color: #fef3c7;
        color: #92400e;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 12px;
        margin: 2px;
    }
    .stExpander {
        border: 1px solid #e5e7eb !important;
        border-radius: 8px !important;
    }
    .approval-box {
        background-color: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 8px;
        padding: 16px;
        margin: 16px 0;
    }
    .approval-approved {
        background-color: #f0fdf4;
        border-color: #86efac;
    }
    .approval-revision {
        background-color: #fffbeb;
        border-color: #fcd34d;
    }
    .approval-rejected {
        background-color: #fef2f2;
        border-color: #fca5a5;
    }
    .revision-note {
        background-color: #fef3c7;
        padding: 8px 12px;
        border-radius: 4px;
        font-size: 14px;
        margin-top: 8px;
    }
    /* Sticky header for SKU panels */
    .sticky-sku-header {
        position: sticky;
        top: 0;
        z-index: 100;
        background: linear-gradient(180deg, #ffffff 0%, #ffffff 90%, transparent 100%);
        padding: 8px 0 16px 0;
        margin-bottom: 8px;
        border-bottom: 1px solid #e5e7eb;
    }
    .sticky-sku-header-content {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
    }
    .sticky-sku-info {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .sticky-sku-name {
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
    }
    .sticky-sku-score {
        font-size: 14px;
        color: #6b7280;
    }
    .sticky-quick-actions {
        display: flex;
        gap: 8px;
    }
    .quick-action-btn {
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 13px;
        cursor: pointer;
        border: 1px solid;
        transition: all 0.15s ease;
    }
    .quick-action-approve {
        background-color: #dcfce7;
        border-color: #86efac;
        color: #166534;
    }
    .quick-action-approve:hover {
        background-color: #bbf7d0;
    }
    .quick-action-revision {
        background-color: #fef3c7;
        border-color: #fcd34d;
        color: #92400e;
    }
    .quick-action-revision:hover {
        background-color: #fde68a;
    }
    .quick-action-reject {
        background-color: #fee2e2;
        border-color: #fca5a5;
        color: #991b1b;
    }
    .quick-action-reject:hover {
        background-color: #fecaca;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("FeedOps Content Review Dashboard")

    # Initialize database
    db_path = DEFAULT_DB_PATH
    init_db(db_path)

    with st.sidebar:
        st.subheader("Data")
        if st.button(
            "🧹 Clear data cache",
            key="clear_data_cache",
            help="Clears Streamlit's cached data loader results and reruns the app.",
        ):
            st.cache_data.clear()
            st.rerun()
        st.caption(
            "Cache is automatically invalidated when exports/reports change on disk."
        )

    # Main navigation tabs
    tab_review, tab_revision, tab_batches, tab_performance = st.tabs(
        ["📋 Review Queue", "🔄 Revision Queue", "✅ Approved / Batches", "📊 Performance View"]
    )

    # Load data with caching
    @st.cache_data
    def load_data(
        *,
        schema_version: str,
        baseline_exports_mtime: float,
        candidate_exports_mtime: float,
        baseline_reports_mtime: float,
        candidate_reports_mtime: float,
    ):
        return load_all_sku_data(
            baseline_exports_dir=baseline_exports_dir,
            candidate_exports_dir=candidate_exports_dir,
            catalog_path=catalog_path,
            baseline_reports_dir=baseline_reports_dir,
            candidate_reports_dir=candidate_reports_dir,
        )

    with st.spinner("Loading data..."):
        baseline_exports_mtime = _latest_mtime(
            baseline_exports_dir, patterns=("*-patch-*.json",)
        )
        candidate_exports_mtime = _latest_mtime(
            candidate_exports_dir, patterns=("*-patch-*.json",)
        )
        baseline_reports_mtime = _latest_mtime(
            baseline_reports_dir, patterns=("sku-*.md",)
        )
        candidate_reports_mtime = _latest_mtime(
            candidate_reports_dir, patterns=("sku-*.md",)
        )
        all_sku_data = load_data(
            schema_version=_DASHBOARD_DATA_SCHEMA_VERSION,
            baseline_exports_mtime=baseline_exports_mtime,
            candidate_exports_mtime=candidate_exports_mtime,
            baseline_reports_mtime=baseline_reports_mtime,
            candidate_reports_mtime=candidate_reports_mtime,
        )

    if not all_sku_data:
        st.error(
            "No SKU data found. Check that export directories exist and contain data."
        )
        return

    # Calculate summary stats
    stats = get_summary_stats(all_sku_data)

    # Render each tab
    with tab_review:
        render_review_queue_tab(
            all_sku_data=all_sku_data,
            stats=stats,
            baseline_exports_dir=baseline_exports_dir,
            candidate_exports_dir=candidate_exports_dir,
            baseline_reports_dir=baseline_reports_dir,
            candidate_reports_dir=candidate_reports_dir,
            db_path=db_path,
        )

    with tab_revision:
        render_revision_queue_tab(
            all_sku_data=all_sku_data,
            db_path=db_path,
        )

    with tab_batches:
        render_batch_management_tab(
            all_sku_data=all_sku_data,
            db_path=db_path,
        )

    with tab_performance:
        render_performance_view_tab(
            all_sku_data=all_sku_data,
            db_path=db_path,
        )


def _candidate_google_variant_title_warnings(sku_data: SKUData) -> list[str]:
    """Compute variant title warnings for the candidate Google patch.

    Uses the same validator as the pipeline. This is a read-only dashboard signal.
    """
    if not validate_variant_title_uniqueness:
        return []
    google = sku_data.candidate.get("google")
    variant_titles = getattr(google, "variant_titles", None) if google else None
    if not variant_titles:
        return []
    return validate_variant_title_uniqueness(list(variant_titles))


def render_compare_mode(
    filtered_data: list[SKUData],
    platform: str,
    db_path: Path,
) -> None:
    """Render side-by-side SKU comparison mode."""
    st.markdown("### 🔀 Compare Mode")
    st.caption("Select two SKUs to compare side-by-side")

    if len(filtered_data) < 2:
        st.warning("Need at least 2 SKUs to compare. Adjust your filters.")
        return

    # Create SKU options list
    sku_options = [
        f"{d.sku} ({d.candidate_scores.get('composite', 0):.1f}%)"
        for d in filtered_data
    ]
    sku_map = {
        f"{d.sku} ({d.candidate_scores.get('composite', 0):.1f}%)": d
        for d in filtered_data
    }

    # Two column layout for selectors
    col1, col2 = st.columns(2)

    with col1:
        selected_sku_1 = st.selectbox(
            "Left SKU",
            sku_options,
            index=0,
            key="compare_sku_1",
        )

    with col2:
        # Default to second SKU if available
        default_idx = 1 if len(sku_options) > 1 else 0
        selected_sku_2 = st.selectbox(
            "Right SKU",
            sku_options,
            index=default_idx,
            key="compare_sku_2",
        )

    # Get selected SKU data
    sku_data_1 = sku_map.get(selected_sku_1)
    sku_data_2 = sku_map.get(selected_sku_2)

    if not sku_data_1 or not sku_data_2:
        return

    st.divider()

    # Side-by-side comparison
    left_col, right_col = st.columns(2)

    with left_col:
        _render_compare_panel(sku_data_1, platform, db_path, "left")

    with right_col:
        _render_compare_panel(sku_data_2, platform, db_path, "right")


def _render_compare_panel(
    sku_data: SKUData,
    platform: str,
    db_path: Path,
    side: str,
) -> None:
    """Render a condensed SKU panel for comparison."""
    # Get scores
    c_score = sku_data.candidate_scores.get("composite", 0.0)
    delta = sku_data.composite_delta

    # Format delta
    if delta > 0.5:
        delta_display = f"🟢 +{delta:.1f}%"
    elif delta < -0.5:
        delta_display = f"🔴 {delta:.1f}%"
    else:
        delta_display = f"⚪ {delta:+.1f}%"

    # Get image URL
    image_url = ""
    if sku_data.original and sku_data.original.image_url:
        image_url = sku_data.original.image_url
    elif sku_data.candidate_report and sku_data.candidate_report.image_url:
        image_url = sku_data.candidate_report.image_url

    # Get approval status
    current_approval = (
        get_sku_approval(db_path, master_sku=sku_data.sku) if db_path else None
    )
    status_badge = ""
    if current_approval:
        status_badges = {
            "approved": "✅",
            "revision": "🔄",
            "rejected": "❌",
            "pending": "⏳",
        }
        status_badge = status_badges.get(current_approval["approval_status"], "")

    # Header
    st.markdown(f"### {sku_data.sku} {status_badge}")
    st.markdown(f"**Score:** {c_score:.1f}% ({delta_display})")

    # Image
    if image_url:
        st.image(image_url, width=150)

    # Category/Collection
    if sku_data.original:
        st.caption(
            f"📁 {sku_data.original.category} | 📦 {sku_data.original.collection}"
        )

    st.divider()

    # Get candidate content for selected platform
    candidate = sku_data.candidate.get(platform)
    if candidate:
        st.markdown("**Title:**")
        st.markdown(
            f"<div class='content-box'>{html.escape(candidate.title)}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("**Description:**")
        # Truncate description for comparison view
        desc = candidate.description
        if len(desc) > 500:
            desc = desc[:500] + "..."
        st.markdown(
            f"<div class='content-box' style='max-height: 300px; overflow-y: auto;'>{html.escape(desc)}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("No content for this platform")

    # Quick approval buttons
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(
            "✅ Approve", key=f"approve_{side}_{sku_data.sku}", width="stretch"
        ):
            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                status="approved",
                title_approved=True,
                description_approved=True,
                image_approved=True,
            )
            st.rerun()
    with col2:
        if st.button("🔄 Revise", key=f"revise_{side}_{sku_data.sku}", width="stretch"):
            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                status="revision",
            )
            st.rerun()
    with col3:
        if st.button("❌ Reject", key=f"reject_{side}_{sku_data.sku}", width="stretch"):
            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                status="rejected",
            )
            st.rerun()


def render_split_pane_view(
    filtered_data: list[SKUData],
    all_sku_data: list[SKUData],
    platform: str,
    db_path: Path,
) -> None:
    """Render split-pane view with SKU list on left and details on right."""
    # Initialize session state for selected SKU
    if "selected_sku" not in st.session_state:
        st.session_state.selected_sku = filtered_data[0].sku if filtered_data else None

    # Ensure selected SKU is in filtered data, otherwise select first
    filtered_skus = {d.sku for d in filtered_data}
    if st.session_state.selected_sku not in filtered_skus:
        st.session_state.selected_sku = filtered_data[0].sku if filtered_data else None

    # Create sku_map for quick lookup
    sku_map = {d.sku: d for d in filtered_data}

    # CSS for split-pane layout
    st.markdown(
        """
        <style>
        .sku-list-container {
            max-height: 75vh;
            overflow-y: auto;
            padding-right: 8px;
        }
        .sku-list-item {
            padding: 12px;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.15s ease;
        }
        .sku-list-item:hover {
            border-color: #3b82f6;
            background-color: #f0f9ff;
        }
        .sku-list-item-selected {
            border-color: #3b82f6;
            background-color: #eff6ff;
            border-width: 2px;
        }
        .sku-list-name {
            font-weight: 600;
            font-size: 14px;
            color: #1f2937;
        }
        .sku-list-score {
            font-size: 13px;
            color: #6b7280;
        }
        .sku-list-status {
            font-size: 12px;
            margin-top: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Split layout: 25% left (SKU list), 75% right (details)
    left_col, right_col = st.columns([1, 3])

    with left_col:
        st.markdown(f"**{len(filtered_data)}** SKUs")

        # Navigation buttons
        nav_col1, nav_col2 = st.columns(2)
        current_idx = next(
            (
                i
                for i, d in enumerate(filtered_data)
                if d.sku == st.session_state.selected_sku
            ),
            0,
        )
        with nav_col1:
            if st.button("⬆️ Prev", disabled=current_idx == 0, width="stretch"):
                st.session_state.selected_sku = filtered_data[current_idx - 1].sku
                st.rerun()
        with nav_col2:
            if st.button(
                "⬇️ Next",
                disabled=current_idx >= len(filtered_data) - 1,
                width="stretch",
            ):
                st.session_state.selected_sku = filtered_data[current_idx + 1].sku
                st.rerun()

        st.divider()

        # SKU list with selection buttons
        for sku_data in filtered_data:
            c_score = sku_data.candidate_scores.get("composite", 0.0)
            delta = sku_data.composite_delta

            # Format delta
            if delta > 0.5:
                delta_display = f"🟢 +{delta:.1f}%"
            elif delta < -0.5:
                delta_display = f"🔴 {delta:.1f}%"
            else:
                delta_display = f"⚪ {delta:+.1f}%"

            # Get approval status
            current_approval = get_sku_approval(db_path, master_sku=sku_data.sku)
            status_icon = ""
            if current_approval:
                status_icons = {
                    "approved": "✅",
                    "revision": "🔄",
                    "rejected": "❌",
                    "pending": "⏳",
                }
                status_icon = status_icons.get(current_approval["approval_status"], "")

            # Highlight if selected
            is_selected = sku_data.sku == st.session_state.selected_sku
            btn_type = "primary" if is_selected else "secondary"

            if st.button(
                f"{status_icon} **{sku_data.sku}**\n{c_score:.0f}% ({delta_display})",
                key=f"sku_btn_{sku_data.sku}",
                width="stretch",
                type=btn_type,
            ):
                st.session_state.selected_sku = sku_data.sku
                st.rerun()

    with right_col:
        # Show selected SKU details
        if st.session_state.selected_sku and st.session_state.selected_sku in sku_map:
            selected_data = sku_map[st.session_state.selected_sku]
            render_sku_detail_panel(selected_data, platform, db_path)
        elif filtered_data:
            st.info("Select a SKU from the list to view details")
        else:
            st.warning("No SKUs match the current filters")


def render_sku_detail_panel(
    sku_data: SKUData, platform: str, db_path: Path | None = None
) -> None:
    """Render detailed view for a single SKU (used in split-pane mode)."""
    # Get scores
    c_score = sku_data.candidate_scores.get("composite", 0.0)
    delta = sku_data.composite_delta

    # Format delta display
    if delta > 0.5:
        delta_display = f"🟢 +{delta:.1f}%"
    elif delta < -0.5:
        delta_display = f"🔴 {delta:.1f}%"
    else:
        delta_display = f"⚪ {delta:+.1f}%"

    # Get image URL
    image_url = ""
    if sku_data.original and sku_data.original.image_url:
        image_url = sku_data.original.image_url
    elif sku_data.candidate_report and sku_data.candidate_report.image_url:
        image_url = sku_data.candidate_report.image_url

    # Get current approval state
    current_approval = None
    if db_path:
        current_approval = get_sku_approval(db_path, master_sku=sku_data.sku)

    # Header with SKU info
    st.markdown(f"## {sku_data.sku}")
    st.markdown(f"**Score:** {c_score:.1f}% ({delta_display})")

    # Product image and basic info
    col_img, col_info = st.columns([1, 3])

    with col_img:
        if image_url:
            st.image(image_url, width=200)
        else:
            st.caption("No image available")

    with col_info:
        if sku_data.original:
            st.markdown(f"**Category:** {sku_data.original.category}")
            st.markdown(f"**Collection:** {sku_data.original.collection}")
            _render_collection_badge(sku_data.original.collection)

        # Auto-calculated approval status from quality evaluation
        status = sku_data.candidate_scores.get("approval_status", "")
        if not status and sku_data.candidate_report:
            status = sku_data.candidate_report.status

        if status:
            status_colors = {"approved": "🟢", "revise": "🟡", "rejected": "🔴"}
            status_emoji = status_colors.get(status.lower(), "⚪")
            st.markdown(f"**Auto-Status:** {status_emoji} {status.upper()}")

        # Manual approval status
        if current_approval:
            manual_status = current_approval["approval_status"]
            manual_colors = {
                "pending": "⏳",
                "approved": "✅",
                "revision": "🔄",
                "rejected": "❌",
            }
            st.markdown(
                f"**Manual Status:** {manual_colors.get(manual_status, '❓')} {manual_status.upper()}"
            )

    st.divider()

    # Approval Controls Section
    if db_path:
        render_approval_controls(sku_data, db_path, current_approval)
        st.divider()

    # Lifestyle images (collapsed by default, only show if images exist)
    has_lifestyle_images = _sku_has_lifestyle_images(sku_data)
    if has_lifestyle_images:
        with st.expander("🖼️ Lifestyle Images", expanded=False):
            render_lifestyle_images_panel(sku_data)

    # Three-way content comparison (always visible - this is the primary content)
    render_content_comparison(sku_data, platform)

    # Reasoning inputs (collapsed by default)
    with st.expander("💡 Reasoning Inputs", expanded=False):
        render_reasoning_panel(sku_data, show_header=False)

    # Quality scores (collapsed by default)
    with st.expander("📊 Quality Scores", expanded=False):
        render_score_panel(sku_data, show_header=False)


def render_review_queue_tab(
    all_sku_data: list[SKUData],
    stats: dict[str, Any],
    baseline_exports_dir: str | Path,
    candidate_exports_dir: str | Path,
    baseline_reports_dir: str | Path | None,
    candidate_reports_dir: str | Path | None,
    db_path: Path,
) -> None:
    """Render the Review Queue tab with approval controls."""
    # Filter out SKUs that have been published to production
    # This is only available when Supabase is configured
    published_skus: set[str] = set()
    if is_supabase_available():
        try:
            published_skus = get_published_skus(environment="production")
        except Exception:
            # If Supabase query fails, show all SKUs
            published_skus = set()
    
    # Filter out published SKUs from the review queue
    review_sku_data = [
        sku_data for sku_data in all_sku_data
        if sku_data.sku not in published_skus
    ]
    published_count = len(all_sku_data) - len(review_sku_data)
    
    # Recalculate stats for filtered data
    if published_count > 0:
        stats = get_summary_stats(review_sku_data)
    
    # Sidebar filters (shared across app)
    with st.sidebar:
        st.header("Filters")
        
        # Show published SKU count if any are filtered
        if published_count > 0:
            st.info(
                f"🚀 **{published_count} SKUs published** to production and "
                f"moved to Performance View"
            )

        # Search
        search_query = st.text_input("Search SKU", placeholder="Enter SKU...")

        # Category filter
        categories = ["All"] + stats["categories"]
        selected_category = st.selectbox("Category", categories)

        # Collection filter
        collections = ["All"] + stats["collections"]
        selected_collection = st.selectbox("Collection", collections)

        # Score filter
        score_filter = st.selectbox(
            "Score Change", ["All", "Improved", "Declined", "Unchanged"]
        )

        # Platform selector (controls which platform expands by default)
        platform = st.radio(
            "Default Platform",
            ["Google", "Bing", "Shopify"],
            horizontal=True,
            help="All platforms are shown in each SKU panel. This controls which one is expanded by default.",
        )

        st.divider()

        # Compare mode toggle
        compare_mode = st.toggle(
            "🔀 Compare Mode",
            value=False,
            help="Enable side-by-side comparison of two SKUs",
        )

        st.divider()

        # Summary stats
        st.subheader("Summary")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total SKUs", stats["total_skus"])
            st.metric("Avg Baseline", f"{stats['avg_baseline']:.1f}%")
        with col2:
            delta_color = "normal" if stats["avg_delta"] >= 0 else "inverse"
            st.metric(
                "Avg Candidate",
                f"{stats['avg_candidate']:.1f}%",
                f"{stats['avg_delta']:+.1f}%",
                delta_color=delta_color,
            )

        st.divider()

        # Score distribution
        st.caption("Score Changes")
        cols = st.columns(3)
        cols[0].markdown(f"🟢 **{stats['improved_count']}** improved")
        cols[1].markdown(f"🔴 **{stats['declined_count']}** declined")
        cols[2].markdown(f"⚪ **{stats['unchanged_count']}** unchanged")

        st.divider()

        debug_info = get_dashboard_debug_info(
            baseline_exports_dir=baseline_exports_dir,
            candidate_exports_dir=candidate_exports_dir,
            baseline_reports_dir=baseline_reports_dir,
            candidate_reports_dir=candidate_reports_dir,
        )
        with st.expander("Debug: Data Sources", expanded=False):
            st.caption("Exports")
            st.code(
                f"Baseline: {debug_info['baseline_exports_dir']}\n"
                f"Candidate: {debug_info['candidate_exports_dir']}\n"
                f"Baseline patches: {debug_info['baseline_exports_count']}\n"
                f"Candidate patches: {debug_info['candidate_exports_count']}",
                language="text",
            )
            st.caption("Reports")
            st.code(
                f"Baseline: {debug_info['baseline_reports_dir']}\n"
                f"Candidate: {debug_info['candidate_reports_dir']}\n"
                f"Baseline reports: {debug_info['baseline_reports_count']}\n"
                f"Candidate reports: {debug_info['candidate_reports_count']}",
                language="text",
            )

    # Apply filters (using review_sku_data which excludes published SKUs)
    filtered_data = filter_sku_data(
        review_sku_data,
        search_query=search_query,
        category=selected_category if selected_category != "All" else None,
        collection=selected_collection if selected_collection != "All" else None,
        score_filter=score_filter if score_filter != "All" else None,
    )

    with st.sidebar:
        # Variant title warnings (computed on current filter set)
        warning_counts: Counter[str] = Counter()
        warnings_by_sku: dict[str, list[str]] = {}
        for d in filtered_data:
            warnings = _candidate_google_variant_title_warnings(d)
            if warnings:
                warnings_by_sku[d.sku] = warnings
                for w in warnings:
                    wl = (w or "").lower()
                    if "duplicate variant title" in wl:
                        warning_counts["duplicate"] += 1
                    elif (
                        "appears after the first" in wl
                        and "consider moving finish earlier" in wl
                    ):
                        warning_counts["finish_after_visible_chars"] += 1
                    else:
                        warning_counts["other"] += 1

        st.subheader("Variant Title Warnings")
        st.caption(
            "Flags variants that look identical in truncated Shopping titles (Google)."
        )
        st.metric("SKUs with warnings", len(warnings_by_sku))
        if warning_counts:
            cols = st.columns(3)
            cols[0].metric("Duplicate titles", warning_counts.get("duplicate", 0))
            cols[1].metric(
                "Finish after ~70 chars",
                warning_counts.get("finish_after_visible_chars", 0),
            )
            cols[2].metric("Other", warning_counts.get("other", 0))

        with st.expander("View warning details", expanded=False):
            if not warnings_by_sku:
                st.caption("No variant title warnings for the current filter set.")
            else:
                sku = st.selectbox(
                    "SKU",
                    options=sorted(warnings_by_sku.keys()),
                    key="variant_title_warning_sku",
                )
                st.code("\n".join(warnings_by_sku.get(sku, [])), language="text")

    # Main content area
    if compare_mode:
        # Compare mode: side-by-side SKU comparison
        render_compare_mode(filtered_data, platform.lower(), db_path)
    else:
        # Split-pane mode: SKU list on left, details on right
        render_split_pane_view(filtered_data, review_sku_data, platform.lower(), db_path)


def render_revision_queue_tab(
    all_sku_data: list[SKUData],
    db_path: Path,
) -> None:
    """Render the Revision Queue tab showing SKUs flagged for revision."""
    st.header("Revision Queue")
    st.caption("SKUs that have been flagged for revision and need additional work")

    # Get revision queue from database
    revisions = get_revision_queue(db_path)

    if not revisions:
        st.info("No SKUs in the revision queue. Great work!")
        return

    st.metric("SKUs Needing Work", len(revisions))

    # Create a lookup from all_sku_data for quick access
    sku_data_map = {sku.sku: sku for sku in all_sku_data}

    for approval in revisions:
        master_sku = approval["master_sku"]
        sku_data = sku_data_map.get(master_sku)

        with st.expander(
            f"**{master_sku}** — Flagged {approval['approved_at'][:10] if approval['approved_at'] else 'N/A'}",
            expanded=False,
        ):
            # Show revision notes
            if approval["notes"]:
                st.markdown(
                    f"<div class='revision-note'><strong>Revision Notes:</strong> {html.escape(approval['notes'])}</div>",
                    unsafe_allow_html=True,
                )

            # Show what was approved/rejected
            col1, col2, col3 = st.columns(3)
            with col1:
                title_status = (
                    "✅"
                    if approval["title_approved"]
                    else "❌" if approval["title_approved"] is False else "⚪"
                )
                st.markdown(f"**Title:** {title_status}")
            with col2:
                desc_status = (
                    "✅"
                    if approval["description_approved"]
                    else "❌" if approval["description_approved"] is False else "⚪"
                )
                st.markdown(f"**Description:** {desc_status}")
            with col3:
                image_status = (
                    "✅"
                    if approval["image_approved"]
                    else "❌" if approval["image_approved"] is False else "⚪"
                )
                st.markdown(f"**Image:** {image_status}")
                if approval["selected_finish"]:
                    st.caption(
                        f"Finish: {_display_selected_finish(approval['selected_finish'])}"
                    )

            st.divider()

            # Show content preview if available
            if sku_data:
                candidate_content = (
                    sku_data.candidate.get("google")
                    or sku_data.candidate.get("bing")
                    or sku_data.candidate.get("shopify")
                )
                if candidate_content:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Current Title:**")
                        st.markdown(
                            f"<div class='content-box'>{html.escape(candidate_content.title) if candidate_content.title else '<em>N/A</em>'}</div>",
                            unsafe_allow_html=True,
                        )
                    with col2:
                        st.markdown("**Current Description:**")
                        st.markdown(
                            f"<div class='content-box' style='max-height: 150px; overflow-y: auto;'>{html.escape(candidate_content.description[:500] if candidate_content.description else '')}</div>",
                            unsafe_allow_html=True,
                        )

            # Action buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Mark as Resolved", key=f"resolve_{master_sku}"):
                    save_sku_approval(
                        db_path,
                        master_sku=master_sku,
                        status="pending",
                        notes=None,
                    )
                    st.success("Moved back to Review Queue")
                    st.rerun()
            with col2:
                if st.button("Reject Permanently", key=f"reject_{master_sku}"):
                    save_sku_approval(
                        db_path,
                        master_sku=master_sku,
                        status="rejected",
                    )
                    st.warning("SKU rejected")
                    st.rerun()


def render_batch_management_tab(
    all_sku_data: list[SKUData],
    db_path: Path,
) -> None:
    """Render the Batch Management tab for approved SKUs and batch creation."""
    st.header("Approved SKUs & Batch Management")

    # Get approved SKUs ready for batching
    approved = get_approved_for_batch(db_path, exclude_batched=True)
    batches = get_all_batches(db_path)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Approved (Ready to Batch)", len(approved))
    with col2:
        st.metric("Total Batches", len(batches))

    st.divider()

    # Batch creation section
    st.subheader("Create New Batch")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        batch_name = st.text_input(
            "Batch Label (optional)",
            placeholder="e.g., 'Q1 2026 Towel Bars'",
            key="new_batch_label",
        )
    with col2:
        max_batch = min(100, len(approved)) if approved else 100
        default_batch = min(40, max_batch) if max_batch > 0 else 1
        batch_size = st.number_input(
            "Batch Size",
            value=default_batch,
            min_value=1,
            max_value=max(max_batch, 1),  # Ensure max_value is at least 1
            key="batch_size",
        )
    # Note: Advanced selection criteria removed - SKUs are already pre-approved
    # in the Review Queue, so batch creation simply takes approved SKUs in order

    if approved:
        if st.button("Create Batch from Approved SKUs", type="primary"):
            # Import batch creation logic
            from feedops.db import create_batch

            # Simple selection: take approved SKUs up to batch_size
            # Advanced performance-based selection is disabled by default
            # since SKUs are already pre-approved in the Review Queue
            selected_skus = [a["master_sku"] for a in approved[:batch_size]]

            if selected_skus:
                batch_id = create_batch(
                    db_path,
                    batch_name=batch_name if batch_name else None,
                    skus=selected_skus,
                    notes={
                        "method": "fifo",
                        "batch_size": batch_size,
                    },
                )
                st.success(f"Created **{batch_id}** with {len(selected_skus)} SKUs")
                st.rerun()
            else:
                st.error("No SKUs could be selected")
    else:
        st.info(
            "No approved SKUs available for batching. Approve SKUs in the Review Queue first."
        )

    st.divider()

    # Show approved SKUs list
    if approved:
        st.subheader("Approved SKUs (Ready for Batch)")
        for approval in approved[:20]:  # Show first 20
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{approval['master_sku']}**")
            with col2:
                elements = []
                if approval["title_approved"]:
                    elements.append("Title")
                if approval["description_approved"]:
                    elements.append("Desc")
                if approval["image_approved"]:
                    elements.append(
                        f"Image ({_display_selected_finish(approval['selected_finish']) or 'N/A'})"
                    )
                st.caption(", ".join(elements) if elements else "No elements")
            with col3:
                st.caption(
                    approval["approved_at"][:10] if approval["approved_at"] else "N/A"
                )

        if len(approved) > 20:
            st.caption(f"... and {len(approved) - 20} more")

    st.divider()

    # Existing batches
    st.subheader("Existing Batches")

    if not batches:
        st.info("No batches created yet.")
    else:
        for batch in batches:
            status_emoji = {
                "pending": "⏳",
                "publishing": "🔄",
                "published": "✅",
                "partial": "⚠️",
            }.get(batch["status"], "❓")

            with st.expander(
                f"{status_emoji} **{batch['batch_id']}** — {batch['status'].upper()} ({batch['sku_count']} SKUs)",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("SKU Count", batch["sku_count"])
                with col2:
                    st.metric("Success", batch["success_count"])
                with col3:
                    st.metric("Failed", batch["failed_count"])

                if batch["name"]:
                    st.markdown(f"**Label:** {batch['name']}")
                if batch["target_date"]:
                    st.markdown(f"**Target Date:** {batch['target_date']}")

                st.caption(
                    f"Created: {batch['created_at'][:10] if batch['created_at'] else 'N/A'}"
                )
                if batch["executed_at"]:
                    st.caption(f"Published: {batch['executed_at'][:10]}")

                # Show SKUs in batch
                from feedops.db import get_batch_skus

                batch_skus = get_batch_skus(db_path, batch_id=batch["batch_id"])
                if batch_skus:
                    with st.expander("View SKUs in Batch"):
                        for sku in batch_skus[:50]:
                            st.markdown(f"- {sku}")
                        if len(batch_skus) > 50:
                            st.caption(f"... and {len(batch_skus) - 50} more")

                # Execute batch button for pending batches
                if batch["status"] == "pending" and batch_skus:
                    st.divider()
                    st.markdown("**Execute Batch**")

                    exec_col1, exec_col2, exec_col3 = st.columns(3)
                    with exec_col1:
                        target_platform = st.selectbox(
                            "Target Platform",
                            ["google", "bing", "shopify", "all"],
                            key=f"exec_platform_{batch['batch_id']}",
                            help="google: Push to GMC supplemental feed via Google Sheets",
                        )
                    with exec_col2:
                        target_environment = st.selectbox(
                            "Environment",
                            ["staging", "production"],
                            key=f"exec_env_{batch['batch_id']}",
                            help="staging: safe preview label. production: live feed data.",
                        )
                    with exec_col3:
                        dry_run = st.checkbox(
                            "Dry Run (preview only)",
                            value=True,
                            key=f"dry_run_{batch['batch_id']}",
                        )

                    if target_environment == "production" and not dry_run:
                        st.warning("⚠️ Production publish will update live Shopping feeds.")

                    if st.button(
                        "🚀 Execute Batch" if not dry_run else "👁️ Preview Batch",
                        key=f"exec_{batch['batch_id']}",
                        type="primary" if not dry_run else "secondary",
                    ):
                        _execute_batch_action(
                            batch_id=batch["batch_id"],
                            batch_skus=batch_skus,
                            platform=target_platform,
                            dry_run=dry_run,
                            db_path=db_path,
                            environment=target_environment,
                        )

                # Rollback for published batches
                if batch["status"] in ("published", "partial") and batch_skus:
                    st.divider()
                    st.markdown("**Rollback**")

                    rollback_col1, rollback_col2 = st.columns(2)
                    with rollback_col1:
                        rollback_dry_run = st.checkbox(
                            "Preview rollback",
                            value=True,
                            key=f"rollback_dry_{batch['batch_id']}",
                        )
                    with rollback_col2:
                        if st.button(
                            "🔙 Preview Rollback" if rollback_dry_run else "🔙 Execute Rollback",
                            key=f"rollback_{batch['batch_id']}",
                            type="secondary",
                        ):
                            _execute_rollback(
                                batch_id=batch["batch_id"],
                                batch_skus=batch_skus,
                                dry_run=rollback_dry_run,
                                db_path=db_path,
                            )


def render_performance_view_tab(
    all_sku_data: list[SKUData],
    db_path: Path,
) -> None:
    """Render the Performance View tab showing published SKUs and their metrics."""
    from feedops.db import get_publish_history
    
    st.header("Performance View")
    st.caption("Monitor SKUs that have been published to production")
    
    # Get published SKUs
    published_skus: set[str] = set()
    if is_supabase_available():
        try:
            published_skus = get_published_skus(environment="production")
        except Exception as e:
            st.warning(f"Could not fetch published SKUs: {e}")
    
    if not published_skus:
        st.info(
            "No SKUs have been published to production yet. "
            "Once you execute a batch with environment='production', "
            "the published SKUs will appear here."
        )
        return
    
    # Filter all_sku_data to only show published SKUs
    published_sku_data = [
        sku_data for sku_data in all_sku_data
        if sku_data.sku in published_skus
    ]
    
    # Get publish history for these SKUs
    publish_history = get_publish_history(
        environment="production",
        limit=500,
    )
    
    # Create a lookup for publish events by SKU
    publish_events_by_sku: dict[str, list[dict]] = {}
    for event in publish_history:
        sku = event.get("master_sku", "")
        if sku not in publish_events_by_sku:
            publish_events_by_sku[sku] = []
        publish_events_by_sku[sku].append(event)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Published SKUs", len(published_skus))
    with col2:
        # Count by platform
        platforms = {}
        for event in publish_history:
            plat = event.get("platform", "unknown")
            platforms[plat] = platforms.get(plat, 0) + 1
        st.metric("Publish Events", len(publish_history))
    with col3:
        # Average quality score
        scores = [
            e.get("quality_score", 0) for e in publish_history
            if e.get("quality_score")
        ]
        avg_score = sum(scores) / len(scores) if scores else 0
        st.metric("Avg Quality Score", f"{avg_score:.1f}%")
    
    st.divider()
    
    # Platform breakdown
    if platforms:
        st.subheader("Publish Events by Platform")
        platform_cols = st.columns(len(platforms))
        for i, (plat, count) in enumerate(sorted(platforms.items())):
            platform_cols[i].metric(plat.title(), count)
    
    st.divider()
    
    # Published SKU list with details
    st.subheader(f"Published SKUs ({len(published_sku_data)})")
    
    if not published_sku_data:
        st.info("No matching SKU data found for published SKUs.")
        return
    
    # Search filter
    search = st.text_input("Search published SKUs", placeholder="Enter SKU...")
    
    filtered_published = published_sku_data
    if search:
        search_lower = search.lower()
        filtered_published = [
            s for s in published_sku_data
            if search_lower in s.sku.lower()
        ]
    
    # Display SKUs
    for sku_data in filtered_published[:50]:  # Limit to 50 for performance
        events = publish_events_by_sku.get(sku_data.sku, [])
        latest_event = events[0] if events else {}
        
        # Format publish date
        published_at = latest_event.get("published_at", "")
        if published_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                published_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                published_str = published_at[:16] if len(published_at) > 16 else published_at
        else:
            published_str = "Unknown"
        
        quality_score = latest_event.get("quality_score", 0)
        platform = latest_event.get("platform", "unknown")
        
        with st.expander(
            f"**{sku_data.sku}** — Published {published_str} via {platform} "
            f"(Score: {quality_score:.1f}%)" if quality_score else
            f"**{sku_data.sku}** — Published {published_str} via {platform}",
            expanded=False,
        ):
            # Show basic info
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Category:** " + (sku_data.category or "N/A"))
                st.markdown("**Collection:** " + (sku_data.collection or "N/A"))
            with col2:
                st.markdown(f"**Quality Score:** {quality_score:.1f}%")
                st.markdown(f"**Platform:** {platform}")
            
            # Show publish history for this SKU
            if len(events) > 1:
                st.markdown("**Publish History:**")
                for event in events[:5]:
                    event_time = event.get("published_at", "")[:16]
                    event_plat = event.get("platform", "")
                    event_env = event.get("environment", "")
                    event_status = event.get("status", "")
                    status_icon = "✅" if event_status == "success" else "❌"
                    st.caption(f"{status_icon} {event_time} — {event_plat} ({event_env})")
            
            # Show current title/description
            if sku_data.candidate_google:
                st.markdown("**Published Title (Google):**")
                st.code(sku_data.candidate_google.get("title", "N/A"))
    
    st.divider()

    # Performance baseline capture section
    st.subheader("Capture Performance Baseline")
    st.caption(
        "Capture pre-publish or current performance metrics for published SKUs. "
        "These baselines are used to measure content optimization impact."
    )

    baseline_col1, baseline_col2 = st.columns(2)
    with baseline_col1:
        baseline_platform = st.selectbox(
            "Platform",
            ["google", "shopify"],
            key="baseline_platform",
            help="Platform to fetch metrics for",
        )
    with baseline_col2:
        baseline_days = st.number_input(
            "Baseline period (days)",
            min_value=7,
            max_value=90,
            value=30,
            key="baseline_days",
            help="Number of days to average for baseline metrics",
        )

    if st.button("📊 Capture Baseline for Published SKUs", key="capture_baseline"):
        from datetime import datetime, timedelta, timezone

        from feedops.db import get_performance_baseline, save_performance_baseline

        published_sku_list = list(published_skus)
        if not published_sku_list:
            st.warning("No published SKUs to capture baselines for.")
        else:
            with st.spinner(f"Capturing baselines for {len(published_sku_list)} SKUs..."):
                end_date = datetime.now(timezone.utc).date()
                start_date = end_date - timedelta(days=baseline_days)

                captured = 0
                skipped = 0
                for sku in published_sku_list:
                    # Check if baseline already exists
                    existing = get_performance_baseline(
                        db_path, master_sku=sku, platform=baseline_platform
                    )
                    if existing:
                        skipped += 1
                        continue

                    # Save placeholder baseline (actual metrics to be filled by monitoring job)
                    save_performance_baseline(
                        db_path,
                        master_sku=sku,
                        platform=baseline_platform,
                        baseline_start_date=start_date.isoformat(),
                        baseline_end_date=end_date.isoformat(),
                    )
                    captured += 1

                if captured > 0:
                    st.success(
                        f"Captured {captured} baselines for {baseline_platform}. "
                        f"({skipped} already had baselines)"
                    )
                else:
                    st.info(f"All {skipped} published SKUs already have baselines.")

    if len(filtered_published) > 50:
        st.caption(f"Showing first 50 of {len(filtered_published)} published SKUs")

    # --- Published SKU Monitoring ---
    st.divider()
    st.subheader("Published SKU Monitoring")
    st.caption(
        "Track recently published SKUs and compare current metrics against baselines."
    )

    from datetime import datetime, timezone

    from feedops.db import get_performance_baseline

    # Build monitoring table from publish events
    monitoring_rows: list[dict] = []
    now = datetime.now(timezone.utc)
    seen_skus: set[str] = set()

    for event in publish_history:
        sku = event.get("master_sku", "")
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)

        published_at = event.get("published_at", "")
        days_since = None
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                days_since = (now - dt).days
            except Exception:
                pass

        plat = event.get("platform", "unknown")
        baseline = get_performance_baseline(
            db_path, master_sku=sku, platform=plat,
        )

        monitoring_rows.append({
            "sku": sku,
            "platform": plat,
            "published_at": published_at[:10] if published_at else "Unknown",
            "days_since": days_since,
            "quality_score": event.get("quality_score"),
            "baseline": baseline,
        })

    # Sort by most recently published
    monitoring_rows.sort(
        key=lambda r: r.get("days_since") if r.get("days_since") is not None else 9999,
    )

    if monitoring_rows:
        # Show monitoring table
        for row in monitoring_rows[:30]:
            days_label = (
                f"{row['days_since']}d ago" if row["days_since"] is not None else "?"
            )
            score_label = (
                f" | Score: {row['quality_score']:.1f}%"
                if row.get("quality_score")
                else ""
            )
            baseline_label = (
                " | Baseline captured"
                if row.get("baseline")
                else " | No baseline"
            )

            with st.expander(
                f"**{row['sku']}** — {row['platform']} — published {days_label}"
                f"{score_label}{baseline_label}",
                expanded=False,
            ):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Published", row["published_at"])
                with col2:
                    st.metric("Days Since Publish", row.get("days_since", "N/A"))
                with col3:
                    st.metric("Platform", row["platform"].title())

                baseline = row.get("baseline")
                if baseline:
                    st.markdown("**Baseline Metrics:**")
                    b_cols = st.columns(4)
                    with b_cols[0]:
                        val = baseline.get("avg_impressions")
                        st.metric("Avg Impressions", f"{val:.0f}" if val else "—")
                    with b_cols[1]:
                        val = baseline.get("avg_clicks")
                        st.metric("Avg Clicks", f"{val:.0f}" if val else "—")
                    with b_cols[2]:
                        val = baseline.get("avg_ctr")
                        st.metric("Avg CTR", f"{val:.2%}" if val else "—")
                    with b_cols[3]:
                        val = baseline.get("avg_conversions")
                        st.metric("Avg Conversions", f"{val:.1f}" if val else "—")
                else:
                    st.info("No baseline captured yet. Use the 'Capture Baseline' button above.")

        if len(monitoring_rows) > 30:
            st.caption(f"Showing first 30 of {len(monitoring_rows)} monitored SKUs")
    else:
        st.info("No published SKUs to monitor yet.")

    # Fetch Latest Metrics button (stub)
    st.divider()
    if st.button("🔄 Fetch Latest Metrics", key="fetch_latest_metrics"):
        st.info(
            "Metric fetching is not yet connected to a data source. "
            "This will pull live performance data from Google Ads / Analytics "
            "once the integration is configured."
        )


def _execute_google_sheets_batch(
    batch_id: str,
    batch_skus: list[str],
    patches_dir: Path,
    dry_run: bool,
    db_path: Path,
    environment: str = "staging",
) -> None:
    """Execute a batch publish to Google Sheets.

    This uses the Google Sheets API to push all batch SKUs to the
    GMC supplemental feed spreadsheet in a single operation.
    """
    from feedops.db import log_publish_event, update_batch_status
    from feedops.integrations.google_sheets import (
        load_patches_for_batch,
        push_patches_to_sheet,
    )

    with st.spinner(
        f"{'Previewing' if dry_run else 'Publishing'} {len(batch_skus)} SKUs to Google Sheets..."
    ):
        try:
            # Load patches for all SKUs in the batch
            patches = load_patches_for_batch(patches_dir, batch_skus, platform="google")

            # Enrich patches with lifestyle image data from approvals
            for patch in patches:
                meta = patch.get("_meta", {})
                sku = meta.get("master_sku", "")
                if not sku:
                    continue
                try:
                    approval = get_sku_approval(db_path, master_sku=sku)
                    if approval and approval.get("image_approved"):
                        # Set the finish filter for per-variant image assignment
                        patch["_image_approved_finish"] = approval.get(
                            "selected_finish", "__ALL_FINISHES__"
                        )
                        # Try to upload image to CDN (best-effort)
                        try:
                            from feedops.integrations.shopify_catalog import (
                                upload_selected_lifestyle_image,
                            )
                            img_result = upload_selected_lifestyle_image(
                                patch, images_base_dir=patches_dir
                            )
                            if img_result and img_result.get("success"):
                                patch["lifestyle_image_link"] = img_result.get(
                                    "image_url", ""
                                )
                        except Exception:
                            pass  # Image upload is best-effort
                except Exception:
                    pass  # Don't fail the batch for image enrichment errors

            if not patches:
                st.error(f"No Google patches found for batch {batch_id}")
                return

            # Push to Google Sheets
            result = push_patches_to_sheet(
                patches=patches,
                environment=environment,
                dry_run=dry_run,
                include_variants=True,
            )

            # Display results
            if result.get("success"):
                if dry_run:
                    st.success(
                        f"✅ Preview complete - would push {len(patches)} SKUs to Google Sheets"
                    )
                    st.info(
                        f"**Summary:**\n"
                        f"- Total variants: {result.get('total_variants', 0)}\n"
                        f"- Rows to update: {result.get('updated_count', 0)}\n"
                        f"- Rows to append: {result.get('appended_count', 0)}"
                    )
                else:
                    st.success(
                        f"✅ Successfully pushed {len(patches)} SKUs to Google Sheets"
                    )
                    st.info(
                        f"**Results:**\n"
                        f"- Total variants: {result.get('total_variants', 0)}\n"
                        f"- Rows updated: {result.get('updated_count', 0)}\n"
                        f"- Rows appended: {result.get('appended_count', 0)}"
                    )

                    # Log publish events for each SKU
                    for patch in patches:
                        meta = patch.get("_meta", {})
                        sku = meta.get("master_sku", "")
                        if sku:
                            log_publish_event(
                                db_path,
                                master_sku=sku,
                                platform="google",
                                environment=environment,
                                action="publish",
                                patch_file=patch.get("_source_file", ""),
                                status="success",
                                quality_score=meta.get("quality_score"),
                                approval_status=meta.get("approval_status"),
                                batch_id=batch_id,
                            )

                    # Update batch status
                    update_batch_status(
                        db_path,
                        batch_id=batch_id,
                        status="published",
                        success_count=len(patches),
                        failed_count=0,
                    )

                # Show detailed breakdown
                with st.expander("📊 Detailed Results"):
                    for patch in patches:
                        meta = patch.get("_meta", {})
                        sku = meta.get("master_sku", "")
                        variants = patch.get("variants", [])
                        st.markdown(
                            f"**{sku}**: {len(variants)} variants, "
                            f"score: {meta.get('quality_score', 0):.1f}%"
                        )
            else:
                errors = result.get("errors", ["Unknown error"])
                st.error(f"❌ Failed to push to Google Sheets")
                for error in errors:
                    st.error(f"• {error}")

                if not dry_run:
                    update_batch_status(
                        db_path,
                        batch_id=batch_id,
                        status="failed",
                        success_count=0,
                        failed_count=len(patches),
                    )

        except Exception as e:
            st.error(f"❌ Error: {e}")
            import traceback

            with st.expander("Error Details"):
                st.code(traceback.format_exc())


def _execute_batch_action(
    batch_id: str,
    batch_skus: list[str],
    platform: str,
    dry_run: bool,
    db_path: Path,
    environment: str = "staging",
) -> None:
    """Execute a batch publish action."""
    from datetime import datetime, timezone
    from pathlib import Path as PathLib

    patches_dir = PathLib("dashboard_data/lifestyle-eval-candidate")

    # Handle google as Google Sheets batch operation
    if platform == "google":
        _execute_google_sheets_batch(
            batch_id=batch_id,
            batch_skus=batch_skus,
            patches_dir=patches_dir,
            dry_run=dry_run,
            db_path=db_path,
            environment=environment,
        )
        return

    # For "all", handle Google via Sheets separately, then do Bing/Shopify per-SKU
    if platform == "all":
        st.markdown("### Google (via Sheets)")
        _execute_google_sheets_batch(
            batch_id=batch_id,
            batch_skus=batch_skus,
            patches_dir=patches_dir,
            dry_run=dry_run,
            db_path=db_path,
            environment=environment,
        )
        st.divider()
        st.markdown("### Bing & Shopify")
        platforms = ["bing", "shopify"]
    else:
        platforms = [platform]

    results = []
    success_count = 0
    failed_count = 0

    with st.spinner(
        f"{'Previewing' if dry_run else 'Publishing'} {len(batch_skus)} SKUs..."
    ):
        for sku in batch_skus:
            sku_results = {"sku": sku, "platforms": {}}

            for plat in platforms:
                # Load patch
                patch_file = patches_dir / f"{plat}-patch-{sku}.json"
                if not patch_file.exists():
                    sku_results["platforms"][plat] = {
                        "success": False,
                        "error": "Patch file not found",
                    }
                    continue

                try:
                    import json

                    patch = json.loads(patch_file.read_text())

                    if plat == "shopify":
                        title = patch.get("title", "")
                        description = patch.get("body_html", "")
                        product_id = patch.get("productId")

                        if dry_run:
                            sku_results["platforms"][plat] = {
                                "success": True,
                                "dry_run": True,
                                "product_id": product_id,
                                "title": (
                                    title[:50] + "..." if len(title) > 50 else title
                                ),
                            }
                        else:
                            from feedops.integrations.shopify_catalog import (
                                publish_to_shopify,
                                upload_selected_lifestyle_image,
                            )

                            result = publish_to_shopify(
                                product_id=str(product_id),
                                title=title,
                                description_html=description,
                                environment=environment,
                                dry_run=False,
                            )
                            sku_results["platforms"][plat] = result
                            if result.get("success"):
                                success_count += 1

                                # Upload lifestyle image if approved
                                try:
                                    approval = get_sku_approval(db_path, master_sku=sku)
                                    if approval and approval.get("image_approved"):
                                        upload_selected_lifestyle_image(
                                            patch, images_base_dir=patches_dir,
                                        )
                                except Exception:
                                    pass  # Image upload is best-effort

                                # Log publish event
                                from feedops.db import log_publish_event

                                meta = patch.get("_meta", {})
                                log_publish_event(
                                    db_path,
                                    master_sku=sku,
                                    platform="shopify",
                                    environment=environment,
                                    action="publish",
                                    patch_file=str(patch_file),
                                    status="success",
                                    quality_score=meta.get("quality_score"),
                                    approval_status=meta.get("approval_status"),
                                    batch_id=batch_id,
                                )
                            else:
                                failed_count += 1

                    elif plat == "bing":
                        title = patch.get("title", "")
                        variants = patch.get("variants", [])

                        if dry_run:
                            sku_results["platforms"][plat] = {
                                "success": True,
                                "dry_run": True,
                                "title": (
                                    title[:50] + "..." if len(title) > 50 else title
                                ),
                                "variant_count": len(variants),
                            }
                        else:
                            sku_results["platforms"][plat] = {
                                "success": True,
                                "message": "Feed generated (Bing push requires API setup)",
                                "variant_count": len(variants),
                            }
                            success_count += 1

                            # Log publish event for Bing
                            from feedops.db import log_publish_event

                            meta = patch.get("_meta", {})
                            log_publish_event(
                                db_path,
                                master_sku=sku,
                                platform="bing",
                                environment=environment,
                                action="publish",
                                patch_file=str(patch_file),
                                status="success",
                                quality_score=meta.get("quality_score"),
                                approval_status=meta.get("approval_status"),
                                batch_id=batch_id,
                            )

                except Exception as e:
                    sku_results["platforms"][plat] = {
                        "success": False,
                        "error": str(e),
                    }
                    failed_count += 1

            results.append(sku_results)

    # Display results
    if dry_run:
        st.success(f"✅ Preview complete for {len(batch_skus)} SKUs")
    else:
        st.success(f"✅ Batch executed: {success_count} success, {failed_count} failed")

        # Update batch status
        from feedops.db import update_batch_status

        update_batch_status(
            db_path,
            batch_id=batch_id,
            status="published" if failed_count == 0 else "partial",
            success_count=success_count,
            failed_count=failed_count,
        )

    # Show detailed results
    for result in results:
        with st.expander(f"📦 {result['sku']}"):
            for plat, plat_result in result["platforms"].items():
                if plat_result.get("success"):
                    if plat_result.get("dry_run"):
                        st.info(f"**{plat.upper()}** - Would publish:")
                        if plat_result.get("title"):
                            st.code(plat_result["title"])
                        if plat_result.get("variant_count"):
                            st.caption(
                                f"Includes {plat_result['variant_count']} variants"
                            )
                    else:
                        st.success(
                            f"**{plat.upper()}** - {plat_result.get('message', 'Published')}"
                        )
                else:
                    st.error(
                        f"**{plat.upper()}** - Error: {plat_result.get('error', 'Unknown error')}"
                    )


def _execute_rollback(
    batch_id: str,
    batch_skus: list[str],
    dry_run: bool,
    db_path: Path,
) -> None:
    """Execute rollback for a published batch."""
    from feedops.db import update_batch_status
    from feedops.rollback import batch_rollback

    patches_dir = Path("dashboard_data/lifestyle-eval-candidate")

    with st.spinner(
        f"{'Previewing' if dry_run else 'Executing'} rollback for {len(batch_skus)} SKUs..."
    ):
        all_results = []
        for platform in ["google", "shopify"]:
            results = batch_rollback(
                batch_skus,
                platform,
                patches_dir=patches_dir,
                db_path=db_path,
                dry_run=dry_run,
            )
            all_results.extend(results)

        # Display results
        successes = sum(1 for r in all_results if r.success)
        failures = sum(1 for r in all_results if not r.success)

        if dry_run:
            st.info(f"Would rollback {successes} SKU-platform combinations ({failures} not available)")
            for r in all_results:
                if r.success:
                    st.markdown(
                        f"- **{r.sku}** ({r.platform}): restore original title"
                    )
                    if r.original_title:
                        with st.expander(f"Preview: {r.sku} ({r.platform})"):
                            st.markdown(f"**Original title:** {r.original_title}")
                            if r.original_description:
                                desc_preview = r.original_description[:200]
                                st.markdown(f"**Original description:** {desc_preview}...")
        else:
            if successes > 0:
                st.success(f"Rolled back {successes}/{len(all_results)} successfully")
            if failures > 0:
                st.warning(f"{failures} rollbacks failed or unavailable")
            for r in all_results:
                if r.success:
                    st.markdown(f"- ✅ **{r.sku}** ({r.platform}): {r.message}")
                else:
                    st.markdown(f"- ❌ **{r.sku}** ({r.platform}): {r.error or r.message}")

            # Update batch status
            update_batch_status(
                db_path,
                batch_id=batch_id,
                status="rolled_back",
            )
            st.rerun()


def filter_sku_data(
    data: list[SKUData],
    search_query: str | None = None,
    category: str | None = None,
    collection: str | None = None,
    score_filter: str | None = None,
) -> list[SKUData]:
    """Filter SKU data based on criteria."""
    filtered = data

    if search_query:
        query_lower = search_query.lower()
        filtered = [d for d in filtered if query_lower in d.sku.lower()]

    if category:
        filtered = [
            d for d in filtered if d.original and d.original.category == category
        ]

    if collection:
        filtered = [
            d for d in filtered if d.original and d.original.collection == collection
        ]

    if score_filter:
        if score_filter == "Improved":
            filtered = [d for d in filtered if d.composite_delta > 0.5]
        elif score_filter == "Declined":
            filtered = [d for d in filtered if d.composite_delta < -0.5]
        elif score_filter == "Unchanged":
            filtered = [d for d in filtered if abs(d.composite_delta) <= 0.5]

    return filtered


def _sku_has_lifestyle_images(sku_data: SKUData) -> bool:
    """Check if SKU has any lifestyle images."""
    for platform in ["google", "bing", "shopify"]:
        content = sku_data.candidate.get(platform)
        if content and content.lifestyle_images:
            return True
    return False


def render_sku_panel(
    sku_data: SKUData, platform: str, db_path: Path | None = None
) -> None:
    """Render a single SKU review panel with approval controls."""
    # Get scores
    b_score = sku_data.baseline_scores.get("composite", 0.0)
    c_score = sku_data.candidate_scores.get("composite", 0.0)
    delta = sku_data.composite_delta

    # Format delta display
    if delta > 0.5:
        delta_display = f"🟢 +{delta:.1f}%"
        delta_class = "score-improved"
    elif delta < -0.5:
        delta_display = f"🔴 {delta:.1f}%"
        delta_class = "score-declined"
    else:
        delta_display = f"⚪ {delta:+.1f}%"
        delta_class = "score-unchanged"

    # Get image URL
    image_url = ""
    if sku_data.original and sku_data.original.image_url:
        image_url = sku_data.original.image_url
    elif sku_data.candidate_report and sku_data.candidate_report.image_url:
        image_url = sku_data.candidate_report.image_url

    # Get current approval state if db_path provided
    current_approval = None
    if db_path:
        current_approval = get_sku_approval(db_path, master_sku=sku_data.sku)

    # Determine approval indicator for expander title
    approval_indicator = ""
    if current_approval:
        if current_approval["approval_status"] == "approved":
            approval_indicator = " ✅"
        elif current_approval["approval_status"] == "revision":
            approval_indicator = " 🔄"
        elif current_approval["approval_status"] == "rejected":
            approval_indicator = " ❌"

    # SKU header
    with st.expander(
        f"**{sku_data.sku}**{approval_indicator} | {c_score:.1f}% ({delta_display})",
        expanded=False,
    ):
        # Product image and basic info
        col_img, col_info = st.columns([1, 3])

        with col_img:
            if image_url:
                st.image(image_url, width=200, caption=sku_data.sku)
            else:
                st.caption("No image available")

        with col_info:
            if sku_data.original:
                st.markdown(f"**Category:** {sku_data.original.category}")
                st.markdown(f"**Collection:** {sku_data.original.collection}")
                _render_collection_badge(sku_data.original.collection)

            # Auto-calculated approval status from quality evaluation
            status = sku_data.candidate_scores.get("approval_status", "")
            if not status and sku_data.candidate_report:
                status = sku_data.candidate_report.status

            if status:
                status_colors = {
                    "approved": "🟢",
                    "revise": "🟡",
                    "rejected": "🔴",
                }
                status_emoji = status_colors.get(status.lower(), "⚪")
                st.markdown(f"**Auto-Status:** {status_emoji} {status.upper()}")

            # Manual approval status
            if current_approval:
                manual_status = current_approval["approval_status"]
                manual_colors = {
                    "pending": "⏳",
                    "approved": "✅",
                    "revision": "🔄",
                    "rejected": "❌",
                }
                st.markdown(
                    f"**Manual Status:** {manual_colors.get(manual_status, '❓')} {manual_status.upper()}"
                )

        st.divider()

        # Approval Controls Section (only if db_path provided)
        if db_path:
            render_approval_controls(sku_data, db_path, current_approval)
            st.divider()

        # Lifestyle images (collapsed by default, only show if images exist)
        has_lifestyle_images = _sku_has_lifestyle_images(sku_data)
        if has_lifestyle_images:
            with st.expander("🖼️ Lifestyle Images", expanded=False):
                render_lifestyle_images_panel(sku_data)

        # Three-way content comparison (always visible - this is the primary content)
        render_content_comparison(sku_data, platform)

        # Reasoning inputs (collapsed by default)
        with st.expander("💡 Reasoning Inputs", expanded=False):
            render_reasoning_panel(sku_data, show_header=False)

        # Quality scores (collapsed by default)
        with st.expander("📊 Quality Scores", expanded=False):
            render_score_panel(sku_data, show_header=False)


def render_approval_controls(
    sku_data: SKUData,
    db_path: Path,
    current_approval: dict | None,
) -> None:
    """Render element-level approval controls for a SKU."""
    st.subheader("📋 Approval")

    # Determine CSS class based on status
    status_class = ""
    if current_approval:
        if current_approval["approval_status"] == "approved":
            status_class = "approval-approved"
        elif current_approval["approval_status"] == "revision":
            status_class = "approval-revision"
        elif current_approval["approval_status"] == "rejected":
            status_class = "approval-rejected"

    # Get available finishes
    available_finishes = load_available_finishes()

    # Initialize checkbox values from current approval
    default_title = (
        current_approval["title_approved"]
        if current_approval and current_approval["title_approved"] is not None
        else False
    )
    default_desc = (
        current_approval["description_approved"]
        if current_approval and current_approval["description_approved"] is not None
        else False
    )
    default_image = (
        current_approval["image_approved"]
        if current_approval and current_approval["image_approved"] is not None
        else False
    )
    default_finish = current_approval["selected_finish"] if current_approval else None

    # Element-level approval checkboxes
    col1, col2, col3 = st.columns(3)
    with col1:
        title_approved = st.checkbox(
            "✅ Title",
            value=default_title,
            key=f"title_approve_{sku_data.sku}",
            help="Approve the optimized title",
        )
    with col2:
        desc_approved = st.checkbox(
            "✅ Description",
            value=default_desc,
            key=f"desc_approve_{sku_data.sku}",
            help="Approve the optimized description",
        )
    with col3:
        image_approved = st.checkbox(
            "✅ Lifestyle Image",
            value=default_image,
            key=f"image_approve_{sku_data.sku}",
            help="Approve the generated lifestyle image",
        )

    # If image approved, show finish selector
    selected_finish = None
    selected_image_index = None
    if image_approved:
        col1, col2 = st.columns(2)
        with col1:
            if available_finishes:
                finish_options = [_ALL_FINISHES_LABEL, *available_finishes]
                finish_index = 0
                if default_finish == _ALL_FINISHES_SENTINEL:
                    finish_index = 0
                elif default_finish and default_finish in available_finishes:
                    finish_index = finish_options.index(default_finish)
                selected_finish_choice = st.selectbox(
                    "Apply lifestyle image to",
                    options=finish_options,
                    index=finish_index,
                    key=f"finish_approve_{sku_data.sku}",
                    help="Choose a single finish, or approve the selected lifestyle image for all finishes.",
                )
                selected_finish = (
                    _ALL_FINISHES_SENTINEL
                    if selected_finish_choice == _ALL_FINISHES_LABEL
                    else selected_finish_choice
                )
            else:
                st.caption("No finishes available")

        with col2:
            # Get number of lifestyle images available
            candidate_content = (
                sku_data.candidate.get("google")
                or sku_data.candidate.get("bing")
                or sku_data.candidate.get("shopify")
            )
            lifestyle_images = (
                getattr(candidate_content, "lifestyle_images", None)
                if candidate_content
                else None
            )
            if lifestyle_images:
                successful_images = [
                    img
                    for img in lifestyle_images
                    if img.get("generation_success", False)
                ]
                if not successful_images:
                    st.caption("No successful lifestyle images available")
                else:
                    image_options = [
                        f"Variation {img.get('variation_num', i + 1)}"
                        for i, img in enumerate(successful_images)
                    ]
                    stored_idx = (
                        current_approval.get("selected_image_index")
                        if current_approval
                        else None
                    )
                    default_idx = _coerce_non_negative_int(stored_idx, default=0)
                    if stored_idx is None:
                        selected_num = getattr(
                            candidate_content, "selected_lifestyle_image", None
                        )
                        if isinstance(selected_num, int):
                            idx_from_patch = _find_variation_index(
                                successful_images, selected_num
                            )
                            if idx_from_patch is not None:
                                default_idx = idx_from_patch
                    default_idx = _clamp_index(default_idx, len(successful_images))
                    selected_image_index = st.selectbox(
                        "Select Image Variation",
                        options=range(len(successful_images)),
                        format_func=lambda x: image_options[x],
                        index=default_idx,
                        key=f"image_idx_{sku_data.sku}",
                        help="Overrides the AI-selected image when approving. Saved to patch JSON and the approvals database.",
                    )

    # Revision notes (for flagging)
    revision_notes = st.text_area(
        "Revision Notes (optional)",
        value=current_approval.get("notes", "") if current_approval else "",
        placeholder="Describe what needs to be changed...",
        key=f"revision_notes_{sku_data.sku}",
        height=80,
    )

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve", key=f"approve_btn_{sku_data.sku}", type="primary"):
            selected_variation_num = None
            if image_approved:
                candidate_content = (
                    sku_data.candidate.get("google")
                    or sku_data.candidate.get("bing")
                    or sku_data.candidate.get("shopify")
                )
                lifestyle_images = (
                    getattr(candidate_content, "lifestyle_images", None)
                    if candidate_content
                    else None
                )
                if (
                    candidate_content
                    and lifestyle_images
                    and isinstance(selected_image_index, int)
                ):
                    successful_images = [
                        img
                        for img in lifestyle_images
                        if img.get("generation_success", False)
                    ]
                    if 0 <= selected_image_index < len(successful_images):
                        selected_variation_num = successful_images[
                            selected_image_index
                        ].get("variation_num")

            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                title_approved=title_approved,
                description_approved=desc_approved,
                image_approved=image_approved,
                selected_finish=selected_finish,
                selected_image_index=selected_image_index,
                status="approved",
                notes=None,
                approved_by="dashboard",
            )
            if image_approved and isinstance(selected_variation_num, int):
                exports_dir_raw = st.session_state.get(
                    "feedops_candidate_exports_dir",
                    "dashboard_data/lifestyle-eval-candidate",
                )
                exports_dir = Path(exports_dir_raw)
                _update_selected_lifestyle_image_in_patches(
                    exports_dir=exports_dir,
                    master_sku=sku_data.sku,
                    selected_variation_num=selected_variation_num,
                )
            st.success("SKU approved!")
            st.rerun()

    with col2:
        if st.button("🔄 Flag for Revision", key=f"revise_btn_{sku_data.sku}"):
            if not revision_notes:
                st.warning(
                    "Please add revision notes explaining what needs to be changed."
                )
            else:
                save_sku_approval(
                    db_path,
                    master_sku=sku_data.sku,
                    title_approved=title_approved,
                    description_approved=desc_approved,
                    image_approved=image_approved,
                    selected_finish=selected_finish,
                    selected_image_index=selected_image_index,
                    status="revision",
                    notes=revision_notes,
                    approved_by="dashboard",
                )
                st.warning("SKU flagged for revision")
                st.rerun()

    with col3:
        if st.button("❌ Reject", key=f"reject_btn_{sku_data.sku}"):
            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                title_approved=False,
                description_approved=False,
                image_approved=False,
                status="rejected",
                notes=revision_notes,
                approved_by="dashboard",
            )
            st.error("SKU rejected")
            st.rerun()


def render_lifestyle_images_panel(sku_data: SKUData) -> None:
    """Render lifestyle images if available."""
    # Get candidate content from any platform (all platforms have same lifestyle images)
    candidate_content = (
        sku_data.candidate.get("google")
        or sku_data.candidate.get("bing")
        or sku_data.candidate.get("shopify")
    )
    if not candidate_content:
        return

    # Check if lifestyle images exist
    lifestyle_images = getattr(candidate_content, "lifestyle_images", None) or []
    if not lifestyle_images:
        return

    # Filter successful generations
    successful = [
        img for img in lifestyle_images if img.get("generation_success", False)
    ]

    if not successful:
        st.warning("Lifestyle image generation failed for this product")
        for img in lifestyle_images:
            if img.get("error_message"):
                st.caption(f"Error: {img['error_message']}")
        return

    st.info(f"✅ {len(successful)} variations generated")

    # Display variations in columns
    cols = st.columns(len(successful))

    selected_variation = getattr(candidate_content, "selected_lifestyle_image", None)

    for i, img in enumerate(successful):
        with cols[i]:
            # Display image
            image_path = img.get("image_path", "")
            variation_num = img.get("variation_num", i + 1)

            if image_path and Path(image_path).exists():
                st.image(
                    image_path,
                    caption=f"Variation {variation_num}",
                    width="stretch",
                )

                # Selection indicator
                if selected_variation == variation_num:
                    st.success("✓ Selected")
                else:
                    st.caption(f"Variation {variation_num}")
            else:
                st.warning(f"Image not found: {image_path}")

    # Show selected image details if available
    if selected_variation:
        st.divider()
        st.markdown("**Selected Image Details**")

        selected = next(
            (
                img
                for img in successful
                if img.get("variation_num") == selected_variation
            ),
            None,
        )

        if selected:
            col1, col2 = st.columns([2, 1])

            with col1:
                image_path = selected.get("image_path", "")
                if image_path and Path(image_path).exists():
                    st.image(image_path, width="stretch")

            with col2:
                st.metric("Variation", f"#{selected.get('variation_num', 'N/A')}")
                st.metric("Generated", selected.get("timestamp", "N/A"))

                prompt_used = selected.get("prompt_used", "")
                if prompt_used:
                    with st.expander("View Prompt"):
                        st.code(prompt_used, language="text")

    st.divider()


def render_content_comparison(sku_data: SKUData, platform: str) -> None:
    """Render three-way content comparison with all platforms."""
    st.subheader("Content Comparison")

    # Get original content (same for all platforms)
    original_title = ""
    original_desc = ""
    if sku_data.original:
        original_title = sku_data.original.title
        original_desc = sku_data.original.description

    with st.expander("Shopify (Live)", expanded=False):
        st.caption(
            "Optional diagnostic view of what is currently on Shopify. "
            "Cache-first (default 24h TTL); use Refresh to force a new fetch."
        )
        enable_live = st.checkbox(
            "Enable Shopify (Live) lookup",
            value=False,
            key=f"shopify_live_enable_{sku_data.sku}",
        )
        if enable_live:
            ttl_hours = st.number_input(
                "Cache TTL (hours)",
                min_value=1.0,
                max_value=168.0,
                value=24.0,
                step=1.0,
                key=f"shopify_live_ttl_{sku_data.sku}",
                help="Only fetches from Shopify when cached data is older than this TTL, unless you click Refresh.",
            )
            force_refresh = st.button(
                "Refresh from Shopify",
                key=f"shopify_live_refresh_{sku_data.sku}",
                help="Forces a fresh Shopify fetch for the currently selected SKU.",
            )
            catalog_path = st.session_state.get("feedops_catalog_path") or None
            live = load_shopify_live_snapshot(
                sku_data.sku,
                force_refresh=force_refresh,
                cache_ttl_hours=float(ttl_hours),
                catalog_path=catalog_path,
            )
            if live.error:
                st.warning(live.error)
            else:
                label = "Fetched just now"
                if live.data_source == "shopify_cached" and live.age_hours is not None:
                    label = f"Cached ~{live.age_hours:.1f}h ago"
                st.caption(f"Source: `{live.data_source}` — {label}")
                st.markdown("**Title:**")
                st.markdown(
                    f"<div class='content-box'>{html.escape(live.title) if live.title else '<em>Not available</em>'}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("**Description:**")
                st.markdown(
                    f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(live.description) if live.description else '<em>Not available</em>'}</div>",
                    unsafe_allow_html=True,
                )

    # Platform info for info boxes
    platform_info = {
        "google": {
            "name": "Google Shopping / Performance Max",
            "icon": "🔍",
            "color": "#4285F4",
            "optimization": [
                "**Semantic matching** - Google's AI understands synonyms and context",
                "**Feed as seed** - Title/desc used to generate PMax ad assets",
                "**First 70 chars critical** - Most visible in search results",
                "**Natural language** - Match how customers actually search",
            ],
            "differences": "Google uses AI to dynamically reorder keywords based on search queries. Front-load high-value terms.",
        },
        "bing": {
            "name": "Microsoft / Bing Shopping",
            "icon": "🅱️",
            "color": "#00A4EF",
            "optimization": [
                "**Literal keyword matching** - More exact than Google",
                "**Include explicit synonyms** - 'towel bar / towel holder / towel rack'",
                "**Copilot integration** - Requires high confidence scores",
                "**Exact Match keywords** - Override Ad Rank in auctions",
            ],
            "differences": "Bing requires explicit keyword variations since matching is more literal. Include synonyms in descriptions.",
        },
        "shopify": {
            "name": "Shopify / On-Site",
            "icon": "🛒",
            "color": "#96BF48",
            "optimization": [
                "**SEO-focused title** - Becomes H1 tag, affects organic ranking",
                "**HTML formatting** - Use `<ul>/<li>` for scannable highlights",
                "**Mobile-first** - Use accordions over tabs for specs",
                "**Conversion copy** - Support both SEO and purchase decision",
            ],
            "differences": "Shopify uses HTML body content. Description must work for both search engines and on-page conversion.",
        },
    }

    # Render each platform as a section
    for plat_key in ["google", "bing", "shopify"]:
        info = platform_info[plat_key]
        is_main = plat_key == platform

        baseline_content = sku_data.baseline.get(plat_key)
        candidate_content = sku_data.candidate.get(plat_key)

        # Determine what content is available
        has_baseline = baseline_content is not None
        has_candidate = candidate_content is not None

        baseline_title = baseline_content.title if baseline_content else ""
        baseline_desc = baseline_content.description if baseline_content else ""

        candidate_title = candidate_content.title if candidate_content else ""
        candidate_desc = candidate_content.description if candidate_content else ""

        # Get scores for this platform
        b_score = sku_data.baseline_scores.get(plat_key, {}).get("composite", 0)
        c_score = sku_data.candidate_scores.get(plat_key, {}).get("composite", 0)
        score_delta = c_score - b_score

        # Build expander label based on available content
        if not has_baseline and not has_candidate:
            # No baseline or candidate - show only Original
            expander_label = (
                f"{info['icon']} **{info['name']}** — Original content only"
            )
        else:
            # Show score and delta when we have comparison content
            if score_delta > 0.5:
                delta_display = f"🟢 +{score_delta:.1f}%"
            elif score_delta < -0.5:
                delta_display = f"🔴 {score_delta:.1f}%"
            else:
                delta_display = f"⚪ {score_delta:+.1f}%"
            expander_label = f"{info['icon']} **{info['name']}** — Score: {c_score:.1f}% ({delta_display})"

        with st.expander(expander_label, expanded=is_main):
            # Platform info box
            st.info(f"**Why {info['name']} is different:** {info['differences']}")

            # Optimization goals in a collapsible
            with st.expander("📋 Optimization Goals", expanded=False):
                for goal in info["optimization"]:
                    st.markdown(f"• {goal}")

            # For Google/Bing, prefer reviewing per-variant content since variants are the
            # shippable unit (offerId/item_id) and the patch JSON is the source of truth.
            show_variant_review = plat_key in ("google", "bing")
            selected_finish: str | None = None
            selected_option_id: str | None = None
            variant_mode = False
            if show_variant_review:
                baseline_variants = _extract_variants(baseline_content)
                candidate_variants = _extract_variants(candidate_content)
                finishes_set: set[str] = set()
                for v in candidate_variants + baseline_variants:
                    finish = _variant_finish(v)
                    if finish:
                        finishes_set.add(finish)
                finishes = sorted(finishes_set)
                if finishes:
                    st.success(
                        "Reviewing per-variant (finish) title/description from the patch JSON. "
                        "This matches what is published for each offerId."
                    )

                    default_finish = None
                    if candidate_variants:
                        default_finish = _variant_finish(candidate_variants[0])
                    if not default_finish and baseline_variants:
                        default_finish = _variant_finish(baseline_variants[0])
                    finish_index = (
                        finishes.index(default_finish)
                        if default_finish in finishes
                        else 0
                    )

                    selected_finish = st.selectbox(
                        "Finish",
                        options=finishes,
                        index=finish_index,
                        key=f"content_finish_{plat_key}_{sku_data.sku}",
                    )

                    option_variants = [
                        v
                        for v in candidate_variants
                        if _variant_finish(v) == selected_finish
                    ] or [
                        v
                        for v in baseline_variants
                        if _variant_finish(v) == selected_finish
                    ]
                    option_ids = [_variant_option_id(v) for v in option_variants]
                    if len(option_ids) > 1:
                        selected_option_id = st.selectbox(
                            "Variant (size/option)",
                            options=option_ids,
                            key=f"content_option_{plat_key}_{sku_data.sku}",
                        )
                    else:
                        selected_option_id = option_ids[0] if option_ids else None

                    # Apply the selected variant mapping to baseline/candidate display fields.
                    baseline_selected = _choose_variant(
                        baseline_variants,
                        finish=selected_finish,
                        option_id=selected_option_id,
                    )
                    candidate_selected = _choose_variant(
                        candidate_variants,
                        finish=selected_finish,
                        option_id=selected_option_id,
                    )

                    if baseline_selected:
                        baseline_title = (
                            baseline_selected.get("title") or baseline_title
                        )
                        baseline_desc = (
                            baseline_selected.get("description") or baseline_desc
                        )
                    if candidate_selected:
                        candidate_title = (
                            candidate_selected.get("title") or candidate_title
                        )
                        candidate_desc = (
                            candidate_selected.get("description") or candidate_desc
                        )

                    with st.expander(
                        "Advanced: Primary item payload (patch top-level title/description)",
                        expanded=False,
                    ):
                        st.caption(
                            "These are the patch's top-level title/description fields. "
                            "For variant-heavy SKUs, focus on the per-variant content above."
                        )
                        adv_col1, adv_col2 = st.columns(2)
                        with adv_col1:
                            st.markdown("**Baseline primary title/description**")
                            st.markdown(
                                f"<div class='content-box'>{html.escape((baseline_content.title if baseline_content else '') or '')}</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape((baseline_content.description if baseline_content else '') or '')}</div>",
                                unsafe_allow_html=True,
                            )
                        with adv_col2:
                            st.markdown("**Candidate primary title/description**")
                            st.markdown(
                                f"<div class='content-box'>{html.escape((candidate_content.title if candidate_content else '') or '')}</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape((candidate_content.description if candidate_content else '') or '')}</div>",
                                unsafe_allow_html=True,
                            )

            # Conditional column rendering based on available content
            if not has_baseline and not has_candidate:
                # Only Original column (full width)
                st.markdown("##### Baseline (Snapshot)")
                st.markdown(
                    "<div class='version-label'>Deterministic snapshot for review</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("**Title:**")
                st.markdown(
                    f"<div class='content-box'>{html.escape(original_title) if original_title else '<em>Not available</em>'}</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("**Description:**")
                if plat_key == "shopify" and original_desc:
                    st.markdown(
                        f"<div class='content-box'>{original_desc}</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(original_desc) if original_desc else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

            elif has_baseline and has_candidate:
                # Three columns for full comparison
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.markdown("##### Baseline (Snapshot)")
                    st.markdown(
                        "<div class='version-label'>Deterministic snapshot for review</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Title:**")
                    st.markdown(
                        f"<div class='content-box'>{html.escape(original_title) if original_title else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Description:**")
                    if plat_key == "shopify" and original_desc:
                        st.markdown(
                            f"<div class='content-box'>{original_desc}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(original_desc) if original_desc else '<em>Not available</em>'}</div>",
                            unsafe_allow_html=True,
                        )

                with col2:
                    st.markdown("##### Baseline (Previous)")
                    st.markdown(
                        f"<div class='version-label'>Score: {b_score:.1f}%</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Title:**")
                    st.markdown(
                        f"<div class='content-box'>{html.escape(baseline_title) if baseline_title else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Description:**")
                    if plat_key == "shopify" and baseline_desc:
                        st.markdown(
                            f"<div class='content-box'>{baseline_desc}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(baseline_desc) if baseline_desc else '<em>Not available</em>'}</div>",
                            unsafe_allow_html=True,
                        )

                with col3:
                    st.markdown("##### Candidate (Current)")
                    st.markdown(
                        f"<div class='version-label'>Score: {c_score:.1f}%</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Title:**")
                    st.markdown(
                        f"<div class='content-box'>{html.escape(candidate_title) if candidate_title else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Description:**")
                    if plat_key == "shopify" and candidate_desc:
                        st.markdown(
                            f"<div class='content-box'>{candidate_desc}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(candidate_desc) if candidate_desc else '<em>Not available</em>'}</div>",
                            unsafe_allow_html=True,
                        )

            else:
                # Two columns: Original + whichever exists (baseline or candidate)
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("##### Baseline (Snapshot)")
                    st.markdown(
                        "<div class='version-label'>Deterministic snapshot for review</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Title:**")
                    st.markdown(
                        f"<div class='content-box'>{html.escape(original_title) if original_title else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Description:**")
                    if plat_key == "shopify" and original_desc:
                        st.markdown(
                            f"<div class='content-box'>{original_desc}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(original_desc) if original_desc else '<em>Not available</em>'}</div>",
                            unsafe_allow_html=True,
                        )

                with col2:
                    if has_baseline:
                        st.markdown("##### Baseline (Previous)")
                        st.markdown(
                            f"<div class='version-label'>Score: {b_score:.1f}%</div>",
                            unsafe_allow_html=True,
                        )
                        display_title = baseline_title
                        display_desc = baseline_desc
                    else:
                        st.markdown("##### Candidate (Current)")
                        st.markdown(
                            f"<div class='version-label'>Score: {c_score:.1f}%</div>",
                            unsafe_allow_html=True,
                        )
                        display_title = candidate_title
                        display_desc = candidate_desc

                    st.markdown("**Title:**")
                    st.markdown(
                        f"<div class='content-box'>{html.escape(display_title) if display_title else '<em>Not available</em>'}</div>",
                        unsafe_allow_html=True,
                    )

                    st.markdown("**Description:**")
                    if plat_key == "shopify" and display_desc:
                        st.markdown(
                            f"<div class='content-box'>{display_desc}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(display_desc) if display_desc else '<em>Not available</em>'}</div>",
                            unsafe_allow_html=True,
                        )


def render_reasoning_panel(sku_data: SKUData, show_header: bool = True) -> None:
    """Render the reasoning inputs panel."""
    if show_header:
        st.subheader("Reasoning Inputs")

    report = sku_data.candidate_report
    if not report:
        st.info("No report data available for this SKU.")
        return

    st.markdown(f"**Provider/Model:** {report.provider_model or 'Unknown'}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Keywords Used")

        if report.keywords:
            for key, value in report.keywords.items():
                if value:
                    # Display as chips
                    keywords = [k.strip() for k in str(value).split(",")]
                    chips_html = "".join(
                        f"<span class='keyword-chip'>{html.escape(k)}</span>"
                        for k in keywords[:10]  # Limit to 10
                    )
                    st.markdown(f"**{key}:**")
                    st.markdown(chips_html, unsafe_allow_html=True)
        else:
            st.caption("No keyword data available")

    with col2:
        st.markdown("##### Enrichment Context")

        if report.enrichment:
            for key, value in report.enrichment.items():
                if value:
                    display_key = key.replace("_", " ").title()
                    st.markdown(f"**{display_key}:** {value}")
        else:
            st.caption("No enrichment data available")

    # Expandable evidence + prompt (from report markdown)
    if report.evidence_markdown:
        with st.expander("Available Product Data"):
            st.markdown(report.evidence_markdown)

    if report.prompt_text:
        with st.expander("Full Prompt"):
            st.code(report.prompt_text, language="text")

    # Provider info (footer)
    st.caption(
        f"Model: {report.provider_model or 'Unknown'} | Cost: {report.estimated_cost or 'N/A'}"
    )


def render_score_panel(sku_data: SKUData, show_header: bool = True) -> None:
    """Render quality score visualization."""
    if show_header:
        st.subheader("Quality Scores")

    # Actual score dimensions from the evaluator
    dimensions = [
        ("ctr_proxy", "CTR Proxy (Title)"),
        ("cvr_proxy", "CVR Proxy (Description)"),
        ("brand_voice", "Brand Voice"),
    ]

    # Get scores from baseline and candidate
    baseline_scores = sku_data.baseline_scores
    candidate_scores = sku_data.candidate_scores

    # Create comparison table
    score_data = []
    for dim_key, display_name in dimensions:
        # Get platform average for each dimension
        b_vals = []
        c_vals = []
        for platform in ["google", "bing", "shopify"]:
            b_platform = baseline_scores.get(platform, {})
            c_platform = candidate_scores.get(platform, {})
            if dim_key in b_platform:
                b_vals.append(b_platform[dim_key])
            if dim_key in c_platform:
                c_vals.append(c_platform[dim_key])

        b_avg = sum(b_vals) / len(b_vals) if b_vals else 0
        c_avg = sum(c_vals) / len(c_vals) if c_vals else 0
        delta = c_avg - b_avg

        # Color code the delta
        delta_str = f"{delta:+.1f}" if delta else "0.0"

        score_data.append(
            {
                "Dimension": display_name,
                "Baseline": f"{b_avg:.1f}/10",
                "Candidate": f"{c_avg:.1f}/10",
                "Delta": delta_str,
            }
        )

    # Add composite row
    b_composite = baseline_scores.get("composite", 0)
    c_composite = candidate_scores.get("composite", 0)
    composite_delta = c_composite - b_composite

    score_data.append(
        {
            "Dimension": "**Composite**",
            "Baseline": f"**{b_composite:.1f}%**",
            "Candidate": f"**{c_composite:.1f}%**",
            "Delta": f"**{composite_delta:+.1f}%**",
        }
    )

    # Display as table
    st.table(score_data)

    # Visual bar chart for dimensions
    import pandas as pd

    chart_data = []
    has_data = False
    for dim_key, display_name in dimensions:
        b_vals = []
        c_vals = []
        for platform in ["google", "bing", "shopify"]:
            b_platform = baseline_scores.get(platform, {})
            c_platform = candidate_scores.get(platform, {})
            if dim_key in b_platform:
                b_vals.append(b_platform[dim_key])
            if dim_key in c_platform:
                c_vals.append(c_platform[dim_key])

        b_avg = sum(b_vals) / len(b_vals) if b_vals else 0
        c_avg = sum(c_vals) / len(c_vals) if c_vals else 0

        if b_avg > 0 or c_avg > 0:
            has_data = True

        chart_data.append(
            {"Dimension": display_name, "Baseline": b_avg, "Candidate": c_avg}
        )

    if has_data:
        df = pd.DataFrame(chart_data)
        df = df.set_index("Dimension")
        st.bar_chart(df)
    else:
        st.info("No score data available for chart")


def get_dashboard_debug_info(
    *,
    baseline_exports_dir: Path | str | None,
    candidate_exports_dir: Path | str | None,
    baseline_reports_dir: Path | str | None,
    candidate_reports_dir: Path | str | None,
) -> dict[str, int | str | None]:
    """Collect filesystem-level debug info for dashboard data sources."""

    def _count_files(path: Path | str | None, pattern: str) -> int:
        if not path:
            return 0
        path = Path(path)
        if not path.exists():
            return 0
        return sum(1 for _ in path.glob(pattern))

    return {
        "baseline_exports_dir": (
            str(baseline_exports_dir) if baseline_exports_dir else None
        ),
        "candidate_exports_dir": (
            str(candidate_exports_dir) if candidate_exports_dir else None
        ),
        "baseline_reports_dir": (
            str(baseline_reports_dir) if baseline_reports_dir else None
        ),
        "candidate_reports_dir": (
            str(candidate_reports_dir) if candidate_reports_dir else None
        ),
        "baseline_exports_count": _count_files(baseline_exports_dir, "*-patch-*.json"),
        "candidate_exports_count": _count_files(
            candidate_exports_dir, "*-patch-*.json"
        ),
        "baseline_reports_count": _count_files(baseline_reports_dir, "sku-*.md"),
        "candidate_reports_count": _count_files(candidate_reports_dir, "sku-*.md"),
    }


def format_variant_description(description: str, max_chars: int | None = None) -> str:
    """Format variant description for preview display."""
    if max_chars is None or max_chars <= 0:
        return description
    if len(description) <= max_chars:
        return description
    return description[:max_chars] + "..."


def _extract_variants(content: Any) -> list[dict[str, Any]]:
    variants = getattr(content, "variants", None) if content else None
    if not isinstance(variants, list):
        return []
    return [v for v in variants if isinstance(v, dict)]


def _variant_finish(variant: dict[str, Any]) -> str | None:
    meta = variant.get("_meta")
    if isinstance(meta, dict):
        finish = meta.get("finish")
        if isinstance(finish, str) and finish.strip():
            return finish.strip()

    title = variant.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    # Many patches encode finish in the variant title (e.g. "... | Autumn Sparkle | Carolina | Allied Brass")
    parts = [p.strip() for p in title.split("|") if p.strip()]
    if not parts:
        return None
    if parts and parts[-1].lower() == "allied brass":
        parts = parts[:-1]
    if len(parts) >= 3:
        return parts[-2]
    if len(parts) >= 2:
        return parts[-1]
    return None


def _variant_option_id(variant: dict[str, Any]) -> str:
    meta = variant.get("_meta")
    if isinstance(meta, dict):
        option_sku = meta.get("option_sku")
        if isinstance(option_sku, str) and option_sku.strip():
            return option_sku
    offer_id = variant.get("offerId")
    return offer_id if isinstance(offer_id, str) and offer_id.strip() else "(unknown)"


def _choose_variant(
    variants: list[dict[str, Any]],
    *,
    finish: str,
    option_id: str | None,
) -> dict[str, Any] | None:
    matching_finish = [v for v in variants if _variant_finish(v) == finish]
    if not matching_finish:
        return None
    if option_id:
        for v in matching_finish:
            if _variant_option_id(v) == option_id:
                return v
    return matching_finish[0]


def select_patch_variants_for_preview(
    sku_data: SKUData,
) -> tuple[str | None, list[dict[str, Any]]]:
    """Return (platform, variants) for the first candidate patch that has variants.

    The dashboard's Variant Preview must reflect the patch JSON (source of truth) when
    `variants` are present. This helper isolates selection logic so it can be unit tested
    without Streamlit rendering.
    """
    for platform_name in ("google", "bing"):
        candidate_content = sku_data.candidate.get(platform_name)
        platform_variants = (
            getattr(candidate_content, "variants", None) if candidate_content else None
        )
        if not isinstance(platform_variants, list) or not platform_variants:
            continue
        cleaned = [v for v in platform_variants if isinstance(v, dict)]
        if cleaned:
            return platform_name, cleaned
    return None, []


def render_variant_preview(sku_data: SKUData, show_divider: bool = True) -> None:
    """Render variant preview section with finish selector."""
    if show_divider:
        st.divider()
        st.subheader("Variant Preview")
    st.caption(
        "Preview how content will appear for specific finish variants. "
        "Lifestyle images above apply to all variants."
    )

    # Prefer previewing the actual patch variants (this is what will show on Google/Bing).
    variant_source_platform, variants = select_patch_variants_for_preview(sku_data)
    if variants:
        finishes = sorted(
            {
                v.get("_meta", {}).get("finish")
                for v in variants
                if v.get("_meta", {}).get("finish")
            }
        )
        if not finishes:
            st.warning(
                "No finish metadata found in patch variants; falling back to generated preview."
            )
        else:
            st.success(
                f"Previewing the exact per-variant title/description from the generated patch ({(variant_source_platform or 'unknown').title()})."
            )
            selected_finish = st.selectbox(
                "Select Finish to Preview",
                options=finishes,
                key=f"finish_select_{sku_data.sku}",
                help="Shows the exact title/description from the generated patch variants.",
            )

            finish_variants = [
                v
                for v in variants
                if v.get("_meta", {}).get("finish") == selected_finish
            ]
            if not finish_variants:
                st.info("No variants found for selected finish.")
                return

            chosen = finish_variants[0]
            if len(finish_variants) > 1:
                option_skus = [
                    v.get("_meta", {}).get("option_sku")
                    or v.get("offerId")
                    or "(unknown)"
                    for v in finish_variants
                ]
                selected_option = st.selectbox(
                    "Select Variant (Size/Option)",
                    options=option_skus,
                    key=f"option_select_{sku_data.sku}",
                    help="Some finishes have multiple variants (e.g., different sizes).",
                )
                idx = option_skus.index(selected_option)
                chosen = finish_variants[idx]

            variant_title = chosen.get("title", "")
            variant_description = chosen.get("description", "")
            category = sku_data.original.category if sku_data.original else None
            variant_keywords = generate_variant_keywords(selected_finish, category)

            # Display variant preview in two columns
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("##### Variant Title")
                st.markdown(
                    f"<div class='content-box'>{html.escape(variant_title) if variant_title else '<em>N/A</em>'}</div>",
                    unsafe_allow_html=True,
                )

                st.markdown("##### Variant Keywords")
                if variant_keywords:
                    chips_html = "".join(
                        f"<span class='keyword-chip'>{html.escape(kw)}</span>"
                        for kw in variant_keywords
                    )
                    st.markdown(chips_html, unsafe_allow_html=True)
                else:
                    st.caption("No keywords generated")

            with col2:
                st.markdown("##### Variant Description")
                preview_desc = format_variant_description(variant_description)
                st.markdown(
                    f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(preview_desc) if preview_desc else '<em>N/A</em>'}</div>",
                    unsafe_allow_html=True,
                )
            return

    # Fallback: generated variant preview (legacy). This is useful when patch variants are not present.
    # Use product-specific finishes if available, otherwise fall back to all finishes.
    available_finishes: list[str] = []
    if sku_data.original and sku_data.original.available_finishes:
        available_finishes = sku_data.original.available_finishes
        st.info(
            f"Showing {len(available_finishes)} finishes available for this product"
        )
    else:
        available_finishes = load_available_finishes()
        st.warning("Using all finishes (product-specific finish data not available)")

    if not available_finishes:
        st.info("Finish data not available. Ensure data/finishes.txt exists.")
        return

    fallback_content = (
        sku_data.candidate.get("google")
        or sku_data.candidate.get("bing")
        or sku_data.candidate.get("shopify")
    )
    if not fallback_content:
        st.info("No candidate content available for variant preview.")
        return

    base_title = fallback_content.title
    base_description = fallback_content.description

    collection_name = sku_data.original.collection if sku_data.original else None
    category = sku_data.original.category if sku_data.original else None

    selected_finish = st.selectbox(
        "Select Finish to Preview",
        options=available_finishes,
        key=f"finish_select_fallback_{sku_data.sku}",
        help="Generated preview (not pulled from patch variants).",
    )

    if not selected_finish:
        return

    variant_title = generate_variant_title(base_title, selected_finish)
    variant_description = generate_variant_description(
        base_description,
        selected_finish,
        collection_name=collection_name,
        category=category,
        platform="google",
    )
    variant_keywords = generate_variant_keywords(selected_finish, category)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### Variant Title")
        st.markdown(
            f"<div class='content-box'>{html.escape(variant_title)}</div>",
            unsafe_allow_html=True,
        )

        st.markdown("##### Variant Keywords")
        if variant_keywords:
            chips_html = "".join(
                f"<span class='keyword-chip'>{html.escape(kw)}</span>"
                for kw in variant_keywords
            )
            st.markdown(chips_html, unsafe_allow_html=True)
        else:
            st.caption("No keywords generated")

    with col2:
        st.markdown("##### Variant Description")
        preview_desc = format_variant_description(variant_description)
        st.markdown(
            f"<div class='content-box' style='white-space: pre-wrap;'>{html.escape(preview_desc)}</div>",
            unsafe_allow_html=True,
        )


def parse_args():
    """Parse command line arguments passed through Streamlit."""
    import argparse
    import os
    import sys

    # Streamlit passes args after "--"
    # Find the index of "--" in sys.argv
    try:
        sep_idx = sys.argv.index("--")
        args_to_parse = sys.argv[sep_idx + 1 :]
    except ValueError:
        args_to_parse = []

    parser = argparse.ArgumentParser(description="FeedOps Review Dashboard")
    parser.add_argument(
        "--baseline",
        "-b",
        default=str(BASELINE_EXPORTS_DIR),
        help="Baseline exports directory",
    )
    parser.add_argument(
        "--candidate",
        "-c",
        default=str(CANDIDATE_EXPORTS_DIR),
        help="Candidate exports directory",
    )
    parser.add_argument("--catalog", default=None, help="Path to Product Catalog.csv")
    parser.add_argument(
        "--baseline-reports", default=None, help="Baseline reports directory"
    )
    parser.add_argument(
        "--candidate-reports", default=None, help="Candidate reports directory"
    )

    args, _ = parser.parse_known_args(args_to_parse)

    # Also check environment variables (set by CLI launcher)
    args.baseline = os.environ.get("FEEDOPS_BASELINE_DIR", args.baseline)
    args.candidate = os.environ.get("FEEDOPS_CANDIDATE_DIR", args.candidate)
    args.catalog = os.environ.get("FEEDOPS_CATALOG_PATH", args.catalog)
    args.baseline_reports = os.environ.get(
        "FEEDOPS_BASELINE_REPORTS", args.baseline_reports
    )
    args.candidate_reports = os.environ.get(
        "FEEDOPS_CANDIDATE_REPORTS", args.candidate_reports
    )

    return args


def main():
    """Entry point for standalone execution."""
    args = parse_args()

    # Convert to paths and set defaults
    baseline_dir = Path(args.baseline)
    candidate_dir = Path(args.candidate)

    # Try to find default catalog and reports if not specified
    catalog_path = (
        Path(args.catalog) if args.catalog else Path("data/catalog/Product Catalog.csv")
    )
    baseline_reports = (
        Path(args.baseline_reports) if args.baseline_reports else BASELINE_REPORTS_DIR
    )
    candidate_reports = (
        Path(args.candidate_reports)
        if args.candidate_reports
        else CANDIDATE_REPORTS_DIR
    )

    # Check if paths exist
    if not baseline_dir.exists():
        st.error(f"Baseline exports directory not found: {baseline_dir}")
        st.info("Use --baseline to specify the correct path")
        st.stop()

    if not candidate_dir.exists():
        st.error(f"Candidate exports directory not found: {candidate_dir}")
        st.info("Use --candidate to specify the correct path")
        st.stop()

    run_dashboard(
        baseline_exports_dir=baseline_dir,
        candidate_exports_dir=candidate_dir,
        catalog_path=catalog_path if catalog_path.exists() else None,
        baseline_reports_dir=baseline_reports if baseline_reports.exists() else None,
        candidate_reports_dir=candidate_reports if candidate_reports.exists() else None,
    )


if __name__ == "__main__":
    main()
