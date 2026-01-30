"""Finish-specific content injection for per-GMCID descriptions.

This module handles:
1. Loading finish metadata
2. Determining if finish + collection aesthetics align
3. Generating finish-specific description snippets
4. Injecting snippets into base descriptions
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

# Load finish metadata at module import
_FINISH_METADATA_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "finish-metadata.json"
)
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
    # Replace plural first, then singular, to preserve number agreement
    text = re.sub(r"\bbathrooms\b", "kitchens", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbathroom\b", "kitchen", text, flags=re.IGNORECASE)
    text = re.sub(r"\bbath\b", "kitchen", text, flags=re.IGNORECASE)
    return text


def _build_finish_benefit_clause(
    finish_name: str,
    meta: dict | None,
    room_context: str | None,
) -> str | None:
    """Build a relative clause describing the finish benefit.

    The returned string is joined onto the first sentence as:
        ``"...in {finish_name}, {clause}."``
    so it must be grammatically valid after a comma — typically a
    relative clause starting with "which" or a participial phrase.
    """
    if not meta:
        return None
    functional_desc = (meta.get("functional_description") or "").strip()
    if not functional_desc:
        return None
    functional_desc = _apply_room_context(functional_desc, room_context).rstrip(".")
    lower = functional_desc.lower()
    finish_lower = finish_name.lower()
    if lower.startswith(finish_lower):
        rest = functional_desc[len(finish_name) :].lstrip()
        if not rest:
            return None
        # If the remainder starts with a verb, make it a relative clause.
        if rest.lower().startswith(_FINISH_VERB_PREFIXES):
            return f"which {rest}"
        # Otherwise also wrap with "which" so the join is grammatical.
        # "in Antique Brass, features a softened..." is broken;
        # "in Antique Brass, which features a softened..." is correct.
        if rest[0].islower():
            return f"which {rest}"
        # Starts with uppercase — treat as an appositive.
        first_word = rest.split()[0].rstrip(",").lower()
        if first_word.startswith(("a ", "an ")):
            return rest[0].lower() + rest[1:]
        return f"which {rest[0].lower()}{rest[1:]}"
    # functional_desc doesn't start with finish name — use as-is,
    # but ensure it can follow "in {finish}, ..."
    if functional_desc[0].isupper():
        return f"which {functional_desc[0].lower()}{functional_desc[1:]}"
    return f"which {functional_desc}"


def _update_size_in_description(description: str, size: str) -> str:
    """Update size references in description for variant-specific content.

    For multi-size products, ensures the description reflects the specific size
    of this variant rather than generic sizing language.

    Args:
        description: The base description
        size: The variant's size (e.g., "18 Inch", "24 Inch")

    Returns:
        Description with size-specific content
    """
    if not description or not size:
        return description

    # Extract numeric size (e.g., "18" from "18 Inch")
    size_match = re.search(r"(\d+)", size)
    if not size_match:
        return description
    size_num = size_match.group(1)

    # Pattern to match size references like "18-Inch", "18 Inch", "18-inch", "18 in"
    # IMPORTANT: avoid matching the fractional part of decimal measurements (e.g., "2.64-Inch")
    # which would corrupt dimensions when performing replacements.
    size_pattern = r"(?<!\.)\b\d+[-\s]?[Ii]nch\b|(?<!\.)\b\d+[-\s]?in\b"

    # Replace size references in common contexts
    # "Length: 18 Inch" -> keep as is if already correct, or update
    desc = description

    # Update "Length: X Inch" or "X-Inch" references
    def replace_size(match):
        return f"{size_num}-Inch"

    # Only replace if we find size references that aren't already the correct size
    current_sizes = re.findall(size_pattern, desc)
    if current_sizes:
        # Check if all sizes are already correct
        correct_pattern = rf"(?<!\.)\b{size_num}[-\s]?[Ii]nch\b|(?<!\.)\b{size_num}[-\s]?in\b"
        if not all(re.match(correct_pattern, s, re.IGNORECASE) for s in current_sizes):
            # Replace with the specific size
            desc = re.sub(size_pattern, f"{size_num}-Inch", desc, count=1)

    # Add size to specs section if present but doesn't have correct size
    if "Length:" in desc and f"Length: {size_num}" not in desc:
        desc = re.sub(r"Length:\s*\d+\s*[Ii]nch", f"Length: {size}", desc)

    return desc


def _replace_first_sentence_with_finish(
    description: str,
    finish_name: str,
    clause: str | None,
    sku_hint: str = "",
) -> str:
    """Replace the first sentence with a finish-forward version.

    Uses deterministic pattern variation (based on sku_hint hash) to avoid
    every variant description starting with the same sentence structure.
    """
    if not description:
        return description
    # Match a sentence-ending period — skip decimal points inside numbers
    # like "4.5 in" or "0.38 in" by requiring the period NOT be surrounded
    # by digits on both sides.
    match = re.search(r"(?<!\d)\.(?!\d)", description)
    if not match:
        base_sentence = description.strip()
        rest = ""
    else:
        base_sentence = description[: match.start()].strip()
        rest = description[match.end() :]
    if not base_sentence or finish_name.lower() in base_sentence.lower():
        return description
    base_sentence = base_sentence.rstrip(".")

    # Strip leading <p> tag if present — re-added after pattern application
    # so that all patterns produce text inside the HTML element.
    html_prefix = ""
    if base_sentence.startswith("<p>"):
        html_prefix = "<p>"
        base_sentence = base_sentence[3:]

    # Select sentence pattern deterministically by SKU hash
    patterns = [
        # Pattern 0: original — "{base} in {Finish}, {clause}."
        lambda base, fn, cl: f"{base} in {fn}, {cl}." if cl else f"{base} in {fn}.",
        # Pattern 1: finish-forward — "Finished in {Finish}, {base}..."
        lambda base, fn, cl: (
            f"Finished in {fn}, {base[0].lower()}{base[1:]}"
            + (f", {cl}" if cl else "")
            + "."
        ),
        # Pattern 2: dash-style — "{base} — available in {Finish}..."
        lambda base, fn, cl: (
            f"{base} — available in {fn}"
            + (f", {cl}" if cl else "")
            + "."
        ),
    ]
    idx = hash(sku_hint) % len(patterns) if sku_hint else 0
    new_sentence = html_prefix + patterns[idx](base_sentence, finish_name, clause)

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
            if collection_subgroup == "Designer Statement" and affinity in (
                "bold",
                "eclectic",
                "contemporary",
            ):
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
    if (
        description_type == "coordination"
        and coordination_note
        and collection_name
        and collection_group
    ):
        # Check style alignment
        if _check_style_alignment(
            style_affinities, collection_group, collection_subgroup
        ):
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
            finish_section = (
                f"\n\n<p><strong>About This Finish:</strong> {finish_snippet}</p>\n\n"
            )
        else:
            # Plain text for Google/Bing
            finish_section = f"\n\nAbout This Finish: {finish_snippet}\n\n"

        return before + finish_section + after
    else:
        # No specs section found - append at end
        if platform == "shopify":
            return (
                base_description
                + f"\n\n<p><strong>About This Finish:</strong> {finish_snippet}</p>"
            )
        else:
            return base_description + f"\n\nAbout This Finish: {finish_snippet}"


def _get_finish_specific_bullets(
    finish_name: str,
    meta: dict,
    room_context: str | None = None,
    category: str | None = None,
) -> list[str]:
    """Generate finish-appropriate benefit bullets.

    When a product category is provided, bullets are tailored to the
    product type for more relevant copy.
    """
    bullets: list[str] = []
    finish_category = meta.get("category", "")
    description_type = meta.get("description_type", "coordination")
    finish_lower = finish_name.lower()
    cat_lower = (category or "").lower()

    if finish_category == "statement_color":
        if "grab bar" in cat_lower or "ada" in cat_lower:
            bullets.append(f"{finish_name} adds style to a safety essential")
        elif "cabinet" in cat_lower:
            bullets.append(f"{finish_name} makes a bold accent on cabinetry")
        else:
            bullets.append(
                f"{finish_name} transforms this essential into a conversation piece"
            )
        bullets.append(
            f"{finish_name} delivers a bold design statement with personal style"
        )
    elif finish_category == "living_finish":
        bullets.append(
            f"{finish_name} develops a unique, one-of-a-kind patina over time"
        )
        bullets.append("Each piece evolves to tell its own story")
    elif "chrome" in finish_lower or "nickel" in finish_lower:
        bullets.append(
            f"{finish_name} coordinates seamlessly with chrome faucets and fixtures"
        )
        if "polished" in finish_lower:
            bullets.append(f"{finish_name} adds bright, reflective light to the room")
        elif "satin" in finish_lower or "brushed" in finish_lower:
            bullets.append(
                f"{finish_name} hides fingerprints and water spots with a soft sheen"
            )
    elif "brass" in finish_lower:
        bullets.append(f"{finish_name} brings warm, timeless elegance")
        if "antique" in finish_lower:
            bullets.append(f"{finish_name} adds vintage-inspired character and warmth")
        elif "polished" in finish_lower:
            bullets.append(f"{finish_name} creates a classic, sophisticated glow")
    elif "bronze" in finish_lower:
        bullets.append(f"{finish_name} brings rich depth and character")
        if "oil rubbed" in finish_lower or "venetian" in finish_lower:
            bullets.append(
                f"{finish_name} highlights craftsmanship with subtle accents"
            )
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
    if not _check_style_alignment(
        style_affinities, collection_group, collection_subgroup
    ):
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
            return "Solid brass construction -- outlasts die-cast zinc and plastic alternatives found in mass-market brands"
        if "brass" in material_lower:
            return "Brass construction -- outlasts die-cast zinc and plastic alternatives"
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
    size: Optional[str] = None,
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
        size: Optional size for multi-size products (e.g., "18 Inch")

    Returns:
        Variant-specific description with finish content injected
    """
    # Remove generic "Available in X finishes" text since this is for a specific finish
    desc = base_description

    # Remove any Finish options lines entirely (some upstream templates include these as a
    # generic "available in multiple finishes" statement which becomes incorrect after
    # finish-specific injection). This must happen before any string replacements to avoid
    # leaving a dangling unbulleted line.
    desc = re.sub(r"(?im)^[ \t-]*finish options:.*\n", "", desc)
    desc = re.sub(
        r"(?im)^[ \t]*multiple designer finish options available\s*\n",
        "",
        desc,
    )

    # For Google/Bing, update size references in description if size is provided.
    # For Shopify, keep description generic — Shopify product pages display all
    # size variants together, so size-specific language would be misleading.
    if size and platform in ("google", "bing"):
        desc = _update_size_in_description(desc, size)

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
    ]

    for pattern in patterns_to_remove:
        desc = desc.replace(pattern, "").replace(pattern + "\n", "")

    # Remove any leftover "Finish options:" lines with partial content
    desc = re.sub(r"- Finish options:[^\n]*\n?", "", desc)
    desc = re.sub(r"Finish options:[^\n]*\n?", "", desc)

    # Remove generic "available in X designer finishes" text (case-insensitive)
    desc = re.sub(r"[Aa]vailable in \d+ designer finishes[^\n]*\n?", "", desc)

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
    # Build a deterministic hint from finish + category for sentence pattern variation
    sku_hint = f"{finish_name}:{category or ''}"
    desc = _replace_first_sentence_with_finish(desc, finish_name, clause, sku_hint=sku_hint)

    replacement_bullets: list[str] = []
    if meta:
        finish_bullets = _get_finish_specific_bullets(
            finish_name,
            meta,
            room_context=room_context,
            category=category,
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
    size: str | None = None,
    platform: str = "google",
) -> str:
    """Generate a variant-specific title with finish name and optional size.

    The title should include the specific finish name for this GMCID.
    For Google/Bing, also includes size if the product has multiple sizes.

    Args:
        base_title: The base title (from LLM for MasterSKU)
        finish_name: The variant's finish
        size: Optional size (e.g., "18 Inch", "24 Inch") for multi-size products
        platform: Target platform (google, bing, shopify)

    Returns:
        Variant-specific title with finish (and size for Google/Bing) included
    """
    # For Shopify, we don't include size in title since the product page shows all sizes
    include_size = size and platform in ("google", "bing")

    # Check if finish is already in title
    finish_in_title = finish_name.lower() in base_title.lower()

    # Check if size is already in title (for cases like "18-Inch Towel Bar")
    size_in_title = False
    if size:
        # Normalize size for comparison (e.g., "18 Inch" matches "18-Inch")
        size_normalized = size.lower().replace(" ", "-").replace("inch", "").strip("-")
        size_in_title = size_normalized in base_title.lower().replace(" ", "-")

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
            # Update size in first segment if needed
            if include_size and size and not size_in_title:
                # Try to insert/replace size in the first segment
                first_seg = segments[0]
                # Common patterns: "Towel Bar 18-Inch" or "18-Inch Towel Bar"
                # Avoid matching fractional parts of decimals like "2.64-Inch"
                size_pattern = r"(?<!\.)\b\d+\s*-?\s*[Ii]nch\b"
                if re.search(size_pattern, first_seg):
                    # Replace existing size reference
                    first_seg = re.sub(size_pattern, size.replace(" ", "-"), first_seg)
                else:
                    # Insert size after product type if possible
                    first_seg = f"{first_seg} {size.replace(' ', '-')}"
                segments[0] = first_seg

            # Insert finish after first segment
            if not finish_in_title:
                segments = [segments[0], finish_name] + segments[1:]

            # If finish ends up beyond common truncation zones, move it into the first segment.
            # This preserves readability while ensuring variants differentiate early in SERPs.
            joined_preview = " | ".join(segments + ([brand] if brand else []))
            finish_pos = joined_preview.lower().find(finish_name.lower())
            if finish_pos >= 70 and len(segments) >= 2 and segments[1] == finish_name:
                segments = [f"{finish_name} {segments[0]}"] + segments[2:]
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
        title = f"{before} | {finish_name} | Allied Brass"
    else:
        title = f"{base_title} | {finish_name}"

    # Add size for Google/Bing if not already present
    if include_size and not size_in_title:
        title = f"{title} ({size})"

    return title


