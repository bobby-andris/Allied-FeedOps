"""Tests for token bucket rate limiter.

Validates JOB-08 requirement: Rate limiting enforcement for Google Ads API calls.
"""

import asyncio
import threading
import time

import pytest

from feedops.jobs.rate_limiter import (
    TokenBucket,
    google_ads_limiter,
    keyword_planner_limiter,
)


def test_consume_allows_burst_up_to_capacity():
    """Test that token bucket allows burst consumption up to capacity."""
    bucket = TokenBucket(rate=10.0, capacity=5)

    # Should be able to consume all 5 tokens quickly
    for i in range(5):
        assert bucket.consume(1) is True, f"Token {i+1} should be available"

    # 6th token should not be available (capacity exceeded)
    assert bucket.consume(1) is False, "Should not have tokens beyond capacity"


def test_consume_respects_rate():
    """Test that token bucket enforces rate limit after burst capacity depleted."""
    bucket = TokenBucket(rate=100.0, capacity=1)

    # Consume the single token
    assert bucket.consume(1) is True, "Initial token should be available"

    # Immediately try to consume again - should fail
    assert bucket.consume(1) is False, "Should not have tokens immediately after"

    # Sleep 0.015s (15ms) - at 100 tokens/second, should refill at least 1 token
    time.sleep(0.015)

    # Should now have a token available
    assert bucket.consume(1) is True, "Token should have refilled at expected rate"


def test_available_tokens_refills():
    """Test that available_tokens property correctly tracks refill over time."""
    bucket = TokenBucket(rate=10.0, capacity=10)

    # Consume all tokens
    for _ in range(10):
        assert bucket.consume(1) is True

    # Should be at 0 tokens
    assert bucket.available_tokens < 0.1, "Should have consumed all tokens"

    # Sleep 0.5s - at 10 tokens/second, should refill 5 tokens
    time.sleep(0.5)

    # Allow some tolerance for timing variance (±1 token)
    available = bucket.available_tokens
    assert 4.0 <= available <= 6.0, f"Expected ~5 tokens after 0.5s, got {available}"


@pytest.mark.asyncio
async def test_acquire_blocks_until_available():
    """Test that async acquire blocks until tokens are available."""
    bucket = TokenBucket(rate=100.0, capacity=1)

    # Consume the single token
    assert bucket.consume(1) is True

    # Start timer and call acquire (should block)
    start = time.monotonic()
    await bucket.acquire(1)
    elapsed = time.monotonic() - start

    # At 100 tokens/second, refill time is ~10ms
    # Allow generous tolerance for test timing variance (5-50ms)
    assert 0.005 <= elapsed <= 0.05, f"Expected ~10ms wait, got {elapsed*1000:.1f}ms"


def test_thread_safety():
    """Test that token bucket is thread-safe under concurrent access."""
    bucket = TokenBucket(rate=1000.0, capacity=100)
    consumed_count = []
    lock = threading.Lock()

    def consume_tokens():
        """Worker function to consume 10 tokens."""
        local_count = 0
        for _ in range(10):
            if bucket.consume(1):
                local_count += 1
        with lock:
            consumed_count.append(local_count)

    # Spawn 10 threads, each trying to consume 10 tokens
    threads = []
    for _ in range(10):
        t = threading.Thread(target=consume_tokens)
        t.start()
        threads.append(t)

    # Wait for all threads
    for t in threads:
        t.join()

    # Total consumed should equal capacity (100)
    total_consumed = sum(consumed_count)
    assert total_consumed == 100, f"Expected 100 consumed, got {total_consumed}"


def test_preconfigured_limiters():
    """Test that pre-configured limiters have correct parameters."""
    # Google Ads limiter: 10 QPS with burst to 20
    assert google_ads_limiter.rate == 10.0, "Google Ads limiter should have 10 QPS rate"
    assert google_ads_limiter.capacity == 20, "Google Ads limiter should have capacity 20"

    # Keyword Planner limiter: 2 QPS with burst to 5
    assert keyword_planner_limiter.rate == 2.0, "Keyword Planner limiter should have 2 QPS rate"
    assert keyword_planner_limiter.capacity == 5, "Keyword Planner limiter should have capacity 5"
