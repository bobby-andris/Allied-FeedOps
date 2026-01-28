"""Unified loader for ParentSKU with cache + API + CSV fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from feedops.db.schema import (
    cache_shopify_product,
    get_cached_merchant_center_items,
    get_cached_shopify_product,
    get_connection,
    init_db,
    upsert_merchant_center_items,
)
from feedops.integrations.merchant_center import fetch_merchant_center_items
from feedops.integrations.shopify_catalog import (
    _derive_finish,
    _derive_finish_code,
    _derive_master_sku,
    _extract_image_url,
    _extract_material,
    _load_finish_codes,
    _parse_gid,
    _strip_html,
    fetch_shopify_product,
)
from feedops.loaders.catalog import get_parent_sku, load_catalog
from feedops.loaders.catalog_resolver import resolve_catalog_path
from feedops.models.parent_sku import ParentSKU
from feedops.models.variant import Variant


def _resolve_db_path() -> Path:
    return Path(os.environ.get("DATABASE_PATH", "data/feedops.db"))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get_cached_shopify_fetched_at(master_sku: str) -> datetime | None:
    db_path = _resolve_db_path()
    if not db_path.exists():
        return None
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT fetched_at FROM shopify_products WHERE master_sku = ?",
        (master_sku,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _parse_timestamp(row["fetched_at"])


def _format_age_minutes(fetched_at: datetime | None) -> str:
    if not fetched_at:
        return "unknown"
    minutes = int((_now_utc() - fetched_at).total_seconds() / 60)
    return f"{max(minutes, 0)}m"


def get_cached_shopify_age_hours(master_sku: str) -> float | None:
    fetched_at = _get_cached_shopify_fetched_at(master_sku)
    if not fetched_at:
        return None
    return (_now_utc() - fetched_at).total_seconds() / 3600


def _extract_product_id(payload: dict) -> str | None:
    product_id = payload.get("legacyResourceId") or _parse_gid(payload.get("id"))
    if product_id is None:
        return None
    return str(product_id)


def _derive_gmc_ids(payload: dict) -> list[str]:
    product_id = _extract_product_id(payload)
    if not product_id:
        return []
    gmc_ids: list[str] = []
    variants = payload.get("variants", {}).get("nodes", []) or []
    for variant in variants:
        variant_id = variant.get("legacyResourceId") or _parse_gid(variant.get("id"))
        if variant_id:
            gmc_ids.append(f"shopify_US_{product_id}_{variant_id}")
    return gmc_ids


@dataclass
class UnifiedLoadStatus:
    data_source: str | None = None
    api_error: str | None = None
    csv_error: str | None = None
    api_attempted: bool = False
    csv_attempted: bool = False


def _build_parent_from_shopify_payload(
    payload: dict, master_sku_hint: str | None = None
) -> ParentSKU | None:
    product_type = payload.get("productType") or "Uncategorized"
    collections = payload.get("collections", {}).get("nodes", []) or []
    collection = collections[0].get("title") if collections else None

    title = payload.get("title") or ""
    description = _strip_html(payload.get("descriptionHtml")) or title
    material = _extract_material(payload) or None

    featured_media = payload.get("featuredMedia") or {}
    featured_image_url = ""
    if featured_media.get("image"):
        featured_image_url = featured_media["image"].get("url") or ""

    product_id = _extract_product_id(payload) or ""

    finish_map = _load_finish_codes()
    variants: list[Variant] = []
    master_sku = (master_sku_hint or "").strip()
    for variant in payload.get("variants", {}).get("nodes", []) or []:
        sku = variant.get("sku") or ""
        if not sku:
            continue
        finish = _derive_finish(variant)
        finish_code = _derive_finish_code(sku, finish, finish_map)
        derived_master = _derive_master_sku(sku, finish_code)
        if derived_master and not master_sku:
            master_sku = derived_master

        variant_id = variant.get("legacyResourceId") or _parse_gid(variant.get("id"))
        gmc_id = ""
        if product_id and variant_id:
            gmc_id = f"shopify_US_{product_id}_{variant_id}"
        if not gmc_id:
            continue

        variant_media_nodes = variant.get("media", {}).get("nodes", []) or []
        main_image_url = _extract_image_url(variant_media_nodes) or featured_image_url
        main_image = os.path.basename(main_image_url) if main_image_url else None

        variants.append(
            Variant(
                option_sku=sku,
                finish=finish,
                finish_code=finish_code,
                gmc_id=gmc_id,
                upc=variant.get("barcode") or None,
                gtin=variant.get("barcode") or None,
                position=int(variant.get("position") or 0),
                main_image=main_image,
                main_image_url=main_image_url or None,
            )
        )

    if not variants:
        return None
    if not master_sku:
        master_sku = master_sku_hint or variants[0].option_sku

    return ParentSKU(
        master_sku=master_sku,
        category=product_type,
        collection=collection,
        current_title=title,
        current_description=description,
        material=material,
        variants=variants,
    )


def _load_gmc_items(
    master_sku: str, payload: dict, cache_ttl_hours: float
) -> list[dict]:
    cached_items = get_cached_merchant_center_items(
        master_sku, max_age_hours=cache_ttl_hours
    )
    if cached_items:
        print("Cache hit: Merchant Center items", flush=True)
        return cached_items
    print("Cache miss: Merchant Center items", flush=True)

    try:
        items = fetch_merchant_center_items(limit=None)
    except Exception as exc:
        print(f"Warning: unable to fetch Merchant Center items: {exc}", flush=True)
        return []

    if items:
        db_path = _resolve_db_path()
        init_db(db_path)
        upsert_merchant_center_items(db_path, items)

    gmc_ids = set(_derive_gmc_ids(payload))
    return [item for item in items if item.get("offerId") in gmc_ids]


def load_parent_sku_unified_with_status(
    master_sku: str,
    force_refresh: bool = False,
    catalog_path: Optional[str] = None,
    cache_ttl_hours: float = 24.0,
) -> tuple[ParentSKU | None, UnifiedLoadStatus]:
    """Load ParentSKU with hierarchy: DB cache → Shopify API → GMC API → CSV fallback."""
    status = UnifiedLoadStatus()
    cached_payload = None
    if not force_refresh:
        cached_payload = get_cached_shopify_product(
            master_sku, max_age_hours=cache_ttl_hours
        )
        if cached_payload:
            parent = _build_parent_from_shopify_payload(
                cached_payload, master_sku_hint=master_sku
            )
            if parent:
                status.data_source = "shopify_cached"
                parent = parent.model_copy(update={"data_source": status.data_source})
                fetched_at = _get_cached_shopify_fetched_at(master_sku)
                age_label = _format_age_minutes(fetched_at)
                print(f"Data source: Shopify API (cached {age_label} ago)", flush=True)
                print("Cache hit: Shopify product", flush=True)
                gmc_items = _load_gmc_items(master_sku, cached_payload, cache_ttl_hours)
                if gmc_items:
                    parent = parent.model_copy(
                        update={"merchant_center_items": gmc_items}
                    )
                return parent, status
        print("Cache miss: Shopify product", flush=True)

    status.api_attempted = True
    try:
        product = fetch_shopify_product(master_sku)
    except Exception as exc:
        product = None
        status.api_error = str(exc)
        print(f"Warning: Shopify API failed: {exc}", flush=True)

    if product:
        product_id = _extract_product_id(product) or ""
        cache_shopify_product(
            master_sku=master_sku,
            product_id=product_id,
            payload=product,
            ttl_hours=cache_ttl_hours,
        )
        parent = _build_parent_from_shopify_payload(product, master_sku_hint=master_sku)
        if parent:
            status.data_source = "shopify_fresh"
            parent = parent.model_copy(update={"data_source": status.data_source})
            print("Data source: Shopify API (fetched just now)", flush=True)
            gmc_items = _load_gmc_items(master_sku, product, cache_ttl_hours)
            if gmc_items:
                parent = parent.model_copy(update={"merchant_center_items": gmc_items})
            return parent, status

    status.csv_attempted = True
    try:
        resolved_path = (
            Path(catalog_path).expanduser()
            if catalog_path
            else resolve_catalog_path(None)
        )
        df = load_catalog(resolved_path)
        parent = get_parent_sku(df, master_sku)
        if parent:
            status.data_source = "csv_fallback"
            parent = parent.model_copy(update={"data_source": status.data_source})
        print(f"Data source: CSV fallback ({resolved_path})", flush=True)
        return parent, status
    except Exception as exc:
        status.csv_error = str(exc)
        print(f"Warning: CSV fallback failed: {exc}", flush=True)
        return None, status


def load_parent_sku_unified(
    master_sku: str,
    force_refresh: bool = False,
    catalog_path: Optional[str] = None,
    cache_ttl_hours: float = 24.0,
) -> ParentSKU | None:
    """Load ParentSKU with hierarchy: DB cache → Shopify API → GMC API → CSV fallback."""
    parent, _status = load_parent_sku_unified_with_status(
        master_sku=master_sku,
        force_refresh=force_refresh,
        catalog_path=catalog_path,
        cache_ttl_hours=cache_ttl_hours,
    )
    return parent
