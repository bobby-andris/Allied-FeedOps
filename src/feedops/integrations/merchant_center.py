"""Merchant Center metadata snapshot integration."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import google.auth
import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

from feedops.db.schema import (
    init_db,
    load_merchant_center_items,
    upsert_merchant_center_items,
)

MAPI_SCOPE = "https://www.googleapis.com/auth/content"
MAPI_PRODUCTS_ENDPOINT = (
    "https://merchantapi.googleapis.com/products/v1/accounts/{account}/products"
)
DEFAULT_MC_METADATA_PATH = (
    Path.home() / ".cache" / "feedops" / "merchant_center" / "items.jsonl"
)


def _get_access_token(env: Mapping[str, str]) -> str:
    credentials, _source = _load_credentials(env)
    credentials.refresh(Request())
    token = credentials.token
    if not token:
        raise ValueError("Failed to obtain Merchant Center access token.")
    return token


def _load_credentials(env: Mapping[str, str]):
    gmc_key = (env.get("GMC_API_KEY") or "").strip()
    gac = (env.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()

    gmc_path = Path(gmc_key).expanduser() if gmc_key else None
    gac_path = Path(gac).expanduser() if gac else None

    if gac:
        gac_path = Path(gac).expanduser()
        if gac_path.exists():
            return (
                service_account.Credentials.from_service_account_file(
                    str(gac_path), scopes=[MAPI_SCOPE]
                ),
                "google_application_credentials",
            )
    if gmc_key:
        gmc_path = Path(gmc_key).expanduser()
        if gmc_path.exists():
            return (
                service_account.Credentials.from_service_account_file(
                    str(gmc_path), scopes=[MAPI_SCOPE]
                ),
                "gmc_api_key_path",
            )
        if gmc_key.startswith("{"):
            info = json.loads(gmc_key)
            return (
                service_account.Credentials.from_service_account_info(
                    info, scopes=[MAPI_SCOPE]
                ),
                "gmc_api_key_json",
            )

    ads_config_value = (
        env.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH")
        or env.get("FEEDOPS_GOOGLE_ADS_CONFIG")
        or ""
    ).strip()
    creds_dir_value = (env.get("FEEDOPS_CREDS_DIR") or "").strip()
    if ads_config_value:
        ads_config_path = Path(ads_config_value).expanduser()
    elif creds_dir_value:
        ads_config_path = Path(creds_dir_value).expanduser() / "google-ads.yaml"
    else:
        ads_config_path = (
            Path(__file__).resolve().parents[3] / "creds" / "google-ads.yaml"
        )
    if ads_config_path.exists():
        config = _parse_google_ads_yaml(ads_config_path)
        client_id = config.get("client_id")
        client_secret = config.get("client_secret")
        refresh_token = config.get("refresh_token")
        if client_id and client_secret and refresh_token:
            return (
                Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=[MAPI_SCOPE],
                ),
                "google_ads_config",
            )

    if creds_dir_value:
        creds_dir = Path(creds_dir_value).expanduser()
    else:
        creds_dir = Path(__file__).resolve().parents[3] / "creds"

    if creds_dir.exists():
        preferred_name = gmc_key if gmc_key.endswith(".json") else None
        candidate = _select_service_account_file(creds_dir, preferred_name)
        if candidate:
            return (
                service_account.Credentials.from_service_account_file(
                    str(candidate), scopes=[MAPI_SCOPE]
                ),
                "creds_dir_fallback",
            )

    credentials, _project_id = google.auth.default(scopes=[MAPI_SCOPE])
    return credentials, "adc_default"


def _select_service_account_file(
    creds_dir: Path, preferred_name: str | None
) -> Path | None:
    if preferred_name:
        candidate = creds_dir / preferred_name
        if candidate.exists():
            return candidate

    candidates = []
    for path in sorted(creds_dir.glob("*.json")):
        name = path.name.lower()
        if "client_secret" in name:
            continue
        candidates.append(path)

    return candidates[0] if candidates else None


def _parse_google_ads_yaml(path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            config[key] = value
    return config


def _get_field(source: dict, *keys: str):
    for key in keys:
        if key in source:
            return source.get(key)
    return None


def _normalize_product(product: dict, fetched_at: str) -> dict | None:
    offer_id = product.get("offerId")
    if not offer_id:
        return None

    attributes = product.get("productAttributes", {}) or {}
    status = product.get("productStatus", {}) or {}

    return {
        "offerId": offer_id,
        "customLabel0": _get_field(attributes, "customLabel0", "custom_label_0"),
        "customLabel1": _get_field(attributes, "customLabel1", "custom_label_1"),
        "customLabel2": _get_field(attributes, "customLabel2", "custom_label_2"),
        "customLabel3": _get_field(attributes, "customLabel3", "custom_label_3"),
        "customLabel4": _get_field(attributes, "customLabel4", "custom_label_4"),
        "googleProductCategory": _get_field(
            attributes, "googleProductCategory", "google_product_category"
        ),
        "productTypes": _get_field(attributes, "productTypes", "product_types") or [],
        "destinationStatuses": _get_field(
            status, "destinationStatuses", "destination_statuses"
        )
        or [],
        "itemLevelIssues": _get_field(status, "itemLevelIssues", "item_level_issues")
        or [],
        "fetched_at": fetched_at,
    }


def _write_empty_snapshot(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix in {".db", ".sqlite"}:
        init_db(output_path)
        return
    output_path.write_text("")


def fetch_merchant_center_products(
    limit: int | None = None, *, env: Mapping[str, str] | None = None
) -> list[dict]:
    env = env or os.environ
    merchant_id = env.get("GMC_MERCHANT_ID")
    if not merchant_id:
        raise ValueError("Missing GMC_MERCHANT_ID for Merchant Center API.")

    token = _get_access_token(env)
    headers = {"Authorization": f"Bearer {token}"}
    endpoint = MAPI_PRODUCTS_ENDPOINT.format(account=merchant_id)

    products: list[dict] = []
    page_token: str | None = None

    with httpx.Client(timeout=httpx.Timeout(30.0)) as client:
        while True:
            page_size = 1000
            if limit is not None:
                remaining = max(limit - len(products), 0)
                if remaining == 0:
                    break
                page_size = min(page_size, remaining)

            params = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token

            response = client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()

            payload = response.json()
            products.extend(payload.get("products", []) or [])

            page_token = payload.get("nextPageToken")
            if not page_token:
                break

    return products


def load_merchant_center_snapshot(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    if path.suffix in {".db", ".sqlite"}:
        return load_merchant_center_items(path)

    records: dict[str, dict] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        offer_id = payload.get("offerId")
        if offer_id:
            records[offer_id] = payload
    return records


def write_merchant_center_snapshot(
    output_path: Path, *, limit: int | None = None, env: Mapping[str, str] | None = None
) -> None:
    """Write Merchant Center metadata snapshot.

    Writes JSONL by default or SQLite if output_path ends with .db/.sqlite.
    """
    env = env or os.environ
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        products = fetch_merchant_center_products(limit, env=env)
    except Exception as exc:
        print(f"Warning: unable to fetch Merchant Center products: {exc}")
        _write_empty_snapshot(output_path)
        return

    fetched_at = datetime.now(timezone.utc).isoformat()
    normalized = []
    for product in products:
        record = _normalize_product(product, fetched_at)
        if record:
            normalized.append(record)

    if output_path.suffix in {".db", ".sqlite"}:
        init_db(output_path)
        upsert_merchant_center_items(output_path, normalized)
        return

    with output_path.open("w") as handle:
        for record in normalized:
            handle.write(json.dumps(record))
            handle.write("\n")
