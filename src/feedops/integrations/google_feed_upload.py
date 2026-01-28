"""Google Merchant Center Content API v2.1 feed upload.

Handles creation and upload of supplemental feeds to Google Merchant Center.
Reuses authentication from merchant_center module.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

import httpx

from feedops.integrations.merchant_center import _get_access_token

# Content API v2.1 endpoints
CONTENT_API_BASE = "https://shoppingcontent.googleapis.com/content/v2.1"
DATAFEEDS_ENDPOINT = f"{CONTENT_API_BASE}/{{merchantId}}/datafeeds"
DATAFEED_ENDPOINT = f"{CONTENT_API_BASE}/{{merchantId}}/datafeeds/{{datafeedId}}"


def list_datafeeds(
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> list[dict]:
    """List all datafeeds in the Merchant Center account.

    Args:
        merchant_id: GMC account ID (defaults to GMC_MERCHANT_ID env var).
        env: Environment variables mapping.

    Returns:
        List of datafeed resources.
    """
    env = env or os.environ
    merchant_id = merchant_id or env.get("GMC_MERCHANT_ID")
    if not merchant_id:
        raise ValueError("Missing GMC_MERCHANT_ID for Merchant Center API.")

    token = _get_access_token(env)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = DATAFEEDS_ENDPOINT.format(merchantId=merchant_id)

    datafeeds: list[dict] = []
    page_token: str | None = None

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        while True:
            params: dict = {"maxResults": 250}
            if page_token:
                params["pageToken"] = page_token

            response = client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()

            payload = response.json()
            datafeeds.extend(payload.get("resources", []) or [])

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

    return datafeeds


def find_datafeed_by_name(
    feed_name: str,
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict | None:
    """Find an existing datafeed by name.

    Args:
        feed_name: Name of the datafeed to find.
        merchant_id: GMC account ID.
        env: Environment variables mapping.

    Returns:
        Datafeed resource dict or None if not found.
    """
    datafeeds = list_datafeeds(merchant_id, env=env)
    for feed in datafeeds:
        if feed.get("name") == feed_name:
            return feed
    return None


def create_datafeed(
    feed_name: str,
    *,
    merchant_id: str | None = None,
    content_type: str = "supplemental products",
    target_country: str = "US",
    content_language: str = "en",
    file_name: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Create a new supplemental datafeed in Merchant Center.

    Args:
        feed_name: Display name for the datafeed.
        merchant_id: GMC account ID.
        content_type: Feed content type (default: "supplemental products").
        target_country: Target country code (default: "US").
        content_language: Content language code (default: "en").
        file_name: Optional filename for the feed.
        env: Environment variables mapping.

    Returns:
        Created datafeed resource.

    Raises:
        httpx.HTTPStatusError: If the API request fails.
    """
    env = env or os.environ
    merchant_id = merchant_id or env.get("GMC_MERCHANT_ID")
    if not merchant_id:
        raise ValueError("Missing GMC_MERCHANT_ID for Merchant Center API.")

    token = _get_access_token(env)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    endpoint = DATAFEEDS_ENDPOINT.format(merchantId=merchant_id)

    # Build datafeed resource
    datafeed_body = {
        "name": feed_name,
        "contentType": content_type,
        "targets": [
            {
                "country": target_country,
                "language": content_language,
                "includedDestinations": ["Shopping"],
            }
        ],
    }

    if file_name:
        datafeed_body["fileName"] = file_name

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.post(endpoint, headers=headers, json=datafeed_body)
        response.raise_for_status()
        return response.json()


