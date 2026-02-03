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
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, TypeVar

try:
    from supabase import Client, create_client
except ImportError:
    Client = None  # type: ignore[assignment,misc]
    create_client = None  # type: ignore[assignment]

_client: Client | None = None  # type: ignore[type-arg]

# Retry configuration for transient errors
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 0.5

T = TypeVar("T")


def _with_retry(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator to retry Supabase operations on transient errors.

    Handles httpx.RemoteProtocolError and similar connection issues
    that can occur with Supabase on Streamlit Cloud.
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_name = type(e).__name__
                # Retry on transient connection errors
                if any(x in error_name for x in ["RemoteProtocolError", "ConnectionError", "TimeoutError"]) or \
                   any(x in str(e) for x in ["Server disconnected", "Connection reset", "timed out"]):
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
                        # Reset the client to get a fresh connection
                        global _client
                        _client = None
                        continue
                # Non-retryable error, raise immediately
                raise
        # All retries exhausted
        raise last_error  # type: ignore[misc]
    return wrapper


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


def _row_to_approval_dict(row: dict) -> dict:
    """Convert a Supabase sku_approvals row to a consistent dict.

    Column names now match between SQLite and Supabase, so this is
    mostly pass-through with boolean normalization.
    """
    return {
        "master_sku": row["master_sku"],
        "title_approved": row.get("title_approved"),
        "description_approved": row.get("description_approved"),
        "image_approved": row.get("image_approved"),
        "selected_finish": row.get("selected_finish"),
        "selected_image_index": row.get("selected_image_index"),
        "approval_status": row.get("approval_status", "pending"),
        "notes": row.get("notes"),
        "approved_by": row.get("approved_by"),
        "approved_at": row.get("approved_at") or row.get("updated_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


# SKU Approval functions


@_with_retry
def save_sku_approval(
    _db_path=None,
    *,
    master_sku: str,
    title_approved: bool | None = None,
    description_approved: bool | None = None,
    image_approved: bool | None = None,
    selected_finish: str | None = None,
    selected_image_index: int | None = None,
    status: str = "pending",
    notes: str | None = None,
    approved_by: str | None = None,
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
        "title_approved": title_approved,
        "description_approved": description_approved,
        "image_approved": image_approved,
        "selected_finish": selected_finish,
        "selected_image_index": selected_image_index,
        "approved_at": now if status == "approved" else None,
        "approved_by": approved_by,
        "notes": notes,
        "updated_at": now,
    }

    # Upsert (insert or update)
    client.table("sku_approvals").upsert(data, on_conflict="master_sku").execute()

    return master_sku


@_with_retry
def get_sku_approval(
    _db_path=None,
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
    return _row_to_approval_dict(row)


@_with_retry
def get_pending_approvals(
    _db_path=None,
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

    return [_row_to_approval_dict(row) for row in result.data]


@_with_retry
def get_approved_for_batch(
    _db_path=None,
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

    return [_row_to_approval_dict(row) for row in approved]


# Batch management functions


@_with_retry
def create_batch(
    _db_path=None,
    *,
    batch_label: str | None = None,
    target_date: str | None = None,
    notes: dict | str | None = None,
    skus: list[str] | None = None,
    # Legacy alias
    selection_criteria: dict | None = None,
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

    # Resolve notes from either param
    resolved_notes = notes or selection_criteria
    notes_str = str(resolved_notes) if resolved_notes else None

    # Create batch
    batch_data = {
        "batch_id": batch_id,
        "name": batch_label,
        "status": "pending",
        "created_at": now.isoformat(),
        "notes": notes_str,
    }

    client.table("publish_batches").insert(batch_data).execute()

    # Assign SKUs if provided
    if skus:
        assign_skus_to_batch(batch_id=batch_id, skus=skus)

    return batch_id


@_with_retry
def get_batch(
    _db_path=None,
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
        "name": row.get("name"),
        "target_date": row.get("target_date"),
        "status": row["status"],
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "executed_at": row.get("executed_at"),
        "sku_count": row.get("sku_count", 0),
        "success_count": row.get("success_count", 0),
        "failed_count": row.get("failed_count", 0),
    }


@_with_retry
def get_all_batches(
    _db_path=None,
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
            "name": row.get("name"),
            "target_date": row.get("target_date"),
            "status": row["status"],
            "notes": row.get("notes"),
            "created_at": row.get("created_at"),
            "executed_at": row.get("executed_at"),
            "sku_count": row.get("sku_count", 0),
            "success_count": row.get("success_count", 0),
            "failed_count": row.get("failed_count", 0),
        }
        for row in result.data
    ]


@_with_retry
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


@_with_retry
def get_batch_skus(
    _db_path=None,
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


@_with_retry
def update_batch_status(
    _db_path=None,
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


@_with_retry
def log_publish_event(
    _db_path=None,
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
    rollback_id: int | None = None,
    batch_id: str | None = None,
    product_category: str | None = None,
    product_collection: str | None = None,
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
        "approval_status": approval_status,
        "error_message": error_message,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published_by": published_by or "cli",
        "rollback_id": rollback_id,
        "product_category": product_category,
        "product_collection": product_collection,
    }

    result = client.table("publish_events").insert(data).execute()

    return result.data[0]["id"] if result.data else 0


@_with_retry
def get_publish_history(
    _db_path=None,
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
            "approval_status": row.get("approval_status"),
            "error_message": row.get("error_message"),
            "published_at": row.get("published_at"),
            "published_by": row.get("published_by"),
            "rollback_id": row.get("rollback_id"),
            "product_category": row.get("product_category"),
            "product_collection": row.get("product_collection"),
        }
        for row in result.data
    ]


def get_last_publish_event(
    _db_path=None,
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


@_with_retry
def get_published_skus(
    _db_path=None,
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
    _db_path=None,
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


@_with_retry
def get_revision_queue(_db_path=None, *, limit: int = 100) -> list[dict]:
    """Get SKUs that need revision from Supabase."""
    client = get_client()
    result = (
        client.table("sku_approvals")
        .select("*")
        .eq("approval_status", "revision")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [_row_to_approval_dict(row) for row in result.data]


# Variant Approval functions


def save_variant_approval(
    _db_path=None,
    *,
    master_sku: str,
    finish: str,
    finish_code: str | None = None,
    title_approved: bool | None = None,
    description_approved: bool | None = None,
    image_approved: bool | None = None,
    selected_image_index: int | None = None,
    status: str = "pending",
    notes: str | None = None,
    approved_by: str | None = None,
) -> str:
    """Save or update a variant approval record in Supabase.

    Returns:
        The master_sku.
    """
    client = get_client()
    now = datetime.now(timezone.utc).isoformat()

    # Auto-derive status
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
        "finish": finish,
        "finish_code": finish_code,
        "title_approved": title_approved,
        "description_approved": description_approved,
        "image_approved": image_approved,
        "selected_image_index": selected_image_index,
        "approval_status": status,
        "notes": notes,
        "approved_by": approved_by,
        "approved_at": now if status == "approved" else None,
        "updated_at": now,
    }

    client.table("variant_approvals").upsert(
        data, on_conflict="master_sku,finish"
    ).execute()

    return master_sku


@_with_retry
def get_variant_approval(
    _db_path=None,
    *,
    master_sku: str,
    finish: str,
) -> dict | None:
    """Get variant approval for a specific master_sku + finish."""
    client = get_client()

    result = (
        client.table("variant_approvals")
        .select("*")
        .eq("master_sku", master_sku)
        .eq("finish", finish)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    return {
        "id": row.get("id"),
        "master_sku": row["master_sku"],
        "finish": row["finish"],
        "finish_code": row.get("finish_code"),
        "title_approved": row.get("title_approved"),
        "description_approved": row.get("description_approved"),
        "image_approved": row.get("image_approved"),
        "selected_image_index": row.get("selected_image_index"),
        "approval_status": row.get("approval_status", "pending"),
        "notes": row.get("notes"),
        "approved_by": row.get("approved_by"),
        "approved_at": row.get("approved_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def get_variant_approvals_for_sku(
    _db_path=None,
    *,
    master_sku: str,
) -> list[dict]:
    """Get all variant approvals for a given master SKU."""
    client = get_client()

    result = (
        client.table("variant_approvals")
        .select("*")
        .eq("master_sku", master_sku)
        .order("finish", desc=False)
        .execute()
    )

    return [
        {
            "id": row.get("id"),
            "master_sku": row["master_sku"],
            "finish": row["finish"],
            "finish_code": row.get("finish_code"),
            "title_approved": row.get("title_approved"),
            "description_approved": row.get("description_approved"),
            "image_approved": row.get("image_approved"),
            "selected_image_index": row.get("selected_image_index"),
            "approval_status": row.get("approval_status", "pending"),
            "notes": row.get("notes"),
            "approved_by": row.get("approved_by"),
            "approved_at": row.get("approved_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
        for row in result.data
    ]


# Performance tracking functions (mirror SQLite interface)


def save_performance_baseline(
    _db_path=None,
    *,
    master_sku: str,
    platform: str,
    baseline_start_date: str,
    baseline_end_date: str,
    avg_impressions: float | None = None,
    avg_clicks: float | None = None,
    avg_ctr: float | None = None,
    avg_conversions: float | None = None,
    avg_conversion_value: float | None = None,
    avg_cvr: float | None = None,
    avg_cost: float | None = None,
    avg_roas: float | None = None,
) -> None:
    """Save or update a performance baseline in Supabase."""
    client = get_client()

    data = {
        "master_sku": master_sku,
        "platform": platform,
        "baseline_start_date": baseline_start_date,
        "baseline_end_date": baseline_end_date,
        "avg_impressions": avg_impressions,
        "avg_clicks": avg_clicks,
        "avg_ctr": avg_ctr,
        "avg_conversions": avg_conversions,
        "avg_conversion_value": avg_conversion_value,
        "avg_cvr": avg_cvr,
        "avg_cost": avg_cost,
        "avg_roas": avg_roas,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    client.table("performance_baselines").upsert(
        data, on_conflict="master_sku,platform"
    ).execute()


def get_performance_baseline(
    _db_path=None,
    *,
    master_sku: str,
    platform: str,
) -> dict | None:
    """Retrieve a performance baseline for a SKU/platform combination."""
    client = get_client()

    result = (
        client.table("performance_baselines")
        .select("*")
        .eq("master_sku", master_sku)
        .eq("platform", platform)
        .execute()
    )

    if not result.data:
        return None

    row = result.data[0]
    return {
        "master_sku": row["master_sku"],
        "platform": row["platform"],
        "baseline_start_date": row.get("baseline_start_date"),
        "baseline_end_date": row.get("baseline_end_date"),
        "avg_impressions": row.get("avg_impressions"),
        "avg_clicks": row.get("avg_clicks"),
        "avg_ctr": row.get("avg_ctr"),
        "avg_conversions": row.get("avg_conversions"),
        "avg_conversion_value": row.get("avg_conversion_value"),
        "avg_cvr": row.get("avg_cvr"),
        "avg_cost": row.get("avg_cost"),
        "avg_roas": row.get("avg_roas"),
        "created_at": row.get("created_at"),
    }


def save_performance_snapshot(
    _db_path=None,
    *,
    master_sku: str,
    platform: str,
    environment: str,
    snapshot_date: str,
    impressions: int = 0,
    clicks: int = 0,
    ctr: float = 0.0,
    conversions: int = 0,
    conversion_value: float = 0.0,
    cvr: float = 0.0,
    cost: float = 0.0,
    cpc: float = 0.0,
    roas: float = 0.0,
    publish_event_id: int | None = None,
    content_version: str | None = None,
    days_since_publish: int | None = None,
) -> int:
    """Save a performance snapshot to Supabase."""
    client = get_client()

    data = {
        "master_sku": master_sku,
        "platform": platform,
        "environment": environment,
        "snapshot_date": snapshot_date,
        "impressions": impressions,
        "clicks": clicks,
        "ctr": ctr,
        "conversions": conversions,
        "conversion_value": conversion_value,
        "cvr": cvr,
        "cost": cost,
        "cpc": cpc,
        "roas": roas,
        "publish_event_id": publish_event_id,
        "content_version": content_version,
        "days_since_publish": days_since_publish,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    result = client.table("performance_snapshots").insert(data).execute()

    return result.data[0]["id"] if result.data else 0


def get_performance_snapshots(
    _db_path=None,
    *,
    master_sku: str | None = None,
    platform: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Retrieve performance snapshots from Supabase."""
    client = get_client()

    query = client.table("performance_snapshots").select("*")

    if master_sku:
        query = query.eq("master_sku", master_sku)

    if platform:
        query = query.eq("platform", platform)

    if start_date:
        query = query.gte("snapshot_date", start_date)

    if end_date:
        query = query.lte("snapshot_date", end_date)

    result = query.order("snapshot_date", desc=True).limit(limit).execute()

    return [
        {
            "id": row["id"],
            "master_sku": row["master_sku"],
            "platform": row["platform"],
            "environment": row["environment"],
            "snapshot_date": row["snapshot_date"],
            "impressions": row.get("impressions", 0),
            "clicks": row.get("clicks", 0),
            "ctr": row.get("ctr", 0.0),
            "conversions": row.get("conversions", 0),
            "conversion_value": row.get("conversion_value", 0.0),
            "cvr": row.get("cvr", 0.0),
            "cost": row.get("cost", 0.0),
            "cpc": row.get("cpc", 0.0),
            "roas": row.get("roas", 0.0),
            "publish_event_id": row.get("publish_event_id"),
            "content_version": row.get("content_version"),
            "days_since_publish": row.get("days_since_publish"),
            "fetched_at": row.get("fetched_at"),
        }
        for row in result.data
    ]
