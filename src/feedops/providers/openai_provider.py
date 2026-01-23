"""OpenAI LLM provider with JSON mode and retry logic."""
import base64
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from feedops.providers.base import ImageInput, LLMProvider, LLMError

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
        model: str = "gpt-5.2",
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

    async def generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        image: ImageInput | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response with retry loop.

        Args:
            prompt: Full prompt with evidence table and constraints.
            schema: Expected JSON schema for validation.

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        current_prompt = prompt
        last_error = None
        content = ""

        for attempt in range(self.max_retries):
            try:
                if image:
                    encoded = base64.b64encode(image.data).decode("utf-8")
                    response = await self.client.responses.create(
                        model=self.model,
                        input=[{
                            "role": "user",
                            "content": [
                                {"type": "input_text", "text": current_prompt},
                                {"type": "input_image", "image_url": f"data:{image.mime_type};base64,{encoded}"},
                            ],
                        }],
                    )
                    self._last_usage = _extract_usage(response)
                    content = _extract_output_text(response)
                else:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        response_format={"type": "json_object"},
                        temperature=0.7,
                    )
                    self._last_usage = _extract_usage(response)
                    content = response.choices[0].message.content
                logger.debug(f"Token usage: {self._last_usage}")
                result = json.loads(content)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                if image:
                    current_prompt = (
                        "Your response was not valid JSON.\n"
                        f"Error: {last_error}\n\n"
                        f"Original request: {prompt}\n\n"
                        "Please respond with valid JSON only."
                    )
                else:
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


def _extract_usage(response: Any) -> dict[str, int]:
    """Normalize usage fields across OpenAI response types."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
        return {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

    prompt_tokens = getattr(usage, "prompt_tokens", None)
    if prompt_tokens is None:
        prompt_tokens = getattr(usage, "input_tokens", 0)
    completion_tokens = getattr(usage, "completion_tokens", None)
    if completion_tokens is None:
        completion_tokens = getattr(usage, "output_tokens", 0)
    return {"prompt_tokens": prompt_tokens or 0, "completion_tokens": completion_tokens or 0}


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

    @property
    def last_usage(self) -> dict[str, int]:
        """Return token usage from last generation."""
        return self._last_usage.copy()
