"""OpenAI LLM provider with JSON mode and retry logic."""

import asyncio
import base64
import json
import logging
import time
from typing import Any

from openai import AsyncOpenAI

from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.providers.base import ImageInput, LLMError, LLMProvider
from feedops.providers.reliability import (
    circuit_breakers,
    compute_backoff_seconds,
    is_retryable_provider_error,
)

logger = logging.getLogger(__name__)


def _parse_json_payload(raw: str) -> dict[str, Any]:
    """Parse JSON payload with light normalization for provider edge cases."""

    def _unwrap_content_wrapper(value: Any) -> Any:
        current = value
        for _ in range(3):
            if isinstance(current, dict) and set(current.keys()) == {"content"}:
                inner = current.get("content")
                if isinstance(inner, (dict, list)):
                    current = inner
                    continue
                if isinstance(inner, str):
                    stripped = inner.strip()
                    if not stripped:
                        break
                    try:
                        current = json.loads(stripped)
                        continue
                    except json.JSONDecodeError:
                        break
            break
        return current

    text = (raw or "").strip()
    if not text:
        raise json.JSONDecodeError("empty response", raw, 0)

    try:
        parsed = _unwrap_content_wrapper(json.loads(text))
    except json.JSONDecodeError:
        fenced_start = text.find("```")
        if fenced_start != -1:
            fenced_end = text.rfind("```")
            if fenced_end > fenced_start:
                fenced_body = text[fenced_start + 3 : fenced_end].strip()
                if fenced_body.startswith("json"):
                    fenced_body = fenced_body[4:].strip()
                parsed = _unwrap_content_wrapper(json.loads(fenced_body))
            else:
                raise
        else:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise
            parsed = _unwrap_content_wrapper(json.loads(text[start : end + 1]))

    if not isinstance(parsed, dict):
        raise json.JSONDecodeError("parsed payload is not an object", raw, 0)
    return parsed


