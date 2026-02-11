"""In-memory metrics for reliability/observability verification."""

from __future__ import annotations

import contextlib
import threading
import time
from collections import defaultdict
from collections.abc import Iterator

MetricKey = tuple[str, tuple[tuple[str, str], ...]]


def _normalize_tags(tags: dict[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((str(k), str(v)) for k, v in tags.items()))


class MetricsRegistry:
    """Thread-safe in-process metrics store (counters + observed timings)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[MetricKey, int] = defaultdict(int)
        self._timings: dict[MetricKey, list[float]] = defaultdict(list)

    def increment(self, name: str, value: int = 1, **tags: str) -> None:
        key = (name, _normalize_tags(tags))
        with self._lock:
            self._counters[key] += int(value)

    def observe(self, name: str, value: float, **tags: str) -> None:
        key = (name, _normalize_tags(tags))
        with self._lock:
            self._timings[key].append(float(value))

    @contextlib.contextmanager
    def timer(self, name: str, **tags: str) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start, **tags)

    def snapshot(self) -> dict[str, dict[MetricKey, int | list[float]]]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "timings": {k: list(v) for k, v in self._timings.items()},
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._timings.clear()


metrics_registry = MetricsRegistry()

