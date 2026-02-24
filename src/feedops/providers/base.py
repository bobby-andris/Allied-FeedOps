"""Base provider interfaces."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImageInput:
    """Image payload for multimodal provider requests."""

    data: bytes
    mime_type: str
    source_url: str


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement the generate method to produce
    structured JSON output for product optimization.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,
        max_completion_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response from prompt.

        Args:
            prompt: The user prompt (dynamic per-SKU content).
            schema: JSON schema the response must conform to.
            image: Optional image payload for multimodal models.
            system_prompt: Optional static system prompt. When provided, sent as
                a separate system/developer message to enable prompt caching.
                If None, the prompt is sent as a single user message (legacy).
            reasoning_effort: Optional reasoning effort level for models that
                support it (e.g. GPT-5.2). One of "low", "medium", "high".
                When None, the model uses its default.
            max_completion_tokens: Optional max completion/output token budget.
                Providers that don't support this can ignore it.

        Returns:
            Parsed JSON dict matching the schema.

        Raises:
            LLMError: If generation fails after retries.
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available and configured.

        Returns:
            True if provider can accept requests.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging."""
        pass


class LLMError(Exception):
    """Error during LLM generation."""

    def __init__(self, message: str, provider: str, retries: int = 0):
        self.provider = provider
        self.retries = retries
        super().__init__(f"[{provider}] {message} (after {retries} retries)")
