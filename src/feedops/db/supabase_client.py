"""Supabase client for FeedOps workflow state management.

This module provides the same interface as schema.py but uses Supabase
for persistent storage. It's used when deploying to Streamlit Cloud
where SQLite isn't persistent.

Configuration:
- SUPABASE_URL: Supabase project URL
- SUPABASE_KEY: Supabase anon key (from Streamlit secrets or env var)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

try:
    from supabase import Client, create_client
except ImportError:
    Client = None  # type: ignore[assignment,misc]
    create_client = None  # type: ignore[assignment]

_client: Client | None = None  # type: ignore[type-arg]


def _get_supabase_config() -> tuple[str, str] | None:
    """Get Supabase URL and key from Streamlit secrets or environment.

    Returns:
        Tuple of (url, key) or None if not configured.
    """
    # Try Streamlit secrets first
    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_KEY")
            if url and key:
                return url, key
    except Exception:
        pass

    # Fall back to environment variables
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key

    return None


def is_supabase_available() -> bool:
    """Check if Supabase is configured and available."""
    if Client is None:
        return False
    return _get_supabase_config() is not None


def get_client() -> Client:
    """Get or create Supabase client singleton."""
    global _client
    if _client is None:
        config = _get_supabase_config()
        if not config:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_KEY."
            )
        url, key = config
        _client = create_client(url, key)
    return _client


# SKU Approval functions


def save_sku_approval(
    *,
    master_sku: str,
    title_approved: bool | None = None,
    description_approved: bool | None = None,
    image_approved: bool | None = None,
    selected_finish: str | None = None,
    selected_image_index: int | None = None,
    status: str = "pending",
    revision_notes: str | None = None,
    reviewed_by: str | None = None,
) -> str:
    """Save or update a SKU approval record in Supabase.

    Returns:
        The master_sku (primary key).
    """
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    # Determine overall approval status based on element approvals
    if status == "pending":
        if title_approved and description_approved and image_approved:
            status = "approved"
        elif (
            title_approved is False
            or description_approved is False
            or image_approved is False
        ):
            status = "rejected"

    data = {
        "master_sku": master_sku,
        "approval_status": status,
        "approved_at": now if status == "approved" else None,
        "approved_by": reviewed_by,
        "notes": revision_notes,
        "updated_at": now,
    }

    # Upsert (insert or update)
    result = (
        client.table("sku_approvals").upsert(data, on_conflict="master_sku").execute()
    )

    return master_sku


def get_sku_approval(
    *,
    master_sku: str,
) -> dict | None:
    """Get approval state for a SKU from Supabase."""
    client = get_client()

    result = (
        client.table("sku_approvals").select("*").eq("master_sku", master_sku).execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    return {
        "master_sku": row["master_sku"],
        "status": row["approval_status"],
        "approved_at": row.get("approved_at"),
        "approved_by": row.get("approved_by"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_pending_approvals(
    *,
    limit: int = 100,
) -> list[dict]:
    """Get SKUs awaiting review (pending status) from Supabase."""
    client = get_client()

    result = (
        client.table("sku_approvals")
        .select("*")
        .eq("approval_status", "pending")
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )

    return [
        {
            "master_sku": row["master_sku"],
            "status": row["approval_status"],
            "approved_at": row.get("approved_at"),
            "notes": row.get("notes"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in result.data
    ]


def get_approved_for_batch(
    *,
    exclude_batched: bool = True,
    limit: int = 500,
) -> list[dict]:
    """Get approved SKUs ready for batching from Supabase."""
    client = get_client()

    # Get all approved SKUs
    result = (
        client.table("sku_approvals")
        .select("*")
        .eq("approval_status", "approved")
        .order("updated_at", desc=False)
        .limit(limit)
        .execute()
    )

    if not result.data:
        return []

    approved = result.data

    if exclude_batched:
        # Get SKUs already in batches
        batched_result = (
            client.table("batch_sku_assignments").select("master_sku").execute()
        )
        batched_skus = {row["master_sku"] for row in batched_result.data}

        # Filter out batched SKUs
        approved = [row for row in approved if row["master_sku"] not in batched_skus]

    return [
        {
            "master_sku": row["master_sku"],
            "status": row["approval_status"],
            "approved_at": row.get("approved_at"),
            "notes": row.get("notes"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in approved
    ]


# Batch management functions


def create_batch(
    *,
    batch_label: str | None = None,
    target_date: str | None = None,
    selection_criteria: dict | None = None,
    skus: list[str] | None = None,
) -> str:
    """Create a new publish batch in Supabase.

    Returns:
        The generated batch_id.
    """
    client = get_client()
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    # Count existing batches for today to generate unique ID
    existing = (
        client.table("publish_batches")
        .select("batch_id", count="exact")
        .like("batch_id", f"Batch-{date_str}-%")
        .execute()
    )

    seq = (existing.count or 0) + 1
    batch_id = f"Batch-{date_str}-{seq:03d}"

    # Create batch
    batch_data = {
        "batch_id": batch_id,
        "name": batch_label,
        "status": "pending",
        "created_at": now.isoformat(),
        "notes": str(selection_criteria) if selection_criteria else None,
    }

    client.table("publish_batches").insert(batch_data).execute()

    # Assign SKUs if provided
    if skus:
        assign_skus_to_batch(batch_id=batch_id, skus=skus)

    return batch_id


def get_batch(
    *,
    batch_id: str,
) -> dict | None:
    """Get batch details by ID from Supabase."""
    client = get_client()

    result = (
        client.table("publish_batches").select("*").eq("batch_id", batch_id).execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    return {
        "batch_id": row["batch_id"],
        "batch_label": row.get("name"),
        "status": row["status"],
        "created_at": row.get("created_at"),
        "executed_at": row.get("executed_at"),
        "success_count": row.get("success_count", 0),
        "failed_count": row.get("failed_count", 0),
        "notes": row.get("notes"),
    }


def get_all_batches(
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get all batches, optionally filtered by status, from Supabase."""
    client = get_client()

    query = client.table("publish_batches").select("*")

    if status:
        query = query.eq("status", status)

    result = query.order("created_at", desc=True).limit(limit).execute()

    return [
        {
            "batch_id": row["batch_id"],
            "batch_label": row.get("name"),
            "status": row["status"],
            "created_at": row.get("created_at"),
            "executed_at": row.get("executed_at"),
            "success_count": row.get("success_count", 0),
            "failed_count": row.get("failed_count", 0),
            "notes": row.get("notes"),
        }
        for row in result.data
    ]


