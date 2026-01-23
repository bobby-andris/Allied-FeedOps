"""Google Gemini LLM provider using the new google-genai SDK."""
import json
import logging
import re
from typing import Any

from google import genai
from google.genai import types

from feedops.providers.base import LLMProvider, LLMError

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
        model: str = "gemini-2.0-flash",
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

    async def _call_api(self, prompt: str) -> str:
        """Make async call to Gemini API."""
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
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

    async def generate(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate structured JSON response.

        Args:
            prompt: Full prompt with evidence table and constraints.
            schema: Expected JSON schema (used for repair hints).

        Returns:
            Parsed JSON dict.

        Raises:
            LLMError: After max_retries failures.
        """
        current_prompt = prompt + "\n\nRespond with valid JSON only, no markdown."
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response_text = await self._call_api(current_prompt)
                json_text = self._extract_json(response_text)
                result = json.loads(json_text)
                return result

            except json.JSONDecodeError as e:
                last_error = str(e)
                logger.warning(f"JSON parse error (attempt {attempt + 1}): {last_error}")
                current_prompt = f"""Your previous response was not valid JSON.
Error: {last_error}

Original request: {prompt}

Please respond with ONLY valid JSON, no explanations or markdown."""

            except Exception as e:
                last_error = str(e)
                logger.error(f"Gemini API error (attempt {attempt + 1}): {last_error}")

        raise LLMError(f"Failed to generate valid JSON: {last_error}", self.name, self.max_retries)
