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


def provider_label(provider: object) -> str:
    """Best-effort provider display name for lineage and logging."""
    if provider is None:
        return "unknown"
    name = getattr(provider, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    return provider.__class__.__name__


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


def extract_scoped_telemetry(
    *,
    platforms: list[str] | tuple[str, ...],
    usage_by_platform: dict | None,
    latency_by_platform: dict | None,
    retry_by_platform: dict | None,
) -> dict[str, object]:
    """Aggregate telemetry across one logical content scope.

    Description scopes on Google/Bing can span both the primary task and the
    shared finish task. This helper rolls those task-level snapshots up into the
    lineage record that represents the full request scope for one persisted row.
    """
    total_tokens = 0
    saw_tokens = False
    total_cost = 0.0
    saw_cost = False
    total_latency = 0
    saw_latency = False
    total_attempts = 0
    total_parse_retries = 0

    for platform in platforms:
        telemetry = extract_platform_telemetry(
            platform=platform,
            usage_by_platform=usage_by_platform,
            latency_by_platform=latency_by_platform,
            retry_by_platform=retry_by_platform,
        )
        if telemetry["tokens_used"] is not None:
            total_tokens += safe_int(telemetry["tokens_used"], 0)
            saw_tokens = True
        if telemetry["cost_usd"] is not None:
            total_cost += float(telemetry["cost_usd"])
            saw_cost = True
        if telemetry["latency_ms"] is not None:
            total_latency += safe_int(telemetry["latency_ms"], 0)
            saw_latency = True
        total_attempts += safe_int(telemetry["provider_attempt_count"], 0)
        total_parse_retries += safe_int(telemetry["parse_retry_count"], 0)

    return {
        "tokens_used": total_tokens if saw_tokens else None,
        "cost_usd": round(total_cost, 6) if saw_cost else None,
        "latency_ms": total_latency if saw_latency else None,
        "provider_attempt_count": total_attempts,
        "parse_retry_count": total_parse_retries,
    }