def assign_skus_to_batch(
    *,
    batch_id: str,
    skus: list[str],
) -> int:
    """Assign SKUs to a batch in Supabase.

    Returns:
        Number of SKUs assigned.
    """
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    # Prepare assignment records
    assignments = [
        {
            "batch_id": batch_id,
            "master_sku": sku,
            "created_at": now,
        }
        for sku in skus
    ]

    # Use upsert to handle duplicates gracefully
    result = (
        client.table("batch_sku_assignments")
        .upsert(assignments, on_conflict="batch_id,master_sku")
        .execute()
    )

    return len(result.data) if result.data else 0


def get_batch_skus(
    *,
    batch_id: str,
) -> list[str]:
    """Get all SKUs assigned to a batch from Supabase."""
    client = get_client()

    result = (
        client.table("batch_sku_assignments")
        .select("master_sku")
        .eq("batch_id", batch_id)
        .order("created_at", desc=False)
        .execute()
    )

    return [row["master_sku"] for row in result.data]


def update_batch_status(
    *,
    batch_id: str,
    status: str,
    success_count: int | None = None,
    failed_count: int | None = None,
) -> None:
    """Update batch status and counts in Supabase."""
    client = get_client()

    updates: dict[str, Any] = {"status": status}

    if status == "published":
        updates["executed_at"] = datetime.now(timezone.utc).isoformat()

    if success_count is not None:
        updates["success_count"] = success_count

    if failed_count is not None:
        updates["failed_count"] = failed_count

    client.table("publish_batches").update(updates).eq("batch_id", batch_id).execute()


# Publish event functions


def log_publish_event(
    *,
    master_sku: str,
    platform: str,
    environment: str,
    action: str = "publish",
    patch_file: str = "",
    status: str = "pending",
    quality_score: float | None = None,
    approval_status: str | None = None,
    error_message: str | None = None,
    published_by: str | None = None,
    batch_id: str | None = None,
    **kwargs,  # Accept extra kwargs for compatibility
) -> int:
    """Log a publish event to Supabase.

    Returns:
        ID of the inserted row.
    """
    client = get_client()

    data = {
        "master_sku": master_sku,
        "platform": platform,
        "environment": environment,
        "action": action,
        "status": status,
        "batch_id": batch_id,
        "patch_file": patch_file,
        "quality_score": quality_score,
        "error_message": error_message,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }

    result = client.table("publish_events").insert(data).execute()

    return result.data[0]["id"] if result.data else 0


def get_publish_history(
    *,
    master_sku: str | None = None,
    platform: str | None = None,
    environment: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve publish event history from Supabase."""
    client = get_client()

    query = client.table("publish_events").select("*")

    if master_sku:
        query = query.eq("master_sku", master_sku)

    if platform:
        query = query.eq("platform", platform)

    if environment:
        query = query.eq("environment", environment)

    result = query.order("published_at", desc=True).limit(limit).execute()

    return [
        {
            "id": row["id"],
            "master_sku": row["master_sku"],
            "platform": row["platform"],
            "environment": row["environment"],
            "action": row.get("action", "publish"),
            "status": row["status"],
            "batch_id": row.get("batch_id"),
            "patch_file": row.get("patch_file"),
            "quality_score": row.get("quality_score"),
            "error_message": row.get("error_message"),
            "published_at": row.get("published_at"),
        }
        for row in result.data
    ]


def get_last_publish_event(
    *,
    master_sku: str,
    platform: str,
) -> dict | None:
    """Get the most recent publish event for a SKU/platform combination."""
    history = get_publish_history(
        master_sku=master_sku,
        platform=platform,
        limit=1,
    )
    return history[0] if history else None


def get_published_skus(
    *,
    platform: str | None = None,
    environment: str = "production",
) -> set[str]:
    """Get set of SKUs that have been successfully published.

    This is used to filter out published SKUs from the Review Queue.
    """
    client = get_client()

    query = (
        client.table("publish_events")
        .select("master_sku")
        .eq("environment", environment)
        .eq("status", "success")
    )

    if platform:
        query = query.eq("platform", platform)

    result = query.execute()

    return {row["master_sku"] for row in result.data}


def get_skus_needing_review(
    *,
    all_skus: list[str],
    platform: str | None = None,
) -> list[str]:
    """Filter SKUs to only those not yet published to production.

    Args:
        all_skus: List of all candidate SKUs (from patch files).
        platform: Optional platform filter.

    Returns:
        List of SKUs that haven't been published to production.
    """
    published = get_published_skus(platform=platform, environment="production")
    return [sku for sku in all_skus if sku not in published]
