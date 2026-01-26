"""Finish-specific content injection for per-GMCID descriptions.

This module handles:
1. Loading finish metadata
2. Determining if finish + collection aesthetics align
3. Generating finish-specific description snippets
4. Injecting snippets into base descriptions
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

# Load finish metadata at module import
_FINISH_METADATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "finish-metadata.json"
_FINISH_METADATA: dict = {}
_FINISHES: dict = {}
_STYLE_TO_GROUPS: dict = {}
_FINISH_FORWARD_FLAG = "FEEDOPS_FINISH_FORWARD_V2"

_FINISH_VERB_PREFIXES = (
    "offers",
    "delivers",
    "provides",
    "brings",
    "creates",
    "introduces",
    "combines",
    "presents",
    "captures",
    "radiates",
    "makes",
    "is",
)


def _finish_forward_enabled() -> bool:
    """Check if finish-forward variant behavior is enabled."""
    value = os.getenv(_FINISH_FORWARD_FLAG)
    if value is None:
        return True
    return value.strip().lower() in {"1", "true", "yes"}


def _apply_room_context(text: str, room_context: str | None) -> str:
    """Normalize room wording to match kitchen vs bathroom context."""
    if not text or room_context != "kitchen":
        return text
    text = re.sub(r"\bbathrooms?\b", "kitchens", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbath\b", "kitchen", text, flags=re.IGNORECASE)
    return text


def _build_finish_benefit_clause(
    finish_name: str,
    meta: dict | None,
    room_context: str | None,
) -> str | None:
    if not meta:
        return None
    functional_desc = (meta.get("functional_description") or "").strip()
    if not functional_desc:
        return None
    functional_desc = _apply_room_context(functional_desc, room_context).rstrip(".")
    lower = functional_desc.lower()
    finish_lower = finish_name.lower()
    if lower.startswith(finish_lower):
        rest = functional_desc[len(finish_name):].lstrip()
        if not rest:
            return None
        if rest.lower().startswith(_FINISH_VERB_PREFIXES):
            return f"which {rest}"
        return rest
    return functional_desc


def _replace_first_sentence_with_finish(
    description: str,
    finish_name: str,
    clause: str | None,
) -> str:
    """Replace the first sentence with a finish-forward version."""
    if not description:
        return description
    match = re.search(r"\.", description)
    if not match:
        base_sentence = description.strip()
        rest = ""
    else:
        base_sentence = description[:match.start()].strip()
        rest = description[match.end():]
    if not base_sentence or finish_name.lower() in base_sentence.lower():
        return description
    base_sentence = base_sentence.rstrip(".")
    if clause:
        new_sentence = f"{base_sentence} in {finish_name}, {clause}."
    else:
        new_sentence = f"{base_sentence} in {finish_name}."
    if not rest:
        return new_sentence
    if rest.startswith("\n"):
        return f"{new_sentence}{rest}"
    return f"{new_sentence} {rest.lstrip()}"


def _replace_highlight_bullets(
    description: str,
    replacement_bullets: list[str],
    platform: str,
) -> str:
    if not replacement_bullets:
        return description
    if platform == "shopify":
        pattern = re.compile(r"<li>.*?</li>", re.DOTALL)
        index = 0

        def _replace(match: re.Match) -> str:
            nonlocal index
            if index < len(replacement_bullets):
                text = replacement_bullets[index]
                index += 1
                return f"<li>{text}</li>"
            return match.group(0)

        return pattern.sub(_replace, description, count=len(replacement_bullets))

    lines = description.splitlines()
    markers = ("Highlights:", "Key Features:")
    for idx, line in enumerate(lines):
        if line.strip() in markers:
            bullet_prefix = "- "
            cursor = idx + 1
            replaced = 0
            while cursor < len(lines) and lines[cursor].lstrip().startswith(("-", "•")):
                if replaced < len(replacement_bullets):
                    lines[cursor] = f"{bullet_prefix}{replacement_bullets[replaced]}"
                    replaced += 1
                cursor += 1
            if replaced < len(replacement_bullets):
                insert_at = idx + 1
                for bullet in reversed(replacement_bullets[replaced:]):
                    lines.insert(insert_at, f"{bullet_prefix}{bullet}")
            return "\n".join(lines)
    return description


def _load_finish_metadata() -> None:
    """Load finish metadata from JSON file."""
    global _FINISH_METADATA, _FINISHES, _STYLE_TO_GROUPS
    if _FINISH_METADATA:
        return  # Already loaded
    
    try:
        with open(_FINISH_METADATA_PATH) as f:
            _FINISH_METADATA = json.load(f)
            _FINISHES = _FINISH_METADATA.get("finishes", {})
            _STYLE_TO_GROUPS = _FINISH_METADATA.get("style_to_collection_groups", {})
    except FileNotFoundError:
        pass  # Graceful degradation


def get_finish_metadata(finish_name: str) -> Optional[dict]:
    """Get metadata for a specific finish."""
    _load_finish_metadata()
    
    # Try exact match first
    if finish_name in _FINISHES:
        return _FINISHES[finish_name]
    
    # Try case-insensitive match
    finish_lower = finish_name.lower()
    for name, meta in _FINISHES.items():
        if name.lower() == finish_lower:
            return meta
    
    return None


def _check_style_alignment(
    finish_affinities: list[str],
    collection_group: str,
    collection_subgroup: Optional[str] = None,
) -> bool:
    """Check if finish style affinities align with collection group.
    
    Args:
        finish_affinities: List of style affinities for the finish
        collection_group: The collection's group (e.g., "Transitional", "Contemporary/Modern")
        collection_subgroup: Optional subgroup (e.g., "Industrial Modern", "Coastal Modern")
        
    Returns:
        True if styles align, False otherwise
    """
    _load_finish_metadata()
    
    # Check each finish affinity
    for affinity in finish_affinities:
        matching_groups = _STYLE_TO_GROUPS.get(affinity, [])
        
        # Check if collection group matches
        if collection_group in matching_groups:
            return True
        
        # Check subgroup-specific matching
        if collection_subgroup:
            if collection_subgroup == "Industrial Modern" and affinity == "industrial":
                return True
            if collection_subgroup == "Coastal Modern" and affinity == "coastal":
                return True
            if collection_subgroup == "Designer Statement" and affinity in ("bold", "eclectic", "contemporary"):
                return True
    
    return False


def generate_finish_snippet(
    finish_name: str,
    collection_name: Optional[str] = None,
    collection_group: Optional[str] = None,
    collection_subgroup: Optional[str] = None,
) -> Optional[str]:
    """Generate a finish-specific description snippet.
    
    Args:
        finish_name: The finish name (e.g., "Polished Chrome", "Fire Engine Red")
        collection_name: The collection name (e.g., "Dottingham", "Pipeline")
        collection_group: The collection's group (e.g., "Transitional")
        collection_subgroup: Optional subgroup (e.g., "Industrial Modern")
        
    Returns:
        A finish-specific snippet to inject into description, or None if no metadata found
    """
    meta = get_finish_metadata(finish_name)
    if not meta:
        return None
    
    functional_desc = meta.get("functional_description", "")
    description_type = meta.get("description_type", "coordination")
    coordination_note = meta.get("coordination_note")
    style_affinities = meta.get("style_affinities", [])
    
    # Start with functional description
    # Note: functional_desc already starts with the finish name in most cases,
    # so we just use it directly
    snippet = functional_desc
    
    # For coordination finishes, check if we should mention collection
    if description_type == "coordination" and coordination_note and collection_name and collection_group:
        # Check style alignment
        if _check_style_alignment(style_affinities, collection_group, collection_subgroup):
            # Add collection coordination note
            coord_text = coordination_note.format(collection=collection_name)
            snippet += f" As part of the {collection_name} collection, it {coord_text}."
    
    # Statement finishes don't mention collection - the functional description stands alone
    # (already handled by not having a coordination_note)
    
    return snippet


def inject_finish_into_description(
    base_description: str,
    finish_snippet: str,
    platform: str = "google",
) -> str:
    """Inject finish snippet into base description.
    
    The snippet is inserted before the Specs section (if present) or appended at the end.
    
    Args:
        base_description: The base description (from LLM)
        finish_snippet: The finish-specific snippet
        platform: The target platform (google, bing, shopify)
        
    Returns:
        Description with finish content injected
    """
    if not finish_snippet:
        return base_description
    
    # Find insertion point - before Specs section
    specs_markers = ["Specs:", "Specs\n", "\nSpecs", "Specifications:"]
    insertion_point = None
    
    for marker in specs_markers:
        pos = base_description.find(marker)
        if pos != -1:
            insertion_point = pos
            break
    
    if insertion_point:
        # Insert finish snippet before specs
        before = base_description[:insertion_point].rstrip()
        after = base_description[insertion_point:]
        
        # Add finish section
        if platform == "shopify":
            # HTML format for Shopify
            finish_section = f"\n\n<p><strong>About This Finish:</strong> {finish_snippet}</p>\n\n"
        else:
            # Plain text for Google/Bing
            finish_section = f"\n\nAbout This Finish: {finish_snippet}\n\n"
        
        return before + finish_section + after
    else:
        # No specs section found - append at end
        if platform == "shopify":
            return base_description + f"\n\n<p><strong>About This Finish:</strong> {finish_snippet}</p>"
        else:
            return base_description + f"\n\nAbout This Finish: {finish_snippet}"


def _get_finish_specific_bullets(
    finish_name: str,
    meta: dict,
    room_context: str | None = None,
) -> list[str]:
    """Generate finish-appropriate benefit bullets."""
    bullets: list[str] = []
    finish_category = meta.get("category", "")
    description_type = meta.get("description_type", "coordination")
    finish_lower = finish_name.lower()

    if finish_category == "statement_color":
        bullets.append(f"{finish_name} transforms this essential into a conversation piece")
        bullets.append(f"{finish_name} delivers a bold design statement with personal style")
    elif finish_category == "living_finish":
        bullets.append(f"{finish_name} develops a unique, one-of-a-kind patina over time")
        bullets.append("Each piece evolves to tell its own story")
    elif "chrome" in finish_lower or "nickel" in finish_lower:
        bullets.append(f"{finish_name} coordinates seamlessly with chrome faucets and fixtures")
        if "polished" in finish_lower:
            bullets.append(f"{finish_name} adds bright, reflective light to the room")
        elif "satin" in finish_lower or "brushed" in finish_lower:
            bullets.append(f"{finish_name} hides fingerprints and water spots with a soft sheen")
    elif "brass" in finish_lower:
        bullets.append(f"{finish_name} brings warm, timeless elegance")
        if "antique" in finish_lower:
            bullets.append(f"{finish_name} adds vintage-inspired character and warmth")
        elif "polished" in finish_lower:
            bullets.append(f"{finish_name} creates a classic, sophisticated glow")
    elif "bronze" in finish_lower:
        bullets.append(f"{finish_name} brings rich depth and character")
        if "oil rubbed" in finish_lower or "venetian" in finish_lower:
            bullets.append(f"{finish_name} highlights craftsmanship with subtle accents")
    elif "black" in finish_lower:
        bullets.append(f"{finish_name} makes a bold, modern statement")
        bullets.append(f"{finish_name} pairs cleanly with any color palette")
    elif "gold" in finish_lower:
        bullets.append(f"{finish_name} elevates the room with luxe gold tones")
    elif "copper" in finish_lower:
        bullets.append(f"{finish_name} creates an inviting, organic feel")
    elif "pewter" in finish_lower:
        bullets.append(f"{finish_name} blends effortlessly with transitional decor")

    if description_type == "statement" and not bullets:
        bullets.append(f"{finish_name} creates a distinctive focal point")

    return [_apply_room_context(bullet, room_context) for bullet in bullets]


def _get_coordination_bullet(
    meta: dict | None,
    collection_name: str | None,
    collection_group: str | None,
    collection_subgroup: str | None,
    room_context: str | None,
) -> str | None:
    if not meta or not collection_name or not collection_group:
        return None
    if meta.get("description_type") != "coordination":
        return None
    coordination_note = meta.get("coordination_note")
    if not coordination_note:
        return None
    style_affinities = meta.get("style_affinities", [])
    if not _check_style_alignment(style_affinities, collection_group, collection_subgroup):
        return None
    bullet = coordination_note.format(collection=collection_name).strip()
    if bullet:
        bullet = bullet[0].upper() + bullet[1:]
    return _apply_room_context(bullet, room_context)


def _get_competitive_bullet(
    *,
    material: str | None,
    finish_count: int | None,
    room_context: str | None,
) -> str | None:
    if finish_count:
        room_label = room_context or "space"
        return f"Choose from {finish_count} designer finishes to match the rest of your {room_label}"
    if material:
        material_lower = material.lower()
        if "solid brass" in material_lower:
            return "Built from solid brass for long-term durability"
        if "brass" in material_lower:
            return "Crafted from brass for long-term durability"
    return None


def generate_variant_description(
    base_description: str,
    finish_name: str,
    collection_name: Optional[str] = None,
    collection_group: Optional[str] = None,
    collection_subgroup: Optional[str] = None,
    category: Optional[str] = None,
    room_context: Optional[str] = None,
    material: Optional[str] = None,
    finish_count: Optional[int] = None,
    platform: str = "google",
) -> str:
    """Generate a variant-specific description with finish content.
    
    This is the main entry point for generating per-GMCID descriptions.
    
    Args:
        base_description: The base description (from LLM for MasterSKU)
        finish_name: The variant's finish
        collection_name: The collection name
        collection_group: The collection's group
        collection_subgroup: Optional subgroup
        category: Optional category name for room context
        room_context: Optional room context override (kitchen/bathroom)
        material: Optional material for competitive bullets
        finish_count: Optional finish count for competitive bullets
        platform: Target platform
        
    Returns:
        Variant-specific description with finish content injected
    """
    # Remove generic "Available in X finishes" text since this is for a specific finish
    desc = base_description
    
    # Common patterns to remove (generic finish availability text)
    patterns_to_remove = [
        "Available in a wide variety of designer finishes",
        "Available in a wide variety of lifetime designer finishes",
        "available in a wide variety of designer finishes",
        "Available in 25 designer finishes",
        "Available in 28 designer finishes",
        "Available in multiple designer finishes",
        "Finish options: Available in a wide variety of designer finishes",
        "- Finish options: Available in a wide variety of designer finishes",
        "- Available in a wide variety of lifetime designer finishes",
        "- Finish options: ",
        "Finish options: ",
    ]
    
    for pattern in patterns_to_remove:
        desc = desc.replace(pattern, "").replace(pattern + "\n", "")
    
    # Remove any leftover "Finish options:" lines with partial content
    desc = re.sub(r'- Finish options:[^\n]*\n?', '', desc)
    desc = re.sub(r'Finish options:[^\n]*\n?', '', desc)
    
    # Remove generic "available in X designer finishes" text (case-insensitive)
    desc = re.sub(r'[Aa]vailable in \d+ designer finishes[^\n]*\n?', '', desc)
    
    # Clean up any double newlines created by removal
    while "\n\n\n" in desc:
        desc = desc.replace("\n\n\n", "\n\n")
    
    if not room_context and category:
        from feedops.pipeline.keyword_placement import get_room_context
        room_context = get_room_context(category)

    if not _finish_forward_enabled():
        snippet = generate_finish_snippet(
            finish_name=finish_name,
            collection_name=collection_name,
            collection_group=collection_group,
            collection_subgroup=collection_subgroup,
        )
        if snippet:
            desc = inject_finish_into_description(desc, snippet, platform)
        return desc.strip()

    meta = get_finish_metadata(finish_name)
    clause = _build_finish_benefit_clause(finish_name, meta, room_context)
    desc = _replace_first_sentence_with_finish(desc, finish_name, clause)

    replacement_bullets: list[str] = []
    if meta:
        finish_bullets = _get_finish_specific_bullets(
            finish_name,
            meta,
            room_context=room_context,
        )
        if finish_bullets:
            replacement_bullets.append(finish_bullets[0])
    coord_bullet = _get_coordination_bullet(
        meta,
        collection_name,
        collection_group,
        collection_subgroup,
        room_context,
    )
    if coord_bullet:
        replacement_bullets.append(coord_bullet)
    competitive_bullet = _get_competitive_bullet(
        material=material,
        finish_count=finish_count,
        room_context=room_context,
    )
    if competitive_bullet:
        replacement_bullets.append(competitive_bullet)

    desc = _replace_highlight_bullets(desc, replacement_bullets, platform)
    return desc.strip()


def generate_variant_title(
    base_title: str,
    finish_name: str,
) -> str:
    """Generate a variant-specific title with finish name.
    
    The title should include the specific finish name for this GMCID.
    
    Args:
        base_title: The base title (from LLM for MasterSKU)
        finish_name: The variant's finish
        
    Returns:
        Variant-specific title with finish included
    """
    # Check if finish is already in title
    if finish_name.lower() in base_title.lower():
        return base_title

    if _finish_forward_enabled():
        segments = [seg.strip() for seg in base_title.split("|") if seg.strip()]
        brand = None
        if segments and segments[-1].lower() == "allied brass":
            brand = "Allied Brass"
            segments = segments[:-1]
        else:
            for seg in segments:
                if seg.lower() == "allied brass":
                    brand = "Allied Brass"
                    segments = [s for s in segments if s.lower() != "allied brass"]
                    break
        if not segments:
            segments = [finish_name]
        else:
            segments = [segments[0], finish_name] + segments[1:]
        if brand:
            segments.append(brand)
        return " | ".join(segments)

    # Legacy behavior: insert finish before brand or at end
    brand_marker = "| Allied Brass"
    if brand_marker in base_title:
        pos = base_title.find(brand_marker)
        before = base_title[:pos].rstrip()
        if before.endswith("|"):
            before = before[:-1].rstrip()
        return f"{before} | {finish_name} | Allied Brass"
    return f"{base_title} | {finish_name}"


def generate_variant_keywords(
    finish_name: str,
    category: str | None = None,
) -> list[str]:
    """Generate finish-specific keywords for a variant.

    These keywords are used for variant-level targeting, NOT at the parent SKU level.

    Args:
        finish_name: The variant's finish (e.g., "Fire Engine Red", "Polished Chrome")
        category: The product category for more specific keywords (e.g., "Towel Bars")

    Returns:
        List of finish-specific keywords for search targeting
    """
    keywords = []
    finish_lower = finish_name.lower()

    # Base finish + product type keywords
    keywords.append(f"{finish_lower} bathroom hardware")
    keywords.append(f"{finish_lower} bath accessories")

    # Category-specific keywords if provided
    if category:
        category_lower = category.lower()
        keywords.append(f"{finish_lower} {category_lower}")

    # Check finish metadata for additional keyword opportunities
    meta = get_finish_metadata(finish_name)
    if meta:
        description_type = meta.get("description_type", "coordination")
        category_type = meta.get("category", "")

        # Statement finishes get additional bold/unique keywords
        if description_type == "statement":
            keywords.append(f"{finish_lower} statement finish")
            keywords.append(f"{finish_lower} designer hardware")

        # Living finish gets patina keywords
        if category_type == "living_finish":
            keywords.append(f"{finish_lower} living finish")
            keywords.append(f"{finish_lower} patina")

        # Statement colors get color-specific keywords
        if category_type == "statement_color":
            keywords.append(f"{finish_lower} colored hardware")
            keywords.append(f"{finish_lower} color bathroom")

    return keywords
