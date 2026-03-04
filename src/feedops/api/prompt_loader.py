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
from feedops.pipeline.skill_loader import get_platform_system_prompt
from feedops.pipeline.skill_loader import load_skills_for_prompt

logger = logging.getLogger(__name__)

# Thresholds updated to accommodate skill-enriched prompts.
# With all 8 skills loaded (~254K chars), total prompt can reach 260K+.
SYSTEM_PROMPT_WARN_THRESHOLD_CHARS = 280_000
SYSTEM_PROMPT_CI_MAX_CHARS = 300_000
_prompt_size_warning_emitted = False


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


def get_system_prompt(
    mode: str = "batch",
    platform: str | None = None,
) -> str:
    """Get the canonical system prompt enriched with skill content.

    Assembles the system prompt by starting with the canonical SYSTEM_PROMPT
    from code, then appending all relevant Claude Code skill SKILL.md files.

    Args:
        mode: "batch" loads all skills (system prompt cached across all SKUs
              in a batch run — cost amortized). "single" loads core +
              platform-relevant skills only (lower token cost for single-SKU
              regeneration).
        platform: Target platform for single mode ("google", "bing", "shopify").
                  Ignored in batch mode.

    Returns:
        System prompt string with skill sections appended. Skills are 5-10x
        richer than YAML config distillations and improve first-pass quality.
    """
    global _prompt_size_warning_emitted

    prompt = CANONICAL_SYSTEM_PROMPT

    # Append skill content for enriched prompts.
    # Skills are loaded from .claude/skills/{name}/SKILL.md with lru_cache.
    # Falls back to empty string gracefully if skills directory unavailable
    # (YAML configs in prompt_builder.py remain as the backup injection path).
    skill_content = load_skills_for_prompt(mode=mode, platform=platform)
    if skill_content:
        prompt = prompt + "\n\n" + skill_content
        logger.info(
            "Skills injected into system prompt: total %d chars (mode=%s, platform=%s)",
            len(prompt),
            mode,
            platform,
        )

    prompt_len = len(prompt)
    if (
        prompt_len > SYSTEM_PROMPT_WARN_THRESHOLD_CHARS
        and not _prompt_size_warning_emitted
    ):
        logger.warning(
            "SYSTEM_PROMPT length is %s chars (> %s). Consider reducing prompt entropy.",
            prompt_len,
            SYSTEM_PROMPT_WARN_THRESHOLD_CHARS,
        )
        _prompt_size_warning_emitted = True

    return prompt


def get_system_prompt_hash(
    mode: str = "batch",
    platform: str | None = None,
) -> str:
    """Get stable short hash for canonical prompt versioning.

    Hash reflects the full enriched prompt (base + skills) so that different
    mode/platform combinations produce different hashes.

    Args:
        mode: "batch" or "single" — same as get_system_prompt().
        platform: Target platform for single mode.

    Returns:
        First 16 chars of SHA256 hash of the enriched system prompt.
    """
    return hashlib.sha256(
        get_system_prompt(mode=mode, platform=platform).encode()
    ).hexdigest()[:16]


def get_platform_system_prompt_hash(platform: str) -> str:
    """Get stable short hash for platform-specific system prompts.

    This hash uses the extracted, platform-targeted system prompt from
    ``skill_loader.get_platform_system_prompt`` so audit logs can trace
    which platform prompt variant produced each content payload.
    """
    return hashlib.sha256(get_platform_system_prompt(platform).encode()).hexdigest()[:16]


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


def get_finish_list_for_sku(master_sku: str) -> list[str]:
    """Get the actual finish list for a specific SKU from variant_index.

    Queries Supabase variant_index to find which finishes this SKU actually has.
    Falls back to FINISH_LIST_28 if Supabase is unavailable or no variants found.

    Returns:
        List of finish names for this SKU's actual variants.
    """
    if not is_supabase_available():
        logger.warning(
            "Supabase unavailable for get_finish_list_for_sku(%s), falling back to FINISH_LIST_28",
            master_sku,
        )
        return FINISH_LIST_28
    try:
        supabase = get_client()
        result = (
            supabase.table("variant_index")
            .select("finish")
            .eq("master_sku", master_sku)
            .execute()
        )
        finishes = sorted(set(
            row["finish"] for row in (result.data or [])
            if row.get("finish")
        ))
        if not finishes:
            logger.warning(
                "No variant_index finishes found for %s, falling back to FINISH_LIST_28",
                master_sku,
            )
            return FINISH_LIST_28
        return finishes
    except Exception as exc:
        logger.warning(
            "Failed to query variant_index for %s: %s — falling back to FINISH_LIST_28",
            master_sku,
            exc,
        )
        return FINISH_LIST_28


def clear_cache() -> None:
    """Clear the cached prompt template."""
    global _cached_template, _cache_timestamp
    _cached_template = None
    _cache_timestamp = None