def _build_strict_schema(
    schema: dict[str, Any],
    *,
    schema_name: str = "feedops_response",
) -> dict[str, Any]:
    """Convert a schema to OpenAI strict json_schema format.

    Strict mode requires:
    - "additionalProperties": false on every object type
    - All properties listed in "required" arrays

    Returns:
        OpenAI response_format dict with type "json_schema".
    """

    def _make_strict(schema: dict[str, Any]) -> dict[str, Any]:
        """Recursively add additionalProperties: false to all object schemas."""
        result = dict(schema)
        if result.get("type") == "object":
            result["additionalProperties"] = False
            # Ensure all properties are required
            if "properties" in result:
                props = result["properties"]
                existing_required = set(result.get("required", []))
                all_props = set(props.keys())
                result["required"] = sorted(all_props | existing_required)
                # Recurse into nested properties
                result["properties"] = {
                    k: _make_strict(v) for k, v in props.items()
                }
        elif result.get("type") == "array" and "items" in result:
            result["items"] = _make_strict(result["items"])
        return result

    strict_schema = _make_strict(schema)
    return {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "strict": True,
            "schema": strict_schema,
        },
    }


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider with structured JSON output.

    Features:
    - JSON mode for structured output
    - Retry with repair loop on validation failure
    - Token usage logging (no secrets)
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.2",
        max_retries: int = 3,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self._last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    def _use_max_completion_tokens(self) -> bool:
        """Return True when model requires max_completion_tokens."""
        return self.model.startswith("gpt-5")

    def _default_max_tokens(self) -> int:
        # JSON outputs can be large (descriptions + claims), so keep this generous.
        return 2000

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            params = {
                "model": self.model,
                "messages": [{"role": "user", "content": "ping"}],
            }
            if self._use_max_completion_tokens():
                params["max_completion_tokens"] = 5
            else:
                params["max_tokens"] = 5
            response = await self.client.chat.completions.create(**params)
            return response.choices[0].message.content is not None
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

    def _supports_reasoning_effort(self) -> bool:
        """Return True when the model supports the reasoning_effort parameter."""
        return self.model.startswith("gpt-5") or self.model.startswith("o")

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

        When *system_prompt* is provided, it is sent as a separate system
        message so OpenAI can cache the static prefix across requests.

        Args:
            prompt: User prompt (dynamic per-SKU content).
            schema: Expected JSON schema for validation.
            image: Optional image for multimodal models.
            system_prompt: Optional static system prompt for cache efficiency.
            reasoning_effort: Optional reasoning effort level ("low", "medium",
                "high"). Only applied to models that support it (GPT-5.x, o-series).
            max_completion_tokens: Optional max completion token budget override.

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
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

        # Build initial message list with optional system message for caching.
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build reasoning_effort kwarg for models that support it.
        reasoning_params: dict[str, str] = {}
        if reasoning_effort and self._supports_reasoning_effort():
            reasoning_params["reasoning_effort"] = reasoning_effort

        # Temperature and reasoning_effort are mutually exclusive on GPT-5.2.
        # Only pass temperature when reasoning_effort is NOT set.
        sampling_params: dict[str, float] = {}
        if not reasoning_params:
            sampling_params["temperature"] = 0.7

        # Build strict response format from the schema requested by the caller.
        response_format = _build_strict_schema(schema)
        max_output_tokens = max_completion_tokens or self._default_max_tokens()

        current_prompt = prompt
        last_error = None
        content = ""

        for attempt in range(self.max_retries):
            try:
                token_params: dict[str, int] = {}
                if self._use_max_completion_tokens():
                    token_params["max_completion_tokens"] = max_output_tokens
                else:
                    token_params["max_tokens"] = max_output_tokens

                if image:
                    encoded = base64.b64encode(image.data).decode("utf-8")
                    image_messages: list[dict[str, Any]] = []
                    if system_prompt:
                        image_messages.append(
                            {"role": "system", "content": system_prompt}
                        )
                    image_messages.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": current_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{image.mime_type};base64,{encoded}"
                                    },
                                },
                            ],
                        }
                    )
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=image_messages,
                        response_format=response_format,
                        extra_body={"prompt_cache_retention": "24h"},
                        **token_params,
                        **sampling_params,
                        **reasoning_params,
                    )
                    self._last_usage = _extract_usage(response)
                    content = response.choices[0].message.content
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        response_format=response_format,
                        extra_body={"prompt_cache_retention": "24h"},
                        **token_params,
                        **sampling_params,
                        **reasoning_params,
                    )
                    self._last_usage = _extract_usage(response)
                    content = response.choices[0].message.content
                cached = self._last_usage.get("cached_tokens", 0)
                if cached:
                    logger.info(
                        f"Token usage: {self._last_usage} "
                        f"(cache hit: {cached}/{self._last_usage.get('prompt_tokens', 0)} "
                        f"= {cached * 100 // max(self._last_usage.get('prompt_tokens', 1), 1)}%)"
                    )
                else:
                    logger.debug(f"Token usage: {self._last_usage}")
                result = _parse_json_payload(content)
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
                metrics_registry.increment(
                    "provider_retry_total", provider=self.name, reason="json_decode"
                )
                logger.warning(
                    f"JSON parse error (attempt {attempt + 1}): {last_error}"
                )
                if image:
                    current_prompt = (
                        "Your response was not valid JSON.\n"
                        f"Error: {last_error}\n\n"
                        f"Original request: {prompt}\n\n"
                        "Please respond with valid JSON only."
                    )
                else:
                    # Add repair instruction for next attempt
                    messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Your response was not valid JSON. Error: {last_error}. Please fix and respond with valid JSON only.",
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
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {last_error}")
                if retryable and attempt < self.max_retries - 1:
                    delay = compute_backoff_seconds(attempt)
                    metrics_registry.increment(
                        "provider_retry_total",
                        provider=self.name,
                        reason="retryable_api_error",
                    )
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
            attempts=self.max_retries,
            error=last_error,
            circuit_opened=opened,
        )
        raise LLMError(
            f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries
        )

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from last generation."""
        return self._last_usage.copy()


def _extract_cached_tokens(usage: Any) -> int:
    """Extract cached_tokens from prompt_tokens_details if available."""
    # Dict-style usage (e.g. from mock or raw dict)
    if isinstance(usage, dict):
        details = usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            return details.get("cached_tokens", 0) or 0
        return getattr(details, "cached_tokens", 0) or 0

    # Object-style usage (OpenAI SDK response)
    details = getattr(usage, "prompt_tokens_details", None)
    if details is None:
        return 0
    if isinstance(details, dict):
        return details.get("cached_tokens", 0) or 0
    return getattr(details, "cached_tokens", 0) or 0


def _extract_usage(response: Any) -> dict[str, int]:
    """Normalize usage fields across OpenAI response types.

    Extracts prompt_tokens, completion_tokens, and cached_tokens
    (from prompt_tokens_details) for cache hit rate monitoring.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0}

    cached_tokens = _extract_cached_tokens(usage)

    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = (
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        }

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if prompt_tokens is None:
        prompt_tokens = getattr(usage, "input_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if completion_tokens is None:
        completion_tokens = getattr(usage, "output_tokens", 0)
    return {
        "prompt_tokens": prompt_tokens or 0,
        "completion_tokens": completion_tokens or 0,
        "cached_tokens": cached_tokens,
    }


def _extract_output_text(response: Any) -> str:
    """Extract text content from Responses API result."""
    text = getattr(response, "output_text", None)
    if text:
        return text
    output = getattr(response, "output", None)
    if isinstance(output, list):
        for item in output:
            content = getattr(item, "content", None)
            if isinstance(content, list):
                for part in content:
                    part_text = getattr(part, "text", None)
                    if part_text:
                        return part_text
    raise LLMError("OpenAI response missing output text", "openai", 1)
