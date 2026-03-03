"""GMC Sync API endpoints for Cloud Run.

Provides a POST /gmc/sync endpoint that queries the Merchant Reports API
for disapproved/limited products and upserts results into gmc_product_status.

Architecture:
- Uses run_async_in_thread() for Cloud Run container lifecycle compatibility
- Returns 202 Accepted immediately with a job_id
- Actual sync runs in background thread
- Results queryable from gmc_product_status Supabase table
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from feedops.api.telemetry import run_async_in_thread
from feedops.db.supabase_client import get_client, is_supabase_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmc", tags=["gmc"])

# In-memory job status tracker (sufficient for short-lived sync jobs)
_sync_jobs: dict[str, dict] = {}


class GmcSyncResponse(BaseModel):
    """Response from /gmc/sync endpoint (202 Accepted)."""

    success: bool
    job_id: str
    status: str
    message: str


class GmcSyncStatusResponse(BaseModel):
    """Response from /gmc/sync/{job_id} status endpoint."""

    job_id: str
    status: str
    synced_count: int | None = None
    disapproved_count: int | None = None
    limited_count: int | None = None
    eligible_count: int | None = None
    error: str | None = None
    completed_at: str | None = None


@router.post("/sync", response_model=GmcSyncResponse, status_code=202)
async def trigger_gmc_sync():
    """Trigger a full GMC product status sync.

    Queries the Merchant Reports API for all disapproved and limited products,
    looks up master_sku from variant_index, and upserts into gmc_product_status.

    Returns 202 Accepted immediately. Use GET /gmc/sync/{job_id} to check status.
    """
    if not is_supabase_available():
        raise HTTPException(status_code=503, detail="Supabase not available")

    job_id = str(uuid.uuid4())
    _sync_jobs[job_id] = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    run_async_in_thread(
        _run_gmc_sync,
        job_id=job_id,
    )

    logger.info("GMC sync job %s started", job_id)
    return GmcSyncResponse(
        success=True,
        job_id=job_id,
        status="running",
        message="GMC sync started. Use GET /gmc/sync/{job_id} to check status.",
    )


@router.get("/sync/{job_id}", response_model=GmcSyncStatusResponse)
async def get_gmc_sync_status(job_id: str):
    """Get status of a GMC sync job."""
    job = _sync_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Sync job not found: {job_id}")

    return GmcSyncStatusResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        synced_count=job.get("synced_count"),
        disapproved_count=job.get("disapproved_count"),
        limited_count=job.get("limited_count"),
        eligible_count=job.get("eligible_count"),
        error=job.get("error"),
        completed_at=job.get("completed_at"),
    )


async def _run_gmc_sync(job_id: str) -> None:
    """Background task: query Merchant API and upsert to gmc_product_status.

    Steps:
    1. Query product_view for disapproved/limited products
    2. For each product, resolve master_sku from variant_index
    3. Bulk upsert to gmc_product_status
    4. Update job status in _sync_jobs
    """
    from feedops.integrations.merchant_api import MerchantApiClient

    job = _sync_jobs.setdefault(job_id, {})

    try:
        supabase = get_client()
        client = MerchantApiClient()

        # Step 1: Fetch disapproved/limited products
        products = client.query_disapproved_products()
        logger.info("GMC sync %s: fetched %d products", job_id, len(products))

        # Step 2: Resolve master_sku for each offer_id
        offer_ids = [p["gmc_offer_id"] for p in products]
        master_sku_map = _resolve_master_skus(supabase, offer_ids)

        # Step 3: Build upsert records
        sync_job_id = job_id
        records = []
        for product in products:
            offer_id = product["gmc_offer_id"]
            records.append({
                "gmc_offer_id": offer_id,
                "master_sku": master_sku_map.get(offer_id),
                "offer_title": product.get("offer_title"),
                "status": product["status"],
                "item_issues": product.get("item_issues"),
                "issue_count": product.get("issue_count", 0),
                "disapproval_count": product.get("disapproval_count", 0),
                "sync_job_id": sync_job_id,
                "synced_at": datetime.now(timezone.utc).isoformat(),
            })

        # Step 4: Bulk upsert
        if records:
            # Upsert in batches of 500 to avoid payload limits
            batch_size = 500
            for i in range(0, len(records), batch_size):
                batch = records[i:i + batch_size]
                supabase.table("gmc_product_status").upsert(
                    batch,
                    on_conflict="gmc_offer_id",
                ).execute()
            logger.info(
                "GMC sync %s: upserted %d records to gmc_product_status",
                job_id,
                len(records),
            )

        # Count by status
        disapproved_count = sum(1 for r in records if r["status"] == "disapproved")
        limited_count = sum(1 for r in records if r["status"] == "limited")
        # Note: eligible products are not synced (only disapproved/limited are fetched)
        # eligible_count here means products NOT disapproved in this sync
        synced_count = len(records)

        # Update job status
        job.update({
            "status": "completed",
            "synced_count": synced_count,
            "disapproved_count": disapproved_count,
            "limited_count": limited_count,
            "eligible_count": 0,  # Not fetched in this query (would need all-products query)
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(
            "GMC sync %s complete: %d synced, %d disapproved, %d limited",
            job_id,
            synced_count,
            disapproved_count,
            limited_count,
        )

    except Exception as exc:
        error_msg = str(exc)[:500]
        logger.error("GMC sync %s failed: %s", job_id, error_msg)
        job.update({
            "status": "failed",
            "error": error_msg,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })


def _resolve_master_skus(supabase, offer_ids: list[str]) -> dict[str, str]:
    """Resolve master_sku for a list of lowercase gmc_offer_ids via variant_index.

    Returns:
        Dict mapping gmc_offer_id (lowercase) -> master_sku
    """
    if not offer_ids:
        return {}

    result_map: dict[str, str] = {}
    # Query in batches to avoid URL length limits
    batch_size = 200
    for i in range(0, len(offer_ids), batch_size):
        batch = offer_ids[i:i + batch_size]
        try:
            rows = (
                supabase.table("variant_index")
                .select("gmc_offer_id, master_sku")
                .in_("gmc_offer_id", batch)
                .execute()
            )
            for row in (rows.data or []):
                # variant_index stores lowercase gmc_offer_id
                result_map[row["gmc_offer_id"]] = row["master_sku"]
        except Exception as exc:
            logger.warning("Failed to resolve master_skus for batch: %s", exc)

    logger.info(
        "Resolved %d/%d master_skus from variant_index",
        len(result_map),
        len(offer_ids),
    )
    return result_map
