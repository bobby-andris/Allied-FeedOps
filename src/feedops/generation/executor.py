"""Task-scoped generation execution with a compatibility bridge for legacy callers."""

from __future__ import annotations

import inspect
import logging
import os
import time
import uuid
from collections import defaultdict
from typing import Any

from feedops.api.generation_telemetry import (
    estimate_openai_cost_usd_from_usage,
    safe_int,
)
from feedops.api.prompt_loader import get_finish_list
from feedops.api.runtime_controls import (
    diagnostic_mode_enabled,
    diagnostic_skip_finish_subcall_enabled,
    request_cost_usd_cap,
)
from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.generation.results import ExecutionBundle, TaskResult
from feedops.generation.tasks import (
    build_task_prompt,
    build_task_schema,
    build_task_system_prompt,
    finish_should_execute,
    legacy_field_key,
    task_prompt_hash,
    task_result_content,
)
from feedops.models.parent_sku import ParentSKU
from feedops.pipeline.evidence import (
    build_evidence_table,
    filter_evidence_for_copy_context,
    format_evidence_markdown,
)
from feedops.pipeline.finish_sentence_placeholder import build_fallback_finish_sentences
from feedops.pipeline.finish_sentence_placeholder import (
    normalize_base_description_with_finish_placeholder,
    strip_generic_finish_count_claims,
    strip_hardcoded_finish_names,
)
from feedops.pipeline.query_intent_brief import build_query_intent_context
from feedops.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ExecutionBudgetExceededError(RuntimeError):
    """Raised when estimated execution cost crosses configured request cap."""

    def __init__(
        self,
        *,
        cap_usd: float,
        estimated_cost_usd: float,
        platform: str,
    ) -> None:
        self.cap_usd = float(cap_usd)
        self.estimated_cost_usd = float(estimated_cost_usd)
        self.platform = platform
        super().__init__(
            "generation_request_budget_exceeded:"
            f" platform={platform} estimated_cost_usd={estimated_cost_usd:.6f}"
            f" cap_usd={cap_usd:.6f}"
        )


def _platform_reasoning_effort(platform: str, default_reasoning_effort: str) -> str:
    if platform == "finish":
        return "low"
    return default_reasoning_effort


def _platform_completion_cap(platform: str, base_cap: int) -> int:
    normalized_cap = max(1, int(base_cap))
    default_cap = max(
        1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_DEFAULT", "8000"))
    )
    finish_cap = max(
        1,
        int(
            os.getenv(
                "FEEDOPS_PLATFORM_COMPLETION_CAP_FINISH",
                os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_DEFAULT", "2000"),
            )
        ),
    )
    platform_limits = {
        "google": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_GOOGLE", str(default_cap)))
        ),
        "bing": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_BING", str(default_cap)))
        ),
        "shopify": max(
            1, int(os.getenv("FEEDOPS_PLATFORM_COMPLETION_CAP_SHOPIFY", str(default_cap)))
        ),
        "finish": finish_cap,
    }
    limit = platform_limits.get(platform)
    if limit is None:
        return normalized_cap
    return min(normalized_cap, limit)


async def _generate_with_provider_compat(
    *,
    provider: LLMProvider,
    prompt: str,
    schema: dict[str, object],
    system_prompt: str,
    reasoning_effort: str,
    max_completion_tokens: int,
) -> dict[str, object]:
    generate_fn = provider.generate
    signature = inspect.signature(generate_fn)
    accepts_varkw = any(
        param.kind == inspect.Parameter.VAR_KEYWORD
        for param in signature.parameters.values()
    )
    kwargs: dict[str, object] = {
        "prompt": prompt,
        "schema": schema,
        "system_prompt": system_prompt,
    }
    if accepts_varkw or "reasoning_effort" in signature.parameters:
        kwargs["reasoning_effort"] = reasoning_effort
    if accepts_varkw or "max_completion_tokens" in signature.parameters:
        kwargs["max_completion_tokens"] = max_completion_tokens
    return await generate_fn(**kwargs)


