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
import re
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

PLATFORM_SKILL_MAP = {
    "google": [
        "google-shopping-content",
        "allied-brass-brand-expert",
        "product-storytelling",
    ],
    "bing": [
        "bing-shopping-content",
        "allied-brass-brand-expert",
    ],
    "shopify": [
        "shopify-conversion-content",
        "allied-brass-brand-expert",
        "product-storytelling",
        "collection-storytelling",
    ],
    "finish": [
        "finish-expertise",
        "collection-storytelling",
        "product-storytelling",
    ],
}

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

ACTIONABLE_XML_TAGS = ("rules", "examples", "formula", "constraints", "brand_voice")
EXCLUDED_SECTION_KEYWORDS = (
    "companion",
    "when to use",
    "workflow",
    "integration with existing pipeline",
    "metadata",
    "quick reference",
    "cross-platform comparison",
)

# Strip stale guidance lines from non-brand skills that conflict with
# current owner-approved policy guardrails.
_SKILL_LINE_BANLIST = (
    "die-cast zinc",
    "plated alternatives",
    "zinc alloy",
    "zamak",
    "chrome-plated steel",
    "hollow zinc",
    "heritage bathroom fixtures",
    "also searched as",
    "also known as",
    "spring-loaded",
    "60 grab bar",
)

_SKILL_LINE_WARNING_BANLIST = (
    "weight capacity",
)

SKILL_SECTION_KEYWORDS = {
    "google-shopping-content": (
        "shopper's reality",
        "title architecture",
        "title rules",
        "description architecture",
        "description structure",
        "bad-to-good",
        "gold standard",
    ),
    "bing-shopping-content": (
        "how bing differs",
        "title optimization",
        "title rules",
        "description architecture",
        "synonym coverage",
        "gold standard",
    ),
    "shopify-conversion-content": (
        "shopify buyer journey",
        "html structure",
        "title strategy",
        "title rules",
        "meta description",
        "character budget",
        "gold standard",
    ),
    "finish-expertise": (
        "the 28 finishes",
        "finish",
        "search behavior",
        "compelling sentences",
        "avoid",
    ),
    "allied-brass-brand-expert": (
        "critical: competitor material prohibition",
        "the allied brass truth",
        "how to express",
        "the allied brass voice",
        "voice anti-patterns",
        "accuracy rules",
    ),
    "product-storytelling": (
        "interior designer's perspective",
        "customer scenario library",
        "design style hooks",
        "finish as design language",
        "feature-to-benefit translation",
        "evidence exclusion rules",
    ),
    "collection-storytelling": (
        "why collections matter",
        "collection profiles",
        "style categories",
        "collection integration patterns",
        "cross-selling language",
    ),
}

PLATFORM_ROLE_MAP = {
    "google": "Google Shopping",
    "bing": "Bing Shopping",
    "shopify": "Shopify storefront",
    "finish": "finish-sentence",
}

SHARED_ACCURACY_RULES = """\
- Ground every factual claim in provided evidence.
- Never invent dimensions, certifications, warranties, or mechanisms.
- Do not mention competitor brands or inferior material names.
- Prefer concrete specifics over adjectives and marketing hype.
- Preserve required placeholders exactly when a schema requires them.
"""


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter and leading title noise from SKILL.md content."""
    return re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL).strip()


def _extract_xml_sections(content: str) -> list[str]:
    """Extract known actionable XML-tag sections when present."""
    extracted: list[str] = []
    for tag in ACTIONABLE_XML_TAGS:
        pattern = rf"<{tag}[^>]*>(.*?)</{tag}>"
        for match in re.finditer(pattern, content, flags=re.IGNORECASE | re.DOTALL):
            body = match.group(1).strip()
            if body:
                extracted.append(f"<{tag}>\n{body}\n</{tag}>")
    return extracted


def _split_markdown_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content into heading + body sections."""
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    lines: list[str] = []

    for line in content.splitlines():
        if re.match(r"^##+\s+", line):
            body = "\n".join(lines).strip()
            if body:
                sections.append((heading, body))
            heading = re.sub(r"^##+\s*", "", line).strip()
            lines = []
            continue
        lines.append(line)

    tail = "\n".join(lines).strip()
    if tail:
        sections.append((heading, tail))
    return sections


def _is_excluded_section(heading: str) -> bool:
    heading_lower = heading.lower()
    return any(token in heading_lower for token in EXCLUDED_SECTION_KEYWORDS)


def _select_markdown_sections(skill_name: str, content: str) -> list[str]:
    """Select actionable markdown sections when XML tags are unavailable."""
    selected: list[str] = []
    sections = _split_markdown_sections(content)
    keywords = SKILL_SECTION_KEYWORDS.get(skill_name, ())

    prioritized: list[tuple[str, str]] = []
    fallback: list[tuple[str, str]] = []

    for heading, body in sections:
        if _is_excluded_section(heading):
            continue
        lower = heading.lower()
        if keywords and any(token in lower for token in keywords):
            prioritized.append((heading, body))
        else:
            fallback.append((heading, body))

    ordered = prioritized if prioritized else fallback
    for heading, body in ordered:
        selected.append(f"## {heading}\n{body.strip()}")
    return selected


