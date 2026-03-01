"""Helpers for using task-scoped results with the existing persistence layer."""

from __future__ import annotations

from datetime import datetime, timezone

from feedops.generation.results import TaskResult


def task_result_key(platform: str, content_type: str) -> str:
    """Stable lookup key for a content-bearing task result."""
    return f"{platform}:{content_type}"


def get_task_result(
    task_results: dict[str, dict[str, object]] | None,
    *,
    platform: str,
    content_type: str,
) -> dict[str, object]:
    """Fetch a content-bearing task result payload by platform/content type."""
    if not isinstance(task_results, dict):
        return {}
    payload = task_results.get(task_result_key(platform, content_type))
    return payload if isinstance(payload, dict) else {}


def get_finish_task_result(
    task_results: dict[str, dict[str, object]] | None,
) -> dict[str, object]:
    """Fetch the finish-sentence task result payload when it exists."""
    if not isinstance(task_results, dict):
        return {}
    payload = task_results.get("finish:finish_sentences")
    return payload if isinstance(payload, dict) else {}


def serialize_task_result(result: TaskResult) -> dict[str, object]:
    """Convert a task result into a persistence-friendly dict."""
    return {
        "task_id": result.task_id,
        "kind": result.kind,
        "status": result.status,
        "platform": result.platform,
        "content_type": result.content_type,
        "content": result.content,
        "metadata": result.metadata,
        "tokens_used": result.tokens_used,
        "cost_usd": result.cost_usd,
        "latency_ms": result.latency_ms,
        "provider_attempt_count": result.provider_attempt_count,
        "parse_retry_count": result.parse_retry_count,
        "system_prompt": result.system_prompt,
        "user_prompt": result.user_prompt,
        "prompt_hash": result.prompt_hash,
        "request_id": result.request_id,
        "raw_payload": result.raw_payload,
    }


def should_persist_finish_sentences(
    *,
    platform: str,
    content_type: str,
    finish_sentences: object,
) -> bool:
    """Persist finish maps only for Google/Bing description flows with concrete content."""
    return (
        content_type == "description"
        and platform in {"google", "bing"}
        and isinstance(finish_sentences, dict)
        and bool(finish_sentences)
    )


def persist_finish_sentences(
    *,
    supabase,
    master_sku: str,
    platform: str,
    finish_sentences: dict[str, str],
) -> bool:
    """Upsert finish maps with an explicit freshness timestamp for lineage comparisons."""
    if not should_persist_finish_sentences(
        platform=platform,
        content_type="description",
        finish_sentences=finish_sentences,
    ):
        return False
    supabase.table("variant_finish_sentences").upsert(
        {
            "master_sku": master_sku,
            "platform": platform,
            "finish_sentences": finish_sentences,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="master_sku,platform",
    ).execute()
    return True
