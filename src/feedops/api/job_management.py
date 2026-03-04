"""Job lifecycle management for FeedOps Pipeline API."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from fastapi import HTTPException

from feedops.api.schemas import (
    RegenerateRequest,
    RegenerateResponse,
    RegenerateJobStatusResponse,
    _normalize_regeneration_job_status,
)
from feedops.observability import get_request_id

logger = logging.getLogger(__name__)


# =============================================================================
# Job lifecycle helpers — extracted from main.py (Plan 01-02)
# =============================================================================


def _create_regeneration_job(
    *,
    supabase,
    request: RegenerateRequest,
    canonical_master_sku: str,
    request_id: str,
    idempotency_key: str,
) -> str:
    """Create a generation_jobs row for async regeneration tracking."""
    job_payload = {
        "master_sku": canonical_master_sku,
        "job_type": "regenerate",
        "status": "pending",
        "priority": 0,
        "input_params": {
            "request": request.model_dump(),
            "request_id": request_id,
            "platform": request.platform,
            "content_type": request.content_type,
            "idempotency_key": idempotency_key,
        },
        "attempt_count": 0,
        "max_attempts": 1,
        "requested_by": "dashboard",
    }
    result = supabase.table("generation_jobs").insert(job_payload).execute()
    data = getattr(result, "data", None)
    if isinstance(data, list) and data and isinstance(data[0], dict) and data[0].get("id"):
        return str(data[0]["id"])
    if isinstance(data, dict) and data.get("id"):
        return str(data["id"])
    raise RuntimeError("Failed to create regeneration job: missing job id")


def _format_job_error(exc: Exception) -> str:
    """Create stable, actionable error text for async job records."""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return json.dumps(detail, default=str)[:2000]
        return str(detail)[:2000]
    return str(exc)[:2000]


def _resolve_execution_request_id(request_id: str | None = None) -> str:
    """Resolve a stable request id for non-HTTP execution paths.

    HTTP calls populate context in middleware. Background jobs/tests may not have
    a request context, so we synthesize one and propagate it explicitly.
    """
    rid = (request_id or get_request_id() or "").strip()
    if not rid or rid == "-":
        rid = uuid.uuid4().hex
        logger.warning("Generated fallback execution request_id: %s", rid)
    return rid


def _regeneration_idempotency_key(
    *,
    request: RegenerateRequest,
    canonical_master_sku: str,
) -> str:
    """Compute a stable idempotency key for async regenerate requests."""
    payload = {
        "master_sku": canonical_master_sku,
        "platform": request.platform,
        "content_type": request.content_type,
        "feedback": (request.feedback or "").strip(),
        "finish_code": (request.finish_code or "").strip(),
        "tone_style": request.tone_style,
        "emphasis": request.emphasis or [],
        "length_preference": request.length_preference,
        "save_as_correction": bool(request.save_as_correction),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _hybrid_generation_idempotency_key(
    *,
    canonical_skus: list[str],
    options: dict,
) -> str:
    """Compute a stable idempotency key for hybrid generation submissions."""
    payload = {
        "skus": sorted({sku for sku in canonical_skus if isinstance(sku, str)}),
        "titles": bool(options.get("titles", True)),
        "descriptions": bool(options.get("descriptions", True)),
        "platforms": sorted(
            {platform for platform in options.get("platforms", []) if isinstance(platform, str)}
        ),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find_active_regeneration_job(
    *,
    supabase,
    canonical_master_sku: str,
    idempotency_key: str,
) -> dict | None:
    """Return matching pending/running regenerate job for dedupe window."""
    lookup = (
        supabase.table("generation_jobs")
        .select("*")
        .eq("master_sku", canonical_master_sku)
        .eq("job_type", "regenerate")
        .in_("status", ["pending", "running"])
        .execute()
    )
    rows = getattr(lookup, "data", None)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        input_params = row.get("input_params")
        if not isinstance(input_params, dict):
            continue
        if input_params.get("idempotency_key") == idempotency_key:
            return row
    return None


def _find_active_hybrid_job(
    *,
    supabase,
    idempotency_key: str,
) -> dict | None:
    """Return matching queued/processing hybrid job for dedupe window."""
    lookup = (
        supabase.table("batch_generation_jobs")
        .select("*")
        .in_("status", ["queued", "processing"])
        .execute()
    )
    rows = getattr(lookup, "data", None)
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        options = row.get("options")
        if not isinstance(options, dict):
            continue
        if options.get("idempotency_key") == idempotency_key:
            return row
    return None


def _normalize_regeneration_job_row(job_row: dict) -> RegenerateJobStatusResponse:
    """Normalize generation_jobs row into API response contract."""
    raw_result = job_row.get("result")
    parsed_result: RegenerateResponse | None = None
    if isinstance(raw_result, dict):
        try:
            parsed_result = RegenerateResponse(**raw_result)
        except Exception:
            parsed_result = None

    request_id = None
    if parsed_result and parsed_result.request_id:
        request_id = parsed_result.request_id
    else:
        input_params = job_row.get("input_params")
        if isinstance(input_params, dict):
            rid = input_params.get("request_id")
            if isinstance(rid, str) and rid.strip():
                request_id = rid.strip()

    error_value = job_row.get("error")
    if not isinstance(error_value, str) or not error_value:
        error_value = None

    return RegenerateJobStatusResponse(
        success=True,
        job_id=str(job_row["id"]),
        status=_normalize_regeneration_job_status(job_row.get("status")),
        request_id=request_id,
        master_sku=job_row.get("master_sku"),
        content_type=(
            parsed_result.content_type
            if parsed_result
            else (
                (job_row.get("input_params") or {}).get("content_type")
                if isinstance(job_row.get("input_params"), dict)
                else None
            )
        ),
        platform=(
            parsed_result.platform
            if parsed_result
            else (
                (job_row.get("input_params") or {}).get("platform")
                if isinstance(job_row.get("input_params"), dict)
                else None
            )
        ),
        result=parsed_result,
        error=error_value,
        created_at=job_row.get("created_at"),
        started_at=job_row.get("started_at"),
        completed_at=job_row.get("completed_at"),
    )
