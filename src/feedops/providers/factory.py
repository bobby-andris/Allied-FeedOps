"""LLM provider factory with automatic fallback."""

import logging
import os

from feedops.providers.base import ImageInput, LLMProvider
from feedops.providers.gemini_provider import GeminiProvider
from feedops.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)


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

    if preferred == "openai" and openai_key:
        if openai_model:
            return OpenAIProvider(api_key=openai_key, model=openai_model)
        return OpenAIProvider(api_key=openai_key)

    if preferred == "gemini" and gemini_key:
        return GeminiProvider(api_key=gemini_key)

    if openai_key:
        logger.info("Using OpenAI provider")
        if openai_model:
            return OpenAIProvider(api_key=openai_key, model=openai_model)
        return OpenAIProvider(api_key=openai_key)

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
    ) -> dict:
        """Try primary, fall back to secondary on failure."""
        try:
            return await self.primary.generate(prompt, schema, image=image)
        except Exception as e:
            logger.warning(f"Primary provider failed: {e}, trying fallback")
            return await self.fallback.generate(prompt, schema, image=image)
