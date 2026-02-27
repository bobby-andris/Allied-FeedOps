"""Shared generation telemetry normalization helpers."""

from __future__ import annotations


def safe_int(value: object, default: int = 0) -> int:
    """Best-effort int conversion for telemetry snapshots."""
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def estimate_openai_cost_usd_from_usage(usage: dict[str, int] | None) -> float | None:
    """Estimate OpenAI cost from usage snapshot for lineage diagnostics."""
    if not isinstance(usage, dict):
        return None
    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    if prompt_tokens is None or completion_tokens is None:
        return None
    cached_tokens = usage.get("cached_tokens", 0) or 0
    uncached_input = max(int(prompt_tokens) - int(cached_tokens), 0)
    input_cost = (uncached_input / 1_000_000) * 1.75 + (cached_tokens / 1_000_000) * 1.75 * 0.5
    output_cost = (int(completion_tokens) / 1_000_000) * 14.0
    return round(input_cost + output_cost, 6)


def extract_platform_telemetry(
    *,
    platform: str,
    usage_by_platform: dict | None,
    latency_by_platform: dict | None,
    retry_by_platform: dict | None,
) -> dict[str, object]:
    """Normalize per-platform usage/latency/retry diagnostics."""
    usage_snapshot: dict = {}
    if isinstance(usage_by_platform, dict):
        raw_usage = usage_by_platform.get(platform)
        if isinstance(raw_usage, dict):
            usage_snapshot = raw_usage

    latency_ms: int | None = None
    if isinstance(latency_by_platform, dict) and platform in latency_by_platform:
        latency_ms = safe_int(latency_by_platform.get(platform), 0)

    retry_snapshot: dict = {}
    if isinstance(retry_by_platform, dict):
        raw_retry = retry_by_platform.get(platform)
        if isinstance(raw_retry, dict):
            retry_snapshot = raw_retry

    prompt_tokens = usage_snapshot.get("prompt_tokens")
    completion_tokens = usage_snapshot.get("completion_tokens")
    tokens_used: int | None = None
    if prompt_tokens is not None and completion_tokens is not None:
        tokens_used = safe_int(prompt_tokens) + safe_int(completion_tokens)

    cost_usd = estimate_openai_cost_usd_from_usage(usage_snapshot) if usage_snapshot else None

    return {
        "tokens_used": tokens_used,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "provider_attempt_count": safe_int(retry_snapshot.get("attempt_count"), 0),
        "parse_retry_count": safe_int(retry_snapshot.get("json_decode_retries"), 0),
    }