def get_datafeed_status(
    datafeed_id: str,
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Get the status of a datafeed.

    Args:
        datafeed_id: ID of the datafeed.
        merchant_id: GMC account ID.
        env: Environment variables mapping.

    Returns:
        Datafeed status resource.
    """
    env = env or os.environ
    merchant_id = merchant_id or env.get("GMC_MERCHANT_ID")
    if not merchant_id:
        raise ValueError("Missing GMC_MERCHANT_ID for Merchant Center API.")

    token = _get_access_token(env)
    headers = {"Authorization": f"Bearer {token}"}

    # Use the datafeedstatuses endpoint
    endpoint = f"{CONTENT_API_BASE}/{merchant_id}/datafeedstatuses/{datafeed_id}"

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.get(endpoint, headers=headers)
        response.raise_for_status()
        return response.json()


def delete_datafeed(
    datafeed_id: str,
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    """Delete a datafeed from Merchant Center.

    Args:
        datafeed_id: ID of the datafeed to delete.
        merchant_id: GMC account ID.
        env: Environment variables mapping.
    """
    env = env or os.environ
    merchant_id = merchant_id or env.get("GMC_MERCHANT_ID")
    if not merchant_id:
        raise ValueError("Missing GMC_MERCHANT_ID for Merchant Center API.")

    token = _get_access_token(env)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = DATAFEED_ENDPOINT.format(merchantId=merchant_id, datafeedId=datafeed_id)

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.delete(endpoint, headers=headers)
        response.raise_for_status()


def create_or_get_datafeed(
    feed_name: str,
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Get existing datafeed or create a new one.

    Args:
        feed_name: Name of the datafeed.
        merchant_id: GMC account ID.
        env: Environment variables mapping.

    Returns:
        Datafeed resource (existing or newly created).
    """
    # Try to find existing
    existing = find_datafeed_by_name(feed_name, merchant_id, env=env)
    if existing:
        return existing

    # Create new
    return create_datafeed(feed_name, merchant_id=merchant_id, env=env)


def upload_supplemental_feed(
    feed_xml: str,
    feed_name: str = "feedops-supplemental",
    merchant_id: str | None = None,
    *,
    output_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Upload a supplemental feed to Google Merchant Center.

    This function:
    1. Creates or finds an existing datafeed by name
    2. Writes the XML to a local file (for reference/debugging)
    3. Returns the datafeed info for manual upload setup

    Note: Google Merchant Center requires feeds to be hosted at a URL or
    uploaded via SFTP. This function prepares the feed and returns the
    datafeed configuration. The actual feed content must be made available
    at a URL that GMC can fetch.

    Args:
        feed_xml: XML content of the supplemental feed.
        feed_name: Name for the datafeed in GMC.
        merchant_id: GMC account ID.
        output_dir: Directory to write the XML file (default: data/feeds/).
        env: Environment variables mapping.

    Returns:
        Dict with:
        - datafeed: The GMC datafeed resource
        - local_file: Path to the local XML file
        - status: 'created' or 'existing'
    """
    env = env or os.environ

    # Determine output directory
    if output_dir is None:
        output_dir = Path("data/feeds")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write XML to local file
    safe_name = feed_name.replace(" ", "-").lower()
    xml_path = output_dir / f"{safe_name}.xml"
    xml_path.write_text(feed_xml, encoding="utf-8")

    # Create or get datafeed in GMC
    existing = find_datafeed_by_name(feed_name, merchant_id, env=env)

    if existing:
        return {
            "datafeed": existing,
            "local_file": str(xml_path),
            "status": "existing",
            "message": (
                f"Datafeed '{feed_name}' already exists. "
                f"XML written to {xml_path}. "
                "Update the datafeed's fetch URL to point to the hosted XML file."
            ),
        }

    # Create new datafeed
    datafeed = create_datafeed(
        feed_name,
        merchant_id=merchant_id,
        file_name=f"{safe_name}.xml",
        env=env,
    )

    return {
        "datafeed": datafeed,
        "local_file": str(xml_path),
        "status": "created",
        "message": (
            f"Datafeed '{feed_name}' created with ID {datafeed.get('id')}. "
            f"XML written to {xml_path}. "
            "Configure the datafeed's fetch URL in Merchant Center to point to the hosted XML file."
        ),
    }


def get_supplemental_feed_info(
    feed_name: str = "feedops-supplemental",
    merchant_id: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict | None:
    """Get information about the FeedOps supplemental feed.

    Args:
        feed_name: Name of the datafeed.
        merchant_id: GMC account ID.
        env: Environment variables mapping.

    Returns:
        Datafeed resource or None if not found.
    """
    return find_datafeed_by_name(feed_name, merchant_id, env=env)
