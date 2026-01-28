"""Bing Merchant Center feed merge integration.

Since Bing doesn't support supplemental feeds, this module merges FeedOps
patches into the primary feed with tracking labels (custom_label_4).

References:
- Bing Merchant Center feed spec: https://help.ads.microsoft.com/#apex/ads/en/51084/1
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# Bing/Google Shopping namespace
G_NAMESPACE = "http://base.google.com/ns/1.0"


def _escape_cdata(text: str) -> str:
    """Escape text for use in CDATA sections."""
    return text.replace("]]>", "]]]]><![CDATA[>")


def load_bing_patches(
    patches_dir: Path,
    *,
    min_score: float | None = None,
    require_approval: bool = False,
) -> list[dict]:
    """Load Bing patch files from a directory.

    Args:
        patches_dir: Directory containing bing-patch-*.json files.
        min_score: Optional minimum quality score filter.
        require_approval: If True, only include approved patches.

    Returns:
        List of patch dictionaries.
    """
    patches_dir = Path(patches_dir)
    patches: list[dict] = []

    for patch_file in patches_dir.glob("bing-patch-*.json"):
        try:
            with open(patch_file) as f:
                patch = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        meta = patch.get("_meta", {})

        # Filter by approval status
        if require_approval:
            if meta.get("approval_status") != "approved":
                continue

        # Filter by minimum score
        if min_score is not None:
            score = meta.get("quality_score", 0)
            if score < min_score:
                continue

        # Add source file reference
        patch["_source_file"] = str(patch_file)
        patches.append(patch)

    return patches


def get_bing_patch_for_sku(
    patches_dir: Path,
    sku: str,
) -> dict | None:
    """Load a specific Bing patch file by SKU.

    Args:
        patches_dir: Directory containing patch files.
        sku: MasterSKU to look up.

    Returns:
        Patch dictionary or None if not found.
    """
    safe_sku = sku.replace("/", "-")
    patch_file = patches_dir / f"bing-patch-{safe_sku}.json"

    if not patch_file.exists():
        return None

    try:
        with open(patch_file) as f:
            patch = json.load(f)
        patch["_source_file"] = str(patch_file)
        return patch
    except (json.JSONDecodeError, OSError):
        return None


def parse_bing_feed(feed_path: Path) -> ET.Element:
    """Parse a Bing feed XML file.

    Args:
        feed_path: Path to the Bing feed XML.

    Returns:
        Root Element of the parsed XML.
    """
    tree = ET.parse(feed_path)
    return tree.getroot()


def _find_item_by_sku(root: ET.Element, sku: str) -> ET.Element | None:
    """Find an item element by SKU/offer_id.

    Args:
        root: Root element of the feed.
        sku: SKU to search for.

    Returns:
        Item element or None if not found.
    """
    # Register namespace for searching
    ns = {"g": G_NAMESPACE}

    # Search in channel/item elements
    for channel in root.findall(".//channel"):
        for item in channel.findall("item"):
            # Check g:id first (standard identifier)
            id_elem = item.find("g:id", ns)
            if id_elem is not None and id_elem.text == sku:
                return item

            # Also check g:offer_id
            offer_id_elem = item.find("g:offer_id", ns)
            if offer_id_elem is not None and offer_id_elem.text == sku:
                return item

    return None


def _set_element_text(
    parent: ET.Element,
    tag: str,
    text: str,
    ns: dict[str, str],
    use_cdata: bool = True,
) -> ET.Element:
    """Set or create an element with text content.

    Args:
        parent: Parent element.
        tag: Element tag (with namespace prefix, e.g., "g:title").
        text: Text content.
        ns: Namespace dictionary.
        use_cdata: Whether to use CDATA markers.

    Returns:
        The element (existing or newly created).
    """
    elem = parent.find(tag, ns)
    if elem is None:
        # Create new element
        # Convert tag like "g:title" to "{namespace}title"
        if ":" in tag:
            prefix, local = tag.split(":", 1)
            full_tag = f"{{{ns.get(prefix, '')}}}{local}"
        else:
            full_tag = tag
        elem = ET.SubElement(parent, full_tag)

    if use_cdata:
        elem.text = f"__CDATA__{_escape_cdata(text)}__ENDCDATA__"
    else:
        elem.text = text

    return elem


def merge_feedops_into_bing_feed(
    patches: list[dict],
    base_feed_path: Path,
    environment: str = "staging",
) -> str:
    """Merge FeedOps patches into an existing Bing feed with tracking labels.

    Args:
        patches: List of bing-patch-*.json dictionaries.
        base_feed_path: Path to the current Bing primary feed XML.
        environment: 'staging' or 'production' - used for custom_label_4.

    Returns:
        Updated feed XML string.

    Process:
    1. Parse existing Bing feed
    2. For each approved patch:
       - Find matching item by sku (offer_id)
       - Update title/description
       - Add custom_label_4 = "feedops-{environment}"
    3. Return merged XML

    Raises:
        FileNotFoundError: If base feed doesn't exist.
    """
    if not base_feed_path.exists():
        raise FileNotFoundError(f"Base feed not found: {base_feed_path}")

    # Register namespace
    ET.register_namespace("g", G_NAMESPACE)
    ns = {"g": G_NAMESPACE}

    # Parse the base feed
    root = parse_bing_feed(base_feed_path)

    tracking_label = f"feedops-{environment}"
    updated_count = 0

    # Process each patch
    for patch in patches:
        sku = patch.get("sku")
        if not sku:
            continue

        # Find the item in the feed
        item = _find_item_by_sku(root, sku)
        if item is None:
            # Item not found in base feed, skip
            continue

        title = patch.get("title")
        description = patch.get("description")

        # Update title
        if title:
            _set_element_text(item, "g:title", title, ns, use_cdata=True)

        # Update description
        if description:
            _set_element_text(item, "g:description", description, ns, use_cdata=True)

        # Set custom_label_4 for tracking
        _set_element_text(item, "g:custom_label_4", tracking_label, ns, use_cdata=False)

        updated_count += 1

    # Convert to string
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

    # Post-process for CDATA
    xml_str = xml_str.replace("__CDATA__", "<![CDATA[")
    xml_str = xml_str.replace("__ENDCDATA__", "]]>")

    # Clean up namespace prefixes
    xml_str = xml_str.replace("ns0:", "g:")
    xml_str = xml_str.replace("xmlns:ns0=", "xmlns:g=")

    return xml_str


def _add_bing_feed_item(
    channel: ET.Element,
    sku: str,
    title: str | None,
    description: str | None,
    tracking_label: str,
) -> None:
    """Add a single item to the Bing feed channel."""
    if not sku:
        return

    if not title and not description:
        return

    item = ET.SubElement(channel, "item")

    # SKU/offer_id (required)
    id_elem = ET.SubElement(item, f"{{{G_NAMESPACE}}}id")
    id_elem.text = sku

    # Title with CDATA
    if title:
        title_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}title")
        title_el.text = f"__CDATA__{_escape_cdata(title)}__ENDCDATA__"

    # Description with CDATA
    if description:
        desc_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}description")
        desc_el.text = f"__CDATA__{_escape_cdata(description)}__ENDCDATA__"

    # Custom label for tracking
    label_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}custom_label_4")
    label_el.text = tracking_label


def generate_bing_feed_from_patches(
    patches: list[dict],
    environment: str = "staging",
    *,
    feed_title: str = "Allied Brass FeedOps - Bing Feed",
    include_variants: bool = True,
) -> str:
    """Generate a standalone Bing feed XML from patches (no base feed required).

    This is useful when you want to create a new feed containing only
    FeedOps-modified items.

    Args:
        patches: List of bing-patch-*.json dictionaries.
        environment: 'staging' or 'production'.
        feed_title: Title for the RSS channel.
        include_variants: If True, include variant-level items in feed.

    Returns:
        XML string in Bing Merchant Center format.
    """
    # Register namespace
    ET.register_namespace("g", G_NAMESPACE)

    # Create root RSS element
    rss = ET.Element("rss", {"version": "2.0", "xmlns:g": G_NAMESPACE})
    channel = ET.SubElement(rss, "channel")

    # Channel metadata
    title_elem = ET.SubElement(channel, "title")
    env_label = environment.capitalize()
    title_elem.text = f"{feed_title} ({env_label})"

    link_elem = ET.SubElement(channel, "link")
    link_elem.text = "https://alliedbrass.com"

    description_elem = ET.SubElement(channel, "description")
    description_elem.text = (
        f"FeedOps-optimized product content for Bing Shopping - {environment} environment. "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    tracking_label = f"feedops-{environment}"

    # Add items from patches
    for patch in patches:
        sku = patch.get("sku")
        if not sku:
            continue

        title = patch.get("title")
        description = patch.get("description")

        if not title and not description:
            continue

        # Add the master/primary item
        _add_bing_feed_item(
            channel=channel,
            sku=sku,
            title=title,
            description=description,
            tracking_label=tracking_label,
        )

        # Add variant items if enabled and variants exist
        if include_variants:
            variants = patch.get("variants", [])
            for variant in variants:
                variant_sku = variant.get("sku") or variant.get("option_sku")
                if not variant_sku or variant_sku == sku:
                    continue

                variant_title = variant.get("title", title)
                variant_description = variant.get("description", description)

                _add_bing_feed_item(
                    channel=channel,
                    sku=variant_sku,
                    title=variant_title,
                    description=variant_description,
                    tracking_label=tracking_label,
                )

    # Convert to string
    xml_str = ET.tostring(rss, encoding="unicode", xml_declaration=True)

    # Post-process for CDATA
    xml_str = xml_str.replace("__CDATA__", "<![CDATA[")
    xml_str = xml_str.replace("__ENDCDATA__", "]]>")

    # Clean up namespace prefixes
    xml_str = xml_str.replace("ns0:", "g:")
    xml_str = xml_str.replace("xmlns:ns0=", "xmlns:g=")

    return xml_str


def rollback_bing_feedops_content(
    base_feed_path: Path,
    skus_to_rollback: list[str],
    *,
    original_content: dict[str, dict] | None = None,
) -> str:
    """Remove FeedOps content from Bing feed for specific SKUs.

    Args:
        base_feed_path: Path to the current Bing feed XML.
        skus_to_rollback: List of SKUs to revert.
        original_content: Dict mapping SKU to original title/description.
            If provided, restores original content. If not, just removes
            the custom_label_4 tracking.

    Returns:
        Updated feed XML string.

    Process:
    1. Parse feed
    2. For each SKU in rollback list:
       - If original_content provided: restore title/description
       - Remove custom_label_4 if it contains "feedops-"
    3. Return cleaned XML
    """
    if not base_feed_path.exists():
        raise FileNotFoundError(f"Feed not found: {base_feed_path}")

    # Register namespace
    ET.register_namespace("g", G_NAMESPACE)
    ns = {"g": G_NAMESPACE}

    # Parse the feed
    root = parse_bing_feed(base_feed_path)

    for sku in skus_to_rollback:
        item = _find_item_by_sku(root, sku)
        if item is None:
            continue

        # Restore original content if provided
        if original_content and sku in original_content:
            orig = original_content[sku]
            if orig.get("title"):
                _set_element_text(item, "g:title", orig["title"], ns, use_cdata=True)
            if orig.get("description"):
                _set_element_text(
                    item, "g:description", orig["description"], ns, use_cdata=True
                )

        # Remove custom_label_4 if it's a feedops label
        label_elem = item.find("g:custom_label_4", ns)
        if label_elem is not None:
            label_text = label_elem.text or ""
            if label_text.startswith("feedops-"):
                item.remove(label_elem)

    # Convert to string
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=True)

    # Post-process for CDATA
    xml_str = xml_str.replace("__CDATA__", "<![CDATA[")
    xml_str = xml_str.replace("__ENDCDATA__", "]]>")

    # Clean up namespace prefixes
    xml_str = xml_str.replace("ns0:", "g:")
    xml_str = xml_str.replace("xmlns:ns0=", "xmlns:g=")

    return xml_str


def write_bing_feed(
    patches_dir: Path,
    output_path: Path,
    environment: str = "staging",
    *,
    base_feed_path: Path | None = None,
    min_score: float | None = None,
    require_approval: bool = False,
    include_variants: bool = True,
) -> int:
    """Generate and write a Bing feed file.

    Args:
        patches_dir: Directory containing bing-patch-*.json files.
        output_path: Path to write the XML feed.
        environment: 'staging' or 'production'.
        base_feed_path: Optional path to base feed (for merge mode).
        min_score: Optional minimum quality score filter.
        require_approval: If True, only include approved patches.
        include_variants: If True, include variant-level items in feed.

    Returns:
        Number of patches included/updated in the feed (variants may expand this).
    """
    patches = load_bing_patches(
        patches_dir,
        min_score=min_score,
        require_approval=require_approval,
    )

    if not patches:
        return 0

    if base_feed_path and base_feed_path.exists():
        # Merge mode: update existing feed
        xml_content = merge_feedops_into_bing_feed(patches, base_feed_path, environment)
    else:
        # Standalone mode: create new feed with only FeedOps items
        xml_content = generate_bing_feed_from_patches(
            patches,
            environment,
            include_variants=include_variants,
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_content, encoding="utf-8")

    return len(patches)
