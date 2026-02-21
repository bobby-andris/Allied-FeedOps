"""Unified skill loader for runtime prompt injection.

Loads full Claude Code skill SKILL.md files and injects them into generation
prompts. Skills are 5-10x richer than YAML config distillations and produce
higher first-pass quality content.

Architecture:
- Skills loaded from .claude/skills/{name}/SKILL.md relative to project root
- For Cloud Run deployment: skills are copied into the container image.
  IMPORTANT: Add to Dockerfile before the final COPY step:
      COPY .claude/skills /app/.claude/skills
  This ensures skills are available at /app/.claude/skills/{name}/SKILL.md.
- lru_cache ensures single load per container lifetime
- Adaptive loading: batch mode loads ALL skills into system prompt (cached
  across all SKUs); single-SKU mode loads core + platform-relevant skills

Public API:
    load_skill_content(skill_name: str) -> str | None
    load_skills_for_prompt(mode: str, platform: str | None) -> str
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skills discovery
# ---------------------------------------------------------------------------

# All 8 skill names available for prompt injection
CORE_SKILLS = [
    "allied-brass-brand-expert",  # brand voice and competitive positioning
    "quality-evaluation",          # 10-criterion rubric with anchors and examples
    "product-storytelling",        # interior designer perspective, scenarios, emotional resonance
]

PLATFORM_SKILLS = {
    "google": "google-shopping-content",
    "bing": "bing-shopping-content",
    "shopify": "shopify-conversion-content",
}

CONDITIONAL_SKILLS = [
    "finish-expertise",        # finish integration is universal
    "collection-storytelling", # collection coordination is universal
]

ALL_SKILLS = (
    CORE_SKILLS
    + list(PLATFORM_SKILLS.values())
    + CONDITIONAL_SKILLS
)


def _find_skills_dir() -> Path | None:
    """Locate the .claude/skills directory.

    Tries multiple paths in order:
    1. Development: relative to this file's location (src/feedops/pipeline -> project root)
    2. Cloud Run container: /app/.claude/skills

    Returns:
        Path to skills directory, or None if not found.
    """
    # Dev path: src/feedops/pipeline/skill_loader.py -> 4 levels up -> project root
    dev_path = Path(__file__).parent.parent.parent.parent / ".claude" / "skills"
    if dev_path.exists():
        return dev_path

    # Cloud Run container path
    container_path = Path("/app/.claude/skills")
    if container_path.exists():
        return container_path

    return None


@lru_cache(maxsize=32)
def load_skill_content(skill_name: str) -> str | None:
    """Load a single skill's SKILL.md content.

    Results are cached for the container lifetime via lru_cache, ensuring
    each skill file is read from disk only once per process.

    Args:
        skill_name: The skill directory name (e.g., "allied-brass-brand-expert").

    Returns:
        Full SKILL.md content string, or None if not found.
    """
    skills_dir = _find_skills_dir()
    if skills_dir is None:
        logger.warning(
            "Skills directory not found. Skills will not be injected. "
            "For Cloud Run: add 'COPY .claude/skills /app/.claude/skills' to Dockerfile."
        )
        return None

    skill_path = skills_dir / skill_name / "SKILL.md"
    if not skill_path.exists():
        logger.warning(
            "Skill file not found: %s. Falling back to YAML config.", skill_path
        )
        return None

    try:
        content = skill_path.read_text(encoding="utf-8")
        logger.debug("Loaded skill '%s' (%d chars)", skill_name, len(content))
        return content
    except OSError as exc:
        logger.warning("Failed to read skill '%s': %s", skill_name, exc)
        return None


def load_skills_for_prompt(
    mode: str = "batch",
    platform: str | None = None,
) -> str:
    """Assemble skill content for prompt injection.

    In batch mode, loads ALL skills (all 8) since the enriched system prompt
    is cached across all SKUs — the cost is amortized over every product in
    the batch.

    In single mode, loads core skills + only the relevant platform skill to
    reduce token cost for single-SKU regeneration.

    Args:
        mode: "batch" loads all skills; "single" loads core + platform-relevant.
        platform: Target platform ("google", "bing", "shopify") for single mode.
                  Ignored in batch mode.

    Returns:
        XML-tagged skill content string ready for system prompt injection,
        or empty string if skills directory is unavailable.
    """
    skills_dir = _find_skills_dir()
    if skills_dir is None:
        logger.warning(
            "Skill loader: skills directory unavailable — returning empty string. "
            "YAML configs will serve as fallback injection path."
        )
        return ""

    # Determine which skills to load
    if mode == "batch":
        # Batch: load all 8 skills (cost amortized across all SKUs)
        skills_to_load = list(ALL_SKILLS)
        logger.debug("Skill loader: batch mode — loading all %d skills", len(skills_to_load))
    else:
        # Single: core + platform-relevant skills only
        skills_to_load = list(CORE_SKILLS) + list(CONDITIONAL_SKILLS)
        if platform and platform in PLATFORM_SKILLS:
            skills_to_load.append(PLATFORM_SKILLS[platform])
        elif platform:
            # Unknown platform — load all platform skills as safe fallback
            skills_to_load.extend(PLATFORM_SKILLS.values())
        logger.debug(
            "Skill loader: single mode (platform=%s) — loading %d skills",
            platform,
            len(skills_to_load),
        )

    # Load and format each skill
    sections: list[str] = []
    loaded_count = 0
    for skill_name in skills_to_load:
        content = load_skill_content(skill_name)
        if content:
            sections.append(
                f'<skill name="{skill_name}">\n{content}\n</skill>'
            )
            loaded_count += 1

    if not sections:
        logger.warning(
            "Skill loader: no skills loaded successfully — returning empty string."
        )
        return ""

    result = "\n\n".join(sections)
    logger.info(
        "Skill loader: injected %d/%d skills (%d chars total, mode=%s, platform=%s)",
        loaded_count,
        len(skills_to_load),
        len(result),
        mode,
        platform,
    )
    return result