def generate_variant_keywords(
    finish_name: str,
    category: str | None = None,
    product_type: str | None = None,
) -> list[str]:
    """Generate finish-specific keywords for a variant.

    These keywords are used for variant-level targeting, NOT at the parent SKU level.

    Args:
        finish_name: The variant's finish (e.g., "Fire Engine Red", "Polished Chrome")
        category: The product category for more specific keywords (e.g., "Towel Bars")
        product_type: The canonical product type (e.g., "Towel Bar") for targeted keywords

    Returns:
        List of finish-specific keywords for search targeting
    """
    keywords = []
    finish_lower = finish_name.lower()

    # Product-type-specific keywords take priority
    if product_type:
        pt_lower = product_type.lower()
        keywords.append(f"{finish_lower} {pt_lower}")
        # Add room-qualified version
        room = "kitchen" if "kitchen" in (category or "").lower() else "bathroom"
        keywords.append(f"{finish_lower} {room} {pt_lower}")

    # Category-specific keywords if provided (and no product_type)
    if category and not product_type:
        category_lower = category.lower()
        keywords.append(f"{finish_lower} {category_lower}")

    # Generic fallback (keep but lower priority)
    keywords.append(f"{finish_lower} bathroom hardware")
    keywords.append(f"{finish_lower} bath accessories")

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
