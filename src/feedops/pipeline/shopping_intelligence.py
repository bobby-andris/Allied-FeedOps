"""Google Shopping intelligence loader for prompt injection.

Loads the three-tier Shopping intelligence config from YAML and formats it
for injection into the dynamic user prompt. Cached for the container lifetime.

Architecture notes:
- YAML file lives at src/feedops/config/shopping_intelligence.yaml — inside the
  src/ tree so it is copied into the Cloud Run container by the Dockerfile.
- Uses lru_cache(maxsize=1), mirroring the pattern in collection_descriptions.py.
- Returns formatted prompt sections for the user prompt (NOT the system prompt)
  so OpenAI prompt caching on the static system prompt is preserved.

Public API:
    get_universal_rules() -> str
    get_category_intelligence(custom_label_0: str | None) -> str
    get_shopping_intelligence_section(custom_label_0: str | None) -> str
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def _load_shopping_intelligence() -> dict:
    """Load Shopping intelligence config. Cached for container lifetime."""
    path = Path(__file__).parent.parent / "config" / "shopping_intelligence.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def get_universal_rules() -> str:
    """Format universal Shopping rules for prompt injection.

    Returns:
        Formatted string of universal rules, or empty string if config missing.
    """
    try:
        data = _load_shopping_intelligence()
    except (FileNotFoundError, Exception):
        return ""

    universal = data.get("universal_rules", {})
    if not universal:
        return ""

    lines: list[str] = ["Universal Rules:"]

    title_rule = universal.get("title_structure", {})
    if title_rule:
        lines.append(f"- {title_rule.get('rule', '')}")
        if example := title_rule.get("example"):
            lines.append(f"  Example: \"{example}\"")

    material_rule = universal.get("material_differentiator", {})
    if material_rule:
        lines.append(f"- {material_rule.get('rule', '')}")

    desc_rule = universal.get("description_structure", {})
    if desc_rule:
        lines.append(f"- {desc_rule.get('rule', '')}")

    finish_rule = universal.get("finish_specificity", {})
    if finish_rule:
        lines.append(f"- {finish_rule.get('rule', '')}")
        if bad := finish_rule.get("bad_example"):
            lines.append(f"  BAD: \"{bad}\"")
        if good := finish_rule.get("good_example"):
            lines.append(f"  GOOD: \"{good}\"")

    front_load = universal.get("front_load_specs", {})
    if front_load:
        lines.append(f"- {front_load.get('rule', '')}")

    return "\n".join(lines)


def get_category_intelligence(custom_label_0: str | None) -> str:
    """Format category-specific Shopping rules for prompt injection.

    Performs case-insensitive, strip-normalized lookup on the category_rules
    YAML section. Returns empty string if no match (graceful fallback).

    Args:
        custom_label_0: The product category label (e.g., "Grab Bars", "Towel Bars").
                        Also accepts product_catalog.category values (same values).

    Returns:
        Formatted category rules string, or empty string if no match.
    """
    if not custom_label_0:
        return ""

    try:
        data = _load_shopping_intelligence()
    except (FileNotFoundError, Exception):
        return ""

    category_rules = data.get("category_rules", {})
    if not category_rules:
        return ""

    # Normalize: lowercase + strip for case-insensitive lookup
    key = custom_label_0.strip().lower()

    # Direct lookup first
    rule = category_rules.get(key)

    # Substring fallback: find any key that contains the normalized input
    # or that the normalized input contains (handles "grab bars" vs "Grab Bars")
    if rule is None:
        for yaml_key, yaml_rule in category_rules.items():
            if yaml_key in key or key in yaml_key:
                rule = yaml_rule
                break

    if rule is None:
        return ""

    lines: list[str] = [f"Category Rules ({custom_label_0.title()}):"]

    if title_instr := rule.get("title_instruction"):
        # Clean multi-line YAML scalars to single line
        cleaned = " ".join(str(title_instr).split())
        lines.append(f"- Title: {cleaned}")

    if size_instr := rule.get("size_instruction"):
        cleaned = " ".join(str(size_instr).split())
        lines.append(f"- Size: {cleaned}")

    if differentiation := rule.get("differentiation"):
        cleaned = " ".join(str(differentiation).split())
        lines.append(f"- Differentiation: {cleaned}")

    if intent_kws := rule.get("intent_keywords"):
        kw_str = ", ".join(f'"{kw}"' for kw in intent_kws[:5])
        lines.append(f"- High-intent keywords: {kw_str}")

    if evidence := rule.get("evidence"):
        cleaned = " ".join(str(evidence).split())
        lines.append(f"- Evidence: {cleaned}")

    if note := rule.get("note"):
        lines.append(f"- Note: {note}")

    is_lost = rule.get("is_lost_to_rank_pct")
    impressions = rule.get("monthly_impressions")
    if is_lost or impressions:
        parts = []
        if impressions:
            parts.append(f"{impressions:,} impressions/month")
        if is_lost:
            parts.append(f"{is_lost}% IS lost to rank")
        lines.append(f"- Performance: {'; '.join(parts)}")

    return "\n".join(lines)


def get_shopping_intelligence_section(custom_label_0: str | None) -> str:
    """Format the complete Shopping intelligence section for prompt injection.

    Combines: universal rules + category-specific rules + Allied Brass USP.
    Returns a formatted block starting with '=== GOOGLE SHOPPING OPTIMIZATION ==='.

    Args:
        custom_label_0: The product category label for category-specific rules.
                        Universal rules and USP are always included.

    Returns:
        Complete Shopping intelligence section string for injection into user prompt.
    """
    try:
        data = _load_shopping_intelligence()
    except (FileNotFoundError, Exception):
        return ""

    parts: list[str] = ["=== GOOGLE SHOPPING OPTIMIZATION ==="]

    universal = get_universal_rules()
    if universal:
        parts.append("")
        parts.append(universal)

    category = get_category_intelligence(custom_label_0)
    if category:
        parts.append("")
        parts.append(category)

    usp = data.get("allied_brass_usp", {})
    if usp:
        parts.append("")
        parts.append("Allied Brass USP:")
        if dual := usp.get("dual_positioning"):
            cleaned = " ".join(str(dual).split())
            parts.append(f"- {cleaned}")
        if quality := usp.get("solid_brass_quality"):
            cleaned = " ".join(str(quality).split())
            parts.append(f"- {cleaned}")
        if variety := usp.get("finish_variety"):
            cleaned = " ".join(str(variety).split())
            parts.append(f"- {cleaned}")

    return "\n".join(parts)
