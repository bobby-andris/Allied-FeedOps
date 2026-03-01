"""Task-scoped generation primitives and execution helpers."""

from feedops.generation.contracts import GenerationTaskKind, TaskSpec
from feedops.generation.results import ExecutionBundle, TaskResult

__all__ = [
    "ExecutionBundle",
    "GenerationTaskKind",
    "TaskResult",
    "TaskSpec",
]
