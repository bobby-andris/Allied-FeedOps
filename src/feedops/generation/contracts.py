"""Canonical task contracts for task-scoped generation execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class GenerationTaskKind(StrEnum):
    """Supported generation task kinds."""

    TITLE = "title"
    DESCRIPTION_BASE = "description_base"
    FINISH_SENTENCES = "finish_sentences"
    VARIANT_ADAPTATION = "variant_adaptation"


@dataclass(frozen=True)
class TaskSpec:
    """Canonical execution spec for exactly one model-backed generation step."""

    task_id: str
    kind: GenerationTaskKind
    master_sku: str
    platform: str
    content_type: str
    prompt_version: str
    request_id: str
    variant_sku: str | None = None
    diagnostic_mode: bool = False
    cost_cap_usd: float | None = None
    job_id: str | None = None
    parent_task_id: str | None = None
    context_refs: dict[str, Any] = field(default_factory=dict)
