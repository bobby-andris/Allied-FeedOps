"""LLM provider factory with automatic fallback."""

import logging
import os

from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.providers.base import ImageInput, LLMProvider
from feedops.providers.gemini_provider import GeminiProvider
from feedops.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r, using default=%s", name, raw, default)
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid float for %s=%r, using default=%s", name, raw, default)
        return default


def _build_openai_provider(*, api_key: str, model: str) -> OpenAIProvider:
    return OpenAIProvider(
        api_key=api_key,
        model=model,
        max_retries=_int_env("FEEDOPS_PROVIDER_MAX_RETRIES", 2),
        sdk_timeout_seconds=_float_env("FEEDOPS_OPENAI_SDK_TIMEOUT_SECONDS", 120.0),
        sdk_max_retries=_int_env("FEEDOPS_OPENAI_SDK_MAX_RETRIES", 0),
        max_total_seconds=_float_env("FEEDOPS_PROVIDER_MAX_TOTAL_SECONDS", 300.0),
    )


def get_provider(preferred: str | None = None) -> LLMProvider:
    """Get configured LLM provider with fallback chain.

    Priority:
    1. Explicitly requested provider (if key available)
    2. OpenAI (if OPENAI_API_KEY set)
    3. Gemini (if GEMINI_API_KEY set)

    Args:
        preferred: Explicitly request 'openai' or 'gemini'.

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If no provider is configured.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_model = os.environ.get("FEEDOPS_OPENAI_MODEL")
    force_fallback = _truthy(os.environ.get("FEEDOPS_FORCE_PROVIDER_FALLBACK"))

    if force_fallback and openai_key and gemini_key:
        if preferred == "gemini":
            return FallbackProvider(
                primary=GeminiProvider(api_key=gemini_key),
                fallback=_build_openai_provider(
                    api_key=openai_key,
                    model=openai_model or "gpt-5.2",
                ),
            )
        return FallbackProvider(
            primary=_build_openai_provider(
                api_key=openai_key,
                model=openai_model or "gpt-5.2",
            ),
            fallback=GeminiProvider(api_key=gemini_key),
        )

    if preferred == "openai" and openai_key:
        return _build_openai_provider(
            api_key=openai_key,
            model=openai_model or "gpt-5.2",
        )

    if preferred == "gemini" and gemini_key:
        return GeminiProvider(api_key=gemini_key)

    if openai_key:
        logger.info("Using OpenAI provider")
        return _build_openai_provider(
            api_key=openai_key,
            model=openai_model or "gpt-5.2",
        )

    if gemini_key:
        logger.info("Using Gemini provider (OpenAI not configured)")
        return GeminiProvider(api_key=gemini_key)

    raise ValueError(
        "No LLM provider configured. Set OPENAI_API_KEY or GEMINI_API_KEY."
    )


class FallbackProvider(LLMProvider):
    """Provider that tries primary, then falls back to secondary.

    Useful for production where you want automatic failover.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback

    @property
    def name(self) -> str:
        return f"{self.primary.name}+{self.fallback.name}"

    async def health_check(self) -> bool:
        """True if either provider is healthy."""
        primary_ok = await self.primary.health_check()
        if primary_ok:
            return True
        return await self.fallback.health_check()

    async def generate(
        self,
        prompt: str,
        schema: dict,
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict:
        """Try primary, fall back to secondary on failure."""
        try:
            return await self.primary.generate(
                prompt, schema, image=image, system_prompt=system_prompt,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=max_completion_tokens,
            )
        except Exception as e:
            metrics_registry.increment(
                "provider_fallback_total", primary=self.primary.name, fallback=self.fallback.name
            )
            log_event(
                logger,
                logging.WARNING,
                "provider.fallback",
                primary=self.primary.name,
                fallback=self.fallback.name,
                error=str(e)[:200],
            )
            logger.warning(f"Primary provider failed: {e}, trying fallback")
            return await self.fallback.generate(
                prompt, schema, image=image, system_prompt=system_prompt,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=max_completion_tokens,
            )
