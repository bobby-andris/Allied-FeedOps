"""Shopify catalog snapshot integration."""

from __future__ import annotations

import csv
import html
import os
import re
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

import httpx

SHOPIFY_API_VERSION_DEFAULT = "2026-01"
SHOPIFY_GRAPHQL_QUERY = """
query ProductsForCatalog($first: Int!, $after: String, $query: String) {
  products(first: $first, after: $after, query: $query) {
    nodes {
      id
      legacyResourceId
      title
      descriptionHtml
      productType
      vendor
      tags
      collections(first: 10) {
        nodes {
          title
        }
      }
      featuredMedia {
        ... on MediaImage {
          image {
            url
          }
        }
      }
      metafields(first: 20) {
        nodes {
          namespace
          key
          value
          type
        }
      }
      variants(first: 250) {
        nodes {
          id
          legacyResourceId
          sku
          barcode
          title
          position
          selectedOptions {
            name
            value
          }
          media(first: 1) {
            nodes {
              ... on MediaImage {
                image {
                  url
                }
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


def _normalize_store_host(store_url: str) -> str:
    parsed = urlparse(store_url)
    if parsed.netloc:
        return parsed.netloc
    return store_url.replace("https://", "").replace("http://", "").strip("/")


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return " ".join(text.split())


def _parse_gid(value: str | None) -> str | None:
    if not value:
        return None
    parts = value.split("/")
    if parts and parts[-1].isdigit():
        return parts[-1]
    return None


def _load_sample_header() -> list[str]:
    sample_path = Path(__file__).resolve().parents[3] / "samples" / "sample-catalog.csv"
    if not sample_path.exists():
        raise FileNotFoundError(f"Missing sample catalog header: {sample_path}")
    with sample_path.open(newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def _load_finish_codes() -> dict[str, str]:
    finish_map: dict[str, str] = {}
    finishes_path = Path(__file__).resolve().parents[3] / "data" / "finishes.txt"
    if not finishes_path.exists():
        return finish_map
    for line in finishes_path.read_text().splitlines():
        if ":" not in line:
            continue
        name, filename, *_rest = [part.strip() for part in line.split(":")]
        if "-" in filename:
            code = filename.split("-")[-1].split(".")[0]
            finish_map[name.lower()] = code
    return finish_map


def _derive_finish(variant: dict) -> str:
    for option in variant.get("selectedOptions", []) or []:
        if option.get("name", "").strip().lower() == "finish":
            return option.get("value") or variant.get("title") or ""
    return variant.get("title") or ""


def _derive_finish_code(
    sku: str | None, finish: str, finish_map: dict[str, str]
) -> str:
    finish_codes = {code.upper() for code in finish_map.values()}
    if sku and "-" in sku:
        suffix = sku.split("-")[-1].strip()
        if suffix and suffix.upper() in finish_codes:
            return suffix.upper()
    mapped = finish_map.get(finish.lower())
    if mapped:
        return mapped.upper()
    if sku and "-" in sku:
        suffix = sku.split("-")[-1].strip()
        if suffix and suffix.isalnum() and 2 <= len(suffix) <= 5:
            return suffix.upper()
    return "UNK"


def _derive_master_sku(sku: str | None, finish_code: str) -> str:
    if not sku:
        return ""
    if finish_code and finish_code != "UNK":
        suffix = f"-{finish_code}".upper()
        if sku.upper().endswith(suffix):
            return sku[: -len(suffix)]
    return sku


def _extract_material(product: dict) -> str:
    for node in product.get("metafields", {}).get("nodes", []) or []:
        key = (node.get("key") or "").lower()
        value = (node.get("value") or "").strip()
        if "material" in key and value:
            return value
    allowed = {
        "brass": "Brass",
        "solid brass": "Solid Brass",
        "stainless steel": "Stainless Steel",
    }
    for tag in product.get("tags", []) or []:
        normalized = tag.strip().lower()
        if normalized in allowed:
            return allowed[normalized]
    return ""


def _extract_image_url(nodes: list[dict]) -> str:
    for node in nodes or []:
        image = node.get("image") if node else None
        if image and image.get("url"):
            return image["url"]
    return ""


def fetch_shopify_products(
    limit: int | None = None,
    *,
    env: Mapping[str, str] | None = None,
    query: str | None = None,
) -> list[dict]:
    env = env or os.environ
    store_url = env.get("SHOPIFY_STORE_URL")
    access_token = env.get("SHOPIFY_ACCESS_TOKEN")
    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    products: list[dict] = []
    after: str | None = None
    remaining = limit
    page_size = 50

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        while True:
            first = page_size
            if remaining is not None:
                first = min(first, remaining)
            variables = {"first": first, "after": after, "query": query}
            response = client.post(
                endpoint,
                json={"query": SHOPIFY_GRAPHQL_QUERY, "variables": variables},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise ValueError(f"Shopify GraphQL errors: {payload['errors']}")

            data = payload.get("data", {})
            result = data.get("products", {})
            nodes = result.get("nodes", [])
            products.extend(nodes)
            page_info = result.get("pageInfo", {})

            if remaining is not None:
                remaining -= len(nodes)
                if remaining <= 0:
                    break

            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

    return products


def fetch_shopify_product(
    master_sku: str, *, env: Mapping[str, str] | None = None
) -> dict | None:
    """Fetch a single Shopify product matching the master SKU."""
    finish_map = _load_finish_codes()
    target = (master_sku or "").strip().upper()
    if not target:
        return None
    search_query = f"sku:{target}*"
    products = fetch_shopify_products(limit=50, env=env, query=search_query)
    if not products:
        products = fetch_shopify_products(limit=200, env=env, query=None)
    for product in products:
        variants = product.get("variants", {}).get("nodes", []) or []
        for variant in variants:
            sku = variant.get("sku") or ""
            finish = _derive_finish(variant)
            finish_code = _derive_finish_code(sku, finish, finish_map)
            derived = _derive_master_sku(sku, finish_code)
            if derived and derived.strip().upper() == target:
                return product
    return None


def write_shopify_catalog_csv(output_path: Path, *, limit: int | None = None) -> None:
    header = _load_sample_header()
    finish_map = _load_finish_codes()
    products = fetch_shopify_products(limit)

    rows: list[list[str]] = []

    for product in products:
        product_type = product.get("productType") or ""
        collections = product.get("collections", {}).get("nodes", []) or []
        collection = collections[0].get("title") if collections else ""
        category = product_type or "Uncategorized"

        title = product.get("title") or ""
        description = _strip_html(product.get("descriptionHtml"))
        if not description:
            description = title

        material = _extract_material(product)
        featured_media = product.get("featuredMedia") or {}
        featured_image_url = ""
        if featured_media.get("image"):
            featured_image_url = featured_media["image"].get("url") or ""

        product_id = product.get("legacyResourceId") or _parse_gid(product.get("id"))
        product_id = str(product_id) if product_id else ""

        for variant in product.get("variants", {}).get("nodes", []) or []:
            sku = variant.get("sku") or ""
            finish = _derive_finish(variant)
            finish_code = _derive_finish_code(sku, finish, finish_map)
            master_sku = _derive_master_sku(sku, finish_code)

            variant_id = variant.get("legacyResourceId") or _parse_gid(
                variant.get("id")
            )
            variant_id = str(variant_id) if variant_id else ""
            gmc_id = ""
            if product_id and variant_id:
                gmc_id = f"shopify_US_{product_id}_{variant_id}"

            variant_media_nodes = variant.get("media", {}).get("nodes", []) or []
            main_image_url = (
                _extract_image_url(variant_media_nodes) or featured_image_url
            )
            main_image = os.path.basename(main_image_url) if main_image_url else ""

            values = {
                "MasterSKU": master_sku,
                "OPTION SKU": sku,
                "UPC": variant.get("barcode") or "",
                "GTIN": variant.get("barcode") or "",
                "GMCID": gmc_id,
                "Finish": finish,
                "Finish Code": finish_code,
                "Position": str(variant.get("position") or ""),
                "Category": category,
                "Collection": collection,
                "Title": title,
                "Narraive Copy": description,
                "Material": material,
                "Main": main_image,
                "Main URL": main_image_url,
            }

            row = [str(values.get(column, "")) for column in header]
            rows.append(row)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


# ============================================================================
# Shopify Product Mutations
# ============================================================================

SHOPIFY_UPDATE_PRODUCT_MUTATION = """
mutation UpdateProduct($input: ProductInput!) {
  productUpdate(input: $input) {
    product {
      id
      title
      descriptionHtml
      tags
    }
    userErrors {
      field
      message
    }
  }
}
"""

SHOPIFY_ADD_TAGS_MUTATION = """
mutation AddProductTags($id: ID!, $tags: [String!]!) {
  tagsAdd(id: $id, tags: $tags) {
    node {
      ... on Product {
        id
        tags
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

SHOPIFY_REMOVE_TAGS_MUTATION = """
mutation RemoveProductTags($id: ID!, $tags: [String!]!) {
  tagsRemove(id: $id, tags: $tags) {
    node {
      ... on Product {
        id
        tags
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""


def _product_gid(product_id: str) -> str:
    """Ensure product ID is in GID format."""
    if product_id.startswith("gid://"):
        return product_id
    return f"gid://shopify/Product/{product_id}"


def update_shopify_product(
    product_id: str,
    title: str | None = None,
    description_html: str | None = None,
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Update Shopify product title and/or description via Admin API.

    Args:
        product_id: Shopify product ID (numeric or GID format).
        title: New product title (optional).
        description_html: New HTML description (optional).
        store_url: Store URL (defaults to SHOPIFY_STORE_URL env var).
        access_token: API token (defaults to SHOPIFY_ACCESS_TOKEN env var).
        env: Environment variables mapping.
        dry_run: If True, validate but don't execute.

    Returns:
        Response dict with:
        - success: bool
        - product: Updated product data (if success)
        - errors: List of error messages (if any)
        - dry_run: True if this was a dry run

    Raises:
        ValueError: If credentials are missing.
        httpx.HTTPStatusError: If the API request fails.
    """
    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    if not title and not description_html:
        return {
            "success": False,
            "errors": ["No title or description provided"],
            "dry_run": dry_run,
        }

    gid = _product_gid(product_id)
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "product_id": gid,
            "title": title,
            "description_html": description_html,
            "message": "Dry run - no changes made",
        }

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    # Build mutation input
    input_data: dict = {"id": gid}
    if title:
        input_data["title"] = title
    if description_html:
        input_data["descriptionHtml"] = description_html

    variables = {"input": input_data}

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.post(
            endpoint,
            json={"query": SHOPIFY_UPDATE_PRODUCT_MUTATION, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    # Check for GraphQL errors
    if payload.get("errors"):
        return {
            "success": False,
            "errors": [str(e) for e in payload["errors"]],
            "dry_run": False,
        }

    # Check for user errors from mutation
    data = payload.get("data", {})
    result = data.get("productUpdate", {})
    user_errors = result.get("userErrors", [])

    if user_errors:
        return {
            "success": False,
            "errors": [f"{e['field']}: {e['message']}" for e in user_errors],
            "dry_run": False,
        }

    return {
        "success": True,
        "product": result.get("product"),
        "dry_run": False,
    }


def add_product_tags(
    product_id: str,
    tags: list[str],
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Add tags to a Shopify product.

    Args:
        product_id: Shopify product ID.
        tags: List of tags to add.
        store_url: Store URL.
        access_token: API token.
        env: Environment variables mapping.

    Returns:
        Response dict with success status.
    """
    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    gid = _product_gid(product_id)
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    variables = {"id": gid, "tags": tags}

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.post(
            endpoint,
            json={"query": SHOPIFY_ADD_TAGS_MUTATION, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        return {"success": False, "errors": [str(e) for e in payload["errors"]]}

    data = payload.get("data", {})
    result = data.get("tagsAdd", {})
    user_errors = result.get("userErrors", [])

    if user_errors:
        return {
            "success": False,
            "errors": [f"{e['field']}: {e['message']}" for e in user_errors],
        }

    return {"success": True, "node": result.get("node")}


def remove_product_tags(
    product_id: str,
    tags: list[str],
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Remove tags from a Shopify product.

    Args:
        product_id: Shopify product ID.
        tags: List of tags to remove.
        store_url: Store URL.
        access_token: API token.
        env: Environment variables mapping.

    Returns:
        Response dict with success status.
    """
    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    gid = _product_gid(product_id)
    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)

    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    variables = {"id": gid, "tags": tags}

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        response = client.post(
            endpoint,
            json={"query": SHOPIFY_REMOVE_TAGS_MUTATION, "variables": variables},
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        return {"success": False, "errors": [str(e) for e in payload["errors"]]}

    data = payload.get("data", {})
    result = data.get("tagsRemove", {})
    user_errors = result.get("userErrors", [])

    if user_errors:
        return {
            "success": False,
            "errors": [f"{e['field']}: {e['message']}" for e in user_errors],
        }

    return {"success": True, "node": result.get("node")}


def publish_to_shopify(
    product_id: str,
    title: str,
    description_html: str,
    environment: str = "staging",
    *,
    env: Mapping[str, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Publish optimized content to Shopify with environment tracking.

    This is the main publish function that:
    1. Adds environment-specific tag (feedops-staging or feedops-production)
    2. Updates the product title and description

    Args:
        product_id: Shopify product ID.
        title: New product title.
        description_html: New HTML description.
        environment: 'staging' or 'production'.
        env: Environment variables mapping.
        dry_run: If True, validate but don't execute.

    Returns:
        Response dict with success status and details.
    """
    tracking_tag = f"feedops-{environment}"

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "product_id": product_id,
            "title": title,
            "description_html": description_html,
            "tracking_tag": tracking_tag,
            "message": "Dry run - no changes made",
        }

    # First, add the tracking tag
    tag_result = add_product_tags(product_id, [tracking_tag], env=env)
    if not tag_result.get("success"):
        return {
            "success": False,
            "errors": tag_result.get("errors", ["Failed to add tracking tag"]),
            "step": "add_tag",
        }

    # Then update the product
    update_result = update_shopify_product(
        product_id,
        title=title,
        description_html=description_html,
        env=env,
        dry_run=False,
    )

    if not update_result.get("success"):
        return {
            "success": False,
            "errors": update_result.get("errors", ["Failed to update product"]),
            "step": "update_product",
            "tracking_tag": tracking_tag,
        }

    return {
        "success": True,
        "product": update_result.get("product"),
        "tracking_tag": tracking_tag,
        "environment": environment,
    }


def load_shopify_patches(
    patches_dir: Path,
    *,
    min_score: float | None = None,
    require_approval: bool = False,
) -> list[dict]:
    """Load Shopify patch files from a directory.

    Args:
        patches_dir: Directory containing shopify-patch-*.json files.
        min_score: Optional minimum quality score filter.
        require_approval: If True, only include approved patches.

    Returns:
        List of patch dictionaries.
    """
    import json

    patches_dir = Path(patches_dir)
    patches: list[dict] = []

    for patch_file in patches_dir.glob("shopify-patch-*.json"):
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


def get_shopify_patch_for_sku(
    patches_dir: Path,
    sku: str,
) -> dict | None:
    """Load a specific Shopify patch file by SKU.

    Args:
        patches_dir: Directory containing patch files.
        sku: MasterSKU to look up.

    Returns:
        Patch dictionary or None if not found.
    """
    import json

    safe_sku = sku.replace("/", "-")
    patch_file = patches_dir / f"shopify-patch-{safe_sku}.json"

    if not patch_file.exists():
        return None

    try:
        with open(patch_file) as f:
            patch = json.load(f)
        patch["_source_file"] = str(patch_file)
        return patch
    except (json.JSONDecodeError, OSError):
        return None


# ============================================================================
# Shopify Image Upload Functions
# ============================================================================

SHOPIFY_STAGED_UPLOADS_CREATE = """
mutation stagedUploadsCreate($input: [StagedUploadInput!]!) {
  stagedUploadsCreate(input: $input) {
    stagedTargets {
      url
      resourceUrl
      parameters {
        name
        value
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

SHOPIFY_FILE_CREATE = """
mutation fileCreate($files: [FileCreateInput!]!) {
  fileCreate(files: $files) {
    files {
      id
      alt
      ... on MediaImage {
        image {
          url
        }
      }
    }
    userErrors {
      field
      message
    }
  }
}
"""

SHOPIFY_PRODUCT_CREATE_MEDIA = """
mutation productCreateMedia($productId: ID!, $media: [CreateMediaInput!]!) {
  productCreateMedia(productId: $productId, media: $media) {
    media {
      id
      alt
      ... on MediaImage {
        image {
          url
        }
      }
    }
    mediaUserErrors {
      field
      message
    }
  }
}
"""


def upload_lifestyle_image_to_shopify(
    image_path: str | Path,
    product_id: str,
    alt_text: str = "AI-generated lifestyle image",
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """
    Upload a lifestyle image to Shopify and attach it to a product.

    This function:
    1. Creates a staged upload URL using Shopify's stagedUploadsCreate mutation
    2. Uploads the image file to the staged URL
    3. Creates the file in Shopify's file storage
    4. Attaches the media to the product

    Args:
        image_path: Local path to the image file
        product_id: Shopify product ID (numeric or GID format)
        alt_text: Alt text for the image
        store_url: Store URL (defaults to SHOPIFY_STORE_URL env var)
        access_token: API token (defaults to SHOPIFY_ACCESS_TOKEN env var)
        env: Environment variables mapping

    Returns:
        Dict with:
        - success: bool
        - image_url: CDN URL of uploaded image (if success)
        - media_id: Shopify media ID (if success)
        - errors: List of error messages (if any)
    """
    import mimetypes

    env = env or os.environ
    store_url = store_url or env.get("SHOPIFY_STORE_URL")
    access_token = access_token or env.get("SHOPIFY_ACCESS_TOKEN")

    if not store_url or not access_token:
        raise ValueError(
            "Missing Shopify credentials. Set SHOPIFY_STORE_URL and SHOPIFY_ACCESS_TOKEN."
        )

    image_path = Path(image_path)
    if not image_path.exists():
        return {
            "success": False,
            "errors": [f"Image file not found: {image_path}"],
        }

    # Determine mime type
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = "image/png"

    api_version = env.get("SHOPIFY_API_VERSION", SHOPIFY_API_VERSION_DEFAULT)
    endpoint = f"https://{_normalize_store_host(store_url)}/admin/api/{api_version}/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token,
    }

    gid = _product_gid(product_id)
    file_size = image_path.stat().st_size

    # Step 1: Create staged upload
    staged_input = [
        {
            "filename": image_path.name,
            "mimeType": mime_type,
            "resource": "IMAGE",
            "fileSize": str(file_size),
            "httpMethod": "POST",
        }
    ]

    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        response = client.post(
            endpoint,
            json={
                "query": SHOPIFY_STAGED_UPLOADS_CREATE,
                "variables": {"input": staged_input},
            },
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        return {
            "success": False,
            "errors": [str(e) for e in payload["errors"]],
            "step": "staged_upload_create",
        }

    staged_data = payload.get("data", {}).get("stagedUploadsCreate", {})
    user_errors = staged_data.get("userErrors", [])
    if user_errors:
        return {
            "success": False,
            "errors": [f"{e['field']}: {e['message']}" for e in user_errors],
            "step": "staged_upload_create",
        }

    targets = staged_data.get("stagedTargets", [])
    if not targets:
        return {
            "success": False,
            "errors": ["No staged upload target returned"],
            "step": "staged_upload_create",
        }

    target = targets[0]
    upload_url = target.get("url")
    resource_url = target.get("resourceUrl")
    parameters = target.get("parameters", [])

    # Step 2: Upload file to staged URL
    form_data = {param["name"]: param["value"] for param in parameters}

    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, mime_type)}
        with httpx.Client(timeout=httpx.Timeout(120.0)) as client:
            upload_response = client.post(upload_url, data=form_data, files=files)

    if upload_response.status_code not in (200, 201, 204):
        return {
            "success": False,
            "errors": [f"Upload failed with status {upload_response.status_code}"],
            "step": "file_upload",
        }

    # Step 3: Attach media to product
    media_input = [
        {
            "originalSource": resource_url,
            "alt": alt_text,
            "mediaContentType": "IMAGE",
        }
    ]

    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        response = client.post(
            endpoint,
            json={
                "query": SHOPIFY_PRODUCT_CREATE_MEDIA,
                "variables": {"productId": gid, "media": media_input},
            },
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()

    if payload.get("errors"):
        return {
            "success": False,
            "errors": [str(e) for e in payload["errors"]],
            "step": "product_create_media",
        }

    media_data = payload.get("data", {}).get("productCreateMedia", {})
    media_errors = media_data.get("mediaUserErrors", [])
    if media_errors:
        return {
            "success": False,
            "errors": [f"{e['field']}: {e['message']}" for e in media_errors],
            "step": "product_create_media",
        }

    media_list = media_data.get("media", [])
    if not media_list:
        return {
            "success": False,
            "errors": ["No media returned after creation"],
            "step": "product_create_media",
        }

    media = media_list[0]
    image_url = ""
    if "image" in media and media["image"]:
        image_url = media["image"].get("url", "")

    return {
        "success": True,
        "image_url": image_url,
        "media_id": media.get("id"),
        "resource_url": resource_url,
    }


def upload_selected_lifestyle_image(
    patch: dict,
    images_base_dir: Path | None = None,
    *,
    store_url: str | None = None,
    access_token: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    """
    Upload the selected lifestyle image from a patch to Shopify.

    Args:
        patch: Shopify patch dictionary with lifestyle_images and selected_lifestyle_image
        images_base_dir: Base directory for resolving image paths (optional)
        store_url: Store URL
        access_token: API token
        env: Environment variables mapping

    Returns:
        Dict with upload result including CDN URL if successful
    """
    # Get selected image
    lifestyle_images = patch.get("lifestyle_images", [])
    selected_num = patch.get("selected_lifestyle_image")

    if not lifestyle_images:
        return {
            "success": False,
            "errors": ["No lifestyle images in patch"],
        }

    # Find the selected image
    selected_image = None
    for img in lifestyle_images:
        if not isinstance(img, dict):
            continue
        if selected_num is not None and img.get("variation_num") == selected_num:
            selected_image = img
            break
        if selected_image is None and img.get("generation_success"):
            selected_image = img  # Fallback to first successful

    if not selected_image:
        return {
            "success": False,
            "errors": ["No valid lifestyle image found"],
        }

    image_path = selected_image.get("image_path")
    if not image_path:
        return {
            "success": False,
            "errors": ["Selected image has no path"],
        }

    # Resolve image path
    resolved_path = Path(image_path)
    if not resolved_path.is_absolute() and images_base_dir:
        resolved_path = images_base_dir / image_path

    if not resolved_path.exists():
        return {
            "success": False,
            "errors": [f"Image file not found: {resolved_path}"],
        }

    # Get product ID from patch
    # Shopify patches use shopify_id or we need to extract from offer ID
    offer_id = patch.get("offerId", "")
    product_id = patch.get("shopify_id")

    if not product_id and offer_id.startswith("shopify_US_"):
        # Extract product ID from format: shopify_US_{product_id}_{variant_id}
        parts = offer_id.split("_")
        if len(parts) >= 3:
            product_id = parts[2]

    if not product_id:
        return {
            "success": False,
            "errors": ["Cannot determine Shopify product ID from patch"],
        }

    # Get SKU for alt text
    meta = patch.get("_meta", {})
    sku = meta.get("master_sku", "")
    alt_text = f"Lifestyle image for {sku}" if sku else "AI-generated lifestyle image"

    return upload_lifestyle_image_to_shopify(
        image_path=resolved_path,
        product_id=product_id,
        alt_text=alt_text,
        store_url=store_url,
        access_token=access_token,
        env=env,
    )