def _fit_chunks_to_window(
    chunks: list[str],
    min_chars: int,
    max_chars: int,
) -> str:
    """Assemble selected chunks into a bounded-size prompt section."""
    assembled: list[str] = []
    total_chars = 0

    for chunk in chunks:
        clean = re.sub(r"\n{3,}", "\n\n", chunk).strip()
        if not clean:
            continue
        projected = total_chars + len(clean) + (2 if assembled else 0)
        if projected > max_chars:
            remaining = max_chars - total_chars
            if remaining > 300:
                clipped = clean[:remaining].rstrip()
                last_break = clipped.rfind("\n")
                if last_break > 120:
                    clipped = clipped[:last_break]
                assembled.append(clipped.strip() + " …")
            break
        assembled.append(clean)
        total_chars = projected
        if total_chars >= min_chars:
            break

    if not assembled and chunks:
        return chunks[0][:max_chars].strip()
    return "\n\n".join(assembled).strip()


def _sanitize_extracted_knowledge(skill_name: str, content: str) -> str:
    """Remove stale/conflicting examples from extracted skill snippets.

    We preserve prohibition language but remove outdated "wrong example"
    lines that can bleed into model output.
    """
    if not content:
        return content

    cleaned_lines: list[str] = []
    for line in content.splitlines():
        lower = line.lower()
        if "wrong:" in lower:
            continue
        if any(term in lower for term in _SKILL_LINE_BANLIST):
            # Keep explicit prohibition language in the brand skill only.
            if skill_name == "allied-brass-brand-expert" and "banned terms:" in lower:
                cleaned_lines.append(line)
            continue
        if any(term in lower for term in _SKILL_LINE_WARNING_BANLIST):
            # Remove prescriptive lines that bias non-grab-bar copy toward
            # capacity callouts; brand/system prompt handles final policy.
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


@lru_cache(maxsize=64)
def extract_actionable_skill_knowledge(
    skill_name: str,
    min_chars: int = 2000,
    max_chars: int = 4000,
) -> str:
    """Extract actionable, platform-usable knowledge from a SKILL.md file."""
    content = load_skill_content(skill_name)
    if not content:
        return ""

    normalized = _strip_frontmatter(content)
    xml_sections = _extract_xml_sections(normalized)
    if xml_sections:
        fitted = _fit_chunks_to_window(
            xml_sections, min_chars=min_chars, max_chars=max_chars
        )
        return _sanitize_extracted_knowledge(skill_name, fitted)

    markdown_sections = _select_markdown_sections(skill_name, normalized)
    if markdown_sections:
        fitted = _fit_chunks_to_window(
            markdown_sections, min_chars=min_chars, max_chars=max_chars
        )
        return _sanitize_extracted_knowledge(skill_name, fitted)

    return _sanitize_extracted_knowledge(skill_name, normalized[:max_chars].strip())


def get_platform_system_prompt(platform: str) -> str:
    """Build a platform-specific system prompt from SYSTEM_PROMPT + creative brief.

    Architecture (v2 — Phase 25.3):
    - SYSTEM_PROMPT provides shared creative direction, objective hierarchy,
      brand voice, and global accuracy/scoring guardrails (cacheable).
    - Platform briefs (GOOGLE_BRIEF, etc.) provide platform-specific rules,
      field contracts, title/description structures, and output keys.
    - Total: ~4.5-5.5K chars — purpose-built GPT-5.2 instructions, not
      extracted skill snippets.

    Feature flags:
    - FEEDOPS_GOOGLE_BRIEF_VERSION: "v2" (default) or "v3" (skill-adapted prompt
      with worked examples and 8-step description structure).
    """
    import os

    from feedops.pipeline.prompts import (
        BING_BRIEF,
        FINISH_BRIEF,
        GOOGLE_BRIEF,
        GOOGLE_BRIEF_V3,
        SHOPIFY_BRIEF,
        SYSTEM_PROMPT,
    )

    platform_key = (platform or "").strip().lower()

    # Resolve Google brief version from env var
    google_brief_version = os.environ.get("FEEDOPS_GOOGLE_BRIEF_VERSION", "v2").strip().lower()
    active_google_brief = GOOGLE_BRIEF_V3 if google_brief_version == "v3" else GOOGLE_BRIEF

    briefs = {
        "google": active_google_brief,
        "bing": BING_BRIEF,
        "shopify": SHOPIFY_BRIEF,
        "finish": FINISH_BRIEF,
    }

    if platform_key not in briefs:
        raise ValueError(
            f"Unsupported platform '{platform}'. "
            f"Expected one of: {', '.join(sorted(briefs))}"
        )

    brief = briefs[platform_key]
    prompt = f"{SYSTEM_PROMPT}\n\n{brief}"

    logger.info(
        "Platform system prompt built: platform=%s brief_version=%s chars=%d",
        platform_key,
        google_brief_version if platform_key == "google" else "default",
        len(prompt),
    )
    return prompt


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
