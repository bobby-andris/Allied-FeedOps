"""Streamlit dashboard for reviewing optimized product content."""

from __future__ import annotations

import html
import os
import re
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
    get_revision_queue,
    get_sku_approval,
    init_db,
    save_sku_approval,
)
from feedops.pipeline.finish_injection import (
    generate_variant_description,
    generate_variant_keywords,
    generate_variant_title,
)
from feedops.quality.data_loader import SKUData, get_summary_stats, load_all_sku_data

# Default database path
DEFAULT_DB_PATH = Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


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
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("FeedOps Content Review Dashboard")

    # Initialize database
    db_path = DEFAULT_DB_PATH
    init_db(db_path)

    # Main navigation tabs
    tab_review, tab_revision, tab_batches = st.tabs(
        ["📋 Review Queue", "🔄 Revision Queue", "✅ Approved / Batches"]
    )

    # Load data with caching
    @st.cache_data
    def load_data():
        return load_all_sku_data(
            baseline_exports_dir=baseline_exports_dir,
            candidate_exports_dir=candidate_exports_dir,
            catalog_path=catalog_path,
            baseline_reports_dir=baseline_reports_dir,
            candidate_reports_dir=candidate_reports_dir,
        )

    with st.spinner("Loading data..."):
        all_sku_data = load_data()

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
    # Sidebar filters (shared across app)
    with st.sidebar:
        st.header("Filters")

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

    # Apply filters
    filtered_data = filter_sku_data(
        all_sku_data,
        search_query=search_query,
        category=selected_category if selected_category != "All" else None,
        collection=selected_collection if selected_collection != "All" else None,
        score_filter=score_filter if score_filter != "All" else None,
    )

    # Main content area
    st.caption(f"Showing {len(filtered_data)} of {len(all_sku_data)} SKUs")

    # Render each SKU with approval controls
    for sku_data in filtered_data:
        render_sku_panel(sku_data, platform.lower(), db_path=db_path)


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
            f"**{master_sku}** — Flagged {approval['reviewed_at'][:10] if approval['reviewed_at'] else 'N/A'}",
            expanded=False,
        ):
            # Show revision notes
            if approval["revision_notes"]:
                st.markdown(
                    f"<div class='revision-note'><strong>Revision Notes:</strong> {html.escape(approval['revision_notes'])}</div>",
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
                    st.caption(f"Finish: {approval['selected_finish']}")

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
                        revision_notes=None,
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
        batch_label = st.text_input(
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
    with col3:
        use_performance_data = st.checkbox(
            "Use Performance Data",
            value=True,
            help="Select SKUs based on performance metrics (efficiency, traffic tiers)",
            key="use_performance_selection",
        )

    # Advanced selection options (when using performance data)
    if use_performance_data:
        with st.expander("Selection Criteria (Advanced)"):
            col1, col2, col3 = st.columns(3)
            with col1:
                exclude_top_n = st.number_input(
                    "Exclude Top N Revenue SKUs",
                    value=5,
                    min_value=0,
                    max_value=20,
                    help="Exclude top revenue SKUs for risk management",
                    key="exclude_top_n",
                )
            with col2:
                min_impressions = st.number_input(
                    "Min Impressions",
                    value=10,
                    min_value=0,
                    max_value=1000,
                    help="Minimum impressions for inclusion",
                    key="min_impressions",
                )
            with col3:
                max_per_category = st.number_input(
                    "Max Per Category",
                    value=0,
                    min_value=0,
                    max_value=50,
                    help="Max SKUs from single category (0 = no limit)",
                    key="max_per_category",
                )

    if approved:
        if st.button("Create Batch from Approved SKUs", type="primary"):
            # Import batch creation logic
            from feedops.db import create_batch

            if use_performance_data:
                # Use data-driven selection
                from feedops.pipeline.batch_selection import (
                    BatchSelectionCriteria,
                    select_batch_by_performance,
                )

                criteria = BatchSelectionCriteria(
                    exclude_top_revenue_count=exclude_top_n,
                    min_impressions=min_impressions,
                    max_per_category=max_per_category if max_per_category > 0 else None,
                )

                selected_skus = select_batch_by_performance(
                    approved_skus=approved,
                    batch_size=batch_size,
                    db_path=db_path,
                    criteria=criteria,
                )
            else:
                # Simple FIFO selection
                selected_skus = [a["master_sku"] for a in approved[:batch_size]]

            if selected_skus:
                batch_id = create_batch(
                    db_path,
                    batch_label=batch_label if batch_label else None,
                    skus=selected_skus,
                    selection_criteria={
                        "method": "performance" if use_performance_data else "fifo",
                        "batch_size": batch_size,
                    },
                )
                st.success(f"Created **{batch_id}** with {len(selected_skus)} SKUs")
                st.rerun()
            else:
                st.error("No SKUs could be selected with the given criteria")
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
                    elements.append(f"Image ({approval['selected_finish'] or 'N/A'})")
                st.caption(", ".join(elements) if elements else "No elements")
            with col3:
                st.caption(
                    approval["reviewed_at"][:10] if approval["reviewed_at"] else "N/A"
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

                if batch["batch_label"]:
                    st.markdown(f"**Label:** {batch['batch_label']}")
                if batch["target_date"]:
                    st.markdown(f"**Target Date:** {batch['target_date']}")

                st.caption(
                    f"Created: {batch['created_at'][:10] if batch['created_at'] else 'N/A'}"
                )
                if batch["published_at"]:
                    st.caption(f"Published: {batch['published_at'][:10]}")

                # Show SKUs in batch
                from feedops.db import get_batch_skus

                batch_skus = get_batch_skus(db_path, batch_id=batch["batch_id"])
                if batch_skus:
                    with st.expander("View SKUs in Batch"):
                        for sku in batch_skus[:50]:
                            st.markdown(f"- {sku}")
                        if len(batch_skus) > 50:
                            st.caption(f"... and {len(batch_skus) - 50} more")


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
        if current_approval["status"] == "approved":
            approval_indicator = " ✅"
        elif current_approval["status"] == "revision":
            approval_indicator = " 🔄"
        elif current_approval["status"] == "rejected":
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
                manual_status = current_approval["status"]
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

        # Lifestyle images (if available)
        render_lifestyle_images_panel(sku_data)

        # Three-way content comparison
        render_content_comparison(sku_data, platform)

        # Variant preview section
        render_variant_preview(sku_data)

        st.divider()

        # Reasoning inputs
        render_reasoning_panel(sku_data)

        st.divider()

        # Quality scores
        render_score_panel(sku_data)


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
        if current_approval["status"] == "approved":
            status_class = "approval-approved"
        elif current_approval["status"] == "revision":
            status_class = "approval-revision"
        elif current_approval["status"] == "rejected":
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
                finish_index = 0
                if default_finish and default_finish in available_finishes:
                    finish_index = available_finishes.index(default_finish)
                selected_finish = st.selectbox(
                    "Select Finish for Image",
                    options=available_finishes,
                    index=finish_index,
                    key=f"finish_approve_{sku_data.sku}",
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
            if candidate_content and candidate_content.lifestyle_images:
                successful_images = [
                    img
                    for img in candidate_content.lifestyle_images
                    if img.get("generation_success", False)
                ]
                if successful_images:
                    image_options = [
                        f"Variation {img.get('variation_num', i+1)}"
                        for i, img in enumerate(successful_images)
                    ]
                    default_idx = (
                        current_approval.get("selected_image_index", 0)
                        if current_approval
                        else 0
                    )
                    selected_image_index = st.selectbox(
                        "Select Image Variation",
                        options=range(len(successful_images)),
                        format_func=lambda x: image_options[x],
                        index=min(default_idx, len(successful_images) - 1),
                        key=f"image_idx_{sku_data.sku}",
                    )

    # Revision notes (for flagging)
    revision_notes = st.text_area(
        "Revision Notes (optional)",
        value=current_approval.get("revision_notes", "") if current_approval else "",
        placeholder="Describe what needs to be changed...",
        key=f"revision_notes_{sku_data.sku}",
        height=80,
    )

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve", key=f"approve_btn_{sku_data.sku}", type="primary"):
            save_sku_approval(
                db_path,
                master_sku=sku_data.sku,
                title_approved=title_approved,
                description_approved=desc_approved,
                image_approved=image_approved,
                selected_finish=selected_finish,
                selected_image_index=selected_image_index,
                status="approved",
                revision_notes=None,
                reviewed_by="dashboard",
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
                    revision_notes=revision_notes,
                    reviewed_by="dashboard",
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
                revision_notes=revision_notes,
                reviewed_by="dashboard",
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
    lifestyle_images = candidate_content.lifestyle_images
    if not lifestyle_images:
        return

    st.subheader("🖼️ Generated Lifestyle Images")

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

    selected_variation = candidate_content.selected_lifestyle_image

    for i, img in enumerate(successful):
        with cols[i]:
            # Display image
            image_path = img.get("image_path", "")
            variation_num = img.get("variation_num", i + 1)

            if image_path and Path(image_path).exists():
                st.image(
                    image_path,
                    caption=f"Variation {variation_num}",
                    use_container_width=True,
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
                    st.image(image_path, use_container_width=True)

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

            # Conditional column rendering based on available content
            if not has_baseline and not has_candidate:
                # Only Original column (full width)
                st.markdown("##### Original (Live)")
                st.markdown(
                    "<div class='version-label'>Current on website</div>",
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
                    st.markdown("##### Original (Live)")
                    st.markdown(
                        "<div class='version-label'>Current on website</div>",
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
                    st.markdown("##### Original (Live)")
                    st.markdown(
                        "<div class='version-label'>Current on website</div>",
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


def render_reasoning_panel(sku_data: SKUData) -> None:
    """Render the reasoning inputs panel."""
    st.subheader("Reasoning Inputs")

    report = sku_data.candidate_report
    if not report:
        st.info("No report data available for this SKU.")
        return

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

    # Expandable evidence table
    if report.evidence_markdown:
        with st.expander("Full Evidence Table"):
            st.markdown(report.evidence_markdown)

    # Provider info
    st.caption(
        f"Model: {report.provider_model or 'Unknown'} | Cost: {report.estimated_cost or 'N/A'}"
    )


def render_score_panel(sku_data: SKUData) -> None:
    """Render quality score visualization."""
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


def render_variant_preview(sku_data: SKUData) -> None:
    """Render variant preview section with finish selector."""
    st.divider()
    st.subheader("Variant Preview")
    st.caption(
        "Preview how content will appear for specific finish variants. "
        "Lifestyle images above apply to all variants."
    )

    # Load available finishes
    available_finishes = load_available_finishes()
    if not available_finishes:
        st.info("Finish data not available. Ensure data/finishes.txt exists.")
        return

    # Get base content from candidate (prefer Google, fall back to others)
    candidate_content = (
        sku_data.candidate.get("google")
        or sku_data.candidate.get("bing")
        or sku_data.candidate.get("shopify")
    )

    if not candidate_content:
        st.info("No candidate content available for variant preview.")
        return

    base_title = candidate_content.title
    base_description = candidate_content.description

    # Get collection info from original data
    collection_name = None
    category = None
    if sku_data.original:
        collection_name = sku_data.original.collection
        category = sku_data.original.category

    # Finish selector dropdown
    selected_finish = st.selectbox(
        "Select Finish to Preview",
        options=available_finishes,
        key=f"finish_select_{sku_data.sku}",
    )

    if selected_finish:
        # Generate variant-specific content
        variant_title = generate_variant_title(base_title, selected_finish)
        variant_description = generate_variant_description(
            base_description,
            selected_finish,
            collection_name=collection_name,
            category=category,
            platform="google",
        )
        variant_keywords = generate_variant_keywords(selected_finish, category)

        # Display variant preview in two columns
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
