"""Prompt Loader - Load prompt data assets from Supabase.

Fetches the active prompt template which includes:
- 10 gold standard examples for few-shot learning
- Category-specific guidance
- Platform rules

The canonical system prompt is code-owned in `feedops.pipeline.prompts`.
Supabase template data is used for examples/guidance only.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

from feedops.db.supabase_client import get_client, is_supabase_available
from feedops.pipeline.prompts import SYSTEM_PROMPT as CANONICAL_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class GoldStandardExample(TypedDict, total=False):
    """Gold standard example structure."""
    index: int
    category: str
    master_sku: str
    gold_standard_content: dict[str, Any]


class PromptTemplate(TypedDict, total=False):
    """Prompt template structure from Supabase."""
    id: str
    name: str
    version: int
    is_active: bool
    system_prompt: str
    gold_standard_examples: dict[str, Any]
    category_guidance: dict[str, str]
    platform_rules: dict[str, Any]
    description: str | None
    created_at: str


# Cache for loaded template (5 minute TTL)
_cached_template: PromptTemplate | None = None
_cache_timestamp: datetime | None = None
CACHE_TTL_SECONDS = 300  # 5 minutes

# 28 finishes (excludes Military Camo and Red White and Blue)
FINISH_LIST_28 = [
    "Antique Brass",
    "Antique Bronze",
    "Antique Copper",
    "Antique Pewter",
    "Autumn Sparkle",
    "Brushed Bronze",
    "Fire Engine Red",
    "Flat Troll Blue",
    "Glokzin Teal",
    "Golden Yellow",
    "Lavender",
    "Matte Black",
    "Matte Gray",
    "Matte White",
    "Mediterranean Blue",
    "Oil Rubbed Bronze",
    "Pink",
    "Polished Brass",
    "Polished Chrome",
    "Polished Nickel",
    "Satin Brass",
    "Satin Chrome",
    "Satin Nickel",
    "Sea Foam Green",
    "Shaded Beige",
    "Spanish Gold",
    "Unlacquered Brass",
    "Venetian Bronze",
]

def load_active_prompt_template() -> PromptTemplate | None:
    """Load the active prompt template from Supabase.

    Returns cached version if available and not expired.

    Returns:
        The active prompt template, or None if not available.
    """
    global _cached_template, _cache_timestamp

    # Check cache
    now = datetime.now(timezone.utc)
    if _cached_template and _cache_timestamp:
        age = (now - _cache_timestamp).total_seconds()
        if age < CACHE_TTL_SECONDS:
            return _cached_template

    # Check if Supabase is available
    if not is_supabase_available():
        logger.warning("Supabase not available, cannot load prompt template")
        return None

    try:
        supabase = get_client()
        result = (
            supabase.table("prompt_templates")
            .select("*")
            .eq("is_active", True)
            .single()
            .execute()
        )

        if not result.data:
            logger.warning("No active prompt template found in Supabase")
            return None

        # Update cache
        _cached_template = result.data
        _cache_timestamp = now

        logger.info(
            f"Loaded prompt template: {result.data.get('name')} "
            f"v{result.data.get('version')}"
        )
        return _cached_template

    except Exception as e:
        logger.error(f"Error loading prompt template: {e}")
        return None


def get_system_prompt() -> str:
    """Get the canonical system prompt from Python code.

    Returns:
        System prompt string.
    """
    return CANONICAL_SYSTEM_PROMPT


def get_system_prompt_hash() -> str:
    """Get stable short hash for canonical prompt versioning.

    Returns:
        First 16 chars of SHA256 hash of canonical system prompt.
    """
    return hashlib.sha256(get_system_prompt().encode()).hexdigest()[:16]


def get_category_guidance(category: str | None) -> str | None:
    """Get category-specific guidance for a product category.

    Args:
        category: The product category (e.g., "Towel Bars", "Grab Bars").

    Returns:
        Category guidance string or None if no match.
    """
    if not category:
        return None

    template = load_active_prompt_template()
    if not template or not template.get("category_guidance"):
        return None

    guidance = template["category_guidance"]

    # Try exact match first
    if category in guidance:
        return guidance[category]

    # Try partial match
    cat_lower = category.lower()
    for key, value in guidance.items():
        if cat_lower in key.lower() or key.lower() in cat_lower:
            return value

    return None


def format_gold_standard_examples(
    platform: str,
    content_type: str,
    max_examples: int = 3,
    max_description_chars: int = 5000,
) -> str:
    """Format gold standard examples for inclusion in a prompt.

    Args:
        platform: Target platform ('google', 'bing', 'shopify').
        content_type: Type of content ('title', 'description').
        max_examples: Maximum number of examples to include.
        max_description_chars: Maximum number of description characters to include.

    Returns:
        Formatted examples string, or empty string if none available.
    """
    template = load_active_prompt_template()
    if not template:
        return ""

    examples_data = template.get("gold_standard_examples", {})
    examples = examples_data.get("examples", [])

    if not examples:
        return ""

    formatted = []
    for idx, ex in enumerate(examples[:max_examples]):
        content = ex.get("gold_standard_content", {})

        # Get appropriate title/description for platform
        if platform == "shopify":
            title = content.get("shopify_title", "")
            description = content.get("shopify_description", "")
        else:
            title = content.get("google_title", "")
            description = content.get("google_description", "")

        why_it_works = content.get("why_it_works", "")
        category = ex.get("category", "Unknown")

        if content_type == "title":
            formatted.append(
                f"Example {idx + 1} ({category}):\n"
                f"Title: {title}\n"
                f"Why it works: {why_it_works}"
            )
        else:
            description = (description or "").strip()
            truncated = len(description) > max_description_chars
            if truncated:
                description = description[:max_description_chars].rstrip() + "…"
            formatted.append(
                f"Example {idx + 1} ({category}):\n"
                f"Description{' (truncated)' if truncated else ''}:\n{description}\n"
                f"Why it works: {why_it_works}"
            )

    return "\n\n".join(formatted)


def format_gold_standard_examples_bundle(
    max_examples: int = 2,
    max_description_chars: int = 5000,
) -> str:
    """Format gold standard examples showing both Google/Bing and Shopify outputs.

    The generation schema returns multiple platform-specific fields in one
    response (Google/Bing + Shopify). This formatter provides few-shot examples
    that demonstrate the expected cross-platform shape without duplicating the
    whole prompt for each platform.

    Args:
        max_examples: Maximum number of examples to include.
        max_description_chars: Maximum number of description characters to include.

    Returns:
        Formatted examples string, or empty string if none available.
    """
    template = load_active_prompt_template()
    if not template:
        return ""

    examples_data = template.get("gold_standard_examples", {})
    examples = examples_data.get("examples", [])
    if not examples:
        return ""

    formatted: list[str] = []
    for idx, ex in enumerate(examples[:max_examples]):
        content = ex.get("gold_standard_content", {})
        category = ex.get("category", "Unknown")
        why_it_works = content.get("why_it_works", "")

        google_title = content.get("google_title", "")
        google_description = content.get("google_description", "")
        shopify_title = content.get("shopify_title", "")
        shopify_description = content.get("shopify_description", "")

        google_description = (google_description or "").strip()
        shopify_description = (shopify_description or "").strip()
        google_truncated = len(google_description) > max_description_chars
        shopify_truncated = len(shopify_description) > max_description_chars
        if google_truncated:
            google_description = google_description[:max_description_chars].rstrip() + "…"
        if shopify_truncated:
            shopify_description = shopify_description[:max_description_chars].rstrip() + "…"

        formatted.append(
            f"Example {idx + 1} ({category}):\n"
            f"Google title: {google_title}\n"
            f"Google description{' (truncated)' if google_truncated else ''}:\n{google_description}\n"
            f"Shopify title: {shopify_title}\n"
            f"Shopify description{' (truncated)' if shopify_truncated else ''}:\n{shopify_description}\n"
            f"Why it works: {why_it_works}"
        )

    return "\n\n".join(formatted)


def get_excluded_finishes() -> list[str]:
    """Get list of finishes to exclude from content generation.

    Returns:
        List of finish names to exclude.
    """
    template = load_active_prompt_template()
    if template:
        rules = template.get("platform_rules", {})
        excluded = rules.get("excluded_finishes", [])
        if excluded:
            return excluded

    # Default exclusions
    return ["Military Camo", "Red White and Blue"]


def get_finish_list() -> list[str]:
    """Get the list of 28 finishes for content generation.

    Returns:
        List of finish names (excludes specialty finishes).
    """
    return FINISH_LIST_28


def clear_cache() -> None:
    """Clear the cached prompt template."""
    global _cached_template, _cache_timestamp
    _cached_template = None
    _cache_timestamp = None
