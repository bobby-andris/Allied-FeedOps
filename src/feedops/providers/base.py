"""Base provider interfaces."""
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Subclasses must implement the generate method to produce
    structured JSON output for product optimization.
    """

    @abstractmethod
    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response from prompt.

        Args:
            prompt: The full prompt including evidence table and constraints.
            schema: JSON schema the response must conform to.

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
