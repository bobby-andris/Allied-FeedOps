"""Provider-level backoff and circuit breaker helpers."""

from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def circuit_breaker_enabled() -> bool:
    return _truthy(os.getenv("FEEDOPS_PROVIDER_CIRCUIT_BREAKER_ENABLED", "1"))


def circuit_failure_threshold() -> int:
    return max(1, _int_env("FEEDOPS_PROVIDER_CIRCUIT_FAILURE_THRESHOLD", 5))


def circuit_cooldown_seconds() -> float:
    return max(1.0, _float_env("FEEDOPS_PROVIDER_CIRCUIT_COOLDOWN_SECONDS", 30.0))


def compute_backoff_seconds(attempt: int) -> float:
    """Exponential backoff with bounded jitter."""
    base = max(0.0, _float_env("FEEDOPS_PROVIDER_BACKOFF_BASE_SECONDS", 0.25))
    max_delay = max(base, _float_env("FEEDOPS_PROVIDER_BACKOFF_MAX_SECONDS", 8.0))
    jitter = max(0.0, _float_env("FEEDOPS_PROVIDER_BACKOFF_JITTER_SECONDS", 0.1))
    delay = min(max_delay, base * (2**max(attempt, 0)))
    if jitter:
        delay += random.uniform(0.0, jitter)
    return max(0.0, delay)


def is_retryable_provider_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retryable_markers = (
        "429",
        "529",
        "rate limit",
        "resource_exhausted",
        "temporarily unavailable",
        "service unavailable",
        "overloaded",
        "timeout",
        "timed out",
        "connection reset",
        "connection aborted",
        "too many requests",
    )
    return any(marker in text for marker in retryable_markers)


@dataclass
class CircuitState:
    failures: int = 0
    open_until: float = 0.0


class CircuitBreakerRegistry:
    """Process-wide circuit state keyed by provider name/model."""

    def __init__(self) -> None:
        self._states: dict[str, CircuitState] = {}
        self._lock = threading.Lock()

    def _state(self, key: str) -> CircuitState:
        state = self._states.get(key)
        if state is None:
            state = CircuitState()
            self._states[key] = state
        return state

    def allow_request(self, key: str) -> tuple[bool, float]:
        if not circuit_breaker_enabled():
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            state = self._state(key)
            if state.open_until > now:
                return False, state.open_until - now
            return True, 0.0

    def record_success(self, key: str) -> None:
        with self._lock:
            state = self._state(key)
            state.failures = 0
            state.open_until = 0.0

    def record_failure(self, key: str) -> bool:
        """Record one failed request. Returns True when the circuit opens."""
        if not circuit_breaker_enabled():
            return False
        now = time.monotonic()
        opened = False
        with self._lock:
            state = self._state(key)
            if state.open_until <= now:
                state.open_until = 0.0
            state.failures += 1
            if state.failures >= circuit_failure_threshold():
                state.open_until = now + circuit_cooldown_seconds()
                opened = True
        return opened

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


circuit_breakers = CircuitBreakerRegistry()

