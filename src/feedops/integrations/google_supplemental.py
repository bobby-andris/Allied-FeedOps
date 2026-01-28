"""Google Merchant Center supplemental feed generation.

Generates RSS 2.0 XML feeds that override titles and descriptions in the primary feed.
Uses custom_label_4 for tracking FeedOps-modified items in Google Ads reports.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# Google base namespace for product data
G_NAMESPACE = "http://base.google.com/ns/1.0"


def _escape_cdata(text: str) -> str:
    """Escape text for use in CDATA sections.

    CDATA sections cannot contain the string "]]>" so we need to split it.
    """
    return text.replace("]]>", "]]]]><![CDATA[>")


def generate_supplemental_feed(
    patches: list[dict],
    environment: str = "staging",
    *,
    feed_title: str = "Allied Brass FeedOps - Supplemental Feed",
) -> str:
    """Generate Google Merchant Center supplemental feed XML.

    Args:
        patches: List of google-patch-*.json dictionaries.
        environment: 'staging' or 'production' - used for custom_label_4.
        feed_title: Title for the RSS channel.

    Returns:
        XML string in Google Merchant Center RSS 2.0 format.

    Notes:
        - Uses CDATA sections for title/description to preserve formatting
        - Sets custom_label_4 to "feedops-staging" or "feedops-production"
        - Includes only approved patches by default (caller should filter)

    Example output:
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
          <channel>
            <title>Allied Brass FeedOps - Supplemental Feed (Staging)</title>
            <item>
              <g:id>shopify_US_7721863643362_42804912849122</g:id>
              <g:title><![CDATA[Traditional Retractable Wall Hook...]]></g:title>
              <g:description><![CDATA[Need a place to hang towels...]]></g:description>
              <g:custom_label_4>feedops-staging</g:custom_label_4>
            </item>
          </channel>
        </rss>
    """
    # Register namespace
    ET.register_namespace("g", G_NAMESPACE)

    # Create root RSS element
    rss = ET.Element("rss", {"version": "2.0", "xmlns:g": G_NAMESPACE})
    channel = ET.SubElement(rss, "channel")

    # Channel title
    title_elem = ET.SubElement(channel, "title")
    env_label = environment.capitalize()
    title_elem.text = f"{feed_title} ({env_label})"

    # Add generated timestamp
    link_elem = ET.SubElement(channel, "link")
    link_elem.text = "https://alliedbrass.com"

    description_elem = ET.SubElement(channel, "description")
    description_elem.text = (
        f"FeedOps-optimized product content - {environment} environment. "
        f"Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )

    # Custom label for tracking
    tracking_label = f"feedops-{environment}"

    # Add items from patches
    for patch in patches:
        offer_id = patch.get("offerId")
        if not offer_id:
            continue

        title = patch.get("title")
        description = patch.get("description")
        short_title = patch.get("short_title")

        if not title and not description:
            continue

        item = ET.SubElement(channel, "item")

        # Product ID (required)
        id_elem = ET.SubElement(item, f"{{{G_NAMESPACE}}}id")
        id_elem.text = offer_id

        # Title with CDATA
        if title:
            title_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}title")
            # We'll handle CDATA in post-processing since ElementTree doesn't support it directly
            title_el.text = f"__CDATA__{_escape_cdata(title)}__ENDCDATA__"

        # Short title (optional)
        if short_title:
            short_title_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}short_title")
            short_title_el.text = f"__CDATA__{_escape_cdata(short_title)}__ENDCDATA__"

        # Description with CDATA
        if description:
            desc_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}description")
            desc_el.text = f"__CDATA__{_escape_cdata(description)}__ENDCDATA__"

        # Custom label for tracking
        label_el = ET.SubElement(item, f"{{{G_NAMESPACE}}}custom_label_4")
        label_el.text = tracking_label

    # Convert to string
    xml_str = ET.tostring(rss, encoding="unicode", xml_declaration=True)

    # Post-process to add proper CDATA sections
    xml_str = xml_str.replace("__CDATA__", "<![CDATA[")
    xml_str = xml_str.replace("__ENDCDATA__", "]]>")

    # Clean up the namespace prefix (ElementTree uses ns0 instead of g)
    xml_str = xml_str.replace("ns0:", "g:")
    xml_str = xml_str.replace("xmlns:ns0=", "xmlns:g=")

    return xml_str


def load_google_patches(
    patches_dir: Path,
    *,
    min_score: float | None = None,
    require_approval: bool = False,
) -> list[dict]:
    """Load Google patch files from a directory.

    Args:
        patches_dir: Directory containing google-patch-*.json files.
        min_score: Optional minimum quality score filter.
        require_approval: If True, only include approved patches.

    Returns:
        List of patch dictionaries.
    """
    patches_dir = Path(patches_dir)
    patches: list[dict] = []

    for patch_file in patches_dir.glob("google-patch-*.json"):
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


def write_supplemental_feed(
    patches_dir: Path,
    output_path: Path,
    environment: str = "staging",
    *,
    min_score: float | None = None,
    require_approval: bool = False,
) -> int:
    """Generate and write a supplemental feed file.

    Args:
        patches_dir: Directory containing google-patch-*.json files.
        output_path: Path to write the XML feed.
        environment: 'staging' or 'production'.
        min_score: Optional minimum quality score filter.
        require_approval: If True, only include approved patches.

    Returns:
        Number of items included in the feed.
    """
    patches = load_google_patches(
        patches_dir,
        min_score=min_score,
        require_approval=require_approval,
    )

    if not patches:
        return 0

    xml_content = generate_supplemental_feed(patches, environment)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml_content, encoding="utf-8")

    return len(patches)


def get_patch_for_sku(
    patches_dir: Path,
    sku: str,
) -> dict | None:
    """Load a specific Google patch file by SKU.

    Args:
        patches_dir: Directory containing patch files.
        sku: MasterSKU to look up.

    Returns:
        Patch dictionary or None if not found.
    """
    # Handle SKUs with / characters (replace with -)
    safe_sku = sku.replace("/", "-")
    patch_file = patches_dir / f"google-patch-{safe_sku}.json"

    if not patch_file.exists():
        return None

    try:
        with open(patch_file) as f:
            patch = json.load(f)
        patch["_source_file"] = str(patch_file)
        return patch
    except (json.JSONDecodeError, OSError):
        return None
