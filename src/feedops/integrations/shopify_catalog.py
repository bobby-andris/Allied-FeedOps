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
query ProductsForCatalog($first: Int!, $after: String) {
  products(first: $first, after: $after) {
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
    limit: int | None = None, *, env: Mapping[str, str] | None = None
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
            variables = {"first": first, "after": after}
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

            if remaining is not None:
                remaining -= len(nodes)
                if remaining <= 0:
                    break

            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
            after = page_info.get("endCursor")

    return products


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
