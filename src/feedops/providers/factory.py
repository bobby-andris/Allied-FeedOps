"""LLM provider factory with automatic fallback."""

import logging
import os

from feedops.observability import log_event
from feedops.observability.metrics import metrics_registry
from feedops.api.runtime_controls import (
    diagnostic_force_low_cost_model_enabled,
    diagnostic_mode_enabled,
    diagnostic_model_name,
)
from feedops.providers.base import ImageInput, LLMProvider, close_provider
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


def _build_claude_provider(*, api_key: str, model: str) -> "ClaudeProvider":
    from feedops.providers.claude_provider import ClaudeProvider  # noqa: PLC0415
    return ClaudeProvider(
        api_key=api_key,
        model=model,
        max_retries=_int_env("FEEDOPS_PROVIDER_MAX_RETRIES", 1),
        sdk_timeout_seconds=_float_env("FEEDOPS_CLAUDE_SDK_TIMEOUT_SECONDS", 60.0),
        max_total_seconds=_float_env("FEEDOPS_PROVIDER_MAX_TOTAL_SECONDS", 120.0),
        json_retry_max=_int_env("FEEDOPS_CLAUDE_JSON_RETRY_MAX", 1),
    )


def _build_openai_provider(*, api_key: str, model: str) -> OpenAIProvider:
    return OpenAIProvider(
        api_key=api_key,
        model=model,
        max_retries=_int_env("FEEDOPS_PROVIDER_MAX_RETRIES", 1),
        sdk_timeout_seconds=_float_env("FEEDOPS_OPENAI_SDK_TIMEOUT_SECONDS", 45.0),
        sdk_max_retries=_int_env("FEEDOPS_OPENAI_SDK_MAX_RETRIES", 0),
        max_total_seconds=_float_env("FEEDOPS_PROVIDER_MAX_TOTAL_SECONDS", 120.0),
        json_retry_max=_int_env("FEEDOPS_OPENAI_JSON_RETRY_MAX", 1),
    )


def _resolve_openai_model(configured_model: str | None) -> str:
    if diagnostic_mode_enabled() and diagnostic_force_low_cost_model_enabled():
        return diagnostic_model_name()
    return configured_model or "gpt-5.2"


def get_provider(preferred: str | None = None) -> LLMProvider:
    """Get configured LLM provider with fallback chain.

    Priority:
    1. FEEDOPS_PROVIDER env var or explicit `preferred` arg ("claude", "openai", "gemini")
    2. OpenAI (if OPENAI_API_KEY set)
    3. Gemini (if GEMINI_API_KEY set)

    Args:
        preferred: Explicitly request 'claude', 'openai', or 'gemini'.

    Returns:
        Configured LLMProvider instance.

    Raises:
        ValueError: If no provider is configured.
    """
    # Check for explicit provider selection via env var
    preferred_env = os.environ.get("FEEDOPS_PROVIDER")
    effective_preferred = preferred or preferred_env

    claude_key = os.environ.get("ANTHROPIC_API_KEY")
    claude_model = os.environ.get("FEEDOPS_CLAUDE_MODEL", "claude-sonnet-4-6")

    # Claude provider (explicit selection only — no auto-fallback)
    if effective_preferred == "claude":
        if not claude_key:
            raise ValueError(
                "FEEDOPS_PROVIDER=claude but ANTHROPIC_API_KEY is not set."
            )
        logger.info("Using Claude provider (FEEDOPS_PROVIDER=claude, model=%s)", claude_model)
        return _build_claude_provider(api_key=claude_key, model=claude_model)

    openai_key = os.environ.get("OPENAI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_model = os.environ.get("FEEDOPS_OPENAI_MODEL")
    resolved_openai_model = _resolve_openai_model(openai_model)
    force_fallback = _truthy(os.environ.get("FEEDOPS_FORCE_PROVIDER_FALLBACK"))

    if force_fallback and openai_key and gemini_key:
        if effective_preferred == "gemini":
            return FallbackProvider(
                primary=GeminiProvider(api_key=gemini_key),
                fallback=_build_openai_provider(
                    api_key=openai_key,
                    model=resolved_openai_model,
                ),
            )
        return FallbackProvider(
            primary=_build_openai_provider(
                api_key=openai_key,
                model=resolved_openai_model,
            ),
            fallback=GeminiProvider(api_key=gemini_key),
        )

    if effective_preferred == "openai" and openai_key:
        return _build_openai_provider(
            api_key=openai_key,
            model=resolved_openai_model,
        )

    if effective_preferred == "gemini" and gemini_key:
        return GeminiProvider(api_key=gemini_key)

    if openai_key:
        logger.info("Using OpenAI provider")
        return _build_openai_provider(
            api_key=openai_key,
            model=resolved_openai_model,
        )

    if gemini_key:
        logger.info("Using Gemini provider (OpenAI not configured)")
        return GeminiProvider(api_key=gemini_key)

    raise ValueError(
        "No LLM provider configured. Set OPENAI_API_KEY, GEMINI_API_KEY, "
        "or ANTHROPIC_API_KEY (with FEEDOPS_PROVIDER=claude)."
    )


class FallbackProvider(LLMProvider):
    """Provider that tries primary, then falls back to secondary.

    Useful for production where you want automatic failover.
    """

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self._last_usage: dict[str, int] = {}
        self._last_parse_details: dict[str, object] = {}
        self._last_retry_counts: dict[str, int] = {}

    @property
    def name(self) -> str:
        return f"{self.primary.name}+{self.fallback.name}"

    @property
    def last_usage(self) -> dict[str, int]:
        return self._last_usage.copy()

    @property
    def last_parse_details(self) -> dict[str, object]:
        return self._last_parse_details.copy()

    @property
    def last_retry_counts(self) -> dict[str, int]:
        return self._last_retry_counts.copy()

    def _snapshot_provider_metrics(self, provider: LLMProvider) -> None:
        usage = getattr(provider, "last_usage", {})
        parse = getattr(provider, "last_parse_details", {})
        retry = getattr(provider, "last_retry_counts", {})
        self._last_usage = usage.copy() if isinstance(usage, dict) else {}
        self._last_parse_details = parse.copy() if isinstance(parse, dict) else {}
        self._last_retry_counts = retry.copy() if isinstance(retry, dict) else {}

    async def health_check(self) -> bool:
        """True if either provider is healthy."""
        primary_ok = await self.primary.health_check()
        if primary_ok:
            return True
        return await self.fallback.health_check()

    async def aclose(self) -> None:
        """Close both primary and fallback providers."""
        close_errors: list[str] = []
        for provider in (self.primary, self.fallback):
            try:
                await close_provider(provider)
            except Exception as exc:
                provider_name = getattr(provider, "name", provider.__class__.__name__)
                close_errors.append(f"{provider_name}: {exc}")
        if close_errors:
            logger.debug("Provider cleanup encountered errors: %s", "; ".join(close_errors))

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
        self._last_usage = {}
        self._last_parse_details = {}
        self._last_retry_counts = {}
        try:
            payload = await self.primary.generate(
                prompt, schema, image=image, system_prompt=system_prompt,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=max_completion_tokens,
            )
            self._snapshot_provider_metrics(self.primary)
            return payload
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
            payload = await self.fallback.generate(
                prompt, schema, image=image, system_prompt=system_prompt,
                reasoning_effort=reasoning_effort,
                max_completion_tokens=max_completion_tokens,
            )
            self._snapshot_provider_metrics(self.fallback)
            return payload
