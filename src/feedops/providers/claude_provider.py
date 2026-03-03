"""Anthropic Claude LLM provider with structured JSON output and retry logic."""

import asyncio
import base64
import json
import logging
import time
from typing import Any

from anthropic import AsyncAnthropic

from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.providers.base import ImageInput, LLMError, LLMProvider
from feedops.providers.openai_provider import _parse_json_payload
from feedops.providers.reliability import (
    circuit_breakers,
    compute_backoff_seconds,
    is_retryable_provider_error,
)

logger = logging.getLogger(__name__)


def _extract_claude_usage(response: Any) -> dict[str, int]:
    """Normalize Anthropic usage fields to standard provider dict.

    Anthropic field names differ from OpenAI:
      input_tokens -> prompt_tokens
      output_tokens -> completion_tokens
      cache_read_input_tokens -> cached_tokens

    Args:
        response: Anthropic API response object.

    Returns:
        Dict with prompt_tokens, completion_tokens, cached_tokens keys.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
        "cached_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }


class ClaudeProvider(LLMProvider):
    """Anthropic Claude provider with structured JSON output.

    Features:
    - Structured JSON output via output_config.format with json_schema type (GA)
    - Automatic prompt caching via cache_control ephemeral mode
    - Retry with repair loop on JSON parse failures
    - Token usage logging matching OpenAIProvider's interface exactly
    - Full image support via Anthropic base64 source format
    - Circuit breaker and backoff using shared reliability.py infrastructure
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 3,
        *,
        sdk_timeout_seconds: float | None = None,
        max_total_seconds: float | None = None,
        json_retry_max: int | None = None,
    ):
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if sdk_timeout_seconds is not None:
            client_kwargs["timeout"] = max(sdk_timeout_seconds, 1.0)
        self.client = AsyncAnthropic(**client_kwargs)
        self.model = model
        self.max_retries = max(1, max_retries)
        self.max_total_seconds = (
            max_total_seconds if max_total_seconds is not None else 300.0
        )
        self.json_retry_max = (
            max(0, int(json_retry_max)) if json_retry_max is not None else 1
        )
        self._last_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
        }
        self._last_parse_details: dict[str, Any] = {
            "parse_mode": "none",
            "parsed_key_count": 0,
            "expected_key_count": 0,
            "missing_keys": [],
        }
        self._last_retry_counts: dict[str, int] = {
            "attempt_count": 0,
            "json_decode_retries": 0,
            "api_retries": 0,
            "budget_retries": 0,
        }

    @property
    def name(self) -> str:
        return f"claude/{self.model}"

    async def aclose(self) -> None:
        """Close the underlying AsyncAnthropic HTTP client explicitly."""
        await self.client.close()

    async def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            return bool(response.content)
        except Exception as e:
            logger.warning("Claude health check failed: %s", e)
            return False

    async def generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response with retry loop.

        Uses output_config.format with json_schema type for constrained decoding.
        Automatic prompt caching via cache_control ephemeral mode.

        Args:
            prompt: User prompt (dynamic per-SKU content).
            schema: Expected JSON schema for structured output.
            image: Optional image for multimodal generation.
            system_prompt: Optional static system prompt (sent as system= kwarg,
                not in messages list, for Anthropic caching optimization).
            reasoning_effort: Accepted but not used in Phase 5. Extended thinking
                will be mapped in Phase 6 (low=2000, medium=8000, high=20000
                budget_tokens). Logged at debug level if provided.
            max_completion_tokens: Optional max output token budget override.

        Returns:
            Parsed JSON dict matching the schema.

        Raises:
            LLMError: After max_retries failures or circuit breaker open.
        """
        if reasoning_effort is not None:
            logger.debug(
                "reasoning_effort=%s passed to ClaudeProvider but not used in Phase 5",
                reasoning_effort,
            )

        circuit_ok, cooldown_remaining = circuit_breakers.allow_request(self.name)
        if not circuit_ok:
            metrics_registry.increment(
                "provider_circuit_open_total", provider=self.name
            )
            raise LLMError(
                f"Circuit breaker open ({cooldown_remaining:.2f}s remaining)",
                self.name,
                0,
            )

        start_time = time.perf_counter()
        log_event(
            logger,
            logging.INFO,
            "provider.generate.start",
            provider=self.name,
            has_image=bool(image),
        )

        max_tokens = max_completion_tokens or 8000

        # Build initial messages list.
        # NOTE: Anthropic system prompt is a separate kwarg, NOT a message.
        # Image messages use base64 source format (different from OpenAI image_url format).
        if image:
            encoded = base64.b64encode(image.data).decode("utf-8")
            messages: list[dict[str, Any]] = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": image.mime_type,
                                "data": encoded,
                            },
                        },
                    ],
                }
            ]
        else:
            messages = [{"role": "user", "content": prompt}]

        # Base kwargs for all requests.
        # output_config.format with json_schema enables constrained decoding (GA for claude-sonnet-4-6).
        # cache_control ephemeral enables automatic prompt caching (system prefix cached).
        create_kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
            "cache_control": {"type": "ephemeral"},
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        last_error: str | None = None
        content = ""
        current_messages = list(messages)  # mutable copy for repair loop
        self._last_retry_counts = {
            "attempt_count": 0,
            "json_decode_retries": 0,
            "api_retries": 0,
            "budget_retries": 0,
        }

        for attempt in range(self.max_retries):
            self._last_retry_counts["attempt_count"] = attempt + 1
            if (time.perf_counter() - start_time) >= self.max_total_seconds:
                last_error = (
                    f"provider_max_total_seconds_exceeded: "
                    f"{self.max_total_seconds:.2f}s"
                )
                break

            parse_details: dict[str, Any] = {}
            try:
                # Update messages for repair loop (non-image path only).
                call_kwargs = dict(create_kwargs)
                if not image:
                    call_kwargs["messages"] = current_messages

                response = await self.client.messages.create(**call_kwargs)
                self._last_usage = _extract_claude_usage(response)

                # Anthropic response path: response.content[0].text
                # CRITICAL: NOT response.choices[0].message.content (OpenAI path)
                content = response.content[0].text

                cached = self._last_usage.get("cached_tokens", 0)
                if cached:
                    logger.info(
                        "Token usage: %s (cache hit: %s/%s = %d%%)",
                        self._last_usage,
                        cached,
                        self._last_usage.get("prompt_tokens", 0),
                        cached * 100 // max(self._last_usage.get("prompt_tokens", 1), 1),
                    )
                else:
                    logger.debug("Token usage: %s", self._last_usage)

                expected_keys = set(schema.get("properties", {}).keys())
                result = _parse_json_payload(
                    content,
                    expected_keys=expected_keys,
                    parse_details=parse_details,
                )
                self._last_parse_details = parse_details
                circuit_breakers.record_success(self.name)
                metrics_registry.observe(
                    "provider_latency_seconds",
                    time.perf_counter() - start_time,
                    provider=self.name,
                )
                log_event(
                    logger,
                    logging.INFO,
                    "provider.generate.success",
                    provider=self.name,
                    attempts=attempt + 1,
                )
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                if parse_details:
                    self._last_parse_details = {
                        "parse_mode": parse_details.get(
                            "parse_mode", "json_decode_error"
                        ),
                        "parsed_key_count": parse_details.get("parsed_key_count", 0),
                        "expected_key_count": parse_details.get(
                            "expected_key_count",
                            len(schema.get("properties", {})),
                        ),
                        "missing_keys": parse_details.get(
                            "missing_keys",
                            sorted(schema.get("properties", {}).keys()),
                        ),
                    }
                else:
                    self._last_parse_details = {
                        "parse_mode": "json_decode_error",
                        "parsed_key_count": 0,
                        "expected_key_count": len(schema.get("properties", {})),
                        "missing_keys": sorted(schema.get("properties", {}).keys()),
                    }

                metrics_registry.increment(
                    "provider_retry_total", provider=self.name, reason="json_decode"
                )
                self._last_retry_counts["json_decode_retries"] += 1
                logger.warning(
                    "JSON parse error (attempt %d): %s (raw_chars=%d)",
                    attempt + 1,
                    last_error,
                    len(content or ""),
                )

                if self._last_retry_counts["json_decode_retries"] > self.json_retry_max:
                    last_error = (
                        f"json_retry_budget_exceeded: "
                        f"{self._last_retry_counts['json_decode_retries']}>{self.json_retry_max}"
                    )
                    logger.error(
                        "JSON retry budget exceeded for provider=%s (%s)",
                        self.name,
                        last_error,
                    )
                    break

                # Build repair messages for next attempt.
                if image:
                    # Image path: can't append assistant turn; rebuild prompt.
                    current_messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        "Your response was not valid JSON.\n"
                                        f"Error: {last_error}\n\n"
                                        f"Original request: {prompt}\n\n"
                                        "Please respond with valid JSON only."
                                    ),
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": image.mime_type,
                                        "data": base64.b64encode(image.data).decode("utf-8"),
                                    },
                                },
                            ],
                        }
                    ]
                else:
                    # Text path: append assistant turn then repair instruction.
                    if (content or "").strip():
                        current_messages.append(
                            {"role": "assistant", "content": content}
                        )
                    current_messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your response was not valid JSON. "
                                f"Error: {last_error}. "
                                "Please fix and respond with valid JSON only."
                            ),
                        }
                    )

                if attempt < self.max_retries - 1:
                    delay = compute_backoff_seconds(attempt)
                    await asyncio.sleep(delay)

            except Exception as e:
                last_error = str(e)
                retryable = is_retryable_provider_error(e)
                metrics_registry.increment(
                    "provider_error_total",
                    provider=self.name,
                    error_type=type(e).__name__,
                )
                logger.error("Claude API error (attempt %d): %s", attempt + 1, last_error)
                if retryable and attempt < self.max_retries - 1:
                    delay = compute_backoff_seconds(attempt)
                    metrics_registry.increment(
                        "provider_retry_total",
                        provider=self.name,
                        reason="retryable_api_error",
                    )
                    self._last_retry_counts["api_retries"] += 1
                    log_event(
                        logger,
                        logging.WARNING,
                        "provider.generate.retry",
                        provider=self.name,
                        attempt=attempt + 1,
                        delay_seconds=round(delay, 4),
                        reason=last_error[:200],
                    )
                    await asyncio.sleep(delay)
                    continue
                if not retryable:
                    break

        opened = circuit_breakers.record_failure(self.name)
        if opened:
            metrics_registry.increment("provider_circuit_open_total", provider=self.name)
        attempts_made = max(
            int(self._last_retry_counts.get("attempt_count", 0)),
            1 if last_error is not None else 0,
        )
        metrics_registry.observe(
            "provider_latency_seconds",
            time.perf_counter() - start_time,
            provider=self.name,
        )
        log_event(
            logger,
            logging.ERROR,
            "provider.generate.failure",
            provider=self.name,
            attempts=attempts_made,
            error=last_error,
            circuit_opened=opened,
        )
        raise LLMError(
            f"Failed to generate valid JSON: {last_error}", self.name, attempts_made
        )

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from last generation."""
        return self._last_usage.copy()

    @property
    def last_parse_details(self) -> dict[str, Any]:
        """Return parse diagnostics from last generation."""
        return self._last_parse_details.copy()

    @property
    def last_retry_counts(self) -> dict[str, int]:
        """Return retry and attempt diagnostics from last generation."""
        return self._last_retry_counts.copy()
