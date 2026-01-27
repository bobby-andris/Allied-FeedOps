"""Catalog sync helpers shared by CLI and resolver."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from feedops.integrations.merchant_center import write_merchant_center_snapshot
from feedops.integrations.shopify_catalog import write_shopify_catalog_csv
from feedops.loaders.catalog_resolver import DEFAULT_CACHE_PATH

DEFAULT_TTL_HOURS = 24
DEFAULT_MC_METADATA_PATH = (
    Path.home() / ".cache" / "feedops" / "merchant_center" / "items.jsonl"
)


@dataclass(frozen=True)
class SyncResult:
    catalog_path: Path
    mc_metadata_path: Path
    refreshed_catalog: bool
    refreshed_mc_metadata: bool


def _default_catalog_path(env: Mapping[str, str]) -> Path:
    if env.get("CATALOG_PATH"):
        return Path(env["CATALOG_PATH"]).expanduser()
    if env.get("FEEDOPS_CATALOG_CACHE_PATH"):
        return Path(env["FEEDOPS_CATALOG_CACHE_PATH"]).expanduser()
    return DEFAULT_CACHE_PATH


def _default_mc_metadata_path(env: Mapping[str, str]) -> Path:
    if env.get("FEEDOPS_MC_METADATA_PATH"):
        return Path(env["FEEDOPS_MC_METADATA_PATH"]).expanduser()
    return DEFAULT_MC_METADATA_PATH


def _is_stale(path: Path, ttl_hours: float | None) -> bool:
    if not path.exists():
        return True
    if ttl_hours is None:
        return False
    if ttl_hours <= 0:
        return True
    updated = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return datetime.now(timezone.utc) - updated > timedelta(hours=ttl_hours)


def sync_catalog(
    *,
    source: str,
    output_catalog: str | None,
    output_mc_metadata: str | None,
    limit: int | None,
    force: bool,
    ttl_hours: float | None,
    env: Mapping[str, str] | None = None,
) -> SyncResult:
    env = env or os.environ
    source_value = source.lower()
    if source_value not in {"shopify", "mapi", "auto"}:
        raise ValueError("source must be one of: shopify, mapi, auto")

    print("Catalog sync: starting", flush=True)

    catalog_path = (
        Path(output_catalog).expanduser()
        if output_catalog
        else _default_catalog_path(env)
    )
    mc_metadata_path = (
        Path(output_mc_metadata).expanduser()
        if output_mc_metadata
        else _default_mc_metadata_path(env)
    )

    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    mc_metadata_path.parent.mkdir(parents=True, exist_ok=True)

    ttl = DEFAULT_TTL_HOURS if ttl_hours is None else ttl_hours

    refresh_catalog = force or _is_stale(catalog_path, ttl)
    refresh_mc = force or _is_stale(mc_metadata_path, ttl)

    if source_value == "shopify":
        refresh_catalog = True
        refresh_mc = False
    elif source_value == "mapi":
        refresh_catalog = False
        refresh_mc = True

    if refresh_mc:
        print(f"Merchant Center metadata: refreshing -> {mc_metadata_path}", flush=True)
        write_merchant_center_snapshot(mc_metadata_path, limit=limit)
        print(f"Merchant Center metadata: refreshed -> {mc_metadata_path}", flush=True)
    else:
        print(f"Merchant Center metadata: cached -> {mc_metadata_path}", flush=True)
    if refresh_catalog:
        print(f"Shopify catalog: refreshing -> {catalog_path}", flush=True)
        write_shopify_catalog_csv(catalog_path, limit=limit)
        print(f"Shopify catalog: refreshed -> {catalog_path}", flush=True)
    else:
        print(f"Shopify catalog: cached -> {catalog_path}", flush=True)

    print("Catalog sync: complete", flush=True)

    return SyncResult(
        catalog_path=catalog_path,
        mc_metadata_path=mc_metadata_path,
        refreshed_catalog=refresh_catalog,
        refreshed_mc_metadata=refresh_mc,
    )
