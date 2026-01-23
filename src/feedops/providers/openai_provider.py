"""OpenAI LLM provider with JSON mode and retry logic."""
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from feedops.providers.base import LLMProvider, LLMError

logger = logging.getLogger(__name__)


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
        model: str = "gpt-4o",
        max_retries: int = 3,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self._last_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return response.choices[0].message.content is not None
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False

    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response with retry loop.

        Args:
            prompt: Full prompt with evidence table and constraints.
            schema: Expected JSON schema for validation.

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        messages = [{"role": "user", "content": prompt}]
        last_error = None
        content = ""

        for attempt in range(self.max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )

                # Log token usage
                self._last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                logger.debug(f"Token usage: {self._last_usage}")

                content = response.choices[0].message.content
                result = json.loads(content)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                # Add repair instruction for next attempt
                messages.append({
                    "role": "assistant",
                    "content": content
                })
                messages.append({
                    "role": "user",
                    "content": f"Your response was not valid JSON. Error: {last_error}. Please fix and respond with valid JSON only."
                })

            except Exception as e:
                last_error = str(e)
                logger.error(f"OpenAI API error (attempt {attempt + 1}): {last_error}")

        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from last generation."""
        return self._last_usage.copy()
