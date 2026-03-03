"""Task-scoped generation result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from feedops.generation.contracts import TaskSpec


@dataclass
class TaskResult:
    """Structured result for one generation task."""

    task_id: str
    kind: str
    status: str
    platform: str
    content_type: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    tokens_used: int | None = None
    cost_usd: float | None = None
    latency_ms: int | None = None
    provider_attempt_count: int = 0
    parse_retry_count: int = 0
    system_prompt: str = ""
    user_prompt: str = ""
    prompt_hash: str = ""
    request_id: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionBundle:
    """Complete task graph execution for one request scope."""

    tasks: list[TaskSpec]
    results: list[TaskResult]
    summary: dict[str, Any] = field(default_factory=dict)
