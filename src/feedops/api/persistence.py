"""Supabase CRUD operations for FeedOps Pipeline API."""

from __future__ import annotations

import hashlib
import json
import logging
import time

from fastapi import HTTPException

from feedops.api.generation_telemetry import safe_int as _safe_int
from feedops.api.utils import _require_request_id
from feedops.api.prompt_loader import get_platform_system_prompt_hash
from feedops.generation.persistence import get_finish_task_result
from feedops.observability import get_request_id
from feedops.pipeline.feature_flags import capture_flag_snapshot
from feedops.pipeline.finish_sentence_placeholder import count_finish_sentence_placeholders

logger = logging.getLogger(__name__)


# =============================================================================
# Supabase CRUD helpers — extracted from main.py (Plan 01-02)
# =============================================================================


def _lookup_generated_content_id(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
) -> str | None:
    """Resolve generated_content.id for history linkage."""
    try:
        lookup = (
            supabase.table("generated_content")
            .select("id")
            .eq("master_sku", master_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .eq("is_current", True)
            .maybe_single()
            .execute()
        )
        data = getattr(lookup, "data", None)
        if isinstance(data, dict):
            content_id = data.get("id")
            if isinstance(content_id, str) and content_id:
                return content_id
    except Exception as exc:
        logger.warning(
            "Failed to resolve generated_content_id for %s/%s/%s: %s",
            master_sku,
            platform,
            content_type,
            exc,
        )
    return None


def _load_generated_content_row(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
) -> dict | None:
    """Load current generated_content row for deterministic regeneration writes."""
    try:
        lookup = (
            supabase.table("generated_content")
            .select("id,version,candidate_content")
            .eq("master_sku", master_sku)
            .eq("platform", platform)
            .eq("content_type", content_type)
            .eq("is_current", True)
            .maybe_single()
            .execute()
        )
        data = getattr(lookup, "data", None)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning(
            "Failed to load generated_content row for %s/%s/%s: %s",
            master_sku, platform, content_type, exc,
        )
        return None


def _assembled_prompt_hash(system_prompt: str, user_prompt: str) -> str:
    """Build deterministic hash of the exact prompt pair used for generation."""
    canonical = json.dumps(
        {
            "system_prompt": system_prompt or "",
            "user_prompt": user_prompt or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _enforce_write_time_finish_placeholder_contract(
    *,
    platform: str,
    content_type: str,
    content: str,
    endpoint: str,
) -> None:
    """Fail fast if Google/Bing descriptions violate finish placeholder contract."""
    if content_type != "description" or platform not in {"google", "bing"}:
        return

    placeholder_count = count_finish_sentence_placeholders(content)
    if placeholder_count == 1:
        return

    if placeholder_count == 0:
        code = "regenerate_description_missing_finish_placeholder"
        message = "Google/Bing descriptions must include exactly one {FINISH_SENTENCE} placeholder before persistence."
    else:
        code = "regenerate_description_multiple_finish_placeholders"
        message = "Google/Bing descriptions must include exactly one {FINISH_SENTENCE}; multiple placeholders are not allowed."

    raise HTTPException(
        status_code=422,
        detail={
            "code": code,
            "message": message,
            "platform": platform,
            "content_type": content_type,
            "placeholder_count": placeholder_count,
            "endpoint": endpoint,
        },
    )


def _persist_regeneration_result(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
    content: str,
    generation_model: str,
    prompt_hash: str,
    system_prompt: str,
    user_prompt: str,
    feedback_text: str | None,
    mode: str,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    generation_diagnostics: dict | None = None,
    latency_ms: int | None = None,
    provider_attempt_count: int | None = None,
    parse_retry_count: int | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    """Persist regeneration content/history with idempotent no-change behavior."""
    current_row = _load_generated_content_row(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    current_content = (
        str(current_row.get("candidate_content", "")).strip()
        if isinstance(current_row, dict) and current_row.get("candidate_content") is not None
        else None
    )
    normalized_content = (content or "").strip()

    if current_content is not None and current_content == normalized_content:
        current_version = int(current_row.get("version") or 1)
        return {
            "state": "no_change",
            "idempotent": True,
            "generated_content_id": current_row.get("id"),
            "version": current_version,
        }

    next_version = (
        int(current_row.get("version") or 0) + 1 if isinstance(current_row, dict) else 1
    )
    generation_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _enforce_write_time_finish_placeholder_contract(
        platform=platform,
        content_type=content_type,
        content=normalized_content,
        endpoint="_persist_regeneration_result",
    )
    write_payload = {
        "master_sku": master_sku,
        "platform": platform,
        "content_type": content_type,
        "candidate_content": normalized_content,
        "version": next_version,
        "is_current": True,
        "generation_model": generation_model,
        "generation_prompt_hash": prompt_hash,
        "generation_timestamp": generation_timestamp,
    }

    generated_content_id: str | None = None
    if isinstance(current_row, dict) and current_row.get("id"):
        (
            supabase.table("generated_content")
            .update(write_payload)
            .eq("id", current_row["id"])
            .execute()
        )
        generated_content_id = str(current_row["id"])
    else:
        (
            supabase.table("generated_content")
            .insert(write_payload)
            .execute()
        )

    if not generated_content_id:
        generated_content_id = _lookup_generated_content_id(
            supabase=supabase,
            master_sku=master_sku,
            platform=platform,
            content_type=content_type,
        )

    lineage_request_id = _require_request_id(request_id or get_request_id())
    flag_snapshot = capture_flag_snapshot()
    if isinstance(generation_diagnostics, dict) and generation_diagnostics:
        flag_snapshot = dict(flag_snapshot)
        flag_snapshot["generation_diagnostics"] = generation_diagnostics

    canonical_platform_hash = get_platform_system_prompt_hash(platform)
    assembled_prompt_hash = _assembled_prompt_hash(system_prompt, user_prompt)
    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "feedback_text": feedback_text,
        "previous_content": current_content,
        "new_content": normalized_content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:50000],
        "user_prompt": user_prompt[:50000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
        "feature_flags_active": flag_snapshot,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "provider_attempt_count": _safe_int(provider_attempt_count, 0),
        "parse_retry_count": _safe_int(parse_retry_count, 0),
        "request_id": lineage_request_id,
        "result_state": "completed",
        "result_version": next_version,
        "result_idempotent": False,
        "idempotency_key": idempotency_key,
        "canonical_platform_hash": canonical_platform_hash,
        "assembled_prompt_hash": assembled_prompt_hash,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()

    return {
        "state": "completed",
        "idempotent": False,
        "generated_content_id": generated_content_id,
        "version": next_version,
    }


def _persist_generated_content_and_history(
    *,
    supabase,
    master_sku: str,
    platform: str,
    content_type: str,
    content: str,
    generation_model: str,
    prompt_hash: str,
    system_prompt: str,
    user_prompt: str,
    mode: str,
    tokens_used: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
    provider_attempt_count: int | None = None,
    parse_retry_count: int | None = None,
    generation_diagnostics: dict | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
):
    """Persist generated content and linked history in one canonical path."""
    _enforce_write_time_finish_placeholder_contract(
        platform=platform,
        content_type=content_type,
        content=content,
        endpoint="_persist_generated_content_and_history",
    )
    supabase.table("generated_content").upsert(
        {
            "master_sku": master_sku,
            "platform": platform,
            "content_type": content_type,
            "candidate_content": content,
            "generation_model": generation_model,
            "generation_prompt_hash": prompt_hash,
        },
        on_conflict="master_sku,platform,content_type",
    ).execute()

    generated_content_id = _lookup_generated_content_id(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    content_row = _load_generated_content_row(
        supabase=supabase,
        master_sku=master_sku,
        platform=platform,
        content_type=content_type,
    )
    result_version = (
        int(content_row.get("version") or 1) if isinstance(content_row, dict) else 1
    )

    lineage_request_id = _require_request_id(request_id or get_request_id())
    flag_snapshot = capture_flag_snapshot()
    if isinstance(generation_diagnostics, dict) and generation_diagnostics:
        flag_snapshot = dict(flag_snapshot)
        flag_snapshot["generation_diagnostics"] = generation_diagnostics

    canonical_platform_hash = get_platform_system_prompt_hash(platform)
    assembled_prompt_hash = _assembled_prompt_hash(system_prompt, user_prompt)
    history_payload = {
        "master_sku": master_sku,
        "content_type": content_type,
        "platform": platform,
        "mode": mode,
        "new_content": content,
        "model_version": generation_model,
        "system_prompt": system_prompt[:50000],
        "user_prompt": user_prompt[:50000],
        "prompt_hash": prompt_hash,
        "generated_content_id": generated_content_id,
        "feature_flags_active": flag_snapshot,
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "provider_attempt_count": _safe_int(provider_attempt_count, 0),
        "parse_retry_count": _safe_int(parse_retry_count, 0),
        "request_id": lineage_request_id,
        "result_state": "completed",
        "result_version": result_version,
        "result_idempotent": False,
        "idempotency_key": idempotency_key,
        "canonical_platform_hash": canonical_platform_hash,
        "assembled_prompt_hash": assembled_prompt_hash,
    }
    supabase.table("regeneration_history").insert(history_payload).execute()


def _persist_finish_prompt_lineage(
    *,
    supabase,
    master_sku: str,
    generated: dict,
    mode: str,
    generation_model: str,
    generation_diagnostics: dict | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
) -> bool:
    """Persist finish subcall prompts as lineage-only rows when the task executed."""
    task_result = get_finish_task_result(generated.get("task_results"))
    if not task_result:
        return False

    metadata = task_result.get("metadata")
    finish_sentences = (
        metadata.get("finish_sentences")
        if isinstance(metadata, dict)
        else generated.get("finish_sentences")
    )
    serialized_finish_payload = ""
    if isinstance(finish_sentences, dict) and finish_sentences:
        serialized_finish_payload = json.dumps(
            finish_sentences,
            sort_keys=True,
            separators=(",", ":"),
        )

    system_prompt = str(task_result.get("system_prompt", ""))
    user_prompt = str(task_result.get("user_prompt", ""))
    prompt_hash = str(
        task_result.get("prompt_hash")
        or get_platform_system_prompt_hash("finish")
    )
    lineage_request_id = _require_request_id(
        str(task_result.get("request_id") or request_id or get_request_id() or "")
    )

    flag_snapshot = capture_flag_snapshot()
    if isinstance(generation_diagnostics, dict) and generation_diagnostics:
        flag_snapshot = dict(flag_snapshot)
        flag_snapshot["generation_diagnostics"] = generation_diagnostics

    history_payload = {
        "master_sku": master_sku,
        "content_type": "finish_sentences",
        "platform": "finish",
        "mode": f"{mode}_finish_sentences",
        "previous_content": None,
        "new_content": serialized_finish_payload,
        "model_version": generation_model,
        "system_prompt": system_prompt[:50000],
        "user_prompt": user_prompt[:50000],
        "prompt_hash": prompt_hash,
        "generated_content_id": None,
        "feature_flags_active": flag_snapshot,
        "tokens_used": task_result.get("tokens_used"),
        "cost_usd": task_result.get("cost_usd"),
        "latency_ms": task_result.get("latency_ms"),
        "provider_attempt_count": _safe_int(
            task_result.get("provider_attempt_count"), 0
        ),
        "parse_retry_count": _safe_int(task_result.get("parse_retry_count"), 0),
        "request_id": lineage_request_id,
        "result_state": "completed",
        "result_version": 1,
        "result_idempotent": False,
        "idempotency_key": idempotency_key,
        "canonical_platform_hash": get_platform_system_prompt_hash("finish"),
        "assembled_prompt_hash": _assembled_prompt_hash(system_prompt, user_prompt),
    }
    supabase.table("regeneration_history").insert(history_payload).execute()
    return True


def _upsert_batch_job_sku_status(
    *,
    supabase,
    job_id: str,
    master_sku: str,
    status: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    error_message: str | None = None,
) -> None:
    """Ensure a batch SKU detail row exists and is updated deterministically."""
    payload: dict[str, object] = {
        "job_id": job_id,
        "master_sku": master_sku,
        "status": status,
    }
    if started_at:
        payload["started_at"] = started_at
    if completed_at:
        payload["completed_at"] = completed_at
    if error_message:
        payload["error_message"] = error_message[:500]
    supabase.table("batch_generation_job_skus").upsert(
        payload,
        on_conflict="job_id,master_sku",
    ).execute()
