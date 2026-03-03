"""Core generation orchestration: prompt assembly and regeneration execution."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from feedops.api.schemas import (
    RegenerateResponse,
    _content_field_key,
)
from feedops.api.persistence import (
    _persist_regeneration_result,
    _persist_finish_prompt_lineage,
)
from feedops.api.telemetry import (
    _emit_generation_summary,
    _should_persist_finish_sentences,
)
from feedops.api.generation_telemetry import (
    estimate_openai_cost_usd_from_usage as _estimate_openai_cost_usd_from_usage,
    provider_label as _provider_label,
    safe_int as _safe_int,
)
from feedops.api.finish_processing import (  # noqa: F401 - used in type hints / external callers
    _build_finish_sentences_user_prompt,
    _validate_finish_sentences_payload,
    _enforce_finish_sentence_parity,
)
from feedops.api.intent_scoring import _extract_query_intent_generation_diagnostics
from feedops.api.job_management import _regeneration_idempotency_key
from feedops.api.prompt_loader import get_platform_system_prompt_hash
from feedops.api.supabase_loader import load_parent_sku_from_supabase
from feedops.api.sku_alias import resolve_canonical_master_sku
from feedops.api.runtime_controls import finish_sentence_regeneration_enabled
from feedops.db.supabase_client import get_client
from feedops.models.parent_sku import ParentSKU
from feedops.api.prompt_builder import build_core_prompt, apply_feedback_layer
from feedops.providers import get_provider
from feedops.providers.base import close_provider
from feedops.pipeline.generator import generate_per_platform
from feedops.generation.persistence import persist_finish_sentences
from feedops.observability import get_request_id, log_event

logger = logging.getLogger(__name__)


def _build_generation_user_prompt(
    parent_sku: ParentSKU,
    evidence_markdown: str,
    platform: str,
    content_type: str,
    feedback: str | None = None,
    finish_code: str | None = None,
    evidence: list | None = None,
) -> str:
    """DEPRECATED: Use build_core_prompt() from prompt_builder.py instead.

    Thin wrapper around build_core_prompt() + apply_feedback_layer() maintained
    for backward compatibility. New call sites should call build_core_prompt()
    directly to pass the raw evidence list for keyword placement enrichment.
    """
    # Shopping intelligence/segment sections are composed inside prompt_builder.
    # This wrapper intentionally delegates all structural prompt rules there.
    core = build_core_prompt(
        parent_sku=parent_sku,
        evidence=evidence or [],
        evidence_markdown=evidence_markdown,
        platform=platform,
        content_type=content_type,
        finish_code=finish_code,
    )
    return apply_feedback_layer(core, corrections=[], session_feedback=feedback)


async def _execute_regeneration_request(
    *,
    request,
    request_id: str,
) -> RegenerateResponse:
    """Execute a single regeneration request and return the full response payload."""
    supabase = get_client()
    canonical_master_sku = resolve_canonical_master_sku(supabase, request.master_sku)
    request_idempotency_key = _regeneration_idempotency_key(
        request=request,
        canonical_master_sku=canonical_master_sku,
    )
    logger.info(
        "Regenerating %s for SKU: requested=%s canonical=%s",
        request.content_type,
        request.master_sku,
        canonical_master_sku,
    )
    log_event(
        logger,
        logging.INFO,
        "generation.regenerate.start",
        endpoint="regenerate",
        master_sku=canonical_master_sku,
        requested_master_sku=request.master_sku,
        platform=request.platform,
        content_type=request.content_type,
        request_id=request_id,
    )

    # Load product data from Supabase
    parent_sku = load_parent_sku_from_supabase(canonical_master_sku)
    if not parent_sku:
        raise HTTPException(status_code=404, detail=f"SKU not found: {request.master_sku}")

    # Get LLM provider
    provider = get_provider()
    prompt_hash = get_platform_system_prompt_hash(request.platform)

    # Load persistent corrections for this SKU (FIX-01: feedback layer)
    # Corrections are platform/content_type scoped so "all" platform corrections apply everywhere
    corrections: list[dict] = []
    try:
        corrections_resp = (
            supabase.table("sku_corrections")
            .select("*")
            .eq("master_sku", canonical_master_sku)
            .in_("platform", [request.platform, "all"])
            .in_("content_type", [request.content_type, "all"])
            .eq("is_active", True)
            .execute()
        )
        corrections = corrections_resp.data or []
        if corrections:
            logger.info(
                "Loaded %s persistent corrections for %s/%s/%s",
                len(corrections),
                canonical_master_sku,
                request.platform,
                request.content_type,
            )
    except Exception as e:
        logger.warning("Failed to load corrections for %s: %s", canonical_master_sku, e)

    # Build session feedback from structured fields (FIX-01)
    feedback_parts: list[str] = []
    if request.tone_style:
        feedback_parts.append(f"Tone/style: {request.tone_style}")
    if request.emphasis:
        feedback_parts.append(f"Emphasize: {', '.join(request.emphasis)}")
    if request.length_preference:
        feedback_parts.append(f"Length: {request.length_preference}")
    if request.feedback:
        feedback_parts.append(request.feedback)
    session_feedback = "\n".join(feedback_parts) if feedback_parts else None

    finish_sentences: dict[str, str] | None = None
    system_prompt = ""
    user_prompt = ""
    regen_latency_ms = 0
    feedback_lines: list[str] = []
    if corrections:
        correction_lines = []
        for correction in corrections:
            text = (
                correction.get("correction_text")
                or correction.get("text")
                or correction.get("correction")
            )
            if text:
                correction_lines.append(f"- {text}")
        if correction_lines:
            feedback_lines.append("Persistent Corrections:\n" + "\n".join(correction_lines))
    if session_feedback:
        feedback_lines.append(session_feedback)

    selected_platforms: list[str] = [request.platform]
    include_finish = (
        request.content_type == "description" and request.platform in {"google", "bing"}
    )
    finish_regen_enabled = finish_sentence_regeneration_enabled()
    if include_finish and finish_regen_enabled:
        selected_platforms.append("finish")

    try:
        generated = await generate_per_platform(
            parent_sku=parent_sku,
            provider=provider,
            prompt_version="v2",
            feedback_by_platform={request.platform: "\n\n".join(feedback_lines)}
            if feedback_lines
            else None,
            selected_platforms=selected_platforms,
            selected_content_types=(request.content_type,),
            request_id=request_id,
        )
    finally:
        await close_provider(provider)
    field_key = _content_field_key(request.platform, request.content_type)
    content = str(generated.get(field_key, "")).strip()
    if not content:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "regenerate_missing_required_platform_field",
                "message": (
                    f"Missing required regenerated field '{field_key}' for "
                    f"{request.platform}/{request.content_type}."
                ),
                "platform": request.platform,
                "content_type": request.content_type,
            },
        )
    prompt_hash = str(
        generated.get("prompt_hashes", {}).get(
            request.platform, get_platform_system_prompt_hash(request.platform)
        )
    )
    system_prompt = str(generated.get("system_prompts", {}).get(request.platform, ""))
    user_prompt = str(generated.get("user_prompts", {}).get(request.platform, ""))
    usage_by_platform = generated.get("usage_by_platform", {})
    latency_by_platform = generated.get("latency_by_platform", {})
    retry_by_platform = generated.get("retry_by_platform", {})
    parse_by_platform = generated.get("parse_by_platform", {})
    regen_latency_ms = int(
        latency_by_platform.get(request.platform, 0) or 0
    )
    total_tokens_used = 0
    estimated_cost_usd = 0.0
    has_cost_samples = False
    has_usage_samples = False
    provider_attempt_count = 0
    parse_retry_count = 0
    if isinstance(usage_by_platform, dict):
        for _platform_name, usage_snapshot in usage_by_platform.items():
            if not isinstance(usage_snapshot, dict):
                continue
            raw_prompt_tokens = usage_snapshot.get("prompt_tokens")
            raw_completion_tokens = usage_snapshot.get("completion_tokens")
            if raw_prompt_tokens is None or raw_completion_tokens is None:
                continue
            prompt_tokens = int(raw_prompt_tokens or 0)
            completion_tokens = int(raw_completion_tokens or 0)
            total_tokens_used += prompt_tokens + completion_tokens
            has_usage_samples = True
            usage_cost = _estimate_openai_cost_usd_from_usage(usage_snapshot)
            if usage_cost is not None:
                has_cost_samples = True
                estimated_cost_usd += usage_cost
    tokens_used_for_lineage = total_tokens_used if has_usage_samples else None
    if isinstance(retry_by_platform, dict):
        for platform_name in selected_platforms:
            snapshot = retry_by_platform.get(platform_name)
            if not isinstance(snapshot, dict):
                continue
            provider_attempt_count += _safe_int(snapshot.get("attempt_count"), 0)
            parse_retry_count += _safe_int(snapshot.get("json_decode_retries"), 0)
    if include_finish:
        raw_finish = generated.get("finish_sentences")
        if isinstance(raw_finish, dict):
            finish_sentences = raw_finish

    persistence = _persist_regeneration_result(
        supabase=supabase,
        master_sku=canonical_master_sku,
        platform=request.platform,
        content_type=request.content_type,
        content=content,
        generation_model=_provider_label(provider),
        prompt_hash=prompt_hash,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        feedback_text=request.feedback,
        mode="with_feedback" if request.feedback else "simple",
        tokens_used=tokens_used_for_lineage,
        cost_usd=round(estimated_cost_usd, 6) if has_cost_samples else None,
        generation_diagnostics={
            "selected_platforms": list(selected_platforms),
            "usage_by_platform": usage_by_platform if isinstance(usage_by_platform, dict) else {},
            "latency_by_platform": latency_by_platform if isinstance(latency_by_platform, dict) else {},
            "parse_by_platform": parse_by_platform if isinstance(parse_by_platform, dict) else {},
            "retry_by_platform": retry_by_platform if isinstance(retry_by_platform, dict) else {},
            **_extract_query_intent_generation_diagnostics(generated),
        },
        latency_ms=regen_latency_ms,
        provider_attempt_count=provider_attempt_count,
        parse_retry_count=parse_retry_count,
        request_id=request_id,
        idempotency_key=request_idempotency_key,
    )

    if (
        finish_sentences
        and persistence["state"] == "completed"
        and _should_persist_finish_sentences(
            platform=request.platform,
            content_type=request.content_type,
            finish_sentences=finish_sentences,
        )
    ):
        try:
            persist_finish_sentences(
                supabase=supabase,
                master_sku=canonical_master_sku,
                platform=request.platform,
                finish_sentences=finish_sentences,
            )
        except Exception as e:
            logger.warning(
                "Failed to persist finish sentences for %s/%s: %s",
                canonical_master_sku,
                request.platform,
                e,
            )

    _persist_finish_prompt_lineage(
        supabase=supabase,
        master_sku=canonical_master_sku,
        generated=generated,
        mode="with_feedback" if request.feedback else "simple",
        generation_model=_provider_label(provider),
        generation_diagnostics={
            "selected_platforms": list(selected_platforms),
            "usage_by_platform": usage_by_platform if isinstance(usage_by_platform, dict) else {},
            "latency_by_platform": latency_by_platform if isinstance(latency_by_platform, dict) else {},
            "parse_by_platform": parse_by_platform if isinstance(parse_by_platform, dict) else {},
            "retry_by_platform": retry_by_platform if isinstance(retry_by_platform, dict) else {},
        },
        request_id=request_id,
        idempotency_key=request_idempotency_key,
    )

    # Persist correction if save_as_correction=True and there's session feedback (FIX-01)
    if request.save_as_correction and session_feedback:
        try:
            # Determine correction type from structured fields (priority order)
            if request.tone_style:
                correction_type = "tone"
            elif request.emphasis:
                correction_type = "emphasis"
            elif request.length_preference:
                correction_type = "length"
            else:
                correction_type = "free_text"

            supabase.table("sku_corrections").upsert(
                {
                    "master_sku": canonical_master_sku,
                    "platform": request.platform,
                    "content_type": request.content_type,
                    "correction_text": session_feedback,
                    "correction_type": correction_type,
                    "is_active": True,
                },
                on_conflict="master_sku,platform,content_type,correction_type,correction_text",
            ).execute()
            logger.info(
                "Saved persistent correction for %s/%s/%s (type=%s)",
                canonical_master_sku,
                request.platform,
                request.content_type,
                correction_type,
            )
        except Exception as e:
            logger.warning("Failed to save correction for %s: %s", canonical_master_sku, e)

    _emit_generation_summary(
        endpoint="regenerate",
        request_id=request_id,
        master_sku=canonical_master_sku,
        platform=request.platform,
        content_type=request.content_type,
        mode="with_feedback" if request.feedback else "simple",
        result_state=str(persistence.get("state", "completed")),
        tokens_used=tokens_used_for_lineage,
        cost_usd=round(estimated_cost_usd, 6) if has_cost_samples else None,
        latency_ms=regen_latency_ms,
        provider_attempt_count=provider_attempt_count,
        parse_retry_count=parse_retry_count,
        diagnostic_mode=bool(generated.get("diagnostic_mode", False)),
        finish_subcall_executed=bool(generated.get("finish_subcall_executed", False)),
        budget_stop_triggered=bool(generated.get("budget_stop_triggered", False)),
    )

    return RegenerateResponse(
        success=True,
        master_sku=canonical_master_sku,
        content_type=request.content_type,
        platform=request.platform,
        content=content,
        finish_sentences=finish_sentences,
        used_feedback=session_feedback is not None,
        prompt_hash=prompt_hash,
        model=_provider_label(provider),
        generated_content_id=(
            str(persistence.get("generated_content_id"))
            if persistence.get("generated_content_id")
            else None
        ),
        version=int(persistence.get("version", 0) or 0),
        state=str(persistence.get("state", "completed")),
        idempotent=bool(persistence.get("idempotent", False)),
        request_id=request_id,
    )
