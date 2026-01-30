"""Google Gemini LLM provider using the new google-genai SDK."""
import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from feedops.providers.base import ImageInput, LLMProvider, LLMError

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider as fallback for OpenAI.

    Uses the new google-genai SDK (replacing deprecated google.generativeai).

    Features:
    - JSON output parsing with cleanup
    - Retry with repair loop
    - Async support via client.aio
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3-flash-preview",
        max_retries: int = 3,
    ):
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.max_retries = max_retries

    @property
    def name(self) -> str:
        return f"gemini/{self.model_name}"

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents="Say 'ok'",
                config=types.GenerateContentConfig(
                    max_output_tokens=10,
                ),
            )
            return "ok" in response.text.lower()
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False

    async def _call_api(self, prompt: str, image: ImageInput | None = None) -> str:
        """Make async call to Gemini API."""
        contents: str | list[Any] = prompt
        if image:
            contents = [
                prompt,
                types.Part.from_bytes(data=image.data, mime_type=image.mime_type),
            ]
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=0.7,
            ),
        )
        return response.text

    def _extract_json(self, text: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        # Try to find JSON in code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            return json_match.group(1).strip()

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_match.group(0)

        return text.strip()

    async def generate(
        self,
        prompt: str,
        schema: dict[str, Any],
        image: ImageInput | None = None,
        system_prompt: str | None = None,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: User prompt (dynamic per-SKU content).
            schema: Expected JSON schema (used for repair hints).
            image: Optional image for multimodal models.
            system_prompt: Optional static system prompt. For Gemini, prepended
                to prompt (Gemini does not have a separate system message channel).
            reasoning_effort: Not used by Gemini; accepted for interface compatibility.

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        # Gemini doesn't have system messages; prepend to user prompt.
        full_prompt = prompt
        if system_prompt:
            full_prompt = system_prompt + "\n\n" + prompt
        current_prompt = full_prompt + "\n\nRespond with valid JSON only, no markdown."
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response_text = await self._call_api(current_prompt, image=image)
                json_text = self._extract_json(response_text)
                result = json.loads(json_text)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                current_prompt = f"""Your previous response was not valid JSON.
Error: {last_error}

Original request: {full_prompt}

Please respond with ONLY valid JSON, no explanations or markdown."""

            except Exception as e:
                last_error = str(e)
                logger.error(f"Gemini API error (attempt {attempt + 1}): {last_error}")

        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)
