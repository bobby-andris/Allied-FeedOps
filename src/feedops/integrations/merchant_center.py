"""Merchant Center metadata snapshot integration."""

from __future__ import annotations

import base64
import binascii
import json
import os
import time
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
# Merchant API list endpoint (current REST form):
#   GET https://merchantapi.googleapis.com/products/v1beta/{parent=accounts/*}/products
# Keep a legacy fallback because some environments still expose v1/account form.
MAPI_PRODUCTS_ENDPOINTS = (
    "https://merchantapi.googleapis.com/products/v1beta/{parent}/products",
    "https://merchantapi.googleapis.com/products/v1/accounts/{account}/products",
)
DEFAULT_MC_METADATA_PATH = (
    Path.home() / ".cache" / "feedops" / "merchant_center" / "items.jsonl"
)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _load_service_account_info(value: str) -> tuple[dict, str] | None:
    """Parse service account JSON from raw JSON or base64-encoded JSON."""
    raw = (value or "").strip()
    if not raw:
        return None

    if raw.startswith("{"):
        return json.loads(raw), "json"

    compact = "".join(raw.split())
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return None

    payload = decoded.decode("utf-8").strip()
    if not payload.startswith("{"):
        return None
    return json.loads(payload), "base64"


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_positive_int_env(
    env: Mapping[str, str], key: str, default: int
) -> int:
    raw = str(env.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _get_positive_float_env(
    env: Mapping[str, str], key: str, default: float
) -> float:
    raw = str(env.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _build_http_timeout(env: Mapping[str, str]) -> httpx.Timeout:
    connect = _get_positive_float_env(env, "GMC_HTTP_CONNECT_TIMEOUT_SECONDS", 15.0)
    read = _get_positive_float_env(env, "GMC_HTTP_READ_TIMEOUT_SECONDS", 120.0)
    write = _get_positive_float_env(env, "GMC_HTTP_WRITE_TIMEOUT_SECONDS", 30.0)
    pool = _get_positive_float_env(env, "GMC_HTTP_POOL_TIMEOUT_SECONDS", 30.0)
    return httpx.Timeout(connect=connect, read=read, write=write, pool=pool)


def _request_page_with_retries(
    client: httpx.Client,
    endpoint: str,
    headers: dict[str, str],
    params: dict[str, str | int],
    *,
    max_attempts: int,
    backoff_seconds: float,
) -> httpx.Response:
    """Fetch a page with retry logic for transient HTTP/network failures."""
    for attempt in range(max_attempts):
        try:
            response = client.get(endpoint, headers=headers, params=params)
            status_code = response.status_code
            if status_code in RETRYABLE_STATUS_CODES and attempt < (max_attempts - 1):
                sleep_seconds = backoff_seconds * (2**attempt)
                time.sleep(sleep_seconds)
                continue
            response.raise_for_status()
            return response
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt >= (max_attempts - 1):
                raise
            sleep_seconds = backoff_seconds * (2**attempt)
            time.sleep(sleep_seconds)

    raise RuntimeError("Merchant Center request retries exhausted without response.")


def _get_access_token(env: Mapping[str, str]) -> str:
    credentials, _source = _load_credentials(env)
    credentials.refresh(Request())
    token = credentials.token
    if not token:
        raise ValueError("Failed to obtain Merchant Center access token.")
    return token


def _load_credentials(env: Mapping[str, str]):
    credential_errors: list[str] = []
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
        parsed = _load_service_account_info(gmc_key)
        if parsed:
            info, encoding = parsed
            try:
                return (
                    service_account.Credentials.from_service_account_info(
                        info, scopes=[MAPI_SCOPE]
                    ),
                    f"gmc_api_key_{encoding}",
                )
            except Exception as exc:
                credential_errors.append(f"GMC_API_KEY ({encoding}): {exc}")

    gsa_key = (env.get("GOOGLE_SERVICE_ACCOUNT_KEY") or "").strip()
    if gsa_key:
        parsed = _load_service_account_info(gsa_key)
        if parsed:
            info, encoding = parsed
            try:
                return (
                    service_account.Credentials.from_service_account_info(
                        info, scopes=[MAPI_SCOPE]
                    ),
                    f"google_service_account_key_{encoding}",
                )
            except Exception as exc:
                credential_errors.append(
                    f"GOOGLE_SERVICE_ACCOUNT_KEY ({encoding}): {exc}"
                )

    gsa_email = (env.get("GOOGLE_SERVICE_ACCOUNT_EMAIL") or "").strip()
    gsa_private_key = (env.get("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY") or "").strip()
    if not gsa_private_key:
        gsa_private_key = (env.get("GOOGLE_SERVICE_ACCOUNT_KEY") or "").strip()
    if gsa_email and gsa_private_key and gsa_private_key.startswith("-----BEGIN"):
        info = {
            "type": "service_account",
            "project_id": (env.get("GOOGLE_PROJECT_ID") or "").strip(),
            "private_key": gsa_private_key.replace("\\n", "\n"),
            "client_email": gsa_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        try:
            return (
                service_account.Credentials.from_service_account_info(
                    info, scopes=[MAPI_SCOPE]
                ),
                "google_service_account_env_split",
            )
        except Exception as exc:
            credential_errors.append(
                "GOOGLE_SERVICE_ACCOUNT_EMAIL/GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: "
                f"{exc}"
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

    if credential_errors and not _is_truthy(env.get("FEEDOPS_ALLOW_ADC_FALLBACK")):
        joined = " | ".join(credential_errors)
        raise ValueError(
            "Merchant credential loading failed for explicit env credentials. "
            f"{joined}. "
            "Set FEEDOPS_ALLOW_ADC_FALLBACK=1 to allow ADC fallback."
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


def _extract_custom_attribute_from_list(
    custom_attributes: list[dict] | None,
    *field_aliases: str,
):
    """Extract attribute value from Merchant API customAttributes list.

    Different API payloads represent custom attributes with slightly different
    keys (name/value, attributeName/attributeValue, etc.), so we normalize here.
    """
    if not custom_attributes:
        return None

    wanted = {alias.casefold() for alias in field_aliases}
    for entry in custom_attributes:
        if not isinstance(entry, dict):
            continue
        name = (
            entry.get("name")
            or entry.get("attributeName")
            or entry.get("attribute")
            or entry.get("key")
        )
        if str(name or "").casefold() not in wanted:
            continue

        for value_key in ("value", "attributeValue", "textValue", "valueText"):
            value = entry.get(value_key)
            if value not in (None, ""):
                return value

        if isinstance(entry.get("value"), dict):
            nested = entry["value"]
            for nested_key in ("value", "text", "stringValue"):
                value = nested.get(nested_key)
                if value not in (None, ""):
                    return value

    return None


def _extract_custom_label(
    attributes: dict,
    custom_attributes: list[dict] | None,
    index: int,
):
    camel = f"customLabel{index}"
    snake = f"custom_label_{index}"
    return (
        _get_field(attributes, camel, snake)
        or _extract_custom_attribute_from_list(custom_attributes, camel, snake)
    )


def _normalize_product(product: dict, fetched_at: str) -> dict | None:
    offer_id = product.get("offerId")
    if not offer_id:
        return None

    attributes = (
        product.get("productAttributes")
        or product.get("attributes")
        or {}
    )
    if not isinstance(attributes, dict):
        attributes = {}
    custom_attributes = product.get("customAttributes") or []
    status = product.get("productStatus", {}) or {}

    return {
        "offerId": offer_id,
        "customLabel0": _extract_custom_label(attributes, custom_attributes, 0),
        "customLabel1": _extract_custom_label(attributes, custom_attributes, 1),
        "customLabel2": _extract_custom_label(attributes, custom_attributes, 2),
        "customLabel3": _extract_custom_label(attributes, custom_attributes, 3),
        "customLabel4": _extract_custom_label(attributes, custom_attributes, 4),
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
    parent = f"accounts/{merchant_id}"
    page_size_default = _get_positive_int_env(env, "GMC_HTTP_PAGE_SIZE", 1000)
    max_attempts = _get_positive_int_env(env, "GMC_HTTP_MAX_ATTEMPTS", 3)
    retry_backoff_seconds = _get_positive_float_env(
        env, "GMC_HTTP_RETRY_BACKOFF_SECONDS", 1.0
    )
    timeout = _build_http_timeout(env)
    endpoints = [
        MAPI_PRODUCTS_ENDPOINTS[0].format(parent=parent),
        MAPI_PRODUCTS_ENDPOINTS[1].format(account=merchant_id),
    ]

    products: list[dict] = []

    last_error: Exception | None = None
    with httpx.Client(timeout=timeout) as client:
        for endpoint in endpoints:
            page_token: str | None = None
            products.clear()
            try:
                while True:
                    page_size = page_size_default
                    if limit is not None:
                        remaining = max(limit - len(products), 0)
                        if remaining == 0:
                            break
                        page_size = min(page_size, remaining)

                    params = {"pageSize": page_size}
                    if page_token:
                        params["pageToken"] = page_token

                    response = _request_page_with_retries(
                        client,
                        endpoint,
                        headers,
                        params,
                        max_attempts=max_attempts,
                        backoff_seconds=retry_backoff_seconds,
                    )

                    payload = response.json()
                    products.extend(payload.get("products", []) or [])

                    page_token = payload.get("nextPageToken")
                    if not page_token:
                        break
            except Exception as exc:
                last_error = exc
                continue
            return products

    if last_error:
        raise last_error
    return []


def fetch_merchant_center_items(
    limit: int | None = None, *, env: Mapping[str, str] | None = None
) -> list[dict]:
    """Fetch and normalize Merchant Center products."""
    products = fetch_merchant_center_products(limit=limit, env=env)
    fetched_at = datetime.now(timezone.utc).isoformat()
    normalized = []
    for product in products:
        record = _normalize_product(product, fetched_at)
        if record:
            normalized.append(record)
    return normalized


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
