"""Finish-specific content injection for per-GMCID descriptions.

This module handles:
1. Loading finish metadata
2. Determining if finish + collection aesthetics align
3. Generating finish-specific description snippets
4. Injecting snippets into base descriptions
"""

import json
from pathlib import Path
from typing import Optional

# Load finish metadata at module import
_FINISH_METADATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "finish-metadata.json"
_FINISH_METADATA: dict = {}
_FINISHES: dict = {}
_STYLE_TO_GROUPS: dict = {}


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


def generate_variant_description(
    base_description: str,
    finish_name: str,
    collection_name: Optional[str] = None,
    collection_group: Optional[str] = None,
    collection_subgroup: Optional[str] = None,
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
    import re
    desc = re.sub(r'- Finish options:[^\n]*\n?', '', desc)
    desc = re.sub(r'Finish options:[^\n]*\n?', '', desc)
    
    # Remove generic "available in X designer finishes" text (case-insensitive)
    desc = re.sub(r'[Aa]vailable in \d+ designer finishes[^\n]*\n?', '', desc)
    
    # Clean up any double newlines created by removal
    while "\n\n\n" in desc:
        desc = desc.replace("\n\n\n", "\n\n")
    
    # Generate and inject finish snippet
    snippet = generate_finish_snippet(
        finish_name=finish_name,
        collection_name=collection_name,
        collection_group=collection_group,
        collection_subgroup=collection_subgroup,
    )
    
    if snippet:
        desc = inject_finish_into_description(desc, snippet, platform)
    
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
    
    # Find position to insert finish (before "Allied Brass" or at end)
    brand_marker = "| Allied Brass"
    if brand_marker in base_title:
        # Insert finish before brand
        pos = base_title.find(brand_marker)
        before = base_title[:pos].rstrip()
        
        # Check if there's already a pipe separator
        if before.endswith("|"):
            before = before[:-1].rstrip()
        
        return f"{before} | {finish_name} | Allied Brass"
    else:
        # Append finish at end
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