def _resolve_requested_platforms(
    selected_platforms: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    ordered = ("google", "bing", "shopify", "finish")
    if not selected_platforms:
        return ordered
    normalized = {
        str(platform).strip().lower()
        for platform in selected_platforms
        if str(platform).strip()
    }
    resolved = tuple(platform for platform in ordered if platform in normalized)
    return resolved or ordered


def _resolve_selected_content_types(
    selected_content_types: tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    ordered = ("title", "description")
    if not selected_content_types:
        return ordered
    normalized = {
        str(content_type).strip().lower()
        for content_type in selected_content_types
        if str(content_type).strip()
    }
    resolved = tuple(content_type for content_type in ordered if content_type in normalized)
    return resolved or ordered


def _build_task_specs(
    *,
    parent_sku: ParentSKU,
    selected_platforms: tuple[str, ...],
    selected_content_types: tuple[str, ...],
    prompt_version: str,
    request_id: str,
    diagnostic_mode: bool,
    cost_cap_usd: float | None,
) -> list[TaskSpec]:
    tasks: list[TaskSpec] = []
    for platform in selected_platforms:
        if platform == "finish":
            continue
        for content_type in selected_content_types:
            kind = (
                GenerationTaskKind.TITLE
                if content_type == "title"
                else GenerationTaskKind.DESCRIPTION_BASE
            )
            tasks.append(
                TaskSpec(
                    task_id=uuid.uuid4().hex,
                    kind=kind,
                    master_sku=parent_sku.master_sku,
                    platform=platform,
                    content_type=content_type,
                    prompt_version=prompt_version,
                    request_id=request_id,
                    diagnostic_mode=diagnostic_mode,
                    cost_cap_usd=cost_cap_usd,
                )
            )

    if finish_should_execute(
        selected_platforms=selected_platforms,
        selected_content_types=selected_content_types,
    ):
        tasks.append(
            TaskSpec(
                task_id=uuid.uuid4().hex,
                kind=GenerationTaskKind.FINISH_SENTENCES,
                master_sku=parent_sku.master_sku,
                platform="finish",
                content_type="description",
                prompt_version=prompt_version,
                request_id=request_id,
                diagnostic_mode=diagnostic_mode,
                cost_cap_usd=cost_cap_usd,
                context_refs={
                    "target_platforms": [
                        platform
                        for platform in selected_platforms
                        if platform in {"google", "bing"}
                    ]
                },
            )
        )

    return tasks


def _task_result_lookup_key(result: TaskResult) -> str:
    if result.kind == GenerationTaskKind.FINISH_SENTENCES:
        return "finish:finish_sentences"
    return f"{result.platform}:{result.content_type}"


def _aggregate_usage(
    current: dict[str, int],
    usage_snapshot: dict[str, Any],
) -> dict[str, int]:
    if not isinstance(usage_snapshot, dict):
        return current
    aggregated = dict(current)
    for key in ("prompt_tokens", "completion_tokens", "cached_tokens"):
        aggregated[key] = safe_int(aggregated.get(key), 0) + safe_int(
            usage_snapshot.get(key), 0
        )
    return aggregated


def _aggregate_retries(
    current: dict[str, int],
    retry_snapshot: dict[str, Any],
) -> dict[str, int]:
    if not isinstance(retry_snapshot, dict):
        return current
    aggregated = dict(current)
    for key in ("attempt_count", "json_decode_retries"):
        aggregated[key] = max(
            safe_int(aggregated.get(key), 0),
            safe_int(retry_snapshot.get(key), 0),
        )
    return aggregated


def _task_result_payload(result: TaskResult) -> dict[str, object]:
    payload = {
        "task_id": result.task_id,
        "kind": result.kind,
        "platform": result.platform,
        "content_type": result.content_type,
        "status": result.status,
        "prompt_hash": result.prompt_hash,
        "system_prompt": result.system_prompt,
        "user_prompt": result.user_prompt,
        "tokens_used": result.tokens_used,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
        "provider_attempt_count": result.provider_attempt_count,
        "parse_retry_count": result.parse_retry_count,
        "request_id": result.request_id,
        "metadata": result.metadata,
    }
    if result.content:
        payload["content"] = result.content
    return payload


def _normalize_task_content(
    *,
    spec: TaskSpec,
    content: str,
) -> str:
    """Apply task-level content normalization shared across all execution modes."""
    normalized = (content or "").strip()
    if (
        spec.kind == GenerationTaskKind.DESCRIPTION_BASE
        and spec.platform in {"google", "bing"}
    ):
        normalized = normalize_base_description_with_finish_placeholder(
            strip_hardcoded_finish_names(
                strip_generic_finish_count_claims(normalized),
                get_finish_list(),
            )
        )
    return normalized


def _build_legacy_payload(
    *,
    bundle: ExecutionBundle,
    selected_platforms: tuple[str, ...],
    diagnostic_mode: bool,
    finish_subcall_skipped: bool,
    estimated_cost_total_usd: float,
) -> dict[str, object]:
    response: dict[str, object] = {
        "google_title": "",
        "google_short_title": "",
        "google_description": "",
        "bing_title": "",
        "bing_description": "",
        "shopify_title": "",
        "shopify_description": "",
        "shopify_meta_description": "",
        "finish_sentences": build_fallback_finish_sentences(get_finish_list()),
        "prompt_hashes": {},
        "system_prompts": {},
        "user_prompts": {},
        "usage_by_platform": {},
        "latency_by_platform": {},
        "parse_by_platform": {},
        "retry_by_platform": {},
        "raw_by_platform": {},
        "schema_hashes": {},
        "task_results": {},
        "diagnostic_mode": diagnostic_mode,
        "finish_subcall_executed": False,
        "finish_subcall_skipped": finish_subcall_skipped,
        "budget_stop_triggered": False,
        "estimated_cost_total_usd": round(estimated_cost_total_usd, 6),
        "query_intent_diagnostics": bundle.summary.get("query_intent_diagnostics", {}),
    }

    usage_by_platform: dict[str, dict[str, int]] = defaultdict(dict)
    retry_by_platform: dict[str, dict[str, int]] = defaultdict(dict)

    for result in bundle.results:
        response["task_results"][_task_result_lookup_key(result)] = _task_result_payload(result)
        response["raw_by_platform"][result.platform] = result.raw_payload
        response["system_prompts"][result.platform] = result.system_prompt
        response["user_prompts"][result.platform] = result.user_prompt
        response["prompt_hashes"][result.platform] = result.prompt_hash
        response["latency_by_platform"][result.platform] = safe_int(result.latency_ms, 0)
        response["parse_by_platform"][result.platform] = {
            "parse_mode": result.metadata.get("parse_mode", "strict_json"),
            "missing_keys": result.metadata.get("missing_keys", []),
        }
        retry_by_platform[result.platform] = _aggregate_retries(
            retry_by_platform[result.platform],
            {
                "attempt_count": result.provider_attempt_count,
                "json_decode_retries": result.parse_retry_count,
            },
        )
        if result.tokens_used is not None:
            prompt_tokens = safe_int(result.raw_payload.get("_usage_prompt_tokens"), 0)
            completion_tokens = safe_int(
                result.raw_payload.get("_usage_completion_tokens"), 0
            )
            cached_tokens = safe_int(result.raw_payload.get("_usage_cached_tokens"), 0)
            if prompt_tokens or completion_tokens or cached_tokens:
                usage_by_platform[result.platform] = _aggregate_usage(
                    usage_by_platform[result.platform],
                    {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "cached_tokens": cached_tokens,
                    },
                )
            else:
                usage_by_platform[result.platform] = _aggregate_usage(
                    usage_by_platform[result.platform],
                    {
                        "prompt_tokens": result.tokens_used,
                        "completion_tokens": 0,
                        "cached_tokens": 0,
                    },
                )

        if result.kind == GenerationTaskKind.FINISH_SENTENCES:
            finish_sentences = result.metadata.get("finish_sentences")
            if isinstance(finish_sentences, dict):
                response["finish_sentences"] = finish_sentences
            response["finish_subcall_executed"] = True
            continue

        field_key = legacy_field_key(result.platform, result.content_type)
        response[field_key] = result.content
        if result.platform == "google" and result.content_type == "title":
            response["google_short_title"] = str(
                result.metadata.get("google_short_title", "")
            ).strip()
        if result.platform == "shopify" and result.content_type == "description":
            response["shopify_meta_description"] = str(
                result.metadata.get("shopify_meta_description", "")
            ).strip()

    response["usage_by_platform"] = dict(usage_by_platform)
    response["retry_by_platform"] = dict(retry_by_platform)
    response["selected_platforms"] = list(selected_platforms)
    response["task_kinds_executed"] = [str(result.kind) for result in bundle.results]
    response["provider_call_count"] = len(bundle.results)
    return response


async def execute_generation_bundle(
    *,
    parent_sku: ParentSKU,
    provider: LLMProvider,
    prompt_version: str = "v2",
    feedback_by_platform: dict[str, str] | None = None,
    reasoning_effort: str = "medium",
    max_completion_tokens: int = 6000,
    selected_platforms: tuple[str, ...] | list[str] | None = None,
    selected_content_types: tuple[str, ...] | list[str] | None = None,
    request_id: str | None = None,
    prompt_overrides: dict[str, str] | None = None,
    system_prompt_overrides: dict[str, str] | None = None,
) -> ExecutionBundle:
    """Execute a scoped task graph for one master SKU."""
    requested_platforms = _resolve_requested_platforms(selected_platforms)
    requested_content_types = _resolve_selected_content_types(selected_content_types)
    diagnostic_mode = diagnostic_mode_enabled()
    finish_subcall_skipped = False
    if (
        diagnostic_mode
        and "finish" in requested_platforms
        and diagnostic_skip_finish_subcall_enabled()
    ):
        requested_platforms = tuple(
            platform for platform in requested_platforms if platform != "finish"
        )
        finish_subcall_skipped = True

    resolved_request_id = (request_id or "").strip() or uuid.uuid4().hex
    cost_cap_usd = request_cost_usd_cap()
    evidence = build_evidence_table(parent_sku)
    evidence_for_copy = filter_evidence_for_copy_context(evidence)
    evidence_markdown = format_evidence_markdown(
        evidence_for_copy if isinstance(evidence_for_copy, list) else [],
        for_customer_copy=True,
    )
    eligible_query_intent_scope = bool(
        {"google", "bing"} & set(requested_platforms)
        and {"title", "description"} & set(requested_content_types)
    )
    query_intent_context = (
        build_query_intent_context(parent_sku, evidence)
        if eligible_query_intent_scope
        else None
    )
    task_specs = _build_task_specs(
        parent_sku=parent_sku,
        selected_platforms=requested_platforms,
        selected_content_types=requested_content_types,
        prompt_version=prompt_version,
        request_id=resolved_request_id,
        diagnostic_mode=diagnostic_mode,
        cost_cap_usd=cost_cap_usd,
    )

    results: list[TaskResult] = []
    estimated_cost_total_usd = 0.0

    for spec in task_specs:
        user_prompt_override = (
            prompt_overrides.get(spec.platform)
            if isinstance(prompt_overrides, dict)
            else None
        )
        if isinstance(user_prompt_override, str) and user_prompt_override.strip():
            user_prompt = user_prompt_override
        else:
            user_prompt = build_task_prompt(
                spec,
                parent_sku=parent_sku,
                evidence=evidence,
                evidence_markdown=evidence_markdown,
                feedback_by_platform=feedback_by_platform,
                query_intent_context=query_intent_context,
            )
        system_prompt_override = (
            system_prompt_overrides.get(spec.platform)
            if isinstance(system_prompt_overrides, dict)
            else None
        )
        if isinstance(system_prompt_override, str) and system_prompt_override.strip():
            system_prompt = system_prompt_override
        else:
            system_prompt = build_task_system_prompt(spec)
        schema = build_task_schema(spec)
        platform_reasoning = _platform_reasoning_effort(spec.platform, reasoning_effort)
        platform_cap = _platform_completion_cap(spec.platform, max_completion_tokens)

        started = time.perf_counter()
        payload = await _generate_with_provider_compat(
            provider=provider,
            prompt=user_prompt,
            schema=schema,
            system_prompt=system_prompt,
            reasoning_effort=platform_reasoning,
            max_completion_tokens=platform_cap,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage_snapshot = getattr(provider, "last_usage", {})
        parse_snapshot = getattr(provider, "last_parse_details", {})
        retry_snapshot = getattr(provider, "last_retry_counts", {})
        content, metadata = task_result_content(payload, spec)
        content = _normalize_task_content(spec=spec, content=content)
        tokens_used = None
        if isinstance(usage_snapshot, dict):
            prompt_tokens = usage_snapshot.get("prompt_tokens")
            completion_tokens = usage_snapshot.get("completion_tokens")
            if prompt_tokens is not None and completion_tokens is not None:
                tokens_used = safe_int(prompt_tokens) + safe_int(completion_tokens)
        cost_usd = (
            estimate_openai_cost_usd_from_usage(usage_snapshot)
            if isinstance(usage_snapshot, dict)
            else None
        )
        if cost_usd is not None:
            estimated_cost_total_usd += cost_usd
            if cost_cap_usd is not None and estimated_cost_total_usd > cost_cap_usd:
                raise ExecutionBudgetExceededError(
                    cap_usd=cost_cap_usd,
                    estimated_cost_usd=estimated_cost_total_usd,
                    platform=spec.platform,
                )

        payload_with_usage = dict(payload)
        if isinstance(usage_snapshot, dict):
            payload_with_usage["_usage_prompt_tokens"] = safe_int(
                usage_snapshot.get("prompt_tokens"), 0
            )
            payload_with_usage["_usage_completion_tokens"] = safe_int(
                usage_snapshot.get("completion_tokens"), 0
            )
            payload_with_usage["_usage_cached_tokens"] = safe_int(
                usage_snapshot.get("cached_tokens"), 0
            )

        results.append(
            TaskResult(
                task_id=spec.task_id,
                kind=str(spec.kind),
                status="completed",
                platform=spec.platform,
                content_type=spec.content_type,
                content=content,
                metadata={
                    **metadata,
                    "parse_mode": parse_snapshot.get("parse_mode", "strict_json")
                    if isinstance(parse_snapshot, dict)
                    else "strict_json",
                    "missing_keys": parse_snapshot.get("missing_keys", [])
                    if isinstance(parse_snapshot, dict)
                    else [],
                },
                tokens_used=tokens_used,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                provider_attempt_count=safe_int(
                    retry_snapshot.get("attempt_count"), 0
                )
                if isinstance(retry_snapshot, dict)
                else 0,
                parse_retry_count=safe_int(
                    retry_snapshot.get("json_decode_retries"), 0
                )
                if isinstance(retry_snapshot, dict)
                else 0,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_hash=task_prompt_hash(system_prompt, user_prompt),
                request_id=resolved_request_id,
                raw_payload=payload_with_usage,
            )
        )

    return ExecutionBundle(
        tasks=task_specs,
        results=results,
        summary={
            "selected_platforms": list(requested_platforms),
            "selected_content_types": list(requested_content_types),
            "diagnostic_mode": diagnostic_mode,
            "finish_subcall_skipped": finish_subcall_skipped,
            "estimated_cost_total_usd": round(estimated_cost_total_usd, 6),
            "query_intent_diagnostics": (
                query_intent_context.diagnostics.as_dict()
                if query_intent_context is not None
                else {}
            ),
        },
    )


async def execute_generation_legacy_payload(
    *,
    parent_sku: ParentSKU,
    provider: LLMProvider,
    prompt_version: str = "v2",
    feedback_by_platform: dict[str, str] | None = None,
    reasoning_effort: str = "medium",
    max_completion_tokens: int = 6000,
    selected_platforms: tuple[str, ...] | list[str] | None = None,
    selected_content_types: tuple[str, ...] | list[str] | None = None,
    request_id: str | None = None,
    prompt_overrides: dict[str, str] | None = None,
    system_prompt_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    """Compatibility bridge that preserves the legacy generate_per_platform payload."""
    requested_platforms = _resolve_requested_platforms(selected_platforms)
    bundle = await execute_generation_bundle(
        parent_sku=parent_sku,
        provider=provider,
        prompt_version=prompt_version,
        feedback_by_platform=feedback_by_platform,
        reasoning_effort=reasoning_effort,
        max_completion_tokens=max_completion_tokens,
        selected_platforms=requested_platforms,
        selected_content_types=selected_content_types,
        request_id=request_id,
        prompt_overrides=prompt_overrides,
        system_prompt_overrides=system_prompt_overrides,
    )
    return _build_legacy_payload(
        bundle=bundle,
        selected_platforms=requested_platforms,
        diagnostic_mode=bool(bundle.summary.get("diagnostic_mode")),
        finish_subcall_skipped=bool(bundle.summary.get("finish_subcall_skipped")),
        estimated_cost_total_usd=float(bundle.summary.get("estimated_cost_total_usd", 0.0)),
    )
