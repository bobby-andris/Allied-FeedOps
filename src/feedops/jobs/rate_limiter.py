"""Token bucket rate limiter for Google Ads API calls.

This module implements a thread-safe token bucket algorithm to enforce rate limits
on API calls. The token bucket allows burst traffic up to the capacity while maintaining
a steady average rate.

Why we need this:
- Google Ads API has a 10 QPS (queries per second) rate limit per developer token
- Keyword Planner API has a lower rate limit (2 QPS recommended)
- Phase 0.3 testing validated batch size 10 with these limits
- Token bucket allows efficient burst processing while preventing quota exhaustion

Algorithm:
- Tokens are added at a constant rate (e.g., 10 tokens/second)
- Maximum tokens are capped at capacity (burst capacity)
- Operations consume tokens; if insufficient tokens, operation waits
- Thread-safe using threading.Lock for multi-threaded async contexts
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time

logger = logging.getLogger(__name__)


class TokenBucket:
    """Thread-safe token bucket rate limiter.

    Allows burst up to capacity, refills at constant rate.
    Thread-safe for use across multiple async tasks in same process.
    """

    def __init__(self, rate: float, capacity: int):
        """
        Args:
            rate: Tokens added per second (e.g., 10.0 for 10 QPS)
            capacity: Maximum tokens (burst capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        """Refill tokens based on elapsed time. Must be called with lock held."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        """Return current token count (after refill calculation)."""
        with self._lock:
            self._refill()
            return self._tokens

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens synchronously.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    async def acquire(self, tokens: int = 1) -> None:
        """Wait until tokens are available, then consume them.

        Args:
            tokens: Number of tokens to acquire

        This method blocks until sufficient tokens are available.
        Logs a warning if waiting exceeds 5 seconds (indicates sustained rate limiting).
        """
        start_time = time.monotonic()
        warned = False

        while True:
            if self.consume(tokens):
                return

            # Check if we've been waiting too long
            wait_time = time.monotonic() - start_time
            if wait_time > 5.0 and not warned:
                logger.warning(
                    f"Rate limiter waiting for {wait_time:.1f}s - sustained rate limiting detected. "
                    f"Rate: {self.rate} QPS, Capacity: {self.capacity}, Tokens requested: {tokens}"
                )
                warned = True

            # Poll every 10ms
            await asyncio.sleep(0.01)


# Pre-configured instances for Google Ads API
google_ads_limiter = TokenBucket(rate=10.0, capacity=20)
"""Rate limiter for standard Google Ads API calls (10 QPS with burst to 20)."""

keyword_planner_limiter = TokenBucket(rate=2.0, capacity=5)
"""Rate limiter for Keyword Planner API calls (2 QPS with burst to 5)."""
